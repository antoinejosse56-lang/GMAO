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

## 6. Une fois que tout fonctionne

Désactiver les tâches planifiées Windows équivalentes pour éviter les doublons (demandez-le à Claude).
