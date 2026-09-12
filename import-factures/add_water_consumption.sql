-- Consommation totale (m3) associee a une facture d'eau (motif='Eau'), pour
-- pouvoir calculer automatiquement le tarif moyen TTC/m3 a repercuter aux
-- locataires (montant_ttc / consommation_m3) au lieu de le saisir a la main.
alter table factures add column if not exists consommation_m3 numeric;
