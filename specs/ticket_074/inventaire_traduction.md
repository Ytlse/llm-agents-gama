# Ticket 074 — Inventaire exhaustif des cas à traduire

> Extrait du code le 2026-09-14, pas reconstitué de mémoire.
> **Verdicts rendus le 2026-09-14 : tout est traduit**, les 22 variantes comprises, y compris
> celles qui ne sont plus référencées que par des exécutions archivées.

---

## A. Ce qu'il est INTERDIT de traduire (pas un choix)

| Cas | Où | Pourquoi |
|---|---|---|
| Étiquettes de mode (`car`, `bicycle`, `foot,bus,foot`) | `models.py:192` | `parse_option_modes` les relit **dans le texte du prompt** ; elles alimentent `categorize_mode`, la loss de calibration et `moves.csv` |
| Libellés d'occupation **à la source** | `scripts/synthesis/frames.py:138`, `scripts/progedo_logit/` | Servent de **clés de jointure** |
| Noms propres : arrêts GTFS, lignes, communes | GTFS Tisséo, INSEE | Invariants par langue |
| Motifs (`work`, `home`, `other`) | eqasim | Déjà anglais |

---

## B-1. Prompts système — `prompts.yaml` (22 variantes, ~80 000 caractères)

| Variante | Famille | Taille | Verdict |
|---|---|---|---|
| `expert_m4` **← ACTIF** | experte | 4 142 car. | ✅ traduire |
| `expert_chaine_m7.1` | experte | 7 142 car. | ✅ traduire |
| `expert_chaine_m7` | experte | 7 132 car. | ✅ traduire |
| `expert_chaine_m6` | experte | 5 814 car. | ✅ traduire |
| `expert_chaine_m5` | experte | 6 045 car. | ✅ traduire |
| `expert_m1` | experte | 5 521 car. | ✅ traduire |
| `expert_gem_3.8_v3` | experte | 4 083 car. | ✅ traduire |
| `expert_gem_3.8_v2` | experte | 2 995 car. | ✅ traduire |
| `expert_gem_3.8_v2_neutre_justif` | experte | 2 906 car. | ✅ traduire |
| `expert_gem_3.8_v1` | experte | 2 975 car. | ✅ traduire |
| `prompt_optimise_v5` | experte | 2 985 car. | ✅ traduire |
| `prompt_optimise_v4` | experte | 3 497 car. | ✅ traduire |
| `persona_v5` … `persona_v1` (5) | experte | 3 193 – 3 831 car. | ✅ traduire |
| `expert` | experte | 3 649 car. | ✅ traduire |
| `b0_pristine` | experte | 2 425 car. | ✅ traduire |
| `b_min` | experte | 833 car. | ✅ traduire |
| `minimal_persona` | experte | 1 717 car. | ✅ traduire |
| `prompt_minimal` | **minimale** | 1 628 car. | ✅ traduire |

> **Question** : traduire les 22, ou seulement celles référencées par une expérience à rejouer ?
> Sur les 10 expériences LLM actives, les variantes utilisées sont `prompt_minimal`,
> `expert_gem_3.8_v2`, `expert_gem_3.8_v3` et `prompt_optimise_v4`. Les 18 autres ne sont
> référencées que par des exécutions archivées.

---

## B-2. Gabarits utilisateur — `categories/*/template.md.j2`

| Fichier | Lignes françaises | Nature | Verdict |
|---|---|---|---|
| `itinary_multi_agent/` | 8 (hors commentaires) | Étiquettes (`Destination :`, `Départ :`, `**Options de trajet**`, `**Météo plus tard :**`, `**Trajets suivants prévus aujourd'hui :**`) + 4 consignes de sortie | ✅ traduire |
| `stm_reflection/` | 25 | Prompt de réflexion à court terme, entier | ✅ traduire |
| `ltm_self_reflection/` | 16 | Prompt de réflexion à long terme, entier | ✅ traduire |
| `perception_filter/` | — | à vérifier | ✅ traduire |

---

## B-3. Schémas de sortie — `categories/*/output_schema.json` (9 champs `description`)

| Schéma | Champ | Texte | Verdict |
|---|---|---|---|
| itinary | `agent_id` | « Recopie exactement l'agent_id fourni pour ce persona… » | ✅ traduire |
| itinary | `probabilities` | « Une entrée par option proposée à ce persona, sans exception… » | ✅ traduire |
| itinary | `…index` | « Index de l'option, tel qu'affiché entre crochets. » | ✅ traduire |
| itinary | `…mode` | « Mode de l'option, recopié depuis l'option. » | ✅ traduire |
| itinary | `…probability` | « Probabilité en % (0 à 100) que ce persona retienne cette option… » | ✅ traduire |
| ltm | `reflection` | « Synthèse des patterns et habitudes observés sur plusieurs jours… » | ✅ traduire |
| perception | `summary` | « L'histoire générée à la première personne » | ✅ traduire |
| stm | `reflection` | « Réflexion narrative sur la journée, 200 mots max » | ✅ traduire |
| stm | `concepts` | « 0-5 concepts pour la mémoire à long terme… » | ✅ traduire |

> Les **clés** (`agents`, `probabilities`, `index`, `mode`, `probability`, `reason`) sont déjà
> anglaises. Seules les `description` sont en français.

---

## B-4. Descriptions d'itinéraire — `text_helper/templates/tpl/descriptions/*.j2`

| Fichier | Chaînes françaises | Verdict |
|---|---|---|
| `travel_plan_describe_v2.j2` | `Durée estimée :`, `Temps de trajet :`, `dont … de marche`, `dont … d'accès et de stationnement`, `Distance :`, `Marche jusqu'à '…'`, `[correspondance]`, `Car scolaire liO (gratuit)` | ✅ traduire |
| `travel_plan_describe.j2` / `_lite.j2` | idem, variantes | ✅ traduire |
| `ob_transfer.j2` | `Arrivé·e à destination à pied, fin du trajet.`, `Marché jusqu'à '…'`, `Durée :`, `Météo :`, `— pluie dans la journée :` | ✅ traduire |
| `ob_transit.j2` | `Durée réelle :`, `Météo :` | ✅ traduire |
| `ob_trip_feedback.j2` | `[ ARRIVÉE ] Arrivé·e`, `Durée réelle :`, `Il faudrait peut-être ajuster le planning.`, `À l'heure.` | ✅ traduire |
| `ob_wait_in_stop.j2` | `[ ATTENTE ] Attente à '…' pour le …` | ✅ traduire |

---

## B-5. Récit de persona — `llm_agent.py:221` (`_build_profile_narrative`)

Rendu actuel : `Thibault, 58 ans, Travail à plein temps (seul(e), revenu très faible)`

| Élément | Valeurs | Verdict |
|---|---|---|
| `_income_map` | `Very Low→très faible`, `Low→faible`, `Medium→moyen`, `Medium-Low→moyen-bas`, `Medium-High→moyen-élevé`, `High→élevé`, `Very High→très élevé` | ✅ traduire |
| « ans » | littéral | ✅ traduire |
| « seul(e) » | littéral | ✅ traduire |
| « famille de {N} pers. » | littéral | ✅ traduire |
| « revenu {x} » | littéral | ✅ traduire |

> 💡 **Le plus simple du lot.** `_income_map` n'existe que pour franciser : le supprimer rend
> `income` tel quel (`Very Low`, `Medium`…), déjà anglais dans la population.

---

## B-6. Bulletin météo — `weather_loader.py:367` + `data/weather/Codes meteo.csv`

| Élément | Volume | Verdict |
|---|---|---|
| Littéraux de `weather_to_natural_language` | `Météo : {temp}°C, {label}.`, `Pas de précipitations prévues.`, `Précipitations prévues dans la journée : … mm.`, `{famille} prévue {quand}`, `rafales à … km/h`, `lever`, `coucher` | ✅ traduire |
| Créneaux : `après-midi`, `en soirée`, `soirée`, `le matin`, `la nuit` | 5 | ✅ traduire |
| **Table des conditions** `data/weather/Codes meteo.csv` | **47 libellés** (`Légères averses de pluie à proximité`, `Ciel dégagé/Ensoleillé`, `Neige modérée ou forte avec orage`…) | ✅ traduire |

> ⚠️ **Point d'attention** : les 47 libellés viennent d'un fichier de **données**, pas de code.
> Traduire = ajouter une colonne `Condition_EN` au CSV, ou une table de correspondance.
> C'est le seul cas où la traduction touche un fichier de données.

---

## B-7. Traits de population — `population.json` (v5)

Découverte de l'audit : **la population n'est pas entièrement en anglais.**

| Trait | Valeurs | Atteint le prompt ? | Verdict |
|---|---|---|---|
| `main_occupation` | 7 valeurs FR : `Travail à plein temps`, `Retraité`, `Scolaire (jusqu'au Bac)`, `Étudiant`, `Chômeur/recherche d'emploi`, `Travail à temps partiel`, `Personne au foyer` | ✅ **OUI** | ✅ traduire |
| `personal_bike` | 3 valeurs FR : `Pas de vélo`, `vélo normal`, `VAE` | ❌ non (retiré le 2026-08-26) | ✅ traduire |
| `residence_zone` | 4 valeurs FR : `Toulouse`, `1ere couronne`, `2eme couronne`, `3eme couronne` | ❌ non | ✅ traduire |
| `housing_type` | 5 valeurs FR : `Individuel isolé`, `Petit habitat collectif`, `Grand habitat collectif`, `Individuel accolé`, `Autres` | ❌ non | ✅ traduire |
| `gender`, `income`, `socioprofessional_class`, `professional_activity`, `car_availability`, `employment_sector` | déjà anglais | — | — |

> **Arbitrage du 2026-09-14 : on régénère la population en v6**, et la v5 part à l'archive froide.
> Les enrichisseurs (`enrich_personal_bike.py`, `enrich_residence_zone.py`,
> `enrich_housing_type.py`) doivent être corrigés pour produire de l'anglais, sinon la v6
> reproduit le problème. Les quatre traits français y passent, dormants compris.

> 💡 Pour mémoire — **`main_occupation` est le seul trait français qui atteint le prompt, et l'équivalent anglais
> existe déjà dans le même enregistrement** — `professional_activity`. La correspondance est
> complète :

| FR (`main_occupation`) | EN (`professional_activity`) | N |
|---|---|---|
| Travail à plein temps | Full-Time Worker | 390 |
| Retraité | Retired | 180 |
| Scolaire (jusqu'au Bac) | Child (under 14) / Student | 132 / 33 |
| Étudiant | Student | 90 |
| Chômeur/recherche d'emploi | Unemployed | 71 |
| Travail à temps partiel | Part-Time Worker | 54 |
| Personne au foyer | Other Inactive / Homemaker | 40 / 10 |

**Conséquence :** inverser la préférence ligne 225 de `llm_agent.py` suffirait à angliciser le
prompt sans toucher à la population. **Ce n'est pas la voie retenue** — on régénère —, mais cela
reste le repli si la v6 devait tarder.

---

## Récapitulatif

| Lot | Volume | Difficulté |
|---|---|---|
| B-1 prompts | 4 variantes utilisées / 22 au total | 🔴 le vrai travail |
| B-2 gabarits | 3 fichiers, ~50 lignes | 🟡 |
| B-3 schémas | 9 descriptions | 🟢 |
| B-4 descriptions | 7 fichiers, ~25 chaînes | 🟡 |
| B-5 persona | 5 littéraux + 1 table à supprimer | 🟢 |
| B-6 météo | ~12 littéraux + **47 libellés en CSV** | 🟡 (touche une donnée) |
| B-7 population | régénération v6 + correction de 3 enrichisseurs | 🟡 |
