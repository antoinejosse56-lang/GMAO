-- Un document depose dans le dossier partage ne concerne pas forcement un
-- bien (DPE, diagnostic...) : ca peut aussi etre un document vehicule (carte
-- grise, assurance, facture entretien -> assets.documents) ou un document
-- personnel d'un membre de la famille (passeport, carte vitale... ->
-- famille.documents). `bien` (deja existant) reste utilise pour le cas bien ;
-- ces 2 colonnes couvrent les 2 autres cibles possibles - une seule des 3
-- est renseignee selon le choix fait dans le GMAO au moment du classement.
alter table documents_a_valider add column if not exists asset_id uuid references assets(id);
alter table documents_a_valider add column if not exists famille_id uuid references famille(id);
