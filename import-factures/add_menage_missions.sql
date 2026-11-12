-- Suivi des missions de menage Turno (courte duree) : une ligne par mission Turno, rapprochee de la
-- reservation GMAO du meme depart (meme chambre, date de la mission = date de depart).
--
-- Sert a :
--  * savoir, pour chaque reservation, si une mission existe et si un agent l'a acceptee / est assigne ;
--  * alerter quand un menage n'est toujours pas assigne a l'approche d'un depart ;
--  * reperer les DOUBLONS (deux missions pour le meme depart : calendrier Airbnb + calendrier Lodgify...) ;
--  * controler la facture mensuelle de l'agent (facture_id) puisque les paiements ne passent pas par Turno.
--
-- A executer une fois dans Supabase (SQL Editor). Peut etre relance sans risque.
create table if not exists menage_missions (
  id uuid primary key default gen_random_uuid(),
  turno_id text not null unique,                -- numero de mission Turno (ex: 39945197)
  room text,                                    -- 'Studio' | 'T2' (reservations.room)
  date_mission date not null,                   -- jour de la mission (= jour de depart du voyageur)
  heure_debut text,                             -- ex '11:00'
  heure_fin text,                               -- ex '17:00'
  agent text,                                   -- nom de l'agent assigne ; NULL = non assignee
  statut text not null default 'non_assignee',  -- 'non_assignee' | 'assignee' | 'annulee'
  reservation_id uuid references reservations(id) on delete set null,
  doublon_de text,                              -- turno_id de la mission conservee, si celle-ci est un doublon
  montant numeric,                              -- cout de la mission si connu
  facture_id uuid references factures(id) on delete set null,  -- facture de l'agent qui la couvre
  notes text,
  vue_le timestamptz not null default now(),    -- derniere fois vue dans Turno
  created_at timestamptz not null default now()
);
create index if not exists menage_missions_date_idx on menage_missions (date_mission);
create index if not exists menage_missions_resa_idx on menage_missions (reservation_id);
alter table menage_missions disable row level security;
