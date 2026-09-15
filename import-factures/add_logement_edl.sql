-- Etat des lieux (entree/sortie). La structure des pieces (nombre de
-- chambres/salles de bain/WC, pieces libres) est configuree une seule fois
-- par logement puis memorisee sur sa fiche (comme les autres faits fixes du
-- logement), pour etre reutilisee automatiquement a chaque etat des lieux
-- suivant (sortie du meme locataire, entree des locataires futurs).
alter table logement_fiches add column if not exists edl_structure jsonb;

create table if not exists logement_edl (
  id uuid primary key default gen_random_uuid(),
  bien text not null,
  tenant_id uuid references tenants(id),
  type text not null,
  linked_edl_id uuid references logement_edl(id),
  date date,
  structure jsonb,
  compteurs jsonb,
  cles jsonb,
  data jsonb,
  observations text,
  paraphe_bailleur text,
  paraphe_locataire text,
  sig_bailleur text,
  sig_locataire text,
  pdf_url text,
  created_at timestamptz not null default now()
);
alter table logement_edl disable row level security;
