# 2026-08-24 — Ce que la correction des couronnes change, sur `v7`

Trace du **lot 4** du [ticket 021](../../tickets/ticket_021_couronne_residence_post_traitement.md).
Reproduire : `make couronne-v7`.

## Le dispositif

| | |
|---|---|
| Base | jeu gelé **`v7`** (production `tt3`), dernière base de référence de [`avancement.yaml`](../../../scripts/synthesis/avancement.yaml) |
| Décisions | **déjà stockées** — `ab_chaine.db`, node `c00b4318b3` (prompt `expert_chaine`), `gemini-3.5-flash-lite`, T = 0,0 |
| Splits retenus | `train` + `val` — **2 197 lignes de décision, 569 agents** |
| `rank` écarté | 75 agents : découpé en quatre couronnes, ses strates tombent sous l'effectif de publication (n ≥ 5) |
| `test` écarté | aucune éval `v7` stockée ; c'est la réserve de la publication, on ne la dépense pas pour une mesure d'agrégation |
| Appels LLM | **zéro** |
| Population | `experiments/archive/2026-08-19_14_36/population_1000.json`, sha256 `cab69d4b…` — **inchangée**, empreinte revérifiée après la mesure |

**« À décisions constantes » est ici structurel, pas une précaution.** La couronne n'entre
ni dans le narratif du persona (liste blanche de `_build_profile_narrative`) ni dans la clé
du cache de décisions (options + météo + agent/activité/créneau). Le reclassement ne peut
donc déplacer aucune décision : seule l'agrégation change.

## Le résultat

**178 personas sur 930 (19,1 %)** changent de couronne. Par strate :

| couronne | L1 métrique | L1 communal | écart |
|---|---:|---:|---:|
| Toulouse | 58,97 | 59,87 | **+0,90** |
| 1ʳᵉ couronne | 28,12 | 32,39 | **+4,27** |
| 2ᵉ couronne | 27,45 | 29,13 | **+1,68** |
| 3ᵉ couronne | *inexistante* | 41,88 | **strate qui apparaît** |

**Chaque strate se dégrade, et une quatrième apparaît.** C'est l'issue attendue : le ticket
retire un avantage que la mesure n'avait pas mérité.

| indicateur | métrique | communal | écart |
|---|---:|---:|---:|
| **L1 pondéré par le cadrage** (publié) | 41,26 | 43,38 | **+2,11 pt** |
| L1 pondéré par la masse observée (non comparable) | 43,83 | 43,58 | −0,26 pt |

## ⚠ Le piège de pondération, et pourquoi il fallait le voir

La première version de cette mesure pondérait le L1 par la **masse observée** de chaque
strate. Elle rendait **−0,26 pt**, c'est-à-dire une *amélioration* — alors que les quatre
strates se dégradent. Ce n'est pas un gain : c'est un déplacement de poids. Le reclassement
sort 47 agents de Toulouse, la strate la PIRE (L1 ≈ 59), et les verse en 1ʳᵉ et 2ᵉ couronne,
qui sont meilleures (L1 ≈ 30). La moyenne baisse par changement de mélange.

Pondérer par la masse observée compare donc deux classements **dont les poids bougent en
même temps que les strates** : ce n'est pas une règle de score valide pour cette question.
Les parts de population du **cadrage** EMC² (36,4 / 34,1 / 14,2 / 15,4 %) sont, elles,
identiques des deux côtés. C'est la grandeur publiée.

Une asymétrie subsiste et elle est **informative, pas gênante** : sous le classement
métrique, la 3ᵉ couronne n'existe pas du tout sur cette population, donc 15,4 points de
poids de cadrage n'ont aucune strate où aller (poids couvert : 84,6 % contre 100 %). Ce
n'est pas un défaut de la mesure — c'est une partie de l'erreur qu'on corrige.

## Ce que `v7` ne mesure pas

**L'axe A4.** Les 930 personas de `v7` sont filtrés par bbox : **aucun** domicile hors
périmètre. La mesure ci-dessus chiffre donc l'axe **A2 seul**.

A4 est chiffré à part, sur la population de référence (`toulouse_population_1000.json`,
1 021 personas) : **45 domiciles hors périmètre, et les 45 étaient rangés en 3ᵉ couronne**
par le classement métrique. Aucun jeu gelé n'expose ce cas aujourd'hui ; il faudrait un jeu
bâti sur une population non filtrée.

**Le composite comparable ne bouge pas** — par construction : `lieu_residence` n'est ni une
dimension de l'évaluateur des jeux gelés (`age, age_cat, occupation, genre, motif,
dist_cat`) ni une dimension notée de `frames` (`scored: False`). Publier ce zéro comme
résultat serait prendre l'absence de mesure pour une mesure.

## Fichiers

| Fichier | Contenu |
|---|---|
| `agent_couronne.csv` | La table de jointure : les 930 personas avec `zf`, secteur, couronne communale, commune, INSEE, et couronne métrique |
| `parts_modales_par_zone.csv` | Parts modales et L1 par zone sous les deux classements, avec les deux pondérations |
| `resultats.json` | Le rapport complet : provenance des décisions, empreinte de la population, les deux deltas, l'avertissement de pondération, le bloc A4 |
