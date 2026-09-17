-- Complete la fiche locataire pour la generation du bail : date/lieu de
-- naissance et nationalite du locataire principal, plus une liste de
-- colocataires (personnes supplementaires sur le meme bail), chacun avec
-- ses propres nom/date/lieu de naissance.
alter table tenants add column if not exists date_naissance date;
alter table tenants add column if not exists lieu_naissance text;
alter table tenants add column if not exists nationalite text;
alter table tenants add column if not exists colocataires jsonb;
