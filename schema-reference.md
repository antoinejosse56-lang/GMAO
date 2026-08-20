# Schéma Supabase — périmètre GMAO Pro
Obtenu par requête SQL directe le 20/08/2026. Les tables pc_* de la même
base (pc_albums, pc_arrivees_departs, pc_checklist, pc_covoiturage,
pc_cuisine, pc_membres, pc_musiques, pc_participants, pc_photos,
pc_planning, pc_push_subscriptions, pc_repas) appartiennent à l'app
Petit Cosquet et sont HORS PÉRIMÈTRE de ce projet.

## rent_payments
id uuid, tenant_id uuid, logement text, annee integer, mois_num integer,
mois text, montant numeric, part_caf numeric (morte, cf CLAUDE.md),
part_locataire numeric (morte, cf CLAUDE.md), date_caf date, date_loc date,
paye boolean, quittance_envoyee boolean, notes text,
created_at timestamp with time zone, locataire_part numeric, caf numeric,
loyer numeric, commentaire text, dette_ant numeric, note_quittance text,
ajustement numeric, remise numeric, remise_motif text

## reservations
id uuid, lodgify_id text, property text, room text, guest_name text,
guest_email text, date_arrivee date, date_depart date, nb_nuits integer,
montant_nuits numeric, frais_menage numeric, frais_resa numeric,
taxe_sejour numeric, montant_total numeric, source text, statut text,
created_at timestamp with time zone, nb_adultes integer, confirm_code text,
notes text, facture_numero text, facture_generee boolean,
menage_prestataire boolean

## tenants
id uuid, logement text, nom text, email text, loyer_ref numeric, caf boolean

## creche_saisies
id uuid, enfant_id uuid, annee integer, mois integer, jour integer,
depose_anticipee time, recuperation_tardive time, heure_contrat_dep time,
heure_contrat_rec time, minutes_sup integer, created_at timestamp with time zone,
arrivee_tardive time, depart_anticipe time, absence_autorisee boolean

## ecole_saisies
id uuid, enfant_id uuid, annee integer, mois integer, jour integer,
peri_matin_dep time, peri_matin_fin time, peri_soir_dep time,
peri_soir_fin time, peri_matin_min integer, peri_soir_min integer,
peri_matin_np_min integer, peri_soir_np_min integer, type_peri text,
cantine boolean, centre_loisir boolean, created_at timestamp with time zone,
absence_autorisee boolean

## famille
id uuid, prenom text, nom text, relation text, naissance date, email text,
telephone text

## assets
id uuid, name text, category text, location text, type text,
description text, status text, next_maint date, documents jsonb,
history jsonb, created_at timestamp with time zone, carte_grise jsonb

## compteurs
id uuid, name text, type text, unite text, numero_serie text,
index_initial numeric, topo_id text, notes text,
created_at timestamp with time zone, tenant_id uuid, prix_unitaire numeric

## releves
id uuid, compteur_id uuid, date date, ancien_index numeric,
nouvel_index numeric, prix_unitaire numeric, notes text,
created_at timestamp with time zone, paye boolean, facture_envoyee boolean

## consommables
id uuid, nom text, categorie text, reference text, stock numeric,
stock_min numeric, unite text, prix_achat numeric, emplacement text,
description text, created_at timestamp with time zone, asset_id uuid,
affect_type text, famille_id uuid, affect_label text, order_links jsonb

## factures
id uuid, date date, fournisseur text, categorie text, description text,
bien text, wo_id uuid, montant_ht numeric, tva numeric, tva_pct numeric,
montant_ttc numeric, numero text, compte text, drive_url text, notes text,
rapproche boolean, created_at timestamp with time zone

## facture_sequence
id integer, annee integer, dernier_numero integer

## maintenance_templates
id uuid, name text, asset_id uuid, type text, period_days integer,
last_done date, next_due date, due_date date, description text,
priority text, assigned_to uuid, created_at timestamp with time zone,
auto_bt boolean, bt_category text, cso_links jsonb, alert_days integer,
bien text, zone_id text, sub_id text, zone_nom text, sub_nom text,
bt_jours_avant integer, bt_recalcul text

## tasks
id uuid, asset_id uuid, title text, description text, due_date date,
status text, priority text, assigned_to uuid, docs jsonb,
created_at timestamp with time zone

## loans
id uuid, tool_id uuid, borrower text, date date, expected_return date,
returned boolean, notes text, created_at timestamp with time zone

## rangements
id uuid, nom text, description text, created_at timestamp with time zone,
lieu text

## revenues
id uuid, prop_id text, prop_name text, zone_id text, sub_id text, type text,
amount numeric, charges numeric, notes text, created_at timestamp with time zone

## app_config
key text, value text
