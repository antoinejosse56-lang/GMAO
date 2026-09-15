-- Caracteristiques fixes d'un logement (independantes du locataire en place :
-- adresse, etage, equipements, chauffage...), saisies une fois depuis la
-- fiche du bien/zone dans la Topologie, et reprises automatiquement par le
-- generateur de bail au lieu d'etre ressaisies a chaque nouveau locataire.
-- `bien` utilise le meme format que bien_documents.bien (chemin topologique
-- "Prop - Zone - SousZone", tiret simple).
create table if not exists logement_fiches (
  id uuid primary key default gen_random_uuid(),
  bien text unique not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table logement_fiches add column if not exists adresse text;
alter table logement_fiches add column if not exists appt text;
alter table logement_fiches add column if not exists type_logement text;
alter table logement_fiches add column if not exists etage text;
alter table logement_fiches add column if not exists annexes text;
alter table logement_fiches add column if not exists type_habitat text;
alter table logement_fiches add column if not exists regime text;
alter table logement_fiches add column if not exists periode_construction text;
alter table logement_fiches add column if not exists surface numeric;
alter table logement_fiches add column if not exists nb_pieces integer;
alter table logement_fiches add column if not exists chauffage text;
alter table logement_fiches add column if not exists eau_chaude text;
alter table logement_fiches add column if not exists equipements text;
alter table logement_fiches add column if not exists parties_communes text;
alter table logement_fiches add column if not exists tic text;
alter table logement_fiches disable row level security;
