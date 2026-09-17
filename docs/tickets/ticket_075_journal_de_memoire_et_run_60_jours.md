# Ticket 075 — Journal de mémoire par agent et run de 60 jours sur cinq habitants


> ⚠ **AVANT DE LANCER UN RUN GAMA — vérifier l'état des accidents sur les axes.**
> Depuis le 2026-09-15, le paramètre « Accidents sur les axes » (catégorie `Simulation`) est
> **VRAI par défaut**, et depuis le 2026-09-15 les accidents **allongent** les itinéraires
> qui les traversent (ticket 070, travaux C/D/E). Tout run en tire selon la loi BAAC
> 2019-2024, et en subit l'effet. ⚠ **Les runs d'avant et d'après le 2026-09-15 ne sont pas
> comparables.**
> Décocher la case si la mesure doit se faire sur un réseau intact, et **lire
> `accidents_enabled` dans le `scenario_params.yaml`** du run avant d'en interpréter les
> résultats. Détail : [`docs/arch/accidents-sur-les-axes.md`](../arch/accidents-sur-les-axes.md).

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-14.
>
> **Objet.** Rendre l'évolution de la mémoire des agents **lisible** sur un run long, et produire
> ce run : cinq habitants, soixante jours simulés, `gemini-3.1-flash-lite` seul, mémoire et
> auto-réflexion actives.
>
> **Relation au 071.** Le [071](ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md) a
> livré les quatre lots du mécanisme de mémoire. Celui-ci n'y touche pas : il **l'observe**. La
> seule exception est la progression de la date météo (§ 1), qui devenait fausse sur un run long.
>
> **Contrat de test.** `specs/ticket_075/tests.md`, écrit AVANT le code, comme les lots du 071.

---

## 0. Pourquoi ce ticket

Les quatre lots du 071 ont été validés par 249 tests unitaires. Aucun ne dit ce que la mémoire
d'un agent **devient** quand elle vit soixante jours : quels concepts se forment, lesquels sont
contredits, ce qui s'oublie, et ce qui, dans le vécu simulé, l'a déclenché. Le dépôt journalise
déjà les écritures (`agent_memory_events.jsonl`) mais ni le **déclencheur** d'une consolidation,
ni l'**avant/après** d'une opération de concept, ni l'**état résultant**. Reconstituer cela après
coup depuis un JSONL est un travail d'archéologue, et il est impossible sur les mises à jour
faites sur place.

---

## 1. Progression de la date météo — le seul changement de mécanisme

`weather_draw.date_meteo` était une fonction pure de `(graine, person_id)` : la date tirée valait
pour tout le run. Le dispositif avait été conçu au ticket 023 pour une journée simulée unique, où
il résout un vrai problème — à mille agents sur un jour, la météo est une constante et son effet
est non mesurable par construction. Sur soixante jours, il produit l'inverse de ce qu'on veut :
chaque agent relit **soixante fois le même bulletin**, sans persistance d'épisode pluvieux ni
saison, et la mémoire épisodique se construit sur une météo immobile.

**Ce qui change.** La date tirée devient un **jour de départ**, avancé d'un jour calendaire par
jour simulé écoulé. Décision de l'auteur du 2026-09-14 : remplacement, pas option.

**Ce que le remplacement ne casse pas.** L'avancement est ancré sur le premier instant simulé du
run (`urban_mobility_agents/utils/ancre_run.py`). Au premier jour, l'écart vaut zéro et la date
rendue est **exactement** celle d'avant le ticket : une expérience d'un seul jour, déjà mesurée et
scellée, rejoue la même météo. Seuls les runs multi-jours voient la progression.

**Deux pièges, tous deux trouvés par les tests avant le code.**

1. L'arithmétique se fait sur le **rang dans l'année**, pas par addition de jours à une date :
   `31 décembre + 60 jours` sortait de l'année pivot et retombait sur le 29 février d'une année
   bissextile — date que la source (365 jours) ne porte pas, et qui aurait fait disparaître le
   bulletin du prompt sans une ligne de journal.
2. L'ancre **ne se réancre pas** à la reprise à chaud. GAMA rejoue depuis son t0 : observer le
   premier timestamp du rejeu ferait rembobiner la météo de tous les agents.

Réglages du run : `weather_window: annee`, `weather_weekdays_only: false` — soixante journées
réellement consécutives, week-ends compris.

---

## 2. Journal de mémoire — un Markdown par agent

`llm/journal_memoire.py`. Un fichier par agent dans `<workdir>/memoires/<person_id>.md`, écrit en
continu pendant le run.

| Événement | Ce qui est écrit |
|---|---|
| Consolidation | section datée, **motif** (`seuil` / `plancher journalier` / `rupture`), ce qui l'a déclenchée, les entrées de mémoire courte consommées, la réflexion écrite, puis l'**état complet** de la mémoire après |
| Opération de concept | l'opération (`créé` / `confirmé` / `précisé` / `contredit`), le contenu avant et après, les compteurs et la confiance avant et après, la mise à l'écart datée le cas échéant |
| Écriture épisodique | une ligne compacte : type, contenu, gravité, force |
| Rappel | une ligne compacte : combien de souvenirs servis, leur force et leur compteur après renforcement |
| Purge | une ligne par entrée oubliée, avec son âge depuis le dernier rappel et sa force |

**Trois garanties.** Éteint par défaut (`agent.journal_memoire_enabled`) — un run à mille agents
ne paie rien. Aucune exception ne remonte à l'appelant : un journal ne fait pas tomber une
simulation de soixante jours. Un agent, un fichier, sans mélange possible.

**Ce que ce n'est pas.** Une source de mesure. Les chiffres se prennent dans les métadonnées de
la mémoire et dans `moves.csv` ; ce fichier-ci est fait pour être **lu**.

---

## 3. Reprise à chaud

`make run OFFLINE=1 CONT=1` réutilise le répertoire du run, donc **retrouve la mémoire pleine**,
tandis que GAMA repart à son t0 et rejoue les jours déjà vécus. Pour un run ordinaire, sans
conséquence. Pour un run dont la mémoire EST l'objet, c'est disqualifiant : les jours rejoués
réécriraient des souvenirs déjà là, doubleraient les épisodes et incrémenteraient deux fois les
compteurs d'observations et de contre-exemples.

**Point de reprise quotidien**, à 3 h simulées — après le drainage nocturne des réflexions et
après le plancher de consolidation de 22 h, quand les tampons de mémoire courte sont vides et que
presque personne n'est en trajet. Il contient la mémoire long terme, les `.md` du journal, l'ancre
du run et les compteurs. Écriture atomique : un point interrompu n'est jamais retenu comme valide.

**Rejeu à mémoire gelée.** À la reprise, l'état est restauré au dernier point, puis les jours
déjà vécus sont rejoués **sans aucune écriture** de mémoire courte, longue ou de journal. Le dégel
a lieu au premier instant postérieur au point de reprise, et il est journalisé ; son absence lève
une alarme.

**Sérialisation GAMA.** L'image `gamaplatform/gama:2025.06.4` embarque
`gama.extension.serialize` (`RestoreStatement`, `SimulationSaveDelegate`, `GamaSavedSimulationFile`) :
sauvegarder l'état de GAMA et repartir au jour k sans rejeu est possible **en principe**. La
mention « GAMA ne sait pas geler son état » de `docs/setup/quickstart.md` date du ticket 002 et
n'est plus vraie pour cette version. Ce qui reste à mesurer sur NOTRE modèle : taille du `.gsim`,
durée, et ce qui survit au tour (graphes routiers, structures GTFS, agents à skills). Tant que ce
n'est pas mesuré, la reprise repose sur le rejeu gelé, qui ne dépend d'aucune fonctionnalité GAMA.

---

## 4. Population de test

`data/population/population_5_memoire_075/`, cinq agents prélevés **tels quels** dans le sceau
`population_1000_AAMAS_v6` par `scripts/data/population/extraire_sous_population.py`. Aucun tirage
aléatoire : chaque profil est un prédicat, l'agent retenu est le premier qui le satisfait dans
l'ordre des identifiants.

| Profil | Agent | Pourquoi ce profil |
|---|---|---|
| `pendulaire_voiture` | 609 | la voiture est le choix par défaut : la mémoire doit peser fort pour en faire dévier |
| `cycliste_urbain` | 899549 | le plus sensible à la météo et aux incidents |
| `usager_transport_collectif` | 616478 | la mémoire porte sur la fiabilité des lignes, donc sur des concepts qui se confirment et se contredisent |
| `scolaire` | 11195 | trajets très réguliers : une habitude doit se former nettement |
| `retraite_multi_motifs` | 41275 | agenda irrégulier : une mémoire qui ne se réduit pas à un aller-retour |

⚠ **Ce n'est pas un sceau AAMAS**, et le MANIFEST le dit. Cinq agents ne représentent rien : ils
servent à observer un mécanisme, jamais à mesurer une part modale.
`population_1000_AAMAS_v6` reste la référence de l'article.

---

## 5. Le run

| Réglage | Valeur | Pourquoi |
|---|---|---|
| Fournisseur | `google_gemini31_key1` + `key2`, seuls | demande explicite : `gemini-3.1-flash-lite` exclusivement, via un fichier de fournisseurs restreint |
| Jours simulés | 60 | horizon du ticket 071 (fenêtre d'âge du rappel plafonnée à 60 j) |
| Mémoire | LTM et auto-réflexion actives | `make run MEM=1` |
| Cache LLM | actif, répertoire dédié | sans lui, la reprise après épuisement du quota rejouerait en repayant chaque appel, et le run n'atteindrait jamais le jour 60 |
| Quota | 2 × 500 requêtes/jour | ≈ 1 400 sollicitations attendues : le run traverse au moins une remise à zéro (minuit Pacifique, 9 h à Paris) |

---

## 6. Ce que ce ticket ne fait pas

Il ne change **aucune** règle de la mémoire : ni gravité, ni oubli, ni viviers, ni score de
rappel, ni opérations de concept. Tout ce qu'il ajoute est observable ou hors du chemin de
décision. La seule exception est la progression météo du § 1, qui est un changement de dispositif
et non de mémoire, et qui est réversible à l'identique au premier jour d'un run.
