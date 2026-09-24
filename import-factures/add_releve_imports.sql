-- Historique des relevés bancaires importés automatiquement par
-- import_releve.py (compte SAVADUR, format OFX) : un rapprochement complet
-- sans etape de validation manuelle (contrairement aux pipelines factures/
-- devis/documents) puisque chaque operation debit se rapproche directement
-- d'une facture existante par montant - seules les anomalies (operation sans
-- facture, ou match ambigu) ont besoin d'un coup d'oeil humain, stockees ici
-- pour affichage dans l'onglet Factures > SAVADUR plutot que de fouiller un
-- fichier de log.

create table if not exists releve_imports (
  id uuid primary key default gen_random_uuid(),
  compte text not null default 'savadur',
  fichier_nom text not null,
  chemin_relatif text not null unique,
  periode_debut date,
  periode_fin date,
  nb_operations integer not null default 0,
  nb_debits_rapproches integer not null default 0,
  nb_debits_sans_facture integer not null default 0,
  nb_ambigus integer not null default 0,
  nb_credits_non_identifies integer not null default 0,
  anomalies jsonb,
  created_at timestamptz not null default now()
);
alter table releve_imports disable row level security;
