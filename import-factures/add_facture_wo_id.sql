-- Permet de rattacher un bon de travaux des la validation automatique d'une
-- facture (comme deja possible sur le formulaire manuel via "BT lie") - sert
-- notamment a deduire le nom du chantier comme dossier d'archivage/regroupement
-- quand le BT n'a pas de bien/zone (construction neuve absente de la topologie).

alter table factures_a_valider add column if not exists wo_id uuid references work_orders(id);
