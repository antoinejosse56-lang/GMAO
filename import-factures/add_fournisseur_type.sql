-- Type d'artisan/entreprise (Artisan, Societe de prestation, Fournisseur de
-- materiel) pour classer la liste "Artisans" - renseigne manuellement au cas
-- par cas depuis la fiche de chaque fournisseur.
alter table fournisseurs add column if not exists type text;
