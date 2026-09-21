"""
Convention de nommage/rangement NAS partagee entre backup_to_nas.py,
import_factures.py et import_devis.py - un seul endroit a faire evoluer pour
que les 3 circuits d'archivage (upload direct dans l'appli, ou mail -> dossier
de transit -> validation) rangent leurs fichiers de facon identique :
<root>/<bien (ou Equipements/<nom equipement> si pas de bien)>/<Factures|
Devis|Documents>/<annee>.<mois>.<Entreprise>.<Description>.ext
Pas de type de travaux/motif en sous-dossier, et pas de bien repete dans le nom
du fichier (deja porte par le dossier) - un seul niveau de tri par logement.
"""
import re
from pathlib import Path


def sanitize_filename(name):
    """Nettoie un nom pour un fichier/dossier Windows valide, en gardant la
    lisibilite (accents/espaces conserves, seuls les caracteres interdits sautent)."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name or "").strip().rstrip(". ")
    return cleaned or "Non classe"


def year_month(date_str):
    return date_str[:4] + "." + date_str[5:7] if date_str and len(date_str) >= 7 else "date-inconnue"


def dest_folder(root, kind, bien=None, equipment=None):
    """<root>/<bien decompose en sous-dossiers>/<kind>, ou <root>/Equipements/
    <equipement>/<kind> si aucun bien n'est renseigne mais qu'un equipement
    (vehicule, bateau...) l'est - permet de classer les factures/devis d'un
    bien mobile qui n'appartient a aucune propriete precise."""
    parts = [p.strip() for p in (bien or "").split(" - ") if p.strip()]
    if parts:
        folder = Path(root)
        for p in parts:
            folder = folder / sanitize_filename(p)
    elif equipment:
        folder = Path(root) / "Équipements" / sanitize_filename(equipment)
    else:
        folder = Path(root) / "Non classe"
    return folder / kind


def dest_filename(ext, date_str, entreprise, description):
    """'<annee>.<mois>.<Entreprise>.<Description><ext>' - le bien/l'equipement
    n'est pas repete ici, il est deja porte par le dossier (dest_folder)."""
    parts = [
        year_month(date_str),
        sanitize_filename(entreprise) if entreprise else "Facture",
        sanitize_filename(description) if description else "Facture",
    ]
    return ".".join(parts) + ext


def dubail_filter(s):
    return "dubail" in (s or "").lower()


def is_savadur_for(bien, asset_id=None, assets=None):
    """SAVADUR/Dubail (True) ou Perso (False) a partir du bien si renseigne,
    sinon du compte/nom de l'equipement lie (vehicule, bateau...)."""
    parts = [p.strip() for p in (bien or "").split(" - ") if p.strip()]
    if parts:
        return dubail_filter(parts[0])
    if asset_id and assets and assets.get(asset_id):
        a = assets[asset_id]
        if a.get("compte"):
            return a["compte"] == "savadur"
        return dubail_filter(a.get("name"))
    return False


def equipment_name_for(asset_id, wo_id, assets, work_orders=None):
    """Nom d'equipement (vehicule, bateau...) a utiliser en repli quand une
    facture/un devis n'a pas de `bien` renseigne mais est rattache a un actif -
    via asset_id direct, ou via un wo_id (bon de travaux) qui pointe lui-meme
    vers un actif."""
    if asset_id and assets.get(asset_id):
        return assets[asset_id].get("name")
    if wo_id and work_orders:
        wo = work_orders.get(wo_id)
        if wo and wo.get("asset_id") and assets.get(wo["asset_id"]):
            return assets[wo["asset_id"]].get("name")
    return None
