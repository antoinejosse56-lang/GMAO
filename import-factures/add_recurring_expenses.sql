-- Prelevements bancaires recurrents reconnus (assurances mensualisees,
-- echeances de pret, abonnements...) : une fois defini une seule fois
-- (libelle bancaire exact + montant fixe), import_releve.py reconnait
-- automatiquement l'operation chaque mois suivant, sans repasser par un
-- rapprochement manuel repetitif. 2 modes :
-- - mode='facture' : la depense doit etre creditee sur une facture existante
--   (ex. assurance annuelle payee en plusieurs prelevements identiques) -
--   utilise le meme mecanisme que le rapprochement manuel (factures.
--   rapprochements). Si cette facture est deja soldee (nouvelle annee sans
--   facture encore recue), l'operation retombe en anomalie normale plutot
--   que de sur-crediter l'ancienne facture - `facture_id` est alors a
--   remettre a jour (ou detacher) manuellement une fois la nouvelle facture
--   recue et attachee.
-- - mode='echeancier' : aucune facture n'est attendue (ex. echeance de pret) -
--   seulement comptabilise comme recurrent reconnu, pas de lien facture.
create table if not exists recurring_expenses (
  id uuid primary key default gen_random_uuid(),
  compte text not null default 'savadur',
  libelle text not null,
  montant numeric not null,
  fournisseur text,
  mode text not null default 'echeancier' check (mode in ('facture','echeancier')),
  facture_id uuid references factures(id) on delete set null,
  notes text,
  actif boolean not null default true,
  created_at timestamptz not null default now()
);
alter table recurring_expenses disable row level security;
create unique index if not exists recurring_expenses_libelle_montant_idx on recurring_expenses (compte, libelle, montant);

-- Compteur dedie sur le rapport d'import (a cote de nb_debits_rapproches),
-- pour distinguer un rapprochement "reel" (facture identifiee ce mois-la)
-- d'une reconnaissance automatique via une regle recurrente deja definie.
alter table releve_imports add column if not exists nb_recurrents_connus integer not null default 0;
