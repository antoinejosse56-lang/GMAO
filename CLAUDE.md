## Fichiers du projet — statut réel (vérifié le 20/08/2026)
- index.html — app principale, monolithe actif, mis à jour régulièrement
- gestion.html — raccourci mobile PIN "Loyer & Meublé" (code 2110), UTILISÉ
  QUOTIDIENNEMENT sur téléphone. Écrit dans rent_payments et reservations,
  en version simplifiée par rapport à index.html.
- saisie.html — raccourci mobile PIN "Saisie Crèche/École" (code 2110), UTILISÉ
  QUOTIDIENNEMENT sur téléphone. Écrit dans creche_saisies et ecole_saisies,
  en version simplifiée par rapport à index.html.
- index.html.txt — ancienne version (v104), non référencée nulle part,
  obsolète, à laisser de côté (pas de suppression pour l'instant)

## RÈGLE CRITIQUE — tables partagées entre 3 fichiers
gestion.html et saisie.html écrivent dans EXACTEMENT les mêmes tables
Supabase que les modules correspondants d'index.html (rent_payments,
reservations, creche_saisies, ecole_saisies), mais avec une logique
plus simple/partielle. Ce sont deux applications séparées actives en
production, pas du code mort.

Avant toute modification touchant une de ces 4 tables (schéma, noms de
champs, valeurs calculées, contraintes) dans index.html, vérifier l'impact
sur gestion.html et saisie.html et le signaler explicitement.
