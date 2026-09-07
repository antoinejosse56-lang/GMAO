-- Chemin de stockage d'un apercu PDF genere automatiquement pour les factures
-- au format .doc/.docx/.odt (non visualisables directement dans un navigateur).
-- NULL = pas encore genere (fichier PDF/JPG/PNG d'origine, ou conversion pas
-- encore faite). Le lien "Ouvrir le fichier" utilise cette colonne en priorite
-- sur storage_path quand elle est renseignee.

alter table factures_a_valider add column if not exists apercu_pdf_path text;
