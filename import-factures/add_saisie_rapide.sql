-- Saisie rapide (rapide.html) : les factures arrivent dans "Factures > A valider".
-- A executer UNE fois dans Supabase > SQL Editor, AVANT de publier les pages modifiees.
-- Ne modifie et ne supprime aucune donnee existante.

-- 1. Compte (savadur / perso) et categorie choisis au moment de la saisie
alter table factures_a_valider add column if not exists compte text;
alter table factures_a_valider add column if not exists categorie text;

-- 2. Autoriser UNIQUEMENT l'ajout d'une ligne en attente issue de la saisie rapide
--    (la table n'autorisait jusqu'ici que la lecture et la mise a jour)
drop policy if exists "Ajout saisie rapide factures_a_valider" on factures_a_valider;
create policy "Ajout saisie rapide factures_a_valider"
on factures_a_valider for insert
with check (
  statut = 'en_attente'
  and facture_id is null
  and chemin_relatif like 'saisie-rapide/%'
);
