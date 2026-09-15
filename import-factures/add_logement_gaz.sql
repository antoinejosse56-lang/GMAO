-- Indique si le logement dispose d'une installation gaz - permet d'exclure
-- automatiquement le diagnostic gaz des documents obligatoires quand ce
-- n'est pas le cas (frequent), sans avoir a le justifier a chaque bail via
-- le contournement manuel.
alter table logement_fiches add column if not exists gaz_present boolean;
