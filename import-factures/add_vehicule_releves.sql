-- Carnet de bord des vehicules (compteur kilometrique/horaire) : historique de
-- releves independant du module compteurs/releves existant (celui-ci est
-- couple a la facturation locataire - une sauvegarde de releve genere
-- automatiquement une ligne dans factures liee a un tenant_id, voir
-- index.html). Un relevé peut etre un simple releve, un plein de carburant
-- (litres/prix_litre/montant renseignes) ou un releve lie a une intervention
-- (wo_id renseigne, ex: vidange).
create table if not exists vehicule_releves (
  id uuid primary key default gen_random_uuid(),
  asset_id uuid not null references assets(id),
  date date not null,
  type text not null default 'releve',   -- 'releve' | 'plein' | 'entretien'
  unite text not null default 'km',      -- 'km' | 'heures'
  valeur numeric not null,
  wo_id uuid references work_orders(id),
  litres numeric,
  prix_litre numeric,
  montant numeric,
  notes text,
  created_at timestamptz not null default now()
);
alter table vehicule_releves disable row level security;
