"""
Prepare les fichiers SQL qui reconstruisent la base GMAO a partir d'une sauvegarde. N'ecrit RIEN dans aucune base.

Usage :
    python preparer_restauration.py <gmao_base_....zip> <structure_base_....sql> <dossier de sortie> [nouvelle adresse]

La nouvelle adresse (https://xxxx.supabase.co) remplace l'ancienne dans les liens vers les documents : a donner
quand on restaure dans un NOUVEAU projet.

Produit, a executer DANS CET ORDRE sur une base VIDE (jamais sur la base en service) :
    1_structure.sql   compteurs et tables
    2_donnees.sql     toutes les lignes
    3_regles.sql      cles, liens, index, protections ; repositionne le compteur de factures

Les trois fichiers s'executent avec psql (option -v ON_ERROR_STOP=1). Les cles secretes masquees dans la
sauvegarde (cle Brevo) sont a ressaisir apres restauration. Les fichiers (documents, photos) se retrouvent grace a
manifeste_fichiers.json, ecrit par backup_to_nas.py.
"""
import json
import os
import re
import sys
import zipfile

MARQUE = "$gmao_donnees$"


def separer_structure(sql):
    """Coupe la structure exportee : (avant les donnees, apres les donnees)."""
    debut = sql.find("\nalter table ")
    if debut < 0 or "create table public." not in sql[:debut]:
        raise ValueError("structure non reconnue (exporter_structure.sql)")
    return sql[:debut] + "\n", sql[debut:]


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__)
        return 1
    archive, structure, sortie = argv[:3]
    nouvelle = argv[3].rstrip("/") if len(argv) == 4 else None
    if nouvelle and not re.fullmatch(r"https://[a-z0-9]+\.supabase\.co", nouvelle):
        print("Nouvelle adresse attendue sous la forme https://xxxx.supabase.co")
        return 1
    liens = 0
    with open(structure, encoding="utf-8") as f:
        sql = f.read().replace("\r\n", "\n")
    avant, apres = separer_structure(sql)
    tables = re.findall(r"create table public\.(\w+) \(", avant)
    os.makedirs(sortie, exist_ok=True)

    def ecrire(nom, contenu):
        with open(os.path.join(sortie, nom), "w", encoding="utf-8", newline="\n") as f:
            f.write(contenu)

    ecrire("1_structure.sql", avant)
    # Tableaux rattaches aux comptes de connexion Supabase (schema auth) : les comptes ne sont pas sauvegardes et
    # auront d'autres identifiants dans un nouveau projet. Leurs lignes ne sont donc pas rechargees.
    lies_aux_comptes = set(re.findall(r"alter table public\.(\w+) add constraint \w+ FOREIGN KEY \([^)]*\) "
                                      r"REFERENCES auth\.", apres))
    blocs, total = ["begin;"], 0
    with zipfile.ZipFile(archive) as z:
        presents = {n[:-5] for n in z.namelist() if n.endswith(".json") and not n.startswith("_")}
        if set(tables) != presents:
            raise ValueError(f"tables differentes entre structure et sauvegarde : {sorted(set(tables) ^ presents)}")
        for t in tables:
            if t in lies_aux_comptes:
                print(f"A REFAIRE A LA MAIN : tableau {t} non recharge (recreer les comptes de connexion puis les relier)")
                continue
            texte = z.read(f"{t}.json").decode("utf-8")   # texte d'origine : aucune valeur reconvertie
            if MARQUE in texte:
                raise ValueError(f"marque de citation presente dans les donnees de {t}")
            n = len(json.loads(texte))
            total += n
            if nouvelle:
                texte, k = re.subn(r"https://[a-z0-9]+\.supabase\.co(?=/storage/v1/object/)", nouvelle, texte)
                liens += k
            if n:
                blocs.append(f"insert into public.{t} select * from json_populate_recordset(null::public.{t}, "
                             f"{MARQUE}{texte}{MARQUE}::json);")
    blocs.append("commit;")
    ecrire("2_donnees.sql", "\n".join(blocs) + "\n")
    suite = ""
    if "facture_sequence_id_seq" in avant:
        suite = ("\n\nselect setval('public.facture_sequence_id_seq', "
                 "coalesce((select max(id) from public.facture_sequence), 0) + 1, false);\n")
    ecrire("3_regles.sql", apres + suite)
    print(f"{len(tables)} tables, {total} lignes -> {sortie}"
          + (f" ({liens} liens de documents rediriges vers {nouvelle})" if nouvelle else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
