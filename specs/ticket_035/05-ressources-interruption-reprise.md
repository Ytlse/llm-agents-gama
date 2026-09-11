# Spec 05 — Ressources, interruption, reprise (ticket 035, `Q`)

## Problème

Quand un quota est épuisé, la passerelle écarte le fournisseur et **cascade** vers un autre modèle :
l'expérience finit, mais avec un autre décideur que celui demandé, sans que le résultat le dise
clairement. Quand l'utilisateur arrête, la reprise rejoue la journée et compte sur un cache technique
pour ne pas repayer. Il faut voir les quotas, s'arrêter proprement quand ils manquent, ne jamais
substituer, et reprendre sans redemander une décision déjà obtenue.

## Utilisateurs

- **Le chercheur** : surveille, met en pause, reprend, arrête. Seul détenteur des clés d'API.
- **Les deux modes d'exécution** (specs 03 et 04) : soumis aux mêmes règles.
- **Le registre** (spec 06) : affiche l'état (en cours, en pause, épuisée, arrêtée) et sa raison.

## Règles métier

- **Q1** — **Surveillance.** Pendant l'exécution, l'utilisateur voit, pour chaque instance de décideur
  sollicitée : requêtes et jetons consommés dans la fenêtre du jour, limites déclarées, marge restante,
  requêtes par minute observées, erreurs de quota (429) et refus de crédit (402). Ces valeurs viennent
  de la passerelle et de sa configuration, jamais d'une constante de la plateforme.
- **Q2** — **Décideur épinglé.** Une expérience désigne son décideur par **modèle + paramètres**
  (température, graine, gabarit). Une instance de passerelle n'est qu'une **ressource** (une clé, un
  quota). L'exécution ne sollicite que des instances qui servent **exactement** ce modèle avec ces
  paramètres ; changer de clé pour le même modèle n'est pas une substitution, changer de modèle l'est.
- **Q3** — **Aucune substitution silencieuse.** Si aucune instance du décideur épinglé n'est
  disponible, l'exécution **attend** ou **s'arrête** (Q4) ; elle ne bascule jamais vers un autre
  modèle, ne réduit jamais la liste présentée, ne change jamais de gabarit, ne relâche jamais un
  paramètre. Toute bascule de la passerelle vers un autre modèle est **refusée** par l'exécution et
  comptée `substitution_refusee`.
- **Q4** — **Arrêt propre sur épuisement.** Quand toutes les instances du décideur sont épuisées ou
  en refus de crédit, l'exécution : cesse d'émettre de nouvelles sollicitations ; attend les
  sollicitations en vol pendant une durée bornée ; archive ce qui est acquis ; passe à l'état
  **épuisée** avec la raison (instance, limite atteinte) et **l'heure de reprise possible** (fin de la
  fenêtre de quota) ; et le dit dans le journal en ERROR avec de quoi agir.
- **Q5** — **Reprise sans double dépense.** À la reprise (après pause, épuisement, panne ou arrêt de la
  machine), toute décision **déjà archivée** dans le résultat de l'exécution est **resservie depuis
  l'archive** ; le décideur n'est sollicité que pour les décisions absentes. Cette règle ne dépend
  d'**aucune** mémoire technique interne (cache sémantique ou autre) : le résultat de l'exécution est
  la seule source.
- **Q6** — **Résultat final invariant.** Une exécution interrompue puis reprise, quel que soit le
  nombre d'interruptions, produit le même résultat final qu'une exécution ininterrompue (au bruit du
  décideur près, mesuré avec le décideur de rejeu), et le résultat porte l'historique des
  interruptions (instant, cause, durée d'arrêt).
- **Q7** — **Pause manuelle.** L'utilisateur suspend à tout moment ; l'exécution atteint un point sûr
  (aucune décision à moitié archivée), écrit son état **atomiquement**, et passe à l'état **en pause**.
  L'arrêt de la machine pendant la pause ne perd rien. La pause est **effective en quelques
  secondes** : passé un **délai de grâce** (`EXP_PAUSE_GRACE_S`, 15 s), les sollicitations encore en
  vol sont abandonnées — leurs déplacements, non archivés, seront redemandés à la reprise
  (révision du 2026-09-08, décision 1 ci-dessous).
- **Q7bis** *(2026-09-08)* — **Pause automatique sur inactivité.** Au-delà de
  `EXP_INACTIVITE_PAUSE_S` (7 min par défaut, `0` désactive) sans **aucun** déplacement réglé —
  décidé, resservi, non couvert, inexploitable, sans solution — l'exécution lève une `[ALARME]`
  nommant ce qu'elle attendait et se met **en pause** d'elle-même, reprenable. L'attente de la
  fenêtre de quota (R4) en est exclue : cette immobilité est demandée.
- **Q8** — **Arrêt définitif.** L'utilisateur arrête ; l'exécution clôt ses journaux, archive ce qui
  est acquis, passe à l'état **arrêtée** et **ne reprend pas** ; le résultat partiel reste exploitable
  et identifié comme partiel (spec 06).
- **Q9** *(déduite)* — **Écriture atomique.** Une décision est archivée entièrement ou pas du tout ;
  une interruption brutale (coupure) ne laisse jamais une trace partielle. Au chargement, une archive
  dont la dernière entrée est tronquée est réparée en **écartant** cette entrée, avec un WARNING qui la
  nomme.
- **Q10** *(déduite, révisée 2026-09-07)* — **Attente visible, jamais un saut.** Une erreur
  **transitoire** (passerelle occupée, timeout, réseau) est réessayée **indéfiniment** — aucun
  déplacement n'est jamais sauté (R1) : pause croissante plafonnée (60 s), interruptible par
  pause/arrêt/signal (le déplacement non archivé est repris tel quel). `attente_max_s` **ne borne
  plus** l'attente ; c'est un **seuil d'alarme** : au-delà, une `[ALARME]` est levée sur front
  montant (une par déplacement) et `progression.json` expose le déplacement en attente et depuis
  combien de temps. Un journal silencieux n'est jamais un état acceptable ; un déplacement sauté
  sans trace non plus. (Seul un épuisement de quota **confirmé** arrête — Q4 — ou fait attendre la
  fenêtre — R4 ci-dessous.)
- **R1/R2/R3** *(2026-09-07)* — **Classement juste et traçabilité.** `epuise` est réservé au quota
  (429) ou au crédit (402) **confirmé** (par le message ET le moniteur) ; « saturés / indisponibles
  / timeout » est `passerelle_occupee`, transitoire. Chaque tentative ratée est archivée dans
  `erreurs.jsonl` (horodatage, person_id, activity_id, tentative, type, message échappé, fournisseur,
  attente) ; tout le journal va aussi dans `execution.log` ; la commande `experiences erreurs`
  rapproche `decisions.jsonl` du jeu (manquants, journées à trous, décisions après un trou). Une
  exécution rouverte alors qu'elle était restée `en_cours` consigne une interruption `arret_force`.
- **R4** *(2026-09-07, `--attendre-fenetre`)* — **Attente de la fenêtre quota en process.** Sur
  épuisement confirmé, l'exécution peut, au lieu de passer `epuisee`, **dormir jusqu'à
  `reprise_possible_a`** (état `en_attente_quota`, in-process, non final), rafraîchir le moniteur,
  puis repartir seule et retenter le déplacement. Aucune substitution, aucune décision par défaut.
- **Q11** *(déduite)* — **Épuisement anticipé.** Avant chaque lot, si la marge restante d'une instance
  est inférieure au coût du lot, le lot n'est pas soumis à cette instance ; s'il ne reste aucune
  instance, Q4 s'applique **avant** le premier 429.
- **Q12** *(déduite)* — **Un décideur local ne s'épuise pas.** Heuristique et modèle supervisé
  n'ont ni quota ni fenêtre ; les règles Q1 à Q4 leur sont inapplicables et l'affichage le dit
  (« sans quota »), au lieu d'afficher 0 / 0.

## Critères d'acceptation

- **Q1** — Pendant une exécution sur `google_gemini31_key1` : l'affichage donne requêtes/jour consommées,
  limite, marge, RPM observé, 429 et 402 ; modifier la limite dans la configuration de la passerelle
  change l'affichage sans toucher à la plateforme.
- **Q2** — Décideur « gemini-3.1-flash-lite, T=0, graine 42 » : les instances `google_gemini31_key1` et
  `google_gemini31_key2` sont toutes deux sollicitées ; `google_gemini35_key1` (autre modèle) jamais.
- **Q3** — Simuler l'épuisement des deux instances → aucune sollicitation vers `mistral` ; compteur
  `substitution_refusee` = 0 si la passerelle n'a rien proposé, > 0 si elle a tenté ; l'exécution
  passe à « épuisée ».
- **Q4** — Épuisement à 14 h 20 UTC → état « épuisée », raison « `google_gemini31_key2` : 500/500 requêtes/jour »,
  reprise possible « 00:00 UTC » ; ligne ERROR contenant instance, limite, heure de reprise.
- **Q5** — Reprendre une exécution à 1 300 décisions archivées → 0 sollicitation pour ces 1 300 ; le
  cache sémantique **désactivé** ne change rien à ce compte.
- **Q6** — Interrompre trois fois (pause, épuisement simulé, coupure) puis reprendre → résultat final
  identique à l'exécution ininterrompue (décideur de rejeu) ; historique à trois entrées.
- **Q7** — Pause pendant un lot en vol → l'état n'est écrit qu'après le retour ou l'abandon tracé du
  lot ; tuer le processus pendant la pause puis relire → état valide.
- **Q8** — Arrêt à 60 % → état « arrêtée », résultat partiel lisible, aucune reprise proposée.
- **Q9** — Tronquer la dernière ligne de l'archive → chargement réussi, WARNING nommant l'entrée
  écartée, reprise la redemande.
- **Q10** — Ressource indisponible au-delà de la durée déclarée → passage à « épuisée » avec raison
  « attente dépassée », pas de processus muet.
- **Q11** — Marge 7 requêtes, lot suivant = 10 sollicitations → lot non soumis, aucun 429 émis,
  état « épuisée » motivé par l'anticipation.
- **Q12** — Décideur « durée minimale » → panneau « sans quota », aucune règle d'épuisement évaluée.

## Non-goals

- Pas de gestion des clés d'API par la plateforme : elles restent dans l'environnement du chercheur.
- Pas de file d'attente multi-expériences ni de planification de reprise automatique à minuit
  (la reprise est un geste de l'utilisateur ; l'heure de reprise possible est **affichée**).
- Pas de repli dégradé d'aucune sorte (RG-2).

## Sécurité

- Les clés d'API n'apparaissent **jamais** dans un journal, un état de pause, un résultat ou un
  affichage ; les instances sont désignées par nom.
- Un état de pause relu est une entrée hostile : empreintes vérifiées, schéma validé, refus si
  incohérent.
- Les messages d'erreur des fournisseurs sont archivés tels quels mais **échappés** à l'affichage.

## Décisions (2026-09-07)

1. **Sollicitations en vol à la pause** *(révisée le 2026-09-08)* : la pause reste prise à un
   **point sûr**, entre deux déplacements d'une personne, mais elle n'attend plus indéfiniment le
   retour d'une sollicitation en cours. Elle lui laisse un **délai de grâce** (`EXP_PAUSE_GRACE_S`,
   15 s) — assez pour qu'un appel normal revienne et soit archivé, donc jamais repayé — puis
   **abandonne** ce qui traîne. Le déplacement non décidé reste non archivé, donc redemandé à la
   reprise : rien n'est sauté, rien n'est fabriqué, le résultat final ne change pas (Q6).
   *Pourquoi la révision* : la version d'origine attendait le retour de l'appel, soit jusqu'au
   timeout de poll de la passerelle (`remote_llm_poll_timeout`, 120 s). Une pause pouvait donc
   devenir effective **deux minutes** après le clic. Le seul coût de l'abandon est monétaire, et
   borné par le parallélisme : au pire `parallelisme` sollicitations payées et jetées.
2. **`attente_max_s`** n'est plus une **durée bornée d'attente** mais un **seuil d'alarme** (Q10
   révisée, décision a) : l'attente d'une erreur transitoire est illimitée (pause croissante
   plafonnée, interruptible) ; `attente_max_s` reste un champ par expérience et déclenche l'`[ALARME]`.
