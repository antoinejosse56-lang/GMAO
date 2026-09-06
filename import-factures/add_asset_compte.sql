-- Compte (savadur/perso) explicite sur chaque equipement, pour ne plus deviner
-- via le nom/emplacement (dubailFilter) lors de la validation d'une facture liee
-- a un equipement sans bien associe (ex: EVOK, vehicule perso sans "Dubail" dans
-- le nom, mais la deduction automatique peut se tromper sur d'autres cas).
-- NULL = non renseigne, l'app retombe sur la deduction automatique existante.

alter table assets add column if not exists compte text check (compte in ('savadur','perso'));
