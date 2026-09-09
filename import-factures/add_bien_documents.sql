-- Nouvelle table pour les documents administratifs lies a un bien (DPE,
-- diagnostic amiante/plomb/electricite, etc.) - distincte de `factures` car
-- ce ne sont pas des depenses a suivre, juste des documents a archiver et
-- retrouver depuis la fiche du bien (onglet Topologie).

create table if not exists bien_documents (
  id uuid primary key default gen_random_uuid(),
  bien text not null,
  type text,
  date date,
  date_expiry date,
  fichier_nom text,
  document_url text,
  notes text,
  created_at timestamptz not null default now()
);
alter table bien_documents disable row level security;

-- Permet de transferer une ligne de factures_a_valider vers bien_documents
-- (statut 'classe') plutot que de la valider comme facture ou de la rejeter.
alter table factures_a_valider drop constraint if exists factures_a_valider_statut_check;
alter table factures_a_valider add constraint factures_a_valider_statut_check
  check (statut in ('en_attente','valide','rejete','classe'));
