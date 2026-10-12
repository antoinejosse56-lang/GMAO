-- Consommation "plein a plein" des vehicules : distingue un plein complet (reservoir rempli a ras)
-- d'un appoint. Les litres d'un appoint sont comptes dans le plein complet suivant pour le calcul
-- de la consommation moyenne affichee sur la page du vehicule. Par defaut tout plein est "complet".
alter table vehicule_releves add column if not exists plein_complet boolean not null default true;
