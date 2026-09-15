-- Support de la synchronisation des BT issus d'une gamme vers Google Calendar
-- (script sync_gamme_calendar.py) : un agenda Google dedie par utilisateur
-- (partage avec lui, sauf pour l'admin qui reste proprietaire du compte), et
-- le suivi des evenements deja crees pour eviter les doublons a chaque
-- execution du script planifie.
alter table users add column if not exists gcal_id text;
-- Un meme BT peut apparaitre dans plusieurs agendas (celui de l'intervenant
-- assigne + celui de l'admin qui voit tout) : on stocke un objet
-- {calendar_id: event_id} plutot qu'un event_id unique.
alter table work_orders add column if not exists gcal_event_ids jsonb default '{}'::jsonb;
