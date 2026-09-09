-- Ajoute un bien/propriete a un chantier (independamment des BT/factures qui
-- lui sont rattaches) pour pouvoir filtrer et regrouper l'onglet Chantiers
-- par bien, comme deja possible par statut et par annee.

alter table chantiers add column if not exists bien text;
