-- Revenus locatifs pour un bien gere entierement par un tiers (agence type
-- Foncia) : loyer/charges/travaux deja geres et netes par l'agence, aucun
-- bail/EDL/quittance a produire depuis le GMAO (a la difference des biens
-- geres directement, ex. SAVADUR/Rue Calvin). Une ligne = un virement net
-- effectivement recu par le proprietaire, tel qu'il apparait sur le compte-
-- rendu de gestion (CRG) de l'agence.
-- Pas de tenant_id : le nom du locataire n'apparait meme pas sur le CRG
-- (l'agence gere la relation locataire de bout en bout) - inutile de creer
-- un faux locataire GMAO pour ce bien.
create table if not exists revenus_geres (
  id uuid primary key default gen_random_uuid(),
  bien text not null,               -- ex: 'Rue Jean Martin'
  gestionnaire text,                -- ex: 'Foncia'
  date date not null,               -- date du virement recu
  mois text not null,               -- 'Janvier'..'Décembre', pour regroupement identique aux autres tableaux de revenus
  annee integer not null,
  montant numeric not null,         -- montant net effectivement recu
  libelle text,                     -- libelle(s) brut(s) du CRG source, pour tracabilite/audit
  notes text,
  created_at timestamptz not null default now()
);
alter table revenus_geres disable row level security;
-- Dedoublonnage : un meme bien ne peut avoir 2 virements identiques (montant
-- ET date) enregistres 2 fois si le CRG est reimporte plus tard avec des
-- lignes qui se chevauchent (ex: reexport mensuel qui reprend l'historique).
create unique index if not exists revenus_geres_bien_date_montant_idx on revenus_geres (bien, date, montant);
