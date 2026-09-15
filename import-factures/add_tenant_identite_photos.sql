-- Photos de pieces d'identite (locataire(s) et garant), rattachees au
-- locataire (pas au logement) : une piece d'identite suit la personne, pas
-- l'appartement, contrairement aux diagnostics de bien_documents. Tableau
-- jsonb libre plutot qu'un modele rigide personne/face, chaque photo porte
-- juste une etiquette texte modifiable (ex: "KAHRAMAN Okan - recto").
alter table tenants add column if not exists identite_photos jsonb;
