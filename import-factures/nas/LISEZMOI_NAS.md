# Imports GMAO sur le NAS Synology

Les imports (courrier, factures, devis, relevés, documents, synchro calendrier, sauvegarde) tournent sur le NAS,
qui reste allumé en permanence, au lieu du PC qui se met en veille. Ce sont les mêmes scripts que sur Windows.

## 1. Préparer le dossier (sur le PC)

```
python nas/build_nas_package.py
```

Le dossier `nas/dist/gmao-imports/` est créé. **Il contient des secrets** (clé Supabase, mots de passe d'application
Gmail dans le fichier `.env`) : ne le déposez que dans un emplacement privé du NAS, pas dans un partage commun.

## 2. Installer Python sur le NAS

DSM → **Centre de paquets** → chercher « **Python 3.9** » (ou 3.11 / 3.12 si proposé) → **Installer**.

## 3. Déposer le dossier

DSM → **File Station** → dossier personnel de l'administrateur (`homes/<votre-compte>/`) → y glisser le dossier
`gmao-imports`. Son chemin devient par exemple `/volume1/homes/<votre-compte>/gmao-imports` (clic droit →
Propriétés pour le voir).

## 4. Créer les 3 tâches (Panneau de configuration → Planificateur de tâches)

Pour chacune : **Créer → Tâche planifiée → Script défini par l'utilisateur**, utilisateur **root**.
Remplacez `CHEMIN` par le chemin de l'étape 3.

| Nom | Planification | Script (onglet « Paramètres de la tâche ») |
|---|---|---|
| GMAO - installation | une seule fois (à lancer à la main) | `bash "CHEMIN/setup_nas.sh"` |
| GMAO - imports | tous les jours, **répéter toutes les heures** (de 00h07 à 23h07) | `bash "CHEMIN/run_all.sh"` |
| GMAO - sauvegarde | tous les jours à 02h00 | `bash "CHEMIN/run_backup.sh"` |

1. Lancez « GMAO - installation » (sélection → **Exécuter**), puis ouvrez `gmao-imports/logs/setup_nas.log` :
   il doit finir par « modules OK » et afficher les deux partages détectés.
2. Lancez « GMAO - imports » à la main et consultez `logs/run_all.log` (un code 0 par étape).

## 5. Ce qui change

* Les pièces jointes des mails étiquetés « A importer » arrivent dans
  `Documents GMAO Perso\_En_cours\Factures a traiter` (et `Devis a traiter` pour les devis), au lieu du dossier
  « A METTRE DANS DEXT » du PC.
* Les aperçus PDF des fichiers Word/ODT (qui demandaient Word sur le PC) ne sont plus générés ; le fichier reste
  importé normalement.
* Les journaux sont dans `gmao-imports/logs/`.

## Sauvegarde et vérification (tables et fichiers)

La tâche « GMAO - sauvegarde » (02h00) lance d'abord `backup_base.py` (tables), puis `backup_to_nas.py` (fichiers).
Chaque passage vérifie ce qu'il a sauvegardé :

* tables : double lecture de la base, puis relecture de l'archive comparée valeur par valeur ;
* fichiers : tous les espaces de stockage, chaque fichier comparé à l'empreinte de l'original ; un fichier
  différent n'est jamais écrasé ni ignoré. `python backup_to_nas.py --simulation` contrôle sans rien écrire.

Si l'une des deux n'est pas complète, `alerte_sauvegarde.py` envoie un mail. Essai de l'alerte :
`python alerte_sauvegarde.py --essai`. Aucun mail n'est possible si le NAS est éteint ou sans internet.
Chaque nuit crée `Documents GMAO Perso\_Sauvegarde base GMAO\gmao_base_AAAA-MM-JJ_HHMMSS.zip` (un fichier JSON
par table). La base est seulement lue. Seules les **3 dernières sauvegardes saines** sont conservées ; en cas
d'alerte ou de sauvegarde incomplète, plus rien n'est supprimé tant que le problème n'a pas été examiné.

À contrôler dans `logs/run_all.log` : `backup_base -> code 0`. Le code 2 signale une sauvegarde incomplète ou
une table disparue, vidée ou ayant perdu au moins 5 lignes et 10 %, le code 1 un échec : détail dans `logs/backup_base.log`.

## 6. Une fois que tout fonctionne

Désactiver les tâches planifiées Windows équivalentes pour éviter les doublons (demandez-le à Claude).
