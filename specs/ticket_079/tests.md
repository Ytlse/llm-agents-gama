# Contrat de test — ticket 079 (chocs déclarés)

> Écrit **avant** le code, comme les lots des tickets 071, 075 et 077. Chaque règle porte un
> numéro ; chaque numéro a un test qui le cite. Une règle sans test n'est pas livrée.
>
> Fichier de tests : `services/llm-agents/tests/test_079_chocs.py`.

## Hypothèses appliquées (questions du ticket, § 10)

| # | Tranchée comme | Conséquence testable |
|---|---|---|
| Q1 | seul le régime **subi** | aucun moteur d'itinéraire n'est sollicité — R14 |
| Q2 | pas de cascade sur l'agenda | `reschedule_activity_departure_time` inchangé — R15 |
| Q3 | cache coupé pendant une campagne à choc | alarme si le cache est actif — R16 |
| Q4 | valeurs assumées comme scénario | la source est déclarée et journalisée — R3 |
| Q5 | exposition par mode seulement | une règle inconnue est refusée — R5 |
| Q6 | ce ticket porte ses traces | colonnes et `chocs.jsonl` — R10 à R13 |

**Décision de langue.** Le dispositif est passé en anglais (ticket 074). Les textes `vecu` livrés
en exemple sont donc **en anglais** : une phrase française dans un prompt anglais réintroduirait
exactement le facteur que la bascule a supprimé. Le format n'impose aucune langue ; les exemples si.

---

## A. Lecture et refus (lot 1)

- **R1** — Un fichier de choc valide se charge : identifiant, libellé, source, règle d'exposition,
  et un profil par jour (retard, incident réseau, texte vécu).
- **R2** — Sans fichier déclaré, le registre est vide et **rien ne change** : aucun retard injecté,
  aucun texte ajouté, aucune colonne renseignée. Un run qui ne demande rien se comporte comme avant.
- **R3** — Le chargement journalise, en INFO : identifiant, libellé, source, jours couverts, règle
  d'exposition et retard de chaque jour. Un choc silencieux n'existe pas.
- **R4** — Refus au chargement, avec le motif et l'emplacement : `jours` vide, `jour` < 1, deux
  entrées pour le même jour, `retard_min` < 0, `vecu` vide.
- **R5** — Refus d'une règle d'exposition inconnue. Les trois règles admises sont `mode`, `tirage`,
  `agents`, et rien d'autre.
- **R6** — Refus d'un mode hors de la hiérarchie canonique du dépôt. Le vocabulaire est celui de
  `llm/axes.py`, jamais une liste recopiée.

## B. Le texte vécu est du vécu (lot 4)

- **R7** — Un `vecu` qui **s'adresse à l'agent** ou lui **dicte une conduite** est **refusé au
  chargement**, pas signalé au journal. Marqueurs refusés, sans distinction de casse : *you should*,
  *you must*, *avoid*, *remember to*, *consider*, *try to*, *don't*, *tu devrais*, *évite*,
  *pense à*, *il faut que tu*, ainsi que toute adresse à la deuxième personne.
- **R8** — Un `vecu` sans aucune marque de première personne (*I*, *my*, *je*, *j'*, *mon*, *ma*,
  *mes*) lève un WARNING nommant le choc : ce n'est pas un vécu, mais le refuser serait trop
  strict pour une phrase nominale (« Flat tyre on the way, hands covered in grease »).
- **R9** — Les cinq cas d'exemple livrés passent R7 et R8 sans avertissement.

## C. Application (lot 2)

- **R10** — Un agent exposé le jour du choc reçoit : le retard déclaré ajouté au retard mesuré, le
  texte vécu joint à l'observation d'arrivée, et `incident_reseau` porté à la gravité.
- **R11** — **Les deux retards ne se confondent jamais.** `retard_mesure_s` et `retard_injecte_s`
  sont deux champs distincts, écrits séparément partout où ils passent. La gravité utilise la somme.
- **R12** — Un agent **non exposé** ne reçoit rien : ni retard, ni texte, ni incident. Il reste le
  témoin interne du même run, et son absence d'exposition est **écrite**, pas déduite.
- **R13** — Un jour sans entrée dans `jours` est un jour **nominal** : aucun choc ne s'applique, et
  le jour relatif est tout de même renseigné (il vaut −2, −1, 0, +1… selon le premier jour du choc).
- **R14** — Aucun moteur d'itinéraire n'est sollicité : le nombre d'appels OTP et OSMnx est le même
  avec et sans choc. C'est la frontière du régime subi.
- **R15** — L'agenda n'est pas décalé : le retard injecté ne replanifie aucune activité tant que
  `reschedule_activity_departure_time` vaut faux.
- **R16** — Une `[ALARME]` se lève si un choc est actif alors que le cache de décisions l'est
  aussi : la clé du cache ne porte aucune durée, une décision d'avant le choc pourrait être
  resservie pendant.

## D. Exposition

- **R17** — Règle `mode` : sont exposés les agents dont le trajet qui arrive a été fait dans l'un
  des modes déclarés, et eux seuls.
- **R18** — Règle `tirage` : la sélection est **déterministe** pour un couple (choc, graine) et
  **stable d'un run à l'autre** — le même agent est touché ou épargné à chaque rejeu, quel que soit
  l'ordre d'arrivée des observations.
- **R19** — Règle `tirage` : la part effectivement touchée est celle qui est déclarée, à la
  précision de l'effectif près, et elle est journalisée.
- **R20** — Règle `agents` : seuls les identifiants désignés sont touchés ; un identifiant absent
  de la population lève un WARNING au chargement et n'empêche pas le run.

## E. Gravité et mémoire

- **R21** — Un choc à 60 minutes avec `incident_reseau` produit une gravité de **0,70**, soit le
  seuil du vivier des chocs, et une force de **14,6 jours**. Le calcul n'est pas recopié : il vient
  de `llm/gravite.py`.
- **R22** — La composante `incident_reseau` cesse d'être déclarée inactive **dès qu'un choc la
  porte**, et `journal_des_composantes()` le dit au démarrage. Sans choc chargé, elle reste
  déclarée inactive : une composante sans source doit continuer de se dire.
- **R23** — Le texte vécu se retrouve **mot pour mot** dans l'entrée de mémoire courte de l'agent.
- **R24** — Mémoire coupée (bras amnésique), le choc s'applique **quand même** : mêmes retards,
  mêmes traces. Sans cela, les deux bras différeraient par autre chose que la mémoire.

## F. Trace (lot 3)

- **R25** — `moves.csv` porte, pour **toute** décision : l'identifiant du choc en vigueur (vide
  s'il n'y en a pas) et le jour relatif au premier jour du choc.
- **R26** — `gama_arrivals.csv` porte `retard_injecte_s` à côté de `delay_s`.
- **R27** — `chocs.jsonl` reçoit une ligne par application : agent, instant, jour du run, jour
  relatif, identifiant du choc, raison de l'exposition, retard injecté, incident, correspondance,
  texte vécu, gravité obtenue et **détail par composante**.
- **R28** — La déclaration complète est archivée dans le répertoire du run, avec l'empreinte du
  fichier source : un résultat se relit sans le dépôt.
- **R29** — Les compteurs de fin de journée sont journalisés **même à zéro** : agents exposés,
  agents épargnés, retard total injecté. Un compteur muet ne distingue pas « rien ne s'est passé »
  de « le mécanisme ne tourne pas ».

## G. Reprise à chaud

- **R30** — Le jour du run se lit sur l'**ancre** du ticket 075, jamais sur le premier timestamp
  observé : après une reprise, un choc déclaré au jour 12 reste au jour 12 et ne rembobine pas.
