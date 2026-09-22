-- Paraphe/signature de chaque colocataire (tenants.colocataires) sur l'etat
-- des lieux, au meme titre que le locataire principal - meme mecanique que
-- bail_data.coloc_sigs cote bail (mais bail_data est un blob jsonb unique
-- alors que logement_edl a une colonne dediee par signataire, d'ou l'ajout
-- explicite de cette colonne).
-- Forme : [{"nom":"...", "paraphe":"data:image/png;base64,...", "sig":"data:image/png;base64,..."}]
alter table logement_edl add column if not exists coloc_sigs jsonb;
