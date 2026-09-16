-- Simplification Outils/Consommables/Rangements : les rangements
-- (magasins : Cave, Garage...) sont desormais rattaches a un bien, et
-- outils/consommables gardent un detail fin (etagere, rang...) separe du
-- nom du rangement lui-meme, pour pouvoir consolider plusieurs anciens
-- emplacements "Etagere N / rang M" en un seul magasin reel.
alter table rangements add column if not exists bien text;
alter table tools add column if not exists location_detail text;
alter table consommables add column if not exists location_detail text;
