-- Date de remboursement du depot de garantie au locataire (rapprochement
-- bancaire d'un debit "virement au locataire" apres son depart) - simple
-- date informative, comme date_paiement sur factures ou date_caf/date_loc
-- sur rent_payments, sans autre effet de bord ailleurs dans le GMAO.
alter table tenants add column if not exists caution_remboursee_date date;
