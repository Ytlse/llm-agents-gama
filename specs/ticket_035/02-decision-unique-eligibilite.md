# Spec 02 — Une seule manière de décider : éligibilité et traçabilité (ticket 035, `D`)

## Problème

La règle qui dit quelles propositions une personne peut réellement emprunter (véhicule possédé,
garé sur place, permis, verrou de retour) vit aujourd'hui dans le contrôleur de simulation,
entrelacée avec la requête aux moteurs. Un mode sans simulateur qui la réimplémenterait créerait
deux logiques « comparables » : toute divergence serait un défaut invisible. De plus, une option
écartée ne laisse aujourd'hui qu'une valeur agrégée (`Contrainte de chaîne`) : on ne sait pas
**laquelle** a été écartée ni **pourquoi**.

## Utilisateurs

- **Les deux modes d'exécution** (specs 03 et 04) : uniques appelants de la décision. Ils fournissent
  la personne, l'état de ses véhicules, les propositions brutes et le contexte ; ils reçoivent la
  décision et sa trace.
- **L'analyste** : relit, pour toute décision archivée, ce qui a été présenté, écarté, et pourquoi.

## Règles métier

- **D1** — Il existe **une seule** fonction de décision, appelée à l'identique par les deux modes.
  Elle prend : la personne, l'état de ses véhicules (position de `bike` et `car`), les propositions
  brutes du déplacement, le contexte (date, météo, mémoire éventuelle, événement éventuel), le
  décideur et le gabarit. Elle rend : la proposition retenue, la distribution de probabilités par
  option, et la **trace** de D6.
- **D2** — **Filtrage à la décision.** Sont écartées, dans cet ordre et avec ce motif : une proposition
  d'un mode véhiculé que la personne **ne possède pas** (`non_possede`) ; une proposition voiture pour
  une personne qui ne peut **ni conduire ni être passagère** (`pas_de_conducteur`) ; une proposition
  d'un mode véhiculé dont le véhicule **n'est pas au point de départ** (`vehicule_ailleurs`), sauf
  passager ; sur un retour au domicile de plus de 1 km, toute proposition d'un autre mode que celui du
  véhicule garé au départ (`retour_force`). Les propositions marche et transports collectifs ne sont
  jamais écartées par ce filtre.
- **D3** — Le filtre reproduit **exactement** les règles documentées de la chaîne des véhicules
  (`docs/arch/vehicle-chain.md`) : possession testée en premier, âge et permis pour conduire, mode
  passager, seuil de 1 km du verrou de retour, orphelins ramenés au domicile. Toute évolution de ces
  règles se fait **dans la fonction unique**, jamais dans un mode.
- **D4** — **Chaîne de la journée.** Après la décision, la position des véhicules est mise à jour selon
  la proposition retenue (le véhicule utilisé suit la personne, les autres restent) et **cet état est
  l'entrée du déplacement suivant**. C'est la seule dépendance entre deux décisions d'une même personne.
- **D5** — Si le filtre ne laisse **aucune** proposition, la décision est « sans solution », tracée
  comme telle avec les motifs de chaque écart, et le décideur **n'est pas sollicité**. Si le filtre
  laisse **une seule** proposition, elle est retenue sans solliciter le décideur et la trace le dit.
- **D6** — **Trace de décision.** Toute décision archive : les propositions **présentées** (dans
  l'ordre présenté), les propositions **écartées** avec leur motif D2, la proposition **retenue**, la
  distribution rendue par le décideur, la réponse brute du décideur, et la **source** de chaque
  proposition (enregistrée / recalculée, voir spec 04). Une option absente de la présentation est
  toujours explicable par la trace.
- **D7** — **Ordre de présentation.** L'ordre des propositions présentées au décideur est une
  fonction déterministe d'une graine d'ordre déclarée par l'expérience et de l'identité du
  déplacement : même graine, même déplacement → même ordre, sur les deux modes. Le tirage final ne
  dépend pas de cet ordre.
- **D8** — **Égalité des modes vérifiable.** Pour toute entrée de D1, les deux modes produisent la
  **même** décision et la **même** trace. La vérification n'est pas postulée : elle s'appuie sur un
  décideur **déterministe** (heuristique de durée minimale) et sur un décideur **de rejeu** qui sert
  les réponses archivées d'une exécution antérieure, afin que le bruit d'un modèle de langage
  n'entre pas dans le test.
- **D9** *(déduite)* — Le décideur ne voit **jamais** la position des véhicules dans le texte : le
  filtre agit sur la liste, pas sur le prompt (choix mesuré du 2026-08-19, `llm-inference.md`).
- **D10** *(déduite)* — Une réponse du décideur inexploitable (vecteur vide, index hors bornes non
  réalignables) produit une décision tracée `repli_uniforme` qui **n'est jamais** considérée comme
  une décision du décideur : elle est comptée à part, exclue des comparaisons, et jamais resservie.
- **D11** *(déduite)* — La fonction de décision est **pure vis-à-vis du temps réel** : elle ne lit ni
  l'horloge du processus ni son fuseau. Toute heure vient de l'horloge simulée fournie en entrée.

## Critères d'acceptation

- **D1** — Les specs 03 et 04 appellent la même fonction ; un test statique vérifie qu'aucune autre
  implémentation du filtre n'existe hors d'elle.
- **D2** — Personne sans vélo → propositions vélo écartées `non_possede` ; mineur sans adulte au foyer →
  voiture écartée `pas_de_conducteur` ; voiture garée au travail, départ du domicile → `vehicule_ailleurs` ;
  retour au domicile de 3 km, vélo garé au départ → seules les propositions vélo restent, les autres
  `retour_force`. Marche et transports collectifs présents dans les quatre cas.
- **D3** — Les 73 tests existants de `test_vehicle_chain.py` passent **sur la fonction unique** sans
  modification de leurs attendus.
- **D4** — Séquence domicile → travail (voiture) → sport (marche) : au troisième déplacement, la
  voiture est au travail et écartée `vehicule_ailleurs`.
- **D5** — Toutes les propositions écartées → décision « sans solution », 0 sollicitation ; une seule
  restante → retenue, 0 sollicitation, trace `choix_unique`.
- **D6** — Pour une décision archivée, la trace contient les cinq éléments ; supprimer l'un d'eux
  rend l'archive invalide au chargement.
- **D7** — Graine 42, même déplacement, appelé depuis les deux modes → ordres identiques ; graine 43 →
  ordre différent ; la proposition retenue par le décideur de rejeu est la même dans les deux ordres.
- **D8** — Population de 100 personnes, jeu enregistré complet, mémoire coupée, décideur durée
  minimale : les deux modes rendent 100 % de décisions identiques ; même test avec le décideur de
  rejeu sur une exécution archivée : 100 % identiques.
- **D9** — Le texte rendu au décideur ne contient aucune mention de position de véhicule.
- **D10** — Réponse `[]` du décideur → trace `repli_uniforme`, compteur dédié incrémenté, ligne exclue
  des parts modales, absente de toute mémoire de réutilisation.
- **D11** — Exécuter la fonction sous `TZ=UTC` puis `TZ=Europe/Paris` → traces identiques.

## Non-goals

- Pas de changement des règles métier de la chaîne des véhicules (seuil 1 km, âge 18, orphelins).
- Pas de modélisation du partage de voiture au sein d'un ménage ni du park-and-ride.
- Pas de décision « par boucle » (tournée domicile → domicile) : le grain reste le déplacement.
- Pas de modification du gabarit de prompt ni du schéma de réponse.

## Sécurité

- La réponse du décideur (modèle de langage) est une **entrée hostile** : parsée strictement, jamais
  interprétée comme instruction ; les textes de justification sont archivés tels quels et **échappés**
  à l'affichage.
- Le contexte injecté (article de presse, événement) est du contenu, pas une consigne ; sa provenance
  est tracée dans la décision.
- Aucun attribut du persona n'est journalisé hors de la trace de décision archivée.

## Questions ouvertes

*Aucune propre à cette spec.* Les points du ticket qui la touchent (unité de sollicitation,
regroupement) sont portés par la spec 03 ; D1 est indifférente à la réponse tant que la trace D6 est
produite **par décision**.
