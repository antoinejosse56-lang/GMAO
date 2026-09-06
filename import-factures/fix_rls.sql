-- Complement a setup.sql : la table factures_a_valider a RLS activee par defaut
-- (contrairement aux autres tables du GMAO), ce qui bloquait sa lecture par la cle
-- anon (le navigateur voyait 0 ligne alors que le script service_role en voit 5).
--
-- Le script d'import (cle service_role) contourne deja RLS pour ecrire - ces policies
-- ne concernent que ce que le GMAO (navigateur, cle anon) a besoin de faire :
-- lire la liste, et mettre a jour le statut/les champs corriges a la validation/rejet.

drop policy if exists "Lecture publique factures_a_valider" on factures_a_valider;
create policy "Lecture publique factures_a_valider"
on factures_a_valider for select
using (true);

drop policy if exists "Maj publique factures_a_valider" on factures_a_valider;
create policy "Maj publique factures_a_valider"
on factures_a_valider for update
using (true) with check (true);
