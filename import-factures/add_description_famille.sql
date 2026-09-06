-- Description sur les factures detectees automatiquement (existe deja sur
-- factures, jamais transmise depuis factures_a_valider faute de colonne) +
-- lien facture -> personne (famille), pour les factures medicales ou autres
-- concernant un membre en particulier - meme principe que le lien equipement
-- (asset_id) deja en place.

alter table factures_a_valider add column if not exists description text;
alter table factures add column if not exists famille_id uuid references famille(id);
alter table factures_a_valider add column if not exists famille_id uuid references famille(id);
