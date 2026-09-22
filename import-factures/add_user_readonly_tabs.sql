-- Onglets en lecture seule pour un utilisateur donne : liste des ids d'onglet
-- (memes valeurs que visible_tabs, ex. 'workorders','locatif'...) sur
-- lesquels canEdit() renvoie false pour cet utilisateur, meme si son role
-- (technicien/admin) l'autorise a modifier ailleurs. Un role='lecteur'
-- reste global et prioritaire (deja gere cote code, pas besoin de colonne
-- supplementaire pour ce cas). Un role='admin' n'est jamais restreint.
alter table users add column if not exists readonly_tabs jsonb;
