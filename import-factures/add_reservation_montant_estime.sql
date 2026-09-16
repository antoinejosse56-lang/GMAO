-- Marque les reservations dont le "Versement hote" (montant_total) et/ou le
-- "Frais resa" ont ete completes automatiquement par l'app (commission
-- Booking.com moyenne estimee, faute de valeur reelle remontee par Lodgify)
-- plutot que fournis par la plateforme ou saisis manuellement - permet de les
-- distinguer visuellement (a verifier) des montants reels.
alter table reservations add column if not exists montant_estime boolean default false;
