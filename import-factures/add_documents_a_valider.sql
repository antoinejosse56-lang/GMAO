-- Pipeline "documents generiques" (import_documents.py), jumeau leger des
-- pipelines factures/devis mais pour tout document qui n'est ni une facture
-- ni un devis (DPE, attestation d'assurance, diagnostic, annexe de bail...) :
-- dossier surveille distinct (partage NAS, accessible par Pauline y compris
-- depuis un smartphone), pas d'extraction automatique (un document generique
-- n'a pas de structure "montant/entreprise" a deviner) - juste un depot, une
-- classification manuelle rapide (bien + type) dans le GMAO, puis un
-- archivage sur le NAS (SAVADUR ou Perso selon le bien choisi).

create table if not exists documents_a_valider (
  id uuid primary key default gen_random_uuid(),
  fichier_nom text not null,
  fichier_date date,
  chemin_relatif text not null unique,
  storage_path text,
  apercu_pdf_path text,
  content_hash text,
  bien text,
  type text,
  date_document date,
  notes text,
  statut text not null default 'en_attente' check (statut in ('en_attente','valide','rejete')),
  erreur_extraction text,
  created_at timestamptz not null default now(),
  traite_at timestamptz
);
alter table documents_a_valider disable row level security;
create index if not exists documents_a_valider_content_hash_idx on documents_a_valider (content_hash);

insert into storage.buckets (id, name, public)
values ('documents-a-valider', 'documents-a-valider', true)
on conflict (id) do nothing;

drop policy if exists "Lecture publique documents-a-valider" on storage.objects;
create policy "Lecture publique documents-a-valider"
on storage.objects for select
using (bucket_id = 'documents-a-valider');
