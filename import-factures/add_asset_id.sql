-- Lien facture -> equipement (assets), en plus du lien bien/zone deja existant
-- (colonne "bien" en texte libre). Permet par ex. de lier une facture MMG a
-- l'equipement "evok" independamment du bien concerne.

alter table factures add column if not exists asset_id uuid references assets(id);
alter table factures_a_valider add column if not exists asset_id uuid references assets(id);
