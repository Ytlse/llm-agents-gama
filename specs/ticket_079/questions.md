# Questions vivantes — ticket 078 (chocs déclarés)

**TRANCHÉES le 2026-09-15, et appliquées dans le code livré.** Les hypothèses ci-dessous ont été
retenues telles quelles ; chacune est vérifiée par au moins un test du contrat
(`specs/ticket_079/tests.md`). Elles restent amendables : c'est une décision, pas un dogme.

## Q1 — Le régime anticipé, jamais ou plus tard ?
Ce ticket ne livre que le **choc subi** : l'agent décide sous information nominale, puis subit. Une
grève annoncée, où il choisit en connaissant la dégradation, demande de couper l'offre dans le
calculateur d'itinéraires plus une garde de cache.
**Hypothèse :** plus tard, ticket séparé ; la limite est écrite dans l'article (le manuscrit § 5.3
exige « le même événement déclaré deux fois », le régime subi ne le déclare qu'une fois).

## Q2 — Le retard injecté décale-t-il les activités suivantes ?
**Hypothèse :** non — on garde `reschedule_activity_departure_time: false` et on le déclare.
**Alternative :** l'activer les seuls jours de choc ; la journée serait réellement désorganisée,
mais le run divergerait de son homologue nominal par autre chose que la mémoire, ce qui brouille
l'imputation.

## Q3 — Le cache de décisions pendant une campagne à choc
**Hypothèse :** coupé (il sert 0 % en régime nominal, 297 miss `no_candidates` sur 314).
**Alternative :** porter la signature du choc dans `extra_key`, champ qui existe et que
l'anticipation du ticket 014 utilise déjà.

## Q4 — Les valeurs des cinq cas
Retards, textes et durées sont des propositions.
**Hypothèse :** assumées comme scénario déclaré, source citée en regard quand elle existe (Zhu et
al. 2010 pour la rupture d'infrastructure, van Exel & Rietveld 2001 pour les grèves).
**Alternative :** les ancrer sur des élasticités publiées, au prix d'un travail de sourçage.

## Q5 — Un choc peut-il toucher un agent qui n'a pas utilisé le mode ?
Le bouchon retarde-t-il aussi le bus pris dans le même trafic ?
**Hypothèse :** non au premier lot — une règle d'exposition par mode, et rien de plus.

## Q6 *(ajoutée)* — Où vivent les traces du choc
Le lot E du ticket 077 instrumente la mémoire mais ne dit rien du choc. Deux voies : ce ticket porte
ses propres colonnes, ou une ligne s'ajoute au lot E du 077.
**Hypothèse :** ce ticket les porte, le 077 étant déjà en cours dans une autre session.

---

## Ce que l'implémentation a tranché en plus

## Q7 *(apparue en codant)* — Le retard sature à 30 minutes
`memoire__retard_ref_s` vaut 1 800 s : au-delà, la composante de retard vaut 0,50 quoi qu'on
déclare. Un profil décroissant 60/40/25 donnait donc la **même gravité** les jours 1 et 2.
**Tranché :** `c1` enjambe le seuil (60/25/12), et la doc en fait le premier piège de toute nouvelle
déclaration. **À rouvrir si** un scénario a besoin de distinguer deux retards au-dessus de 30 min :
il faudrait alors relever `RETARD_REF`, ce qui déplacerait toute l'échelle de gravité et rendrait
les runs antérieurs non comparables.

## Q8 *(apparue en codant)* — Tous les chocs ne franchissent pas le seuil
L'orage plafonne à 0,45, le troisième jour de bouchon à 0,37 : leur souvenir n'entre pas au vivier
des chocs et n'est donc pas repêché hors contexte.
**Tranché :** c'est une **gradation voulue**, pas un défaut. Un orage n'est pas une panne de réseau.
Le souvenir vit tout de même trois à quatre fois plus longtemps qu'un trajet banal et remonte par le
mode concerné. **À dire dans l'article** si une courbe d'hystérésis est publiée sur `c5`.

## Q9 *(reportée)* — Rendre un mode réellement indisponible
`c2` déclare le vélo immobilisé le lendemain, mais seul le souvenir le porte : le vélo reste offert.
**Non tranché, hors de ce lot :** l'indisponibilité passe par le filtre d'éligibilité, partagé avec
la plateforme d'expériences, et la toucher dépasse le périmètre d'un mécanisme de choc.
