-- Motif de la facture (Entretien / Renovation / Travaux / Etudes / Medicale /
-- Diagnostiques / texte libre) - sert a ranger les factures archivees dans
-- un sous-dossier par motif, pour les retrouver facilement en cas de revente
-- d'un bien ou d'une zone precise (ex: tous les diagnostics d'un appartement).

alter table factures add column if not exists motif text;
alter table factures_a_valider add column if not exists motif text;
