-- Montant du devis initial d'un bon de travaux, pour comparer au cout reel
-- (somme des factures liees via factures.wo_id, deja existant) et voir l'ecart
-- devis / reel sur un chantier.

alter table work_orders add column if not exists devis_montant numeric;
