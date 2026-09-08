# Import de factures — script de détection

Scanne le dossier où l'automatisation mail dépose les PDF/photos de factures,
uploade les nouveaux fichiers dans Supabase Storage, tente une extraction
basique (texte natif PDF uniquement — pas d'OCR en v1), et les ajoute à la
table `factures_a_valider` pour validation manuelle dans le GMAO (onglet
Factures → "À valider").

Ne modifie jamais un fichier du dossier source, ne supprime rien. Idempotent :
relancer le script ne retraite jamais un fichier déjà connu.

## Installation (une seule fois)

1. **Python** : si tu ne sais pas s'il est installé, ouvre une invite de commande
   (`Win + R`, taper `cmd`, Entrée) et tape :
   ```
   python --version
   ```
   Si tu obtiens un numéro de version (3.9 ou plus récent), c'est bon, passe à
   l'étape 2. Sinon, télécharge Python depuis https://www.python.org/downloads/
   (installateur Windows) — **coche bien "Add python.exe to PATH"** pendant
   l'installation, sinon la commande `python` ne fonctionnera pas.

2. Dans une invite de commande, place-toi dans ce dossier et installe les
   dépendances :
   ```
   cd "D:\Antoine\GMAO-Android\www\claude code GMAO\import-factures"
   pip install -r requirements.txt
   ```

3. Copie `.env.example` en `.env`, puis édite `.env` pour renseigner
   `SUPABASE_SERVICE_ROLE_KEY` — trouvable dans Supabase Dashboard → Project
   Settings → API → section "service_role" (clé secrète, différente de la clé
   `anon` utilisée dans le GMAO). **Ne jamais** partager ce fichier ni le
   commiter — il est déjà exclu par `.gitignore`.

4. Vérifie que `WATCH_DIR` dans `.env` pointe bien vers le bon dossier (par
   défaut, le dossier OneDrive actuel — à mettre à jour le jour où tu bascules
   vers le NAS, sans autre changement nécessaire).

## Test manuel

```
python import_factures.py
```

Le script affiche ce qu'il fait ligne par ligne. Relance-le une seconde fois
immédiatement : il doit annoncer "0 nouveau(x) fichier(s) traité(s)" puisque
tout est déjà connu — c'est la vérification que l'idempotence fonctionne.

## Exécution automatique (Planificateur de tâches Windows)

1. Ouvrir "Planificateur de tâches" (recherche Windows).
2. Créer une tâche de base → déclencheur "Tous les jours", puis dans les
   propriétés du déclencheur cocher "Répéter la tâche toutes les" → **1 heure**,
   "pendant une durée de" → **1 jour** (= répétition continue toutes les heures).
3. Action : "Démarrer un programme" →
   - Programme : chemin complet vers `python.exe` (ex. `C:\Users\JOSSE\AppData\Local\Programs\Python\Python312\python.exe`,
     trouvable avec `where python` dans une invite de commande)
   - Arguments : `import_factures.py`
   - Démarrer dans : `D:\Antoine\GMAO-Android\www\claude code GMAO\import-factures`

**Si `WATCH_DIR` pointe un jour vers un dossier réseau (NAS)** : la tâche
planifiée doit tourner sous un compte utilisateur qui a accès à ce partage
réseau (les tâches planifiées lancées "que l'utilisateur soit connecté ou non"
n'ont parfois pas accès aux lecteurs réseau mappés — préférer un chemin UNC
complet `\\NAS\...` plutôt qu'une lettre de lecteur mappée dans ce cas).

## Dossier de transit partagé avec le comptable

Ce dossier sert aussi de transit manuel vers le logiciel du comptable
(Antoine y dépose les factures, les transmet, puis les archive ailleurs).
Une fois qu'un fichier est passé par le script (visible dans "À valider",
qu'il soit encore en attente, déjà validé ou rejeté), il est **stocké en
copie indépendante dans Supabase** — le déplacer, le renommer ou le
supprimer du dossier local ensuite n'a aucun effet.

En revanche, un fichier déplacé **avant** le premier passage du script ne
sera jamais proposé (le script ne regarde que ce qui est présent dans le
dossier au moment où il tourne, sans mémoire de ce qui y est passé avant).
Avec un scan toutes les heures, la fenêtre de risque est faible, mais par
sécurité : lancer `python import_factures.py` manuellement avant d'archiver
un lot de factures élimine complètement ce risque.

## Archivage automatique après validation

Si `ARCHIVE_DIR` est renseigné dans `.env`, le script déplace automatiquement,
à chaque exécution, les fichiers du dossier de transit dont la facture a été
**validée** dans le GMAO (statut `valide`) vers :

```
ARCHIVE_DIR\SAVADUR\Factures\<bien>\<zone>\<motif>\   (biens contenant "Dubail")
ARCHIVE_DIR\PERSO\Factures\<bien>\<zone>\<motif>\     (Calvin, Bouvet, Jean Martin...)
ARCHIVE_DIR\<SAVADUR|PERSO>\Factures\Non classe\<motif>\   (facture validée sans bien lié)
```

Racine commune avec les devis (voir plus bas) : `ARCHIVE_DIR\<SAVADUR|PERSO>\Devis\...`
à côté de `...\Factures\...`, et un dossier `...\Quittances\` vide en réserve
pour un usage futur (pas de pipeline automatique dessus pour l'instant).

Les sous-dossiers `<bien>`, `<zone>` et `<motif>` sont créés automatiquement à
la volée, inutile de tout créer à l'avance. Un fichier `en_attente` ou
`rejeté` n'est jamais déplacé — seuls les fichiers déjà validés bougent, et
seulement s'ils sont encore physiquement présents dans le dossier de transit
au moment du scan (voir la section précédente sur la fenêtre de risque).

Pour l'activer, ajoute cette ligne dans ton `.env` :
```
ARCHIVE_DIR=D:\Antoine\GMAO
```
(le dossier racine `D:\Antoine\GMAO\SAVADUR` et `...\PERSO` est déjà créé.)

## Limites connues (v1)

- Pas d'OCR : une facture scannée en image ou une photo de ticket n'aura pas
  d'entreprise/montant extraits automatiquement — à saisir manuellement dans
  le GMAO. Ce n'est pas un bug, c'est le choix fait pour la v1.
- Formats acceptés : PDF, JPG/PNG, et Word/OpenDocument (.doc, .docx, .odt).
  Extraction du texte (entreprise/montant) disponible pour .docx et .odt,
  pas pour .doc (vieux format binaire).
- Le dossier est scanné à plat (pas de sous-dossiers).
- L'extraction de montant/entreprise reste une estimation — toujours vérifier
  avant validation dans le GMAO, surtout pour les factures aux formats
  inhabituels.

## Aperçu PDF pour les fichiers Word/ODT

Ces formats ne s'ouvrent pas nativement dans un navigateur. Le script génère
donc automatiquement une copie PDF (via Microsoft Word, qui doit être installé
sur le PC qui exécute le script) et c'est cette copie que le lien "Ouvrir le
fichier" affiche dans le GMAO — l'original reste stocké tel quel à côté.

**Fragile en tâche planifiée sans session ouverte** : l'automatisation Word
(COM) peut se bloquer sur un fichier corrompu ou une boîte de dialogue
inattendue, sans timeout intégré. Une erreur sur un fichier n'empêche pas les
suivants, mais un blocage complet de Word nécessite de tuer le processus
manuellement (Gestionnaire des tâches → WINWORD.EXE) et de relancer le script
(idempotent, rien n'est retraité en double).

Pour générer l'aperçu des fichiers déjà importés avant l'ajout de cette
fonctionnalité :
```
python backfill_pdf_previews.py "D:\chemin\vers\le\dossier\source"
```

## Pipeline devis (import_devis.py)

Même principe que l'import de factures, mais **séparé** : un devis n'est pas
une pièce comptable à transmettre au comptable, donc pas dans `WATCH_DIR`.
Dossier surveillé et dossier d'archivage dédiés (`DEVIS_WATCH_DIR` /
`DEVIS_ARCHIVE_DIR` dans `.env`), actuellement sur le disque D, à remplacer
par un chemin réseau une fois le NAS en service (aucune modification de code
nécessaire, comme pour `WATCH_DIR`).

Les devis détectés atterrissent dans le GMAO, onglet **Chantiers → 📐 Devis à
valider**, où on les rattache à un bon de travaux existant (obligatoire — un
devis sans BT n'a pas de destination). Plusieurs devis peuvent être rattachés
au même BT pour comparer plusieurs artisans consultés ; un seul est marqué
"retenu" à la fois (visible et modifiable directement dans la fiche du BT),
et c'est son montant qui sert à l'écart devis/réel affiché partout ailleurs.

```
python import_devis.py
```

À planifier de la même façon que `import_factures.py` (tâche Windows
séparée — voir plus haut), aucun paramètre requis.
