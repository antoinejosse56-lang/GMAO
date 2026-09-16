-- Permet a un rangement (magasin, ex: Cave) d'avoir des sous-emplacements
-- (etageres, ex: "Etagere 1 / rang 0"), chacun restant un rangement a part
-- entiere (donc toujours assignable directement a un outil/consommable et
-- toujours dote de sa propre etiquette QR imprimable) - corrige la
-- consolidation trop agressive de la migration precedente qui avait
-- transforme chaque etagere en simple texte sur "Cave" au lieu de les
-- garder comme emplacements distincts.
alter table rangements add column if not exists parent_id uuid references rangements(id);
