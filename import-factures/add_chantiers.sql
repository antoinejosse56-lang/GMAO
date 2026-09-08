-- Chantiers : regroupent plusieurs bons de travaux (ex: une construction avec
-- un BT maconnerie, un BT placo, un BT plomberie, chacun son propre devis et
-- ses propres factures) pour voir le devis/reel cumule de tout le chantier.

create table if not exists chantiers (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  description text,
  statut text not null default 'ouvert' check (statut in ('ouvert','termine')),
  created_at timestamptz not null default now()
);
-- RLS active par defaut sur les nouvelles tables de ce projet (deja rencontre
-- avec "fournisseurs") - desactive pour rester coherent avec le reste du GMAO.
alter table chantiers disable row level security;

-- "on delete set null" : supprimer un chantier detache ses BT au lieu de les
-- supprimer (comportement annonce a l'utilisateur cote GMAO).
alter table work_orders add column if not exists chantier_id uuid references chantiers(id) on delete set null;
