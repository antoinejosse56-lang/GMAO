-- Coordonnees du garant, jusqu'ici saisies uniquement dans le formulaire de
-- bail (donc reservees a cette seule generation, jamais reutilisables ni
-- visibles sur la fiche locataire). Meme logique que les autres champs
-- communs (email, telephone...) : une seule source, pre-remplie dans le
-- bail, synchronisee a l'enregistrement.
alter table tenants add column if not exists garant_nom text;
alter table tenants add column if not exists garant_lien text;
alter table tenants add column if not exists garant_adr text;
