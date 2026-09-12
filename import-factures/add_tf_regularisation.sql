-- Regularisation annuelle de la taxe fonciere pour les locaux commerciaux
-- (BAAM, SARL ANNA...) au prorata de leur surface. tf_surface_m2/tf_surface_totale_m2
-- donnent la fraction (ex: 72/483) ; tf_dernier_regul_annee memorise la derniere
-- annee deja regularisee pour ce locataire, pour savoir a partir de quand
-- calculer la prochaine augmentation et eviter les doublons.
alter table tenants add column if not exists tf_surface_m2 numeric;
alter table tenants add column if not exists tf_surface_totale_m2 numeric;
alter table tenants add column if not exists tf_dernier_regul_annee integer;

-- Historique des regularisations emises (audit + evite de regenerer une lettre
-- deja envoyee pour la meme annee).
create table if not exists tf_regularisations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references tenants(id) on delete cascade,
  annee integer not null,
  tf_annee numeric,
  tf_annee_precedente numeric,
  augmentation_annuelle_ht numeric,
  nb_mois_augmentation numeric,
  augmentation_ht numeric,
  augmentation_ttc numeric,
  regul_mois_ht numeric,
  regul_mois_ttc numeric,
  total_ttc numeric,
  created_at timestamptz not null default now()
);
alter table tf_regularisations disable row level security;
