-- Complement : date d'emission de la facture (extraite du PDF, distincte de la date du
-- fichier/reception mail) + date de paiement (saisie manuelle, n'existait pas du tout).

alter table factures_a_valider add column if not exists date_facture date;
alter table factures add column if not exists date_paiement date;
