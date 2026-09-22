# Ticket 100 — Un seul canal d'événement pour le vécu et le lu

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-21, à la demande de l'auteur, après lecture croisée du chapitre 7 et
> des tickets [059](ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md),
> [078](ticket_078_partage_de_concepts_au_sein_du_foyer.md),
> [079](ticket_079_chocs_declares_vecus_par_les_agents.md) et
> [095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md).
>
> **Plan-first.** Aucune ligne de code avant validation du plan d'architecture
> (`specs/ticket_100/plan.md`) et écriture du contrat de tests (`specs/ticket_100/tests.md`).
> Les questions vivantes vont dans `specs/ticket_100/questions.md`.
>
> **Objet.** Un choc subi sur un trajet et un article lu le matin entrent aujourd'hui par deux
> chemins de code distincts, l'un livré (`llm/chocs.py`), l'autre planifié comme sa copie
> (`llm/informations.py`, 059 lot 4). Tout leur aval est pourtant commun : gravité, force,
> durée de service, consolidation, croyance, contradiction, foyer. Ce ticket pose **un seul
> canal d'événement**, à deux prises d'injection, et rend le foyer indifférent au canal.
>
> **Priorité.** Confirmée par l'auteur le 2026-09-21 : ce ticket passe avant le reste du
> chapitre 7. Le § 7.3 du chapitre 7 (l'article lu) n'a aucune campagne jouable sans
> lui, et les lots qu'il absorbe étaient chacun bloqués par un autre.

---

## 0. Ce que ce ticket joue dans l'article AAMAS

Le chapitre 7 mesure deux régimes qu'aucune variable d'enquête ne porte : un choc vécu par un
agent seul, un article lu par un membre du foyer. Le chapitre 7 du chapitre
(`docs/paper/article/fr/alternative/07_untabulated_regimes.md`, en attente d'accord) ouvre sur
ce que les deux partagent et pose trois prédictions communes : le signe, la forme, et la voie du
retour, par contradiction ou par usure. Ces prédictions ne se testent sur les deux régimes que
si les deux passent par la même mécanique et sortent dans les mêmes fichiers. C'est ce que ce
ticket construit.

---

## 1. L'idée, en une phrase

Un événement, c'est **un texte** posé dans la mémoire d'agents désignés à des jours désignés,
avec **au plus un fait mesuré** et **une estimation de l'agent** ; le reste de la mécanique est
celle de la mémoire, inchangée. Depuis D7, c'est l'estimation **seule** qui fait la gravité — le
fait mesuré reste subi, il décale la journée, mais il ne pèse plus sur ce que le souvenir vaut.

```
  Déclaration (YAML)                  Deux prises                          Un seul aval
 ┌──────────────────────┐    ┌─────────────────────────────┐    ┌────────────────────────────┐
 │ canal  : vecu | lu   │    │ arrivee : après la décision │    │ entrée épisodique qualifiée │
 │ moment : arrivee |   │───►│   + retard subi (fait)      │───►│ gravité = estimée (D7)      │
 │          reveil      │    │ reveil  : avant la décision │    │ force, durée de service     │
 │ texte  : écrit | cité│    │   + rien de mesuré          │    │ consolidation, croyance     │
 │ jugement : oui       │    │ jugement à l'injection      │    │ récit du soir, un saut      │
 └──────────────────────┘    └─────────────────────────────┘    └────────────────────────────┘
```

---

## 2. Décisions de l'auteur, 2026-09-21 et 2026-09-22

| # | Question posée | Décision | Ce qu'elle engage |
|---|---|---|---|
| D1 | Le récit du soir au foyer, restreint aux épisodes au-dessus du seuil de choc ? | **Oui au récit, non à la restriction : tous les épisodes de la journée** | Chaque membre raconte sa journée aux autres, déplacements et événements, lecture du matin comprise. La restriction par gravité disparaît ; la borne du bloc reste (§ 5) |
| D2 | L'information circule-t-elle au-delà du foyer du premier saut ? | **Un seul saut. De la source vers les autres, puis stop. Aucune rétro-information** | Ce qui est entendu ne repart jamais, ni comme récit ni comme croyance. Il faut donc savoir qu'une croyance est née d'un ouï-dire : un champ de provenance, que le 078 refusait (§ 5) |
| D3 | Une seule échelle de jugement ? | **Oui : cinq intensités et une valence**, celles de `gravite.py` et du schéma de `stm_reflection` | La grille à neuf échelons signés du 059 (troisième tour) est retirée. Quatre négatifs, un centre, quatre positifs se retrouvent dans cinq intensités croisées avec une valence |
| D4 | L'agent juge-t-il à l'injection dans les deux régimes ? | **Oui, dans les deux cas c'est l'agent qui juge** | Un appel de jugement par exposition, choc compris. ~~Pour un choc, le fait mesuré reste le plancher par la règle du maximum.~~ **Cette clause est levée par D7.** Le dispositif du § 7.2 change pour la campagne suivante et doit le dire |
| D5 | Le chapitre 7 réorganisé, l'expérience avant l'information ? | **Oui, et la version alternative a été adoptée le 22 septembre** : elle remplace le chapitre 7, il n'y a plus de « chapitre de référence » distinct | Le § 7.4 qu'elle portait est retiré le même jour. Les renvois de ce ticket à un « chapitre alternatif » désignent désormais le chapitre 7 lui-même |
| D6 | Le ticket 100 et le périmètre qu'il retire aux 059, 078, 095 ? | **Oui, et les autres se clôturent ou se réduisent** | § 8 |
| D7 | Le fait mesuré reste-t-il un plancher pour la gravité d'un choc ? | **NON. La gravité d'une entrée est l'estimation de l'agent, et elle seule, dans les deux régimes** | Décision de l'auteur du 2026-09-22, à la relecture du chapitre 7. Elle **rouvre** ce que D4 et `specs/ticket_100/plan.md` disaient fermé. **Appliquée au code le 2026-09-22** (§ 5 bis) |

---

## 2 bis. Ce que D7 retire, et ce qu'il faut accepter avec

`gravite_concept(i_llm, i_det)` existe pour une raison écrite dans son docstring : *« un modèle qui
sous-estime un incident de quarante-cinq minutes ne peut pas le dégrader ».* D7 supprime cette
protection. Trois conséquences, à assumer ensemble ou pas du tout :

1. **Un modèle qui juge « anodin » un dépannage de trente minutes produit un souvenir de trois
   jours**, là où le plancher en imposait quinze. L'effet mesuré au § 7.2 de l'article dépend
   alors entièrement de la qualité du jugement, et une campagne muette ne se distingue plus d'une
   campagne où il ne s'est rien passé.
2. **Le terme déterministe ne disparaît pas du dispositif**, il cesse seulement de peser sur la
   gravité : le retard reste subi, il décale la journée, contraint les trajets suivants et entre
   dans ce que l'agent raconte le soir. C'est ce que le chapitre 7 § 7.1 écrit désormais.
3. **La garde de remplacement est LIVRÉE avec la décision** (2026-09-22, hypothèse Q15). Sans
   plancher, rien ne signalerait un jugement aberrant. L'écart `estimée − déterministe` est
   donc calculé à chaque jugement, écrit dans `evenements.jsonl` sous `ecart_au_fait`, et une
   `[ALARME]` se lève quand l'agent sous-estime de plus de `memoire__ecart_jugement_alarme`
   (0,30, soit plus d'un échelon — les marches valent 0,20 à 0,25). Elle ne corrige **jamais**
   la valeur : corriger en silence rétablirait le plancher sous un autre nom, et la campagne
   mesurerait de nouveau la garde au lieu de l'agent. Le seuil reste à confirmer.

**Portée du changement de code.** `gravite_concept` garde sa signature et son rôle pour les
concepts ; c'est `deposer()` qui cesse de l'appeler avec le terme déterministe et retient
`importance_estimee` seule. Le bras d'ablation `jugement: aucun` (Q4) devient le seul chemin par
lequel la gravité déterministe qualifie encore une entrée.

**Conséquence de D1 sur une option écartée.** L'ancrage par le fait mesuré dans la règle R1 du
078, proposé pour que « l'expérience circule », n'a plus d'objet : l'épisode vécu est raconté le
soir même par le récit du soir. R1 reste telle quelle pour les croyances.

---

## 3. Le format de déclaration

Un fichier par événement, dans `services/llm-agents/config/evenements/`. Les six cas du 079 y
migrent avec `canal: vecu`, les articles du 059 y entrent avec `canal: lu`.

```yaml
evenement: a13_punaises_metro            # ou c6_voiture_suspecte
libelle: "Bed bug scare on the metro"
source: "presse locale — archivé sous articles_html/13_…"
canal: lu                                # vecu | lu
moment: reveil                           # arrivee (après la décision) | reveil (avant la première décision)

texte:
  fichier: docs/paper/sources/actualites/articles_txt/a13_punaises/brut.txt
  sha256: "…"                            # garde de citation : présent ⇒ vérifié au chargement
  # ou, pour un vécu écrit par nous, jour par jour :
  # jours: [{jour: 15, vecu: "The engine made a grinding noise…"}, …]

effet_physique: null                     # ou, par jour : {retard_min: 30, incident_reseau: true, correspondance_ratee: false}

jugement: a_l_injection                  # toujours, décision D4 ; le champ existe pour l'ablation déclarée

calendrier:
  fenetre_jours: [9, 13]                 # tiré par foyer à graine fixe (059 Q5, Q15)
  graine: 59
  # ou : jours: [15, 16]

exposition:
  regle: foyers                          # mode | agents | tirage | foyers
  foyers: ["5177", "18056"]
  lecteurs_par_foyer: 1
  graine: 59
  # modes: [car]                         # restreint aux trajets faits dans ces modes (règles mode et agents)

cadence: jour                            # au plus une application par agent et par jour
```

**Refus au chargement, communs aux deux canaux.** Consigne, verdict, intention dans le texte
(marqueurs du 079, une seule liste) ; jour ou fenêtre hors run ; règle d'exposition inconnue ;
foyer ou agent absent de la population ; un champ `gravite` posé à la main. **Propres à un
canal :** empreinte du texte différente du manifeste quand `sha256` est déclaré ; `effet_physique`
sur un `canal: lu` avec `moment: reveil` (le monde ne change pas avant la décision, § 9).

---

## 4. Architecture

Paquet `services/llm-agents/llm/evenements/`. `llm/chocs.py` devient un adaptateur d'une
version, puis disparaît.

| Module | Porte | Vient de |
|---|---|---|
| `declaration.py` | `Evenement`, `Texte`, `EffetPhysique`, `Calendrier`, `Exposition`, `charger()`, refus | `chocs.py` (dataclasses gelées) |
| `gardes.py` | consigne, verdict, intention ; citation par empreinte | `chocs._verifier_vecu` + 059 plan lot 4 |
| `exposition.py` | `mode`, `agents`, `tirage`, `foyers` ; hachage `graine:evenement_id:cible` | `chocs._expose` + 059 `lecteurs()` |
| `calendrier.py` | `jour_du_run` (jours écoulés du 075), `jour_relatif`, fenêtre tirée par foyer | `chocs.jour_du_run` + 059 `jour_de_parution` |
| `jugement.py` | l'appel d'estimation à l'injection : intensité, valence, modes touchés | schéma `stm_reflection`, champs `severity`, `valence`, `mode` (liste) |
| `registre.py` | `RegistreEvenements` : `due()`, `applique()`, `deposer()`, `tracer()`, compteurs, alarme cache, bascule de journée | `RegistreChocs` |
| `injection.py` | la prise `arrivee` (contrôleur, à l'observation `arrival`) et la prise `reveil` (bascule de journée, avant tout réveil) | contrôleur l. ≈ 2086 et l. ≈ 1775 |

**Une seule fonction dépose l'entrée.** `deposer(person_id, texte, importance, valence, axes,
origine)` écrit la `MemoryEntry`, la force et la durée de service suivant sans une ligne de plus.
La gravité vaut l'**estimation seule** (D7) ; le terme déterministe n'entre plus dans son calcul,
dans aucun des deux canaux.

**La `MemoryEntry` gagne un champ `origine`**, `vecu | lu | entendu`, à défaut `vecu` pour les
entrées antérieures. Il porte D2 (§ 5) et rend la trace lisible.

**Test en or.** Rejouer la déclaration `c6_voiture_suspecte` sur le nouveau paquet et exiger un
`evenements.jsonl` égal champ à champ à l'ancien `chocs.jsonl` archivé, jugement éteint. Les
34 tests du 079 passent sur le nouveau paquet sans changement de leur attendu. Les chiffres du
§ 7.2 restent valides : l'injection ne change pas.

---

## 5. Le foyer, indifférent au canal

Deux choses circulent le soir, à la consolidation, comme **entrées de l'appel** de réflexion du
receveur et jamais écrites dans sa mémoire (078 § 4). Les deux font **un seul saut**.

| Ce qui circule | Règle | Un seul saut, comment |
|---|---|---|
| **Le récit du soir** : les épisodes de la journée de chaque autre membre présent, tous, lecture du matin comprise (D1) | un énoncé par déplacement ou événement, la source nommée avec son âge ; bloc borné, troncature comptée et alarmée | structurel : un récit n'est jamais copié dans la mémoire du receveur, il n'existe que dans l'appel. Rien à re-raconter |
| **Les croyances** : règles R1 à R6 du 078, inchangées | ancrage `observations ≥ 1`, jamais montré deux fois, axe renseigné, mode praticable, borne, membre présent | par la **provenance** : une croyance que la réflexion crée à partir de ce qu'elle a entendu porte `origine: entendu` et ne repart jamais, même confirmée ensuite (§ 10, Q2) |

**La provenance des croyances demande un champ dans le schéma de réflexion.** Le modèle dit,
pour chaque `create`, si la croyance vient de sa propre journée ou de ce qu'il a entendu.
C'est le champ que le 078 § 4.1 refusait ; la décision D2 l'impose, et il n'y a pas de
raccourci : sans lui, un concept né d'un ouï-dire est indiscernable d'un concept né d'un trajet.

**Ce que D1 fait au 059 § 6.1.** La phrase « en l'état, un article ne se diffuse pas » devient
fausse dès que le récit du soir existe : le lecteur raconte sa lecture le soir même. La séquence
datée prédite au § 7.1 de le chapitre 7 devient : parution, décision du lecteur,
récit le soir, première décision du co-résident le lendemain au plus tôt. Un co-résident qui
bouge le jour même de la parution, avant le soir, réfute la séquence.

**Le bras à seuil nul du 078 est RETIRÉ** (décision de l'auteur, 2026-09-22). Il faisait varier
`memoire__partage_foyer_observations_min` pour mesurer si l'ouï-dire circule — mais D1 fait
porter au récit du soir **tous** les épisodes de la journée, sans condition d'ancrage : il n'y a
plus de seuil à mettre à zéro pour observer ce que le bras cherchait.

⚠ **Le réglage reste dans le code, et R1 avec lui.** L'ancrage `observations ≥ 1` continue de
gouverner la circulation des **croyances**, qui est un autre canal que le récit ; ce qui
disparaît est le **bras d'expérience**, pas la règle.

---

## 6. Sorties et mesure, communes

| Sortie | Contenu |
|---|---|
| `evenements.jsonl` | une ligne par application : `evenement_id`, `canal`, `moment`, `jour_run`, `jour_relatif`, `person_id`, `household_id`, `role`, `raison`, `retard_injecte_s`, `importance_estimee`, `valence`, `modes_touches`, `importance_retenue`, `doc_id` |
| `moves.csv` | colonnes `evenement_id`, `jour_relatif`, `role` (`expose \| co_resident \| temoin`), `raison_exposition`, `contrainte_chaine` |
| `agent_memory_events.jsonl` | `origine` sur chaque entrée et chaque croyance ; le récit du soir servi, ligne par ligne |
| mesures du 093 | `evenement_par_jour.csv`, une fonction pour les deux canaux : propension au mode visé sur les trajets où il est offert, par rôle et par jour relatif |
| figure | `figure_evenement.py`, une seule : décrochage et retour par rôle ; la figure 7.2 en est la première instance |
| tableau des quatre voies | même recherche du texte de l'entrée dans `llm_exchanges.jsonl` et `trace_rappel.jsonl`, par régime et par rôle |

Les quatre règles du 093 s'appliquent : journée à 3 h, « la veille » est le jour vécu précédent,
une cellule vide n'est pas un zéro, les jours relatifs se redérivent des horodatages.

---

## 7. Lots

| Lot | Contenu | Dépend de |
|---|---|---|
| **0** | `specs/ticket_100/plan.md`, `tests.md`, `questions.md` ; validation humaine | ce ticket |
| **1** | Paquet `evenements/`, prise `arrivee`, migration des six cas du 079, test en or, `origine` sur `MemoryEntry` | lot 0 |
| **2** | Prise `reveil`, `canal: lu`, garde de citation, règle `foyers`, fenêtre tirée ; les cinq articles du 059 déclarés | lot 1, corpus du 059 lot 1 |
| **3** | Jugement à l'injection, les deux canaux, échelle unique ; refus et `[ALARME]` sur un échelon hors grille, jamais de repli silencieux (059 Q17) | lot 1 |
| **4** | Foyer : récit du soir, croyances R1 à R6, champ de provenance dans le schéma de réflexion, borne et alarme ; drapeau `memoire__partage_foyer_enabled` faux par défaut | lot 1, ticket 077 livré (A et B le sont) |
| **5** | Sorties et mesure communes, figure unique, tableau des quatre voies | lots 1 à 4 |
| **6** | `make run EVENEMENT=`, alias `CHOC=` et `PRESSE=`, passe-plat compose, `docs/arch/evenements.md` remplaçant `chocs-declares.md`, changelog | lot 5 |

Le lot 4 est le plus lourd et le seul qui touche le prompt de réflexion. Il se livre derrière
son drapeau, et sa première mesure est le nombre d'énoncés servis par soir et le nombre de
troncatures : le 077 a mesuré un prompt qui stagne vers 2 100 jetons.

---

## 8. Ce que ce ticket absorbe, et ce qu'il laisse

| Ticket | Passe au 100 | Reste |
|---|---|---|
| 079 | tout le code, migré au lot 1 | déjà clos |
| 078 | lots 1 à 3, rendus indifférents au canal, au lot 4 | **se clôt** : ses règles R1 à R6 et ses décisions restent la référence de conception |
| 059 | lot 4 (canal `information`) | corpus, grille, population de foyers, mesure et figures propres à la presse ; son lot 3 tombe, l'étage 1 n'existant plus |
| 095 | E3 (exposition multi-agents avec témoin interne), qui a besoin de la règle `foyers` | lots C à F, E1, E2, E4, E5 |
| 064 | rien | la campagne de presse, inchangée |

---

## 9. Ce que ce ticket refuse

- **Dégrader l'offre.** Un `canal: lu` ne touche ni OTP, ni GTFS, ni OSMnx. Le régime anticipé
  avec dégradation reste hors périmètre, comme au 079 § 10.
- **Faire circuler au-delà d'un saut.** Aucune option, aucun paramètre ne rouvre la rétro-information.
- **Toucher aux règles de mémoire** hors de ce qui est listé : ni seuil de choc, ni force, ni
  viviers. Le déplacement du seuil à 0,66 (095 Q3bis) reste au 095. ⚠ D7 est l'exception, et
  elle est délibérée : la gravité d'une entrée d'événement cesse de porter un plancher. La
  formule de la force, elle, ne bouge pas — c'est son ENTRÉE qui change.
- **Écrire dans l'article.** Il est sous verrou, il a été entièrement repris le 22 septembre, et
  il bouge encore : ce ticket signale ce qu'il rend caduc, il ne le corrige jamais.

---

## 10. Questions vivantes

À porter dans `specs/ticket_100/questions.md` au lot 0. Hypothèse tenue faute de réponse.

| # | Question | Hypothèse |
|---|---|---|
| Q1 | Le récit du soir : un énoncé par **déplacement**, ou par **entrée brute** ? Une journée produit plusieurs entrées par trajet | par déplacement, plus un énoncé par événement déposé ; borne `memoire__recit_soir_max`, tri par gravité décroissante puis par heure, troncature comptée et alarmée |
| Q2 | Une croyance `entendu` que le receveur **confirme ensuite par un trajet** repart-elle ? | **non**, lecture stricte de D2 ; sa propre journée peut créer une croyance `vecu` distincte, qui circule |
| Q3 | Le récit du soir dit-il **ce qui a été décidé** ou **ce qui a été vécu** ? « J'ai pris le bus » ou « le bus avait douze minutes de retard » | ce qui a été vécu, dans les mots déjà en mémoire ; aucune reformulation |
| Q4 | Le jugement à l'injection d'un choc change le dispositif du § 7.2 : le déclarer dans la prochaine campagne, ou jouer un bras sans jugement pour mesurer l'écart ? | les deux : le bras sans jugement est l'ablation déclarée `jugement: aucun` |
| Q5 | Le cache de décisions pendant un run à événement ? | coupé, `[ALARME]` s'il est actif, comme au 079 |

---

## 11. Documentation et article

- `docs/arch/evenements.md` remplace `chocs-declares.md` ; `memory-stm-ltm.md` gagne le champ
  `origine` et le récit du soir ; `mesures-personas.md` gagne `evenement_par_jour.csv`.
- **Signalement article** à la livraison de chaque lot : le § 3.4 (le foyer n'y figure pas), le
  § 7.2.2 de référence (le jugement à l'injection), le § 7.1 de référence et le § 7.1 de la
  version alternative (la séquence datée change avec D1). Aucune écriture sans accord.

---

## 12. Références

- Tickets [059](ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md),
  [078](ticket_078_partage_de_concepts_au_sein_du_foyer.md),
  [079](ticket_079_chocs_declares_vecus_par_les_agents.md),
  [095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md), [071](ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md).
- `services/llm-agents/llm/chocs.py`, `llm/gravite.py`, `llm/noyau.py`, `llm/memory.py`.
- `specs/ticket_059/plan.md` (lot 4), `specs/ticket_059/questions.md` (Q1, Q15 à Q21),
  `specs/ticket_095/questions.md` (Q3bis, Q6, Q7).
