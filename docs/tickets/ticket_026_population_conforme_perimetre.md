# Ticket 026 — Le bassin de tirage devient le périmètre d'enquête — **version Haute-Garonne**

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> **Nature du ticket** : *correction de bassin*. Il traite l'axe **A9** du
> [ticket 020](ticket_020_perimetre_population_cerema.md) — la surconcentration spatiale —
> par sa cause racine : le **cadre de tirage** n'est pas le périmètre d'enquête.
>
> ## ⚠ VERSION VOLONTAIREMENT PARTIELLE, ET LA LIMITE EST CHIFFRÉE
>
> Ce ticket restreint le cadre de tirage aux **346 communes du périmètre EMC² situées en
> Haute-Garonne**, et non aux 453. Les **107 communes des cinq autres départements** (32, 81,
> 82, 09, 11) restent hors du bassin : elles demandent +10 Go de BD TOPO et de BAN, et une
> régénération plus lourde. C'est un choix assumé de **découpage du travail**, pas une
> approximation qu'on espère négligeable — voir « La limite, chiffrée » ci-dessous, et
> « La suite » pour ce qu'il restera à faire.
>
> **Ce que « conforme » veut dire, et ne veut pas dire.** Conforme = le *cadre de tirage* est
> une **liste de communes** de l'enquête, plus un rectangle. Ce **n'est pas** « chaque commune
> porte au moins un persona » : à 1 000 agents pour 1,37 million d'habitants, la plupart des
> 175 communes de 3ᵉ couronne retenues resteront vides, et c'est correct.

## Le constat : non conforme dans les deux sens

**Le périmètre d'enquête** est plus large qu'on ne le croit en lisant « Toulouse » :
453 communes réparties sur **six départements** — 31 (346), 32 (38), 81 (27), 82 (22),
09 (10), 11 (10) — pour une emprise de lat 43,115 → 43,954 et lon 0,866 → 1,928.

**Vérifié par trois chemins indépendants**, parce que le chiffre surprend :

1. **recompte depuis la couche SIG source** (`EMC2_Toulouse_2023_ZF_26052023.shp`, et non
   depuis la ressource dérivée) : 453 communes, mêmes six départements, mêmes effectifs.
   Noms de contrôle : Ardizas (32), Bannières (81), Bessens (82), La Bastide-de-Besplas
   (09), Baraigne (11) ;
2. **surface** calculée sur cette même couche : **5 428 km²**, contre **5 400 km²** annoncés
   par le rapport auat — la couche EST bien le périmètre officiel ;
3. **le rapport auat lui-même** (*Enquête mobilité 2023 — Bassin de vie toulousain*) :
   453 communes, 5 400 km², 1,4 million d'habitants, 1,32 million de 5 ans et plus, et le
   découpage 1 / 68 / 109 / 275 communes. L'écart d'une commune sur les 1ʳᵉ et 2ᵉ couronnes
   (la couche donne 1 / 69 / 108 / 275) est celui déjà documenté par
   `export_commune_couronne.py` : la couche fait foi, c'est sur ses secteurs que les poids
   de redressement ont été calculés.

**Pourquoi le rapport donne l'impression d'un périmètre « Haute-Garonne ».** Il affiche
« Département 31 » comme **couche de carte** (la limite départementale, tracée en repère) et
comme l'un de ses **périmètres d'analyse** (« Département de la Haute-Garonne », « Périmètre
Tisséo »), à côté du périmètre d'enquête. Il précise d'ailleurs que les habitants des
communes situées **hors** de l'aire urbaine — Montauban, Gaillac, Foix — ne sont pas
comptabilisés : ces communes-là sont bien en dehors des 453.

**La frange hors Haute-Garonne est petite mais périphérique** : 107 communes, 110 zones fines
(14 %), 1 358 km² (**25 % de la surface**), dont **100 communes en 3ᵉ couronne** et 7 en 2ᵉ.
C'est exactement la couronne que le bassin actuel ne peuple pas.

**Et la preuve que ça mord** : sur les 1 021 personas de la population de référence, les
**976** dont la commune est connue sont **tous en département 31**. Les 107 communes
non-31 du périmètre ne sont pas sous-représentées : elles sont **absentes**.

**Ce qu'on génère, mesuré** :

| | population des jeux gelés (930) | population de référence (1 021) |
|---|---|---|
| communes touchées | **111 / 453** (24,5 %) | 126 / 453 |
| zones fines | 290 / 785 | — |
| secteurs de tirage | 83 / 88 | — |
| domiciles **hors** périmètre | 0 | **45 (4,4 %)** |

Et le déficit est **structuré**, pas aléatoire : le filtre est un rectangle, il ampute donc
les couronnes externes.

| couronne | personas (930) | communes couvertes | poids au cadrage |
|---|---:|---|---:|
| Toulouse | 376 | 1 / 1 | 36,4 % |
| 1ʳᵉ couronne | 365 | 56 / 69 | 34,1 % |
| 2ᵉ couronne | 135 | 34 / 108 | 14,2 % |
| **3ᵉ couronne** | **54** | **20 / 275** | **15,4 %** |

D'où le 76,0 % de cœur d'agglomération contre 70,5 % au cadrage, et le code de sortie `4`
que rend aujourd'hui `make residence-zone CHECK=1`.

---

## La limite, chiffrée — à publier telle quelle

Population RP 2022 des communes du périmètre, par couronne, selon le cadre retenu :

| couronne | périmètre complet (453) | **cadre Haute-Garonne (346)** | cadrage EMC² |
|---|---:|---:|---:|
| Toulouse | 511 684 hab · 35,1 % | 511 684 hab · **37,4 %** | 36,4 % |
| 1ʳᵉ couronne | 510 644 hab · 35,0 % | 510 644 hab · **37,4 %** | 34,1 % |
| 2ᵉ couronne | 213 255 hab · 14,6 % | 199 075 hab · **14,6 %** | 14,2 % |
| **3ᵉ couronne** | 223 501 hab · 15,3 % | 145 020 hab · **10,6 %** | **15,4 %** |
| total | 1 459 084 | **1 366 423** (−92 661, −6,4 %) | |

**Ce que ça veut dire, sans emballage.** Le cadre Haute-Garonne **ne peut pas atteindre** la
cible de 15,4 % en 3ᵉ couronne : son plafond est 10,6 %. Le résidu de **4,7 points sur cette
strate est structurel**, pas un défaut de tirage.

Écart L1 de la répartition de population au cadrage, selon le cadre :

| cadre | L1 | lecture |
|---|---:|---|
| population actuelle (bbox × dept 31) | **11,7 pt** | mesuré par `make audit-perimetre` |
| **cadre Haute-Garonne (ce ticket)** | **≈ 9,5 pt** | plancher atteignable |
| cadre complet (453 communes) | ≈ 2,7 pt | ce que la suite apporterait |

Autrement dit : ce ticket referme **2,2 points sur les 9,0 disponibles, soit un quart**.
L'essentiel de son apport est **structurel** — un cadre par liste de communes au lieu d'un
rectangle, et toute la plomberie en place — et non numérique sur A9.

⚠ **Et un piège de lecture à désamorcer tout de suite.** Avec ce cadre, les écarts par
couronne valent +1,0 / +3,3 / +0,4 / **−4,8** points. La tolérance de
`enrich_residence_zone --check` étant de 5 points par couronne, la porte **passera** —
à 4,8 contre 5,0, soit à un cheveu. **Un `--check` vert ne vaudra donc pas conformité** :
il dira seulement que le résidu structurel tient dans la tolérance choisie. La cible du
`--check` reste le **cadrage complet**, jamais une référence restreinte au cadre retenu :
recalibrer la cible sur ce qu'on sait produire, c'est se donner raison par construction.

---

## Trois étages à modifier, et un ordre imposé

### 1 · Le snap — correction : **il n'existe pas**, et c'est instruit

La première rédaction de ce ticket annonçait un piège silencieux : `llm_agents` snapperait
les domiciles hors du polygone OTP, donc une population conforme verrait ses domiciles
éloignés déplacés au bord de l'agglomération. **C'est faux, vérifié le 2026-08-24** :
`_snap_to_polygon` est **défini et appelé nulle part** — une seule occurrence dans tout le
dépôt, sa définition. Le polygone OTP ne sert qu'à décider de rafraîchir `home_location`
depuis la première activité domicile, ce qui est un no-op puisque les coordonnées sont
identiques. Le message du stage le disait à sa façon : *« OTP polygon unavailable —
out-of-graph detection skipped »*.

**Aucun domicile n'est donc déplacé, ni avant ni après ce ticket.** J'aurais dû vérifier
l'appelant avant d'écrire l'avertissement ; c'est exactement le contrôle que le lot 0 du
[ticket 021](ticket_021_couronne_residence_post_traitement.md) avait institué, et que je
n'ai pas appliqué ici.

**Ce qui reste vrai, et qu'il faut connaître** : rien ne ramène dans le graphe une activité
qui en sort. Les personas éloignés n'auront donc **pas d'offre TC** — pas de trajet faussé,
mais un jeu d'options réduit à la voiture, au vélo et à la marche. Le contrôleur le
journalise déjà (`origin_in_bbox` / `dest_in_bbox` sur le chemin « Pas de solution de
déplacement »). C'est cohérent avec le comportement réel d'un habitant de 3ᵉ couronne — 71 %
de ses déplacements sont en voiture — mais ça reste une **limite à publier**, pas une
propriété du modèle : un GTFS régional (liO) la lèverait, et c'est un ticket distinct
puisqu'il change les durées de trajet de **tous** les agents.

### 2 · La génération (eqasim) — **livré**

| # | À modifier | État actuel | Cible — version Haute-Garonne |
|---|---|---|---|
| a | `departments` dans la config synpp de [`generate_population.py`](../../eqasim-toulouse/generate_population.py) | `["31"]` **en dur** | **inchangé** — c'est précisément ce qui rend cette version légère. À étendre aux six départements dans la suite |
| b | Le filtre de communes | `_communes_from_bbox(bbox)` — intersection IRIS × rectangle | Lire les codes INSEE de `llm_module/data/commune_couronne.json` **filtrés sur le préfixe 31** : 346 communes. **Le mécanisme existe déjà** — la config synpp accepte `"communes": communes`. C'est le cœur du ticket, et son seul vrai changement de code |
| c | `sampling_rate` | dérivé de la population des communes retenues (RP 2022) | inchangé dans son principe : il reçoit les 346 communes, donc 1 366 423 habitants au lieu de 1,4 M de département |
| d | **BAN, BD TOPO** | `adresses-31.csv.gz`, `D031` | **rien à télécharger** : le département 31 est déjà là. C'est tout le gain de la version légère |
| e | RP 2022, FILOSOFI, IRIS 2024, codes 2024, ENTD | déjà **nationaux** | rien à faire |

**Un garde-fou à écrire, pas à supposer** : le filtre doit **échouer** si la liste des
communes retenues est vide ou si elle ne recoupe pas `departments` — sinon une faute de
frappe ferait retomber sur le comportement actuel (tout le département) sans un mot, et on
croirait avoir un cadre conforme.

### 3 · Le chargement en simulation — **livré**

`factory.py:151` calcule `world_bbox = emprise des arrêts GTFS ± 0,05°`, soit
lat 43,346 → 43,800 / lon 1,101 → 1,741. Puis `WorldPopulation.load_population` **écarte**
tout agent dont le domicile est hors de cette bbox (`_is_within_bbox`).

Mesuré : cette bbox ne contient que **221 des 453 communes**, **548 des 785 zones fines**,
et **51 des 277 zones fines de 3ᵉ couronne** — 47,9 % de la surface du périmètre. Une
population conforme serait donc **re-tronquée de moitié au chargement**, et l'étage 2
n'aurait servi à rien.

À modifier :

- **le filtre d'admission** devient un filtre de **périmètre**, et il porte sur les **453**
  communes — **pas sur les 346 du cadre de tirage**. La distinction est le point délicat de
  cette version : le *cadre* dit où l'on tire, le *filtre* dit ce qui est dans l'enquête.
  Restreindre le filtre au cadre graverait la limitation Haute-Garonne dans le runtime, et
  la suite du ticket devrait la déterrer. Le trait `residence_zone` du ticket 021 rend ce
  filtre gratuit — plus besoin de géométrie au chargement — et il porte déjà la bonne
  définition. **Un rectangle plus grand ne suffit pas** : la bbox du périmètre admet
  8 004 km² pour 5 428 km² de périmètre, soit **2 577 km² (32 %) de territoire hors
  enquête** — la conformance ne s'exprime pas avec un rectangle ;
- **la `WorldGrid` est inerte, et c'est une bonne nouvelle** : `get_location_grid` — la seule
  méthode qui porte l'assertion « location outside the bounding box » — **n'est appelée
  nulle part** dans le dépôt. La grille est construite, stockée dans `world_data`, et jamais
  interrogée. L'élargir coûte deux entiers (2 652 → 8 084 cellules de 1 km) et ne peut rien
  faire lever ;
- ⚠ **GAMA a son propre monde, et il est PLUS PETIT que le bbox du contrôleur.**
  `Settings.gaml:61` fait `geometry shape <- envelope(routes0_shape_file)`, et
  `includes/routes.shp` (395 objets) s'étend sur lat 43,396 → 43,750 / lon 1,151 → 1,691 —
  l'emprise des arrêts Tisséo, sans même le tampon de 0,05°. Élargir le filtre côté
  contrôleur placerait des agents **hors du monde GAMA**. Aller à l'échelle du périmètre
  demande de reconstruire `routes.shp`, `stops.shp` et l'extrait `Toulouse_bbox_p95.osm.pbf`
  — avec les conséquences de performance côté GAMA ;
- le `PersonCloseToTheStopFilter` (aujourd'hui désactivé, `filters=[]`) doit rester
  désactivé, sinon il rétablit la troncature par un autre chemin.

---

## Ce que ça change, et qu'il faudra re-mesurer

- **A9 s'améliore d'un quart, et le reste est publié** : L1 de répartition 11,7 → ≈ 9,5 pt.
  `make residence-zone CHECK=1` doit passer du code `4` au code `0` — mais voir le piège de
  lecture ci-dessus : la porte passe à 4,8 contre 5,0 ;
- **le cadre devient nommable** : « les 346 communes du périmètre EMC² en Haute-Garonne » se
  dit et se vérifie, là où « le rectangle des arrêts Tisséo élargi de 5 km » ne correspond à
  aucune définition d'enquête. C'est le vrai apport de cette version ;
- **les 45 domiciles hors périmètre disparaissent** de la population de référence : le filtre
  par commune les exclut par construction. Le garde-fou du ticket 021 reste, comme détecteur ;
- **la population change, donc les jeux gelés changent** : nouveau jeu (`v9`), et le
  [ticket 025](ticket_025_dimension_zone_notee.md) devient *envisageable* — mais avec une
  3ᵉ couronne encore à 10,6 % au lieu de 15,4 %, noter la dimension zone reposerait toujours
  sur une strate sous-peuplée. Je le déconseille avant la suite ;
- **le coût de simulation monte modérément** : les communes ajoutées sont en Haute-Garonne,
  donc à moins de 80 km ; le pbf et le graphe routier les couvrent déjà.

## Ce qui a été livré le 2026-08-24

| # | Livré | Où |
|---|---|---|
| 1 | `CommuneTable` — cadre de tirage et test d'appartenance, avec garde-fou sur un cadre vide | [`llm_module/core/residence_zone.py`](../../llm_module/core/residence_zone.py) |
| 2 | Cadre de tirage par **liste de communes** (`EQASIM_PERIMETER=true`, `EQASIM_DEPARTMENTS=31`), `departments` plus en dur, `sampling_rate` calculé sur la population RP 2022 du cadre, paramètre exposé par l'API | [`generate_population.py`](../../eqasim-toulouse/generate_population.py), [`server.py`](../../eqasim-toulouse/server.py), `docker-compose.yml` |
| 3 | Filtre d'admission sur le **périmètre** (trait `residence_zone`), repli sur la bbox **avec alarme** quand le trait manque, comptage des rejets par motif | [`eqasim_loader.py`](../../llm-agents/inputs/population/eqasim_loader.py), [`world/population.py`](../../llm-agents/world/population.py) |
| 4 | 9 tests d'admission + tests du cadre | [`test_perimeter_filter.py`](../../llm-agents/tests/test_perimeter_filter.py), [`test_residence_zone.py`](../../llm_module/tests/test_residence_zone.py) |

**Reste à faire, et c'est de la machine, pas du code** : régénérer la population avec le
nouveau cadre, la ré-enrichir (`make residence-zone`), vérifier que `--check` passe au
code 0, puis rejouer un run. La procédure est dans
[`docs/setup/population.md`](../setup/population.md).

## La suite — les 107 communes des cinq autres départements

Explicitement **hors de ce ticket**, à ouvrir plus tard. Ce qu'elle demandera, déjà instruit :

| # | Poste | Coût |
|---|---|---|
| 1 | `departments` → `["09","11","31","32","81","82"]` | quelques lignes |
| 2 | Liste de communes : les 453 au lieu des 346 | un filtre à retirer |
| 3 | **BD TOPO** pour 5 départements | **≈ +10 Go**, le poste lourd |
| 4 | **BAN** pour 5 départements | ~85 Mo, trivial |
| 5 | Régénération synpp sur six départements | 1–3 h, **pente inconnue** — la mesurer sur 31 + 09 d'abord |
| 6 | Re-mesure et nouveau jeu gelé | un run complet |

Ce qu'elle rapportera : le L1 de répartition de ≈ 9,5 à ≈ 2,7 pt, et une 3ᵉ couronne à
15,3 % au lieu de 10,6 % — c'est-à-dire la strate qui rend le
[ticket 025](ticket_025_dimension_zone_notee.md) défendable.

## Hors périmètre

- **Les cinq autres départements** — cf. « La suite » ci-dessus.
- **Noter la dimension zone** — c'est le [ticket 025](ticket_025_dimension_zone_notee.md),
  qui dépend de celui-ci **et de sa suite**, non l'inverse.
- **Le classement du temps terminal**, toujours métrique (ticket 021, hors périmètre).
- **Le dimensionnement du run** (nombre d'agents, budget LLM) : élargir le bassin ne dit
  rien du nombre d'agents à simuler.

## Sources

- [ticket 020](ticket_020_perimetre_population_cerema.md) — l'axe A9 et son chiffrage.
- [ticket 021](ticket_021_couronne_residence_post_traitement.md) — le trait
  `residence_zone`, qui rend le filtre de périmètre gratuit au chargement.
- [`docs/setup/population.md`](../setup/population.md) — les données d'entrée requises et le
  filtrage bbox actuel.
- [`llm_module/data/commune_couronne.json`](../../llm_module/data/commune_couronne.json) —
  les 453 codes INSEE avec leur couronne — le cadre de tirage de cette version en est le
  sous-ensemble `31*` (346), et le filtre d'admission la liste entière.
