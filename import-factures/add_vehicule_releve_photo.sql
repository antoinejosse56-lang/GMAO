-- Photo optionnelle jointe a un releve vehicule (ex: photo du compteur de la
-- pompe a essence au moment d'un plein, pour preuve/reference rapide).
alter table vehicule_releves add column if not exists photo_url text;
