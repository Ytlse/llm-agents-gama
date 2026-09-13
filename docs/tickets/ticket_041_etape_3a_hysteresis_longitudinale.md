# Ticket 041 — Étape 3a longitudinale : habitudes, choc, récupération (GAMA offline, 5 à 60 jours)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Le plan détaillé est
> [`docs/paper/methode/experience_plan/ETAPE_3A_PLAN_LONGITUDINAL.md`](../paper/experience_plan/ETAPE_3A_PLAN_LONGITUDINAL.md) ;
> les questions ouvertes sont dans [`specs/ticket_041/questions.md`](../../specs/ticket_041/questions.md).
>
> **État au 2026-09-09 : plan v0.1 rédigé, en attente de validation (porte G0). Aucun code.**

## Ce que l'utilisateur doit pouvoir faire

1. Jouer la même cohorte scellée (100 à 200 agents, sous-échantillon par ménages entiers de
   `population_1000_AAMAS_v5`) dans GAMA en mode offline sur **trois bras** — LLM + mémoire, LLM
   amnésique, oracle LightGBM — avec les mêmes graines, la même météo, la même offre et le même
   calendrier, sur 5 à 60 jours ouvrés simulés.
2. Déclarer un **incident** (panne métro, grève, rocade coupée, chute de vélo individuelle,
   placebo, incitation positive…) à un jour et une heure, **deux fois** : dans le graphe (offre,
   durées) et en langue (observations vécues), et savoir pour chaque agent s'il y a été exposé.
3. **Mettre en pause et reprendre** à tout moment sans perdre de souvenirs ni redemander une
   décision archivée ; obtenir le même résultat final qu'une exécution ininterrompue.
4. Retrouver, pour chaque décision, la distribution émise, le mode tiré, les souvenirs
   présentés, la justification, le coût ; pour chaque jour, un instantané de la mémoire.
5. Estimer avant de lancer, depuis les quotas réels de `providers.yaml`, le nombre de jours de
   campagne nécessaires pour N agents, D jours et un jeu de bras.
6. Comparer les bras sur des métriques pré-enregistrées (resserrement de la distribution,
   taux de changement journalier, évitement à J+1, demi-vie et part permanente du retour,
   spécificité placebo / non exposés) avec IC par bootstrap par agent et tests appariés.
7. Ajouter des variantes de mémoire (importance, oubli avec renforcement, registre d'habitudes,
   réflexion périodique) comme bras supplémentaires, sans toucher au bras de référence.

## Pourquoi maintenant

Le manuscrit (§5.1) et les fiches `exp_04a…d` décrivent une expérience de 5 jours dont aucun
mécanisme n'existe : pas d'événement joué, oracle non branché dans GAMA, multi-jours configuré
à 1 jour, mémoire à demi-vie de 1,9 jour incapable de porter une habitude, formule γ/λ sans
correspondance dans le code. Le plan remet ces pièces en ordre et étend l'horizon à deux mois
pour mesurer la formation d'habitudes, pas seulement la réaction.

## Lots (détail et dépendances dans le plan §8)

| Lot | Contenu | Taille |
|---|---|---|
| L0 | Pilote sans code : 100 agents, 5 jours, mémoire active — coefficients de coût, jour de stabilisation, part exposée | 2 j |
| L1 | Multi-jours robuste : calendrier ouvré, post-traitements par jour, pause/reprise invariante, décideur épinglé, cache exact, nettoyage LTM corrigé | S |
| L2 | Événements : format étendu, injection contrôleur → GAMA, exposition tracée, période avant/pendant/après | M |
| L3 | Oracle LightGBM dans le chemin GAMA | S |
| L4 | Collecte : souvenirs présentés, panel parquet, instantanés LTM, audit mémoire, codage des justifications | M |
| L5 | Simulateur de coût `scripts/AAMAS/simulateur_cout_longitudinal.py` | S |
| L6–L8 | Campagne, analyse, rédaction | — |

## Hors périmètre

- La calibration du prompt (ticket 004/009) : le prompt est gelé pour toute la campagne.
- L'Étape 3b (articles de presse) : seul le bras optionnel M-news y touche.
- Toute modification du bras de référence M en cours de campagne.
