-- Repertoire des artisans/entreprises avec qui vous travaillez regulierement,
-- pour retrouver rapidement un nom deja connu (autocompletion) au lieu de le
-- retaper a chaque facture. Ne remplace pas la saisie libre : le champ
-- "Entreprise" des factures reste du texte, ce repertoire sert juste de
-- suggestion (attribut HTML "list" sur le champ existant).

create table if not exists fournisseurs (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  corps_metier text,       -- ex: Plomberie, Electricite, Menage...
  telephone text,
  email text,
  notes text,
  created_at timestamptz not null default now()
);

-- Si l'ecriture depuis le GMAO echoue avec une erreur "row-level security" /
-- "permission denied", dites-le moi : il faudra ajouter une policy RLS
-- equivalente a celles des autres tables du projet.
