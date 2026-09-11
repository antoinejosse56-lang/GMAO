-- Empreinte (SHA256) du contenu binaire de chaque fichier importe, pour
-- detecter automatiquement les doublons a l'import (meme facture recue sur
-- les 2 boites mail, ou deja deposee a la main dans le dossier surveille
-- puis re-recuperee par le scan Gmail) sans attendre la validation manuelle.
alter table factures_a_valider add column if not exists content_hash text;
alter table devis_a_valider add column if not exists content_hash text;
create index if not exists factures_a_valider_content_hash_idx on factures_a_valider (content_hash);
create index if not exists devis_a_valider_content_hash_idx on devis_a_valider (content_hash);
