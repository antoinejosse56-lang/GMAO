-- Suivi des montants deja rapproches sur une facture, en plus du booleen
-- `rapproche` existant : une charge mensualisee (assurance payee en 5
-- prelevements pour 1 seule facture annuelle) doit pouvoir etre rapprochee
-- plusieurs fois sans que la facture ne "disparaisse" du choix tant qu'elle
-- n'est pas soldee - `rapproche` (booleen) ne devient true qu'une fois la
-- somme des rapprochements >= montant_ttc.
alter table factures add column if not exists rapprochements jsonb not null default '[]'::jsonb;
