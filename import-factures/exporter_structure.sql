structure_gmao
"-- PostgreSQL 17.6 on aarch64-unknown-linux-gnu, compiled by gcc (GCC) 15.2.0, 64-bit

-- extension pg_stat_statements 1.11

-- extension pgcrypto 1.3

-- extension plpgsql 1.0

-- extension supabase_vault 0.3.1

-- extension uuid-ossp 1.1

create sequence if not exists public.facture_sequence_id_seq;

create table public.app_config (
  key text not null,
  value text
);

create table public.assets (
  id uuid default gen_random_uuid() not null,
  name text not null,
  category text,
  location text,
  type text,
  description text,
  status text default 'ok'::text,
  next_maint date,
  documents jsonb default '[]'::jsonb,
  history jsonb default '[]'::jsonb,
  created_at timestamp with time zone default now(),
  carte_grise jsonb default '{}'::jsonb,
  compte text
);

create table public.bien_documents (
  id uuid default gen_random_uuid() not null,
  bien text not null,
  type text,
  date date,
  date_expiry date,
  fichier_nom text,
  document_url text,
  notes text,
  created_at timestamp with time zone default now() not null
);

create table public.chantiers (
  id uuid default gen_random_uuid() not null,
  nom text not null,
  description text,
  statut text default 'ouvert'::text not null,
  created_at timestamp with time zone default now() not null,
  date_debut date,
  date_fin date,
  bien text
);

create table public.compteurs (
  id uuid default gen_random_uuid() not null,
  name text not null,
  type text default 'Eau froide'::text,
  unite text default 'm³'::text,
  numero_serie text,
  index_initial numeric default 0,
  topo_id text,
  notes text,
  created_at timestamp with time zone default now(),
  tenant_id uuid,
  prix_unitaire numeric default 0
);

create table public.consommables (
  id uuid default gen_random_uuid() not null,
  nom text not null,
  categorie text,
  reference text,
  stock numeric default 0,
  stock_min numeric default 0,
  unite text default 'pièce(s)'::text,
  prix_achat numeric default 0,
  emplacement text,
  description text,
  created_at timestamp with time zone default now(),
  asset_id uuid,
  affect_type text,
  famille_id uuid,
  affect_label text,
  order_links jsonb default '[]'::jsonb,
  location_detail text
);

create table public.creche_saisies (
  id uuid default gen_random_uuid() not null,
  enfant_id uuid,
  annee integer,
  mois integer,
  jour integer,
  depose_anticipee time without time zone,
  recuperation_tardive time without time zone,
  heure_contrat_dep time without time zone,
  heure_contrat_rec time without time zone,
  minutes_sup integer default 0,
  created_at timestamp with time zone default now(),
  arrivee_tardive time without time zone,
  depart_anticipe time without time zone,
  absence_autorisee boolean default false
);

create table public.devis (
  id uuid default gen_random_uuid() not null,
  wo_id uuid,
  entreprise text,
  montant_ttc numeric,
  date_devis date,
  document_url text,
  motif text,
  retenu boolean default false not null,
  notes text,
  created_at timestamp with time zone default now() not null,
  chantier_id uuid
);

create table public.devis_a_valider (
  id uuid default gen_random_uuid() not null,
  fichier_nom text not null,
  fichier_date date,
  chemin_relatif text not null,
  storage_path text,
  apercu_pdf_path text,
  entreprise text,
  montant_ttc numeric,
  date_devis date,
  bien text,
  wo_id uuid,
  motif text,
  devis_id uuid,
  statut text default 'en_attente'::text not null,
  erreur_extraction text,
  created_at timestamp with time zone default now() not null,
  traite_at timestamp with time zone,
  chantier_id uuid,
  content_hash text
);

create table public.documents_a_valider (
  id uuid default gen_random_uuid() not null,
  fichier_nom text not null,
  fichier_date date,
  chemin_relatif text not null,
  storage_path text,
  apercu_pdf_path text,
  content_hash text,
  bien text,
  type text,
  date_document date,
  notes text,
  statut text default 'en_attente'::text not null,
  erreur_extraction text,
  created_at timestamp with time zone default now() not null,
  traite_at timestamp with time zone,
  asset_id uuid,
  famille_id uuid
);

create table public.ecole_saisies (
  id uuid default gen_random_uuid() not null,
  enfant_id uuid,
  annee integer,
  mois integer,
  jour integer,
  peri_matin_dep time without time zone,
  peri_matin_fin time without time zone,
  peri_soir_dep time without time zone,
  peri_soir_fin time without time zone,
  peri_matin_min integer default 0,
  peri_soir_min integer default 0,
  peri_matin_np_min integer default 0,
  peri_soir_np_min integer default 0,
  type_peri text default 'prevu'::text,
  cantine boolean default false,
  centre_loisir boolean default false,
  created_at timestamp with time zone default now(),
  absence_autorisee boolean default false
);

create table public.facture_sequence (
  id integer default nextval('facture_sequence_id_seq'::regclass) not null,
  annee integer not null,
  dernier_numero integer default 0
);

create table public.factures (
  id uuid default gen_random_uuid() not null,
  date date not null,
  fournisseur text not null,
  categorie text,
  description text,
  bien text,
  wo_id uuid,
  montant_ht numeric default 0,
  tva numeric default 0,
  tva_pct numeric default 0,
  montant_ttc numeric not null,
  numero text,
  compte text default 'savadur'::text,
  drive_url text,
  notes text,
  rapproche boolean default false,
  created_at timestamp with time zone default now(),
  document_url text,
  date_paiement date,
  asset_id uuid,
  famille_id uuid,
  motif text,
  chantier_id uuid,
  consommation_m3 numeric,
  rapprochements jsonb default '[]'::jsonb not null
);

create table public.factures_a_valider (
  id uuid default gen_random_uuid() not null,
  fichier_nom text not null,
  fichier_date date,
  chemin_relatif text not null,
  storage_path text,
  entreprise text,
  montant_ttc numeric,
  bien text,
  statut text default 'en_attente'::text not null,
  erreur_extraction text,
  facture_id uuid,
  created_at timestamp with time zone default now() not null,
  traite_at timestamp with time zone,
  date_facture date,
  asset_id uuid,
  description text,
  famille_id uuid,
  apercu_pdf_path text,
  motif text,
  wo_id uuid,
  chantier_id uuid,
  content_hash text
);

create table public.famille (
  id uuid default gen_random_uuid() not null,
  prenom text not null,
  nom text,
  relation text,
  naissance date,
  email text,
  telephone text,
  notes text,
  events jsonb default '[]'::jsonb,
  docs jsonb default '[]'::jsonb,
  created_at timestamp with time zone default now(),
  documents jsonb default '[]'::jsonb,
  photo_url text,
  contrat_creche jsonb default '{}'::jsonb,
  contrat_ecole jsonb default '{}'::jsonb,
  type_membre text
);

create table public.fiches_paie_chiffrees (
  id uuid default gen_random_uuid() not null,
  periode text not null,
  iv text not null,
  ciphertext text not null,
  type text default 'bulletin'::text not null,
  created_at timestamp with time zone default now() not null
);

create table public.fournisseurs (
  id uuid default gen_random_uuid() not null,
  nom text not null,
  corps_metier text,
  telephone text,
  email text,
  notes text,
  created_at timestamp with time zone default now() not null,
  type text
);

create table public.loans (
  id uuid default gen_random_uuid() not null,
  tool_id uuid,
  borrower text not null,
  date date,
  expected_return date,
  returned boolean default false,
  notes text,
  created_at timestamp with time zone default now()
);

create table public.logement_edl (
  id uuid default gen_random_uuid() not null,
  bien text not null,
  tenant_id uuid,
  type text not null,
  linked_edl_id uuid,
  date date,
  structure jsonb,
  compteurs jsonb,
  cles jsonb,
  data jsonb,
  observations text,
  paraphe_bailleur text,
  paraphe_locataire text,
  sig_bailleur text,
  sig_locataire text,
  pdf_url text,
  created_at timestamp with time zone default now() not null,
  coloc_sigs jsonb
);

create table public.logement_fiches (
  id uuid default gen_random_uuid() not null,
  bien text not null,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null,
  adresse text,
  appt text,
  etage text,
  annexes text,
  type_habitat text,
  regime text,
  periode_construction text,
  surface numeric,
  nb_pieces integer,
  chauffage text,
  eau_chaude text,
  equipements text,
  parties_communes text,
  tic text,
  type_logement text,
  gaz_present boolean,
  edl_structure jsonb
);

create table public.maintenance_templates (
  id uuid default gen_random_uuid() not null,
  name text not null,
  asset_id uuid,
  type text default 'periodic'::text,
  period_days integer,
  last_done date,
  next_due date,
  due_date date,
  description text,
  priority text default 'medium'::text,
  assigned_to uuid,
  created_at timestamp with time zone default now(),
  auto_bt boolean default false,
  bt_category text default 'Entretien'::text,
  cso_links jsonb default '[]'::jsonb,
  alert_days integer,
  bien text,
  zone_id text,
  sub_id text,
  zone_nom text,
  sub_nom text,
  bt_jours_avant integer,
  bt_recalcul text default 'validation'::text
);

create table public.menage_missions (
  id uuid default gen_random_uuid() not null,
  turno_id text not null,
  room text,
  date_mission date not null,
  heure_debut text,
  heure_fin text,
  agent text,
  statut text default 'non_assignee'::text not null,
  reservation_id uuid,
  doublon_de text,
  montant numeric,
  facture_id uuid,
  notes text,
  vue_le timestamp with time zone default now() not null,
  created_at timestamp with time zone default now() not null
);

create table public.pc_albums (
  id uuid default gen_random_uuid() not null,
  nom text not null,
  annee integer,
  created_by text,
  created_at timestamp without time zone default now()
);

create table public.pc_arrivees_departs (
  id uuid default gen_random_uuid() not null,
  prenom text not null,
  date_arrivee date,
  heure_arrivee time without time zone,
  date_depart date,
  heure_depart time without time zone,
  moyen_transport text,
  observations text,
  created_at timestamp without time zone default now()
);

create table public.pc_checklist (
  id uuid default gen_random_uuid() not null,
  tache text not null,
  assignee text,
  statut text default 'À faire'::text,
  date date,
  created_at timestamp without time zone default now()
);

create table public.pc_covoiturage (
  id uuid default gen_random_uuid() not null,
  prenom text not null,
  type text,
  depart text,
  destination text,
  date date,
  heure time without time zone,
  places_disponibles integer,
  commentaire text,
  created_at timestamp without time zone default now()
);

create table public.pc_cuisine (
  id uuid default gen_random_uuid() not null,
  date date not null,
  membre text not null,
  menu_midi text,
  menu_soir text,
  created_at timestamp without time zone default now()
);

create table public.pc_membres (
  id uuid default gen_random_uuid() not null,
  prenom text not null,
  role text not null,
  famille text,
  email text,
  created_at timestamp without time zone default now(),
  mot_de_passe text
);

create table public.pc_musiques (
  id uuid default gen_random_uuid() not null,
  titre text not null,
  url text not null,
  created_at timestamp without time zone default now()
);

create table public.pc_participants (
  id uuid default gen_random_uuid() not null,
  planning_id uuid,
  prenom text not null,
  type text not null,
  created_at timestamp without time zone default now()
);

create table public.pc_photos (
  id uuid default gen_random_uuid() not null,
  url text not null,
  thumbnail_url text,
  public_id text,
  auteur text,
  legende text,
  date_prise date,
  created_at timestamp without time zone default now(),
  album_id uuid
);

create table public.pc_planning (
  id uuid default gen_random_uuid() not null,
  prenom text not null,
  famille text,
  nombre_personnes integer,
  date_arrivee date not null,
  date_depart date not null,
  commentaire text,
  email_proprietaire text,
  created_at timestamp without time zone default now(),
  statut text default 'validé'::text
);

create table public.pc_push_subscriptions (
  id uuid default gen_random_uuid() not null,
  membre text not null,
  famille text,
  subscription jsonb not null,
  created_at timestamp without time zone default now()
);

create table public.pc_repas (
  id uuid default gen_random_uuid() not null,
  prenom text not null,
  date date not null,
  midi boolean default true,
  soir boolean default true,
  planning_id uuid,
  created_at timestamp without time zone default now()
);

create table public.rangements (
  id uuid default gen_random_uuid() not null,
  nom text not null,
  description text,
  created_at timestamp with time zone default now(),
  lieu text,
  bien text,
  parent_id uuid
);

create table public.recurring_expenses (
  id uuid default gen_random_uuid() not null,
  compte text default 'savadur'::text not null,
  libelle text not null,
  montant numeric not null,
  fournisseur text,
  mode text default 'echeancier'::text not null,
  facture_id uuid,
  notes text,
  actif boolean default true not null,
  created_at timestamp with time zone default now() not null
);

create table public.releve_imports (
  id uuid default gen_random_uuid() not null,
  compte text default 'savadur'::text not null,
  fichier_nom text not null,
  chemin_relatif text not null,
  periode_debut date,
  periode_fin date,
  nb_operations integer default 0 not null,
  nb_debits_rapproches integer default 0 not null,
  nb_debits_sans_facture integer default 0 not null,
  nb_ambigus integer default 0 not null,
  nb_credits_non_identifies integer default 0 not null,
  anomalies jsonb,
  created_at timestamp with time zone default now() not null,
  nb_recurrents_connus integer default 0 not null
);

create table public.releves (
  id uuid default gen_random_uuid() not null,
  compteur_id uuid,
  date date not null,
  ancien_index numeric default 0,
  nouvel_index numeric default 0,
  prix_unitaire numeric default 0,
  notes text,
  created_at timestamp with time zone default now(),
  paye boolean default false,
  facture_envoyee boolean default false
);

create table public.rent_payments (
  id uuid default gen_random_uuid() not null,
  tenant_id uuid,
  logement text,
  annee integer,
  mois_num integer,
  mois text,
  montant numeric default 0,
  part_caf numeric default 0,
  part_locataire numeric default 0,
  date_caf date,
  date_loc date,
  paye boolean default false,
  quittance_envoyee boolean default false,
  notes text,
  created_at timestamp with time zone default now(),
  locataire_part numeric default 0,
  caf numeric default 0,
  loyer numeric default 0,
  commentaire text default ''::text,
  dette_ant numeric default 0,
  note_quittance text,
  ajustement numeric default 0,
  remise numeric,
  remise_motif text
);

create table public.reservations (
  id uuid default gen_random_uuid() not null,
  lodgify_id text,
  property text,
  room text,
  guest_name text,
  guest_email text,
  date_arrivee date,
  date_depart date,
  nb_nuits integer,
  montant_nuits numeric,
  frais_menage numeric,
  frais_resa numeric,
  taxe_sejour numeric,
  montant_total numeric,
  source text,
  statut text default 'confirmed'::text,
  created_at timestamp with time zone default now(),
  nb_adultes integer,
  confirm_code text,
  notes text,
  facture_numero text,
  facture_generee boolean default false,
  menage_prestataire boolean default true,
  montant_estime boolean default false
);

create table public.revenues (
  id uuid default gen_random_uuid() not null,
  prop_id text,
  prop_name text,
  zone_id text,
  sub_id text,
  type text,
  amount numeric default 0,
  charges numeric default 0,
  notes text,
  created_at timestamp with time zone default now()
);

create table public.revenus_geres (
  id uuid default gen_random_uuid() not null,
  bien text not null,
  gestionnaire text,
  date date not null,
  mois text not null,
  annee integer not null,
  montant numeric not null,
  libelle text,
  notes text,
  created_at timestamp with time zone default now() not null
);

create table public.tasks (
  id uuid default gen_random_uuid() not null,
  asset_id uuid,
  title text not null,
  description text,
  due_date date,
  status text default 'pending'::text,
  priority text default 'medium'::text,
  assigned_to uuid,
  docs jsonb default '[]'::jsonb,
  created_at timestamp with time zone default now()
);

create table public.tenants (
  id uuid default gen_random_uuid() not null,
  logement text,
  nom text,
  email text,
  loyer_ref numeric default 0,
  caf boolean default false,
  dette numeric default 0,
  actif boolean default true,
  notes text,
  created_at timestamp with time zone default now(),
  type_bail text default 'habitation'::text,
  telephone text,
  caution numeric default 0,
  date_entree date,
  date_sortie date,
  charges numeric default 0,
  bail_url text default ''::text,
  edl_url text default ''::text,
  assurance_url text default ''::text,
  edl_entree jsonb,
  edl_sortie jsonb,
  bail_data jsonb,
  remboursements jsonb default '[]'::jsonb,
  tf_surface_m2 numeric,
  tf_surface_totale_m2 numeric,
  tf_dernier_regul_annee integer,
  garant_nom text,
  garant_lien text,
  garant_adr text,
  identite_photos jsonb,
  date_naissance date,
  lieu_naissance text,
  nationalite text,
  colocataires jsonb,
  caution_remboursee_date date
);

create table public.tf_regularisations (
  id uuid default gen_random_uuid() not null,
  tenant_id uuid,
  annee integer not null,
  tf_annee numeric,
  tf_annee_precedente numeric,
  augmentation_annuelle_ht numeric,
  nb_mois_augmentation numeric,
  augmentation_ht numeric,
  augmentation_ttc numeric,
  regul_mois_ht numeric,
  regul_mois_ttc numeric,
  total_ttc numeric,
  created_at timestamp with time zone default now() not null
);

create table public.tools (
  id uuid default gen_random_uuid() not null,
  name text not null,
  category text,
  location text,
  description text,
  status text default 'available'::text,
  notes text,
  created_at timestamp with time zone default now(),
  location_detail text
);

create table public.topology (
  id uuid default gen_random_uuid() not null,
  data jsonb default '{""properties"": []}'::jsonb not null,
  updated_at timestamp with time zone default now()
);

create table public.users (
  id uuid default gen_random_uuid() not null,
  name text not null,
  email text not null,
  password text not null,
  role text default 'lecteur'::text not null,
  assets text[] default '{}'::text[],
  initials text,
  created_at timestamp with time zone default now(),
  visible_tabs jsonb default '[]'::jsonb,
  visible_assets jsonb default '[]'::jsonb,
  profile text default 'custom'::text,
  gcal_id text,
  readonly_tabs jsonb
);

create table public.vehicule_releves (
  id uuid default gen_random_uuid() not null,
  asset_id uuid not null,
  date date not null,
  type text default 'releve'::text not null,
  unite text default 'km'::text not null,
  valeur numeric not null,
  wo_id uuid,
  litres numeric,
  prix_litre numeric,
  montant numeric,
  notes text,
  created_at timestamp with time zone default now() not null,
  photo_url text,
  plein_complet boolean default true not null
);

create table public.water_readings (
  id uuid default gen_random_uuid() not null,
  logement_id text,
  logement_name text,
  annee integer,
  period text,
  ancien_index numeric default 0,
  nouvel_index numeric default 0,
  consommation numeric default 0,
  prix_unitaire numeric default 0,
  montant numeric default 0,
  date_paiement date,
  paid boolean default false,
  created_at timestamp with time zone default now()
);

create table public.work_orders (
  id uuid default gen_random_uuid() not null,
  asset_id uuid,
  title text not null,
  description text,
  date date,
  status text default 'open'::text,
  category text,
  cost numeric default 0,
  by_user text,
  docs jsonb default '[]'::jsonb,
  created_at timestamp with time zone default now(),
  topo_ref jsonb,
  journal jsonb default '[]'::jsonb,
  by_email text,
  due_date date,
  alert_pref text,
  checklist jsonb default '[]'::jsonb,
  paid boolean default false,
  alert_days integer,
  source text,
  gamme_id uuid,
  devis_montant numeric,
  chantier_id uuid,
  gcal_event_ids jsonb default '{}'::jsonb
);

alter table public.app_config add constraint app_config_pkey PRIMARY KEY (key);

alter table public.assets add constraint assets_compte_check CHECK ((compte = ANY (ARRAY['savadur'::text, 'perso'::text])));

alter table public.assets add constraint assets_pkey PRIMARY KEY (id);

alter table public.bien_documents add constraint bien_documents_pkey PRIMARY KEY (id);

alter table public.chantiers add constraint chantiers_pkey PRIMARY KEY (id);

alter table public.chantiers add constraint chantiers_statut_check CHECK ((statut = ANY (ARRAY['ouvert'::text, 'termine'::text])));

alter table public.compteurs add constraint compteurs_pkey PRIMARY KEY (id);

alter table public.consommables add constraint consommables_pkey PRIMARY KEY (id);

alter table public.creche_saisies add constraint creche_saisies_pkey PRIMARY KEY (id);

alter table public.devis add constraint devis_pkey PRIMARY KEY (id);

alter table public.devis_a_valider add constraint devis_a_valider_chemin_relatif_key UNIQUE (chemin_relatif);

alter table public.devis_a_valider add constraint devis_a_valider_pkey PRIMARY KEY (id);

alter table public.devis_a_valider add constraint devis_a_valider_statut_check CHECK ((statut = ANY (ARRAY['en_attente'::text, 'valide'::text, 'rejete'::text])));

alter table public.documents_a_valider add constraint documents_a_valider_chemin_relatif_key UNIQUE (chemin_relatif);

alter table public.documents_a_valider add constraint documents_a_valider_pkey PRIMARY KEY (id);

alter table public.documents_a_valider add constraint documents_a_valider_statut_check CHECK ((statut = ANY (ARRAY['en_attente'::text, 'valide'::text, 'rejete'::text])));

alter table public.ecole_saisies add constraint ecole_saisies_pkey PRIMARY KEY (id);

alter table public.facture_sequence add constraint facture_sequence_annee_key UNIQUE (annee);

alter table public.facture_sequence add constraint facture_sequence_pkey PRIMARY KEY (id);

alter table public.factures add constraint factures_pkey PRIMARY KEY (id);

alter table public.factures_a_valider add constraint factures_a_valider_chemin_relatif_key UNIQUE (chemin_relatif);

alter table public.factures_a_valider add constraint factures_a_valider_pkey PRIMARY KEY (id);

alter table public.factures_a_valider add constraint factures_a_valider_statut_check CHECK ((statut = ANY (ARRAY['en_attente'::text, 'valide'::text, 'rejete'::text, 'classe'::text])));

alter table public.famille add constraint famille_pkey PRIMARY KEY (id);

alter table public.fiches_paie_chiffrees add constraint fiches_paie_chiffrees_pkey PRIMARY KEY (id);

alter table public.fournisseurs add constraint fournisseurs_pkey PRIMARY KEY (id);

alter table public.loans add constraint loans_pkey PRIMARY KEY (id);

alter table public.logement_edl add constraint logement_edl_pkey PRIMARY KEY (id);

alter table public.logement_fiches add constraint logement_fiches_bien_key UNIQUE (bien);

alter table public.logement_fiches add constraint logement_fiches_pkey PRIMARY KEY (id);

alter table public.maintenance_templates add constraint maintenance_templates_pkey PRIMARY KEY (id);

alter table public.menage_missions add constraint menage_missions_pkey PRIMARY KEY (id);

alter table public.menage_missions add constraint menage_missions_turno_id_key UNIQUE (turno_id);

alter table public.pc_albums add constraint pc_albums_pkey PRIMARY KEY (id);

alter table public.pc_arrivees_departs add constraint pc_arrivees_departs_pkey PRIMARY KEY (id);

alter table public.pc_checklist add constraint pc_checklist_pkey PRIMARY KEY (id);

alter table public.pc_covoiturage add constraint pc_covoiturage_pkey PRIMARY KEY (id);

alter table public.pc_cuisine add constraint pc_cuisine_date_membre_key UNIQUE (date, membre);

alter table public.pc_cuisine add constraint pc_cuisine_pkey PRIMARY KEY (id);

alter table public.pc_membres add constraint pc_membres_pkey PRIMARY KEY (id);

alter table public.pc_musiques add constraint pc_musiques_pkey PRIMARY KEY (id);

alter table public.pc_participants add constraint pc_participants_pkey PRIMARY KEY (id);

alter table public.pc_photos add constraint pc_photos_pkey PRIMARY KEY (id);

alter table public.pc_planning add constraint pc_planning_pkey PRIMARY KEY (id);

alter table public.pc_push_subscriptions add constraint pc_push_subscriptions_membre_key UNIQUE (membre);

alter table public.pc_push_subscriptions add constraint pc_push_subscriptions_pkey PRIMARY KEY (id);

alter table public.pc_repas add constraint pc_repas_pkey PRIMARY KEY (id);

alter table public.rangements add constraint rangements_pkey PRIMARY KEY (id);

alter table public.recurring_expenses add constraint recurring_expenses_mode_check CHECK ((mode = ANY (ARRAY['facture'::text, 'echeancier'::text])));

alter table public.recurring_expenses add constraint recurring_expenses_pkey PRIMARY KEY (id);

alter table public.releve_imports add constraint releve_imports_chemin_relatif_key UNIQUE (chemin_relatif);

alter table public.releve_imports add constraint releve_imports_pkey PRIMARY KEY (id);

alter table public.releves add constraint releves_pkey PRIMARY KEY (id);

alter table public.rent_payments add constraint rent_payments_pkey PRIMARY KEY (id);

alter table public.reservations add constraint reservations_dates_room_key UNIQUE (date_arrivee, date_depart, room);

alter table public.reservations add constraint reservations_pkey PRIMARY KEY (id);

alter table public.revenues add constraint revenues_pkey PRIMARY KEY (id);

alter table public.revenus_geres add constraint revenus_geres_pkey PRIMARY KEY (id);

alter table public.tasks add constraint tasks_pkey PRIMARY KEY (id);

alter table public.tenants add constraint tenants_pkey PRIMARY KEY (id);

alter table public.tf_regularisations add constraint tf_regularisations_pkey PRIMARY KEY (id);

alter table public.tools add constraint tools_pkey PRIMARY KEY (id);

alter table public.topology add constraint topology_pkey PRIMARY KEY (id);

alter table public.users add constraint users_email_key UNIQUE (email);

alter table public.users add constraint users_pkey PRIMARY KEY (id);

alter table public.vehicule_releves add constraint vehicule_releves_pkey PRIMARY KEY (id);

alter table public.water_readings add constraint water_readings_pkey PRIMARY KEY (id);

alter table public.work_orders add constraint work_orders_pkey PRIMARY KEY (id);

alter table public.compteurs add constraint compteurs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id);

alter table public.consommables add constraint consommables_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL;

alter table public.consommables add constraint consommables_famille_id_fkey FOREIGN KEY (famille_id) REFERENCES famille(id) ON DELETE SET NULL;

alter table public.creche_saisies add constraint creche_saisies_enfant_id_fkey FOREIGN KEY (enfant_id) REFERENCES famille(id) ON DELETE CASCADE;

alter table public.devis add constraint devis_chantier_id_fkey FOREIGN KEY (chantier_id) REFERENCES chantiers(id) ON DELETE SET NULL;

alter table public.devis add constraint devis_wo_id_fkey FOREIGN KEY (wo_id) REFERENCES work_orders(id) ON DELETE CASCADE;

alter table public.devis_a_valider add constraint devis_a_valider_chantier_id_fkey FOREIGN KEY (chantier_id) REFERENCES chantiers(id);

alter table public.devis_a_valider add constraint devis_a_valider_devis_id_fkey FOREIGN KEY (devis_id) REFERENCES devis(id);

alter table public.devis_a_valider add constraint devis_a_valider_wo_id_fkey FOREIGN KEY (wo_id) REFERENCES work_orders(id);

alter table public.documents_a_valider add constraint documents_a_valider_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id);

alter table public.documents_a_valider add constraint documents_a_valider_famille_id_fkey FOREIGN KEY (famille_id) REFERENCES famille(id);

alter table public.ecole_saisies add constraint ecole_saisies_enfant_id_fkey FOREIGN KEY (enfant_id) REFERENCES famille(id) ON DELETE CASCADE;

alter table public.factures add constraint factures_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id);

alter table public.factures add constraint factures_chantier_id_fkey FOREIGN KEY (chantier_id) REFERENCES chantiers(id) ON DELETE SET NULL;

alter table public.factures add constraint factures_famille_id_fkey FOREIGN KEY (famille_id) REFERENCES famille(id);

alter table public.factures add constraint factures_wo_id_fkey FOREIGN KEY (wo_id) REFERENCES work_orders(id) ON DELETE SET NULL;

alter table public.factures_a_valider add constraint factures_a_valider_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id);

alter table public.factures_a_valider add constraint factures_a_valider_chantier_id_fkey FOREIGN KEY (chantier_id) REFERENCES chantiers(id);

alter table public.factures_a_valider add constraint factures_a_valider_facture_id_fkey FOREIGN KEY (facture_id) REFERENCES factures(id);

alter table public.factures_a_valider add constraint factures_a_valider_famille_id_fkey FOREIGN KEY (famille_id) REFERENCES famille(id);

alter table public.factures_a_valider add constraint factures_a_valider_wo_id_fkey FOREIGN KEY (wo_id) REFERENCES work_orders(id);

alter table public.loans add constraint loans_tool_id_fkey FOREIGN KEY (tool_id) REFERENCES tools(id) ON DELETE CASCADE;

alter table public.logement_edl add constraint logement_edl_linked_edl_id_fkey FOREIGN KEY (linked_edl_id) REFERENCES logement_edl(id);

alter table public.logement_edl add constraint logement_edl_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id);

alter table public.maintenance_templates add constraint maintenance_templates_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE;

alter table public.maintenance_templates add constraint maintenance_templates_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL;

alter table public.menage_missions add constraint menage_missions_facture_id_fkey FOREIGN KEY (facture_id) REFERENCES factures(id) ON DELETE SET NULL;

alter table public.menage_missions add constraint menage_missions_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL;

alter table public.pc_participants add constraint pc_participants_planning_id_fkey FOREIGN KEY (planning_id) REFERENCES pc_planning(id) ON DELETE CASCADE;

alter table public.pc_photos add constraint pc_photos_album_id_fkey FOREIGN KEY (album_id) REFERENCES pc_albums(id);

alter table public.pc_repas add constraint pc_repas_planning_id_fkey FOREIGN KEY (planning_id) REFERENCES pc_planning(id);

alter table public.rangements add constraint rangements_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES rangements(id);

alter table public.recurring_expenses add constraint recurring_expenses_facture_id_fkey FOREIGN KEY (facture_id) REFERENCES factures(id) ON DELETE SET NULL;

alter table public.releves add constraint releves_compteur_id_fkey FOREIGN KEY (compteur_id) REFERENCES compteurs(id) ON DELETE CASCADE;

alter table public.rent_payments add constraint rent_payments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

alter table public.tasks add constraint tasks_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE;

alter table public.tasks add constraint tasks_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL;

alter table public.tf_regularisations add constraint tf_regularisations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

alter table public.vehicule_releves add constraint vehicule_releves_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id);

alter table public.vehicule_releves add constraint vehicule_releves_wo_id_fkey FOREIGN KEY (wo_id) REFERENCES work_orders(id);

alter table public.work_orders add constraint work_orders_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE;

alter table public.work_orders add constraint work_orders_chantier_id_fkey FOREIGN KEY (chantier_id) REFERENCES chantiers(id) ON DELETE SET NULL;

CREATE INDEX devis_a_valider_content_hash_idx ON public.devis_a_valider USING btree (content_hash);

CREATE INDEX documents_a_valider_content_hash_idx ON public.documents_a_valider USING btree (content_hash);

CREATE INDEX factures_a_valider_content_hash_idx ON public.factures_a_valider USING btree (content_hash);

CREATE INDEX fiches_paie_chiffrees_periode_type_idx ON public.fiches_paie_chiffrees USING btree (periode, type);

CREATE INDEX menage_missions_date_idx ON public.menage_missions USING btree (date_mission);

CREATE INDEX menage_missions_resa_idx ON public.menage_missions USING btree (reservation_id);

CREATE UNIQUE INDEX recurring_expenses_libelle_montant_idx ON public.recurring_expenses USING btree (compte, libelle, montant);

CREATE UNIQUE INDEX revenus_geres_bien_date_montant_idx ON public.revenus_geres USING btree (bien, date, montant);

alter table public.app_config enable row level security;

alter table public.assets enable row level security;

alter table public.compteurs enable row level security;

alter table public.consommables enable row level security;

alter table public.creche_saisies enable row level security;

alter table public.ecole_saisies enable row level security;

alter table public.factures enable row level security;

alter table public.factures_a_valider enable row level security;

alter table public.famille enable row level security;

alter table public.loans enable row level security;

alter table public.maintenance_templates enable row level security;

alter table public.menage_missions enable row level security;

alter table public.pc_albums enable row level security;

alter table public.pc_arrivees_departs enable row level security;

alter table public.pc_checklist enable row level security;

alter table public.pc_covoiturage enable row level security;

alter table public.pc_cuisine enable row level security;

alter table public.pc_membres enable row level security;

alter table public.pc_musiques enable row level security;

alter table public.pc_participants enable row level security;

alter table public.pc_photos enable row level security;

alter table public.pc_planning enable row level security;

alter table public.pc_push_subscriptions enable row level security;

alter table public.pc_repas enable row level security;

alter table public.rangements enable row level security;

alter table public.releves enable row level security;

alter table public.rent_payments enable row level security;

alter table public.revenues enable row level security;

alter table public.tasks enable row level security;

alter table public.tenants enable row level security;

alter table public.tools enable row level security;

alter table public.topology enable row level security;

alter table public.users enable row level security;

alter table public.water_readings enable row level security;

alter table public.work_orders enable row level security;

create policy allow_all on public.app_config as permissive for all to public using (true) with check (true);

create policy app_config_acces on public.app_config as permissive for all to anon, authenticated using (true) with check (true);

create policy app_config_cle_secrete on public.app_config as restrictive for all to anon, authenticated using ((key <> 'brevo_api_key'::text)) with check ((key <> 'brevo_api_key'::text));

create policy ""allow all assets"" on public.assets as permissive for all to public using (true) with check (true);

create policy allow_all on public.assets as permissive for all to public using (true) with check (true);

create policy ""allow all compteurs"" on public.compteurs as permissive for all to public using (true) with check (true);

create policy allow_all on public.compteurs as permissive for all to public using (true) with check (true);

create policy allow_all on public.consommables as permissive for all to public using (true) with check (true);

create policy allow_all on public.creche_saisies as permissive for all to public using (true) with check (true);

create policy allow_all on public.ecole_saisies as permissive for all to public using (true) with check (true);

create policy allow_all on public.factures as permissive for all to public using (true) with check (true);

create policy ""Lecture publique factures_a_valider"" on public.factures_a_valider as permissive for select to public using (true);

create policy ""Maj publique factures_a_valider"" on public.factures_a_valider as permissive for update to public using (true) with check (true);

create policy allow_all on public.famille as permissive for all to public using (true) with check (true);

create policy ""allow all loans"" on public.loans as permissive for all to public using (true) with check (true);

create policy allow_all on public.loans as permissive for all to public using (true) with check (true);

create policy ""allow all maintenance_templates"" on public.maintenance_templates as permissive for all to public using (true) with check (true);

create policy allow_all on public.maintenance_templates as permissive for all to public using (true) with check (true);

create policy ""ecriture publique"" on public.pc_albums as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_albums as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_arrivees_departs as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_arrivees_departs as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_checklist as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_checklist as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_covoiturage as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_covoiturage as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_cuisine as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_cuisine as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_membres as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_membres as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_musiques as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_musiques as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_participants as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_participants as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_photos as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_photos as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_planning as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_planning as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_push_subscriptions as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_push_subscriptions as permissive for select to public using (true);

create policy ""ecriture publique"" on public.pc_repas as permissive for all to public using (true);

create policy ""lecture publique"" on public.pc_repas as permissive for select to public using (true);

create policy allow_all on public.rangements as permissive for all to public using (true) with check (true);

create policy ""allow all releves"" on public.releves as permissive for all to public using (true) with check (true);

create policy allow_all on public.releves as permissive for all to public using (true) with check (true);

create policy ""allow all rent_payments"" on public.rent_payments as permissive for all to public using (true) with check (true);

create policy allow_all on public.rent_payments as permissive for all to public using (true) with check (true);

create policy ""allow all revenues"" on public.revenues as permissive for all to public using (true) with check (true);

create policy allow_all on public.revenues as permissive for all to public using (true) with check (true);

create policy ""allow all tasks"" on public.tasks as permissive for all to public using (true) with check (true);

create policy allow_all on public.tasks as permissive for all to public using (true) with check (true);

create policy ""allow all tenants"" on public.tenants as permissive for all to public using (true) with check (true);

create policy allow_all on public.tenants as permissive for all to public using (true) with check (true);

create policy ""allow all tools"" on public.tools as permissive for all to public using (true) with check (true);

create policy allow_all on public.tools as permissive for all to public using (true) with check (true);

create policy ""allow all topology"" on public.topology as permissive for all to public using (true) with check (true);

create policy allow_all on public.topology as permissive for all to public using (true) with check (true);

create policy ""allow all users"" on public.users as permissive for all to public using (true) with check (true);

create policy allow_all on public.users as permissive for all to public using (true) with check (true);

create policy ""allow all water_readings"" on public.water_readings as permissive for all to public using (true) with check (true);

create policy allow_all on public.water_readings as permissive for all to public using (true) with check (true);

create policy ""allow all work_orders"" on public.work_orders as permissive for all to public using (true) with check (true);

create policy allow_all on public.work_orders as permissive for all to public using (true) with check (true);

-- espace de stockage devis-a-valider (public : t)

-- espace de stockage documents-a-valider (public : t)

-- espace de stockage documents-locataires (public : t)

-- espace de stockage factures-a-valider (public : t)"