# Spec 04 — Simulation sur jeu enregistré (ticket 035, `G`)

## Problème

La simulation calcule ses itinéraires en vol, à chaque déplacement, y compris quand rien n'a changé
depuis la veille. Elle doit pouvoir démarrer sur une population dont les déplacements sont
enregistrés, servir les propositions depuis ce jeu, ne recalculer que quand l'offre ou l'heure a
réellement changé, et le prouver. Elle doit aussi rester lançable par le chemin habituel, et pouvoir
être suspendue puis reprise sans rejouer la journée.

## Utilisateurs

- **Le chercheur** : lance via la plateforme ou via `make run`, suit, met en pause, reprend, arrête.
- **La simulation GAMA** et **le contrôleur** : consommateurs du jeu, appelants de la décision unique.
- **L'analyste** : vérifie après coup que le régime nominal n'a rien recalculé, et pourquoi chaque
  recalcul a eu lieu.

## Règles métier

- **G1** — La simulation peut être lancée sur une population **et** un jeu enregistré (spec 01). Le
  lancement vérifie que l'empreinte de population du jeu est celle de la population chargée ; sinon
  **refus** avant démarrage, avec les deux empreintes.
- **G2** — **Chemin habituel.** `make run` (avec ou sans `OFFLINE=1`) accepte la désignation d'un jeu
  enregistré. Sans jeu désigné, le comportement actuel est **inchangé** (calcul en vol). La plateforme
  n'est jamais un passage obligé.
- **G3** — **Régime nominal.** Quand le jeu couvre un déplacement, ses propositions sont servies
  **depuis le jeu** et la décision unique (spec 02) s'applique ; **aucun** moteur de routage n'est
  appelé. Le résultat compte les appels aux moteurs, par moteur ; en régime nominal ce compte est **0**
  et le compte rendu de fin l'affiche.
- **G4** — **Recalcul sous deux conditions, et seulement là.** Un appel aux moteurs pendant la
  simulation n'est légitime que si : (a) **l'offre a changé** — un événement déclaré par l'expérience
  (incident, fermeture, dégradation) touche une ligne, un tronçon ou une zone que la proposition
  enregistrée emprunte, pour un départ postérieur au début de l'événement ; ou (b) **l'heure réelle de
  départ s'est écartée** de l'heure de référence de la proposition au-delà de la tolérance du mode (G5).
  Tout autre appel est un **défaut** : tracé en ERROR avec le déplacement concerné, et compté à part.
- **G5** — **Tolérance horaire par mode.** Chaque mode déclare sa sensibilité à l'heure : *insensible*
  (aucun recalcul quel que soit l'écart), *à l'heure* (recalcul si l'écart change d'heure pleine), *au
  pas* (recalcul si l'écart dépasse un pas déclaré). Les valeurs sont **déclarées** dans la
  configuration de l'expérience et **archivées** avec le résultat ; défauts proposés, à valider
  (question 1) : marche et vélo insensibles, voiture à l'heure (tables de congestion horaires),
  transports collectifs et train au pas de 10 minutes.
- **G6** — **Un recalcul est attribué.** Toute proposition présentée porte sa source : `enregistrée`,
  `recalculée:offre` (avec l'identifiant de l'événement) ou `recalculée:horaire` (avec l'écart en
  minutes et la tolérance). Le résultat totalise les trois et l'analyste retrouve chaque recalcul.
- **G7** *(déduite)* — **Aucun recalcul stérile.** Si un recalcul horaire rend des propositions
  identiques aux enregistrées (mêmes modes, mêmes durées à la minute), l'écart est compté
  `recalcul_sans_effet`. Une ALARME à front montant se lève si cette part dépasse un seuil déclaré :
  c'est le signe que G5 est trop sensible. Symétriquement, un déclencheur qui ne s'est **jamais**
  déclenché sur toute une exécution est signalé dans le compte rendu (fonction fantôme, EF-44).
- **G8** — **Mémoire.** L'expérience active ou coupe la mémoire des agents ; avec la mémoire active,
  les souvenirs d'un jour entrent dans le contexte de la décision unique les jours suivants, et la
  trace de chaque décision dit **quels souvenirs** ont été présentés.
- **G9** — **Événements.** L'expérience peut porter un incident de réseau ou une information extérieure,
  à un jour et une heure donnés. Toute décision est datée par rapport à l'événement (`avant`, `pendant`,
  `après`) dans la trace, et le résultat sépare les trois périodes.
- **G10** — **Pause à chaud.** L'utilisateur suspend une simulation en cours ; la reprise ne rejoue
  **aucune décision archivée**, les agents reprennent où ils étaient et leur mémoire est conservée. Ce
  qui est sauvegardé exactement et le point de reprise dépendent des questions 2 et 3, **mais** quelle
  que soit la granularité : les décisions déjà archivées ne sont **jamais** redemandées (spec 05, Q5).
- **G11** — **Arrêt propre.** L'arrêt définitif clôt les journaux, produit un résultat partiel
  exploitable, et le registre le marque « arrêtée » avec la couverture atteinte.
- **G12** — **Égalité des modes.** Mémoire coupée, sans événement, sur un jeu complet, et pour tout
  déplacement dont le départ réel reste dans la tolérance G5, la décision prise en simulation est
  **identique** à celle du mode sans simulateur (spec 02, D8). Les déplacements hors tolérance sont
  listés séparément dans la comparaison.
- **G13** *(déduite)* — La simulation **n'écrit jamais** dans le jeu enregistré, y compris ses
  recalculs : ceux-ci vivent dans le résultat de l'exécution.
- **G14** *(déduite)* — Le compte rendu de fin (`make report`) affiche : appels moteurs par moteur,
  propositions par source (G6), recalculs sans effet (G7), déclencheurs jamais déclenchés, couverture.

## Critères d'acceptation

- **G1** — Jeu de la v4 avec population v5 → refus avant démarrage citant les deux empreintes.
- **G2** — `make run OFFLINE=1 JEU=<nom>` démarre sur le jeu ; `make run OFFLINE=1` sans `JEU` → même
  comportement qu'avant (appels moteurs > 0, aucune mention de jeu).
- **G3** — Une journée complète sur un jeu complet, sans événement → 0 appel OTP, 0 appel OSMnx dans le
  compte rendu ; le compteur de propositions `enregistrée` égale le nombre de propositions présentées.
- **G4** — Un appel moteur provoqué artificiellement hors des deux conditions → ligne ERROR avec
  l'identifiant du déplacement, compteur `recalcul_illegitime` = 1.
- **G5** — Départ prévu 8 h 00, réel 8 h 07 : marche/vélo/voiture servis du jeu, transports collectifs
  servis du jeu (< 10 min) ; réel 8 h 12 : transports collectifs recalculés, voiture servie ; réel
  9 h 02 : voiture recalculée aussi. Les tolérances sont relues depuis l'archive du résultat.
- **G6** — Incident déclaré métro ligne A à J2 17 h → une décision à J2 18 h dont une proposition
  empruntait la ligne A porte `recalculée:offre (metro_line_a)` ; à J2 16 h, `enregistrée`.
- **G7** — Recalcul horaire rendant les mêmes propositions → `recalcul_sans_effet` +1 ; 30 % de
  recalculs sans effet au-dessus du seuil → une ALARME ; exécution sans aucun événement ni écart →
  le compte rendu liste les deux déclencheurs comme « jamais déclenchés ».
- **G8** — 5 jours, mémoire active → une décision de J3 dont la trace cite les souvenirs présentés ;
  mémoire coupée → trace sans souvenir et 0 lecture de mémoire.
- **G9** — Incident J2 17 h → chaque décision porte `avant`/`pendant`/`après` ; la synthèse rend trois
  blocs de parts modales.
- **G10** — Pause à J2 14 h puis reprise → 0 sollicitation du décideur pour les décisions archivées
  avant la pause ; les positions des agents et leurs souvenirs à la reprise sont ceux de la pause.
- **G11** — Arrêt à 60 % → résultat lisible, registre « arrêtée · 60 % », rien n'est redemandé si l'on
  ne reprend pas.
- **G12** — 100 personnes, décideur de rejeu, mémoire coupée → décisions identiques entre modes sur tous
  les déplacements dans la tolérance ; les autres apparaissent dans une liste « hors tolérance ».
- **G13** — Empreinte du jeu avant et après une simulation avec recalculs → identique.
- **G14** — `make report` sur l'exécution → les cinq rubriques présentes, chiffrées.

## Non-goals

- Pas de discussion entre agents (perspective, hors exigence).
- Pas de modification du moteur physique de GAMA (congestion, attente, téléportation à 30 min).
- Pas de recalcul « préventif » pour améliorer la qualité des propositions.
- Pas d'interface GAMA nouvelle : les commandes passent par le protocole GAMA Server existant.

## Sécurité

- Un événement déclaré (article de presse, incident) est du **contenu** injecté dans le prompt ; sa
  provenance est archivée, son texte échappé à l'affichage.
- Un état de pause est une entrée hostile à la reprise : validé (empreintes de l'expérience, du jeu,
  de la population) avant d'être chargé ; un état incohérent est refusé, jamais « réparé ».
- Aucun secret dans l'état de pause ni dans le compte rendu.

## Questions ouvertes

1. **Seuils de G5** : les défauts proposés (insensible / heure pleine / 10 minutes) conviennent-ils ?
   Le pas de 10 minutes reprend la tranche du cache actuel ; l'heure pleine reprend les tables de
   congestion. À valider ou corriger avant d'écrire le test G5.
2. **Granularité de la reprise** (ticket §7.4) : à l'instant exact de l'interruption, ou au début de
   la journée en cours ? La seconde exige seulement que les décisions archivées soient resservies
   (G10 le garantit) ; la première exige de sauver l'état de GAMA (positions, véhicules en circulation),
   ce que GAMA ne fait pas aujourd'hui (ticket 002).
3. **Ce que « à chaud » recouvre** (ticket §7.5) : positions, mémoire, décisions acquises,
   sollicitations en vol — les sollicitations en vol au moment de la pause sont-elles attendues,
   abandonnées (et repayées) ou archivées à leur retour ?
4. **Propositions du lendemain** (spec 01, question 3) : si le jeu ne les porte pas, le pré-calcul
   d'horizon glissant en fin de journée est un recalcul **légitime mais non couvert par G4**. Il faut
   soit une troisième condition (`hors_jeu`), soit un jeu qui couvre J+1.
