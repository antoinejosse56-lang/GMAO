-- Pipeline devis, miroir du pipeline factures mais separe (dossier different,
-- table et bucket dedies) - permet de comparer plusieurs devis pour un meme
-- bon de travaux (ex: 3 macons consultes) et de justifier le choix retenu.

-- Devis "valides" (par opposition a devis_a_valider, en attente) - plusieurs
-- lignes possibles par bon de travaux, une seule marquee retenue a la fois.
create table if not exists devis (
  id uuid primary key default gen_random_uuid(),
  wo_id uuid references work_orders(id) on delete cascade,
  entreprise text,
  montant_ttc numeric,
  date_devis date,
  document_url text,
  motif text,
  retenu boolean not null default false,
  notes text,
  created_at timestamptz not null default now()
);
alter table devis disable row level security;

-- Staging : devis detectes automatiquement par import_devis.py, en attente de
-- rattachement a un bon de travaux et de validation manuelle dans le GMAO.
create table if not exists devis_a_valider (
  id uuid primary key default gen_random_uuid(),
  fichier_nom text not null,
  fichier_date date,
  chemin_relatif text not null unique,
  storage_path text,
  apercu_pdf_path text,
  entreprise text,
  montant_ttc numeric,
  date_devis date,
  bien text,
  wo_id uuid references work_orders(id),
  motif text,
  devis_id uuid references devis(id),
  statut text not null default 'en_attente' check (statut in ('en_attente','valide','rejete')),
  erreur_extraction text,
  created_at timestamptz not null default now(),
  traite_at timestamptz
);
alter table devis_a_valider disable row level security;

insert into storage.buckets (id, name, public)
values ('devis-a-valider', 'devis-a-valider', true)
on conflict (id) do nothing;

drop policy if exists "Lecture publique devis-a-valider" on storage.objects;
create policy "Lecture publique devis-a-valider"
on storage.objects for select
using (bucket_id = 'devis-a-valider');
