# Restaurer GMAO à partir des sauvegardes

À utiliser si la base Supabase est perdue ou abîmée. **Ne jamais restaurer par-dessus la base en service** :
on reconstruit dans un projet neuf et vide, on contrôle, puis on y branche les applications.

## Ce qu'il faut (dans `Documents GMAO Perso\_Sauvegarde base GMAO` sur le NAS)

| Fichier | Contenu |
|---|---|
| `gmao_base_AAAA-MM-JJ_HHMMSS.zip` | toutes les lignes de tous les tableaux (3 dernières nuits) |
| `structure_base_AAAA-MM-JJ.sql` | description des tableaux, liens et règles |
| `manifeste_fichiers.json` | pour chaque document : son emplacement d'origine et sa copie sur le NAS |

Une archive dont le nom finit par `_ALERTE` ou `_INCOMPLETE` est suspecte : prendre la dernière sans suffixe.

**La structure ne se met pas à jour seule.** Après tout changement de tableau ou de colonne, relancer
`exporter_structure.sql` dans Supabase (SQL Editor, Run, Export CSV) et déposer le résultat sur le NAS.

## Étapes

1. Créer un projet Supabase neuf. Noter son adresse (`https://xxxx.supabase.co`).
2. Préparer les fichiers SQL, sur un PC avec Python :

       python preparer_restauration.py <archive.zip> <structure.sql> restauration https://xxxx.supabase.co

3. Les exécuter dans l'ordre avec `psql` (fourni dans le paquet « binaries » de PostgreSQL pour Windows).
   La chaîne de connexion se trouve dans Supabase, bouton « Connect », mode « Session pooler » :

       psql "CHAINE_DE_CONNEXION" -v ON_ERROR_STOP=1 -f restauration/1_structure.sql
       psql "CHAINE_DE_CONNEXION" -v ON_ERROR_STOP=1 -f restauration/2_donnees.sql
       psql "CHAINE_DE_CONNEXION" -v ON_ERROR_STOP=1 -f restauration/3_regles.sql

4. Recréer les 4 espaces de stockage (publics, comme aujourd'hui) : `documents-locataires`, `factures-a-valider`,
   `devis-a-valider`, `documents-a-valider`, puis y renvoyer chaque fichier d'après `manifeste_fichiers.json`.
5. Ressaisir la clé Brevo (elle n'est pas dans la sauvegarde) dans la table `app_config`.
   Les **comptes de connexion** (Supabase Authentication) ne sont pas sauvegardés non plus : fermer les inscriptions
   libres, recréer un compte par utilisateur, puis relier chaque compte à son profil dans le tableau `acces`
   (restauré vide), par exemple pour les comptes ayant la même adresse que leur profil GMAO :

       insert into public.acces (auth_id, utilisateur_id)
         select a.id, u.id from auth.users a join public.users u on lower(u.email) = lower(a.email);

   Vérifier ensuite chaque liaison : une adresse de connexion peut différer de celle du profil.
6. Mettre la nouvelle adresse et les nouvelles clés dans `index.html`, `gestion.html`, `saisie.html` et dans le
   fichier `.env` du NAS.
7. Contrôler avant de s'en servir : nombre de loyers, quelques documents qui s'ouvrent, envoi d'un mail d'essai.

## Ce qui a été testé (26/11/2026)

* Étapes 2 et 3 sur une base d'essai PostgreSQL 17 locale : 51 tableaux identiques à la sauvegarde
  (67 517 valeurs), liens et règles actifs.
* 1 927 fichiers retrouvés sur le NAS d'après le manifeste, identiques aux originaux ; les 405 liens de documents
  de la base mènent tous à un fichier sauvegardé.

**Non testé** : la restauration dans un vrai projet Supabase neuf, et le renvoi des fichiers (étape 4), pour lequel
aucun script n'est encore écrit.
