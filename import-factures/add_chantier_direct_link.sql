-- Lien direct facture -> chantier, sans passer par un bon de travaux (utile
-- pour un chantier avec plusieurs artisans/factures mais sans decoupage en
-- BT par corps de metier, ex: piscine) + dates et filtre par annee pour les
-- chantiers, comme pour les bons de travaux.

alter table factures add column if not exists chantier_id uuid references chantiers(id) on delete set null;
alter table factures_a_valider add column if not exists chantier_id uuid references chantiers(id);

alter table chantiers add column if not exists date_debut date;
alter table chantiers add column if not exists date_fin date;
