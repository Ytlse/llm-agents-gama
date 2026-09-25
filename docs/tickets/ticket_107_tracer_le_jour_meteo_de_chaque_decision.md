# Ticket 107 — Tracer le jour météo de chaque décision

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-23, pendant la relecture de la remarque 8 de l'article court
> (« évaluation sur une seule journée »), à la demande de l'auteur.

---

## 1. La question, en une phrase

Une expérience du banc doit pouvoir dire, **décision par décision**, de quel jour vient le
bulletin météo que l'agent a lu, et de quel jour vient l'offre de transport qu'on lui a servie.

## 2. Ce qui est tracé aujourd'hui

| Quoi | Où | Suffisant ? |
|---|---|---|
| La politique de calendrier (`aleatoire`, graine 42) | `experience.yaml` | Oui, pour rejouer |
| Le tirage actif ou non | `identite_run.json`, `meteo_par_agent` (booléen) | Non |
| Le jour de l'offre de transport | nom du jeu (`…_20260316_…`), `jeu.jour_simule` | Implicite |
| **La date météo tirée pour un persona** | **nulle part** | **Non** |
| **La date réelle du relevé météo lu** | **nulle part** | **Non** |

La date se recalcule, puisque le tirage est déterministe (`weather_draw.date_meteo(person_id,
graine, jours)`). Mais il faut alors avoir le code, la bonne graine et la bonne fenêtre. Un
lecteur du package de reproductibilité ne peut pas le lire dans les sorties.

## 3. Trois dates, pas une

La relecture a montré qu'une décision porte en réalité **trois** dates distinctes :

1. **Le jour de l'offre** : horaires et itinéraires du jeu gelé, le lundi 2026-03-16 pour la
   cohorte v6.
2. **Le jour tiré** : un couple (mois, jour) pris parmi les jours ouvrés de la fenêtre de
   collecte de l'EMC², du 2022-09-20 au 2023-02-18
   (`scripts/data/population/population_emc2_2023.yaml:28-40`,
   `llm_agent.py:_weather_eligible_days`).
3. **Le relevé météo lu** : `get_weather` indexe `data/weather/meteo_toulouse_12_mois.csv` par
   (mois, jour) seulement (`weather_loader.py:109`, `:218`), et ce fichier couvre **mai 2025 →
   avril 2026**. Le bulletin d'un jour tiré « 14 novembre » est donc celui du **14 novembre
   2025**, pas celui du 14 novembre 2022.

⚠ Conséquence pour l'article court, § 4.1 : la phrase « The weather and the transport offer are
those of a weekday of the survey's collection period, from September 2022 to February 2023 »
est vraie pour la **saison** (mois et jour), fausse pour l'**année** des relevés comme pour celle
de l'offre. Le texte relève de l'arbitrage de l'auteur. Ce ticket ne le réécrit pas, il rend le
fait lisible.

⚠ Deuxième effet, plus fin : les jours ouvrés sont calculés sur le calendrier 2022-2023, puis
lus en 2025-2026. Un mardi 2022 correspond à un autre jour de la semaine en 2025. La météo n'a pas
de jour de semaine, donc c'est sans effet sur le bulletin. C'est à signaler, pas à corriger.

## 4. Ce qu'il faut livrer

- **A1.** Dans chaque enregistrement de décision d'une expérience, trois champs :
  `jour_offre` (ISO), `jour_meteo_tire` (MM-JJ, ou ISO de la fenêtre), `jour_meteo_lu` (ISO de
  la ligne du CSV effectivement lue). Plus `source_date_meteo` : `tiree` | `declaree`
  (ticket 058, `dates_meteo.json`) | `horloge` (tirage inactif ou repli).
- **A2.** Le repli sur l'horloge simulée (`llm_agent.py:680`, `[ALARME]`) doit apparaître
  dans ces champs, et pas seulement dans le journal : une décision servie avec la mauvaise
  météo doit se compter.
- **A3.** Dans `identite_run.json` : la fenêtre effective (bornes, jours de semaine, nombre de
  jours éligibles), l'empreinte sha256 du CSV météo, et ses dates de début et de fin.
- **A4.** Un compteur en fin d'exécution : nombre de dates météo distinctes servies, et
  répartition par mois. Journalisé en INFO quand tout va bien, en `[ALARME]` si une seule date
  couvre plus de la moitié des décisions (signe que le tirage ne tourne pas).

## 5. Critères d'acceptation

- [ ] Sur une exécution rejouée de la cohorte v6, `jour_meteo_tire` égale
      `date_meteo(person_id, 42, jours)` pour 100 % des décisions.
- [ ] `jour_meteo_lu` pointe une ligne existante du CSV pour 100 % des décisions.
- [ ] Un test force le repli (`_weather_eligible_days` qui lève) et vérifie
      `source_date_meteo == "horloge"` sur la décision.
- [ ] Aucun champ ajouté ne change un score : le composite d'une exécution rejouée est
      identique au bit près.

## 6. Hors périmètre

- Changer le fichier météo pour les relevés 2022-2023. C'est une autre décision, qui toucherait
  tous les scores publiés.
- Réécrire la phrase du § 4.1 de l'article court. Elle passe par l'auteur.

DÉPEND DE : aucun ticket.
