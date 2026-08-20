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

## Comportements connus / limitations documentées (audit du 20/08/2026)

### creche_saisies — minutes_sup peut devenir périmé
saisie.html fait un PATCH partiel qui ne touche jamais heure_contrat_dep,
heure_contrat_rec ni minutes_sup (absentes du payload envoyé, donc jamais
écrasées par PostgREST). Mais si depose_anticipee/recuperation_tardive sont
modifiées via saisie.html, minutes_sup (calculé par index.html à partir de
ces heures + heures de contrat) n'est PAS recalculé automatiquement. La
valeur reste périmée tant qu'on ne repasse pas par index.html pour ce jour.

### ecole_saisies — peri_matin/soir_dep/fin toujours nuls
Ces 4 colonnes sont mises à null aussi bien par index.html (saveEcoleAll)
que par saisie.html à chaque sauvegarde — comportement cohérent entre les
deux fichiers, pas une divergence. Semblent être des champs legacy non
utilisés.

## RÉSOLU — colonnes part_caf / part_locataire dans rent_payments
Vérifié le 20/08/2026 : part_caf et part_locataire n'apparaissent dans
AUCUN des 3 fichiers (index.html, gestion.html, saisie.html), ni en lecture
ni en écriture. caf et locataire_part sont utilisés partout de façon
cohérente entre index.html et gestion.html. Conclusion : part_caf et
part_locataire sont des colonnes mortes dans le schéma Supabase (confirmées
présentes en base par une requête SQL directe), sans lien avec les
régressions passées. Aucune action requise.
