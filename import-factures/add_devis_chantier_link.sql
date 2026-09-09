-- Permet de lier un devis directement a un chantier (sans bon de travaux),
-- meme principe que chantier_id sur factures/factures_a_valider - utile pour
-- reclasser un devis arrive par erreur dans les factures a valider (ex: piscine
-- avec plusieurs artisans consultes, pas de BT par corps de metier).

alter table devis add column if not exists chantier_id uuid references chantiers(id) on delete set null;
alter table devis_a_valider add column if not exists chantier_id uuid references chantiers(id);
