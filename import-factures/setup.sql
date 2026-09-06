-- Setup Supabase pour la fonctionnalité "Import de factures" (v1, sans OCR)
-- À exécuter une seule fois dans Supabase Dashboard → SQL Editor.
-- N'affecte aucune donnée existante : nouvelle table + 1 colonne nullable sur factures + nouveau bucket.

-- 1. Table de staging : factures détectées par le script, en attente de validation manuelle
create table if not exists factures_a_valider (
  id uuid primary key default gen_random_uuid(),
  fichier_nom text not null,
  fichier_date date,
  chemin_relatif text not null unique,  -- garantit l'idempotence du scan (jamais reproposé 2x)
  storage_path text,                    -- chemin du PDF dans le bucket factures-a-valider
  entreprise text,                      -- extrait automatiquement, éditable avant validation
  montant_ttc numeric,                  -- extrait automatiquement, éditable avant validation
  bien text,                            -- "Bien - Zone - SousZone", vide autorisé
  statut text not null default 'en_attente' check (statut in ('en_attente','valide','rejete')),
  erreur_extraction text,               -- message si le PDF est illisible/corrompu
  facture_id uuid references factures(id),
  created_at timestamptz not null default now(),
  traite_at timestamptz
);

-- 2. Nouvelle colonne dédiée sur factures pour les PDF venant de ce pipeline
--    (distincte de drive_url, qui reste réservée aux liens Google Drive existants)
alter table factures add column if not exists document_url text;

-- 3. Bucket de stockage pour les PDF détectés (public, cohérent avec le modèle de confiance
--    du reste du projet : les liens drive_url existants sont eux aussi de simples liens publics)
insert into storage.buckets (id, name, public)
values ('factures-a-valider', 'factures-a-valider', true)
on conflict (id) do nothing;

-- 4. Lecture publique du bucket (le script d'import écrit avec la clé service_role,
--    qui contourne RLS — donc pas besoin de policy d'écriture pour l'app cliente)
drop policy if exists "Lecture publique factures-a-valider" on storage.objects;
create policy "Lecture publique factures-a-valider"
on storage.objects for select
using (bucket_id = 'factures-a-valider');

-- Note : si RLS est activé par défaut sur ton projet pour les nouvelles tables (à vérifier —
-- les tables existantes du GMAO semblent toutes accessibles en lecture/écriture via la clé anon
-- sans policy explicite), il faudra une policy équivalente sur factures_a_valider elle-même.
-- Dis-moi si le script échoue avec une erreur de type "permission denied" / "row-level security"
-- une fois en place, je te donnerai la policy correspondante.
