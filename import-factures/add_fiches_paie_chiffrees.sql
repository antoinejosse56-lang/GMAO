-- Fiches de salaire d'Antoine, chiffrees cote client (AES-256-GCM) avant
-- d'arriver ici : cette table ne contient jamais le detail en clair, meme
-- avec la cle anon Supabase (partagee par toute l'appli, visible dans le
-- code source public). Seule la "periode" (ex: "2026-09") reste en clair,
-- pour pouvoir trier/lister sans avoir a tout dechiffrer.
--
-- Le sel global (PBKDF2) et la passphrase de dechiffrement sont stockes
-- UNIQUEMENT sur le NAS (Famille/Salaire/_cle_dechiffrement.txt), jamais
-- dans Supabase ni dans le code - sans eux, ces lignes sont illisibles,
-- y compris pour quelqu'un ayant un acces complet a la base.
--
-- Visible uniquement dans l'onglet "Salaire" de GMAO, lui-meme reserve a
-- isAdmin() (donc a Antoine) - voir index.html.
create table if not exists fiches_paie_chiffrees (
  id uuid primary key default gen_random_uuid(),
  periode text not null,          -- 'AAAA-MM', en clair (tri/liste uniquement)
  iv text not null,               -- nonce AES-GCM, base64 (12 octets)
  ciphertext text not null,       -- JSON chiffre de la fiche, base64
  type text not null default 'bulletin',  -- 'bulletin' | 'compte_recup'
  created_at timestamptz not null default now()
);
alter table fiches_paie_chiffrees disable row level security;
-- Pas de contrainte unique stricte : un compte-recup peut etre renvoye/mis a
-- jour plusieurs fois sans date mensuelle fixe. L'appli remplace la ligne
-- existante (meme periode+type) plutot que de dupliquer, avant d'inserer.
create index if not exists fiches_paie_chiffrees_periode_type_idx on fiches_paie_chiffrees (periode, type);
