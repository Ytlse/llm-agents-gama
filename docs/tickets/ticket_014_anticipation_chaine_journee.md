# Ticket 014 — Anticipation de la chaîne de déplacements dans le choix modal

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité — un `**Statut**` recopié ici se périmerait en silence. Ce qui suit décrit
> **ce qui est dans le code**, vérifiable fichier par fichier.

## Où en est l'implémentation (2026-08-20)

- **Option 1 — livrée.** Météo des tranches restantes de la journée
  (`weather_loader.day_weather_outlook`) et agenda glissant des trajets restants
  (`simulation_controller._build_anticipation` / `_agenda_lines`), injectés par bloc dans
  `itinary_multi_agent.md.j2`, derrière `settings.agent.agenda_anticipation_enabled`
  (défaut `True`, `False` rétablit le prompt myope pour l'A/B). La signature du contexte
  entre dans la clé du cache de décisions (`extra_key`), la colonne « Anticipation » de
  `moves.csv` dit ce que le prompt contenait, et `tests/test_agenda_anticipation.py`
  couvre l'ensemble. Verdict de mesure : run 2026-08-19_13_17 (§ « Run propre »).
- **Correctif appliqué.** La ligne de position des véhicules a été **retirée** du prompt :
  formulée ainsi, elle agissait comme une invitation (+5,5 pts de part vélo, mesure EMC²).
  La règle de chaîne vit désormais dans le prompt système (variante `expert_chaine`) et la
  disponibilité reste portée par le jeu d'options via les verrous.
- **Reste à décider** : options 2 (prompt-journée) et 3 (ancre de boucle) — cette dernière
  est spécifiée jusqu'à l'instrumentation mais rien n'en est écrit, et ses quatre questions
  ouvertes (§ fin de document) sont intactes. Calendrier annoncé : après le gel de `v4` et
  la campagne `ref2`.

## Constat d'origine

Le choix de mode du matin est **myope** : le LLM ne voit que le trajet courant
(persona, destination, heure, météo, souvenirs LTM, options d'itinéraires —
`build_travel_plan_payload`, [llm_agent.py](../../llm-agents/urban_mobility_agents/agents/llm_agent.py)).
Il ne sait pas que l'agent ira à la salle de sport à 18h ni faire une course éloignée.
La cohérence de la chaîne de véhicules est garantie **réactivement** par les trois
verrous du contrôleur (sortie, stationnement, retour — ticket 008, tests
[test_vehicle_chain.py](../../llm-agents/tests/test_vehicle_chain.py)), jamais
**prospectivement** : partir à vélo prive de voiture tout le reste de la journée,
mais rien ne permet à l'agent d'en tenir compte au moment du choix.

## OPTION 1 — Injecter l'agenda restant dans le prompt trajet par trajet

Le choix reste par trajet. On ajoute au payload un résumé des activités restantes
de la journée (« ensuite : sport à 18h à 4 km, retour au domicile à 20h »), le LLM
peut anticiper, et les trois verrous restent en filet de sécurité.

- Décision et mesure inchangées : granularité par trajet, moves.csv, métriques
  L1/EMD/JSD, corpus `itinary_multi_agent` — la calibration reste comparable
  (au changement de checksum de prompt près, qui invalide de toute façon le cache).
- Coût faible : un bloc de plus dans le gabarit, l'agenda est déjà connu du contrôleur.
- Impact cache décisions à évaluer : la clé s'enrichit de l'agenda → espace de clés
  plus grand, taux de hit en baisse (à chiffrer).

### Forme retenue (esquissée par l'utilisateur le 2026-08-19)

Bloc persona enrichi de trois éléments, la notation restant limitée aux options
du **prochain trajet** :

```
--- agent_id=514467 | Planification de la journée du lundi ---
**Contexte du jour :** Météo : 12–13°C, Ciel dégagé/Ensoleillé toute la journée.
Marthe, 35 ans, Travail à plein temps (famille de 2 pers., revenu faible)
Mobilité : conducteur·trice, voiture toujours dispo | abonné·e TC | vélo classique
**État initial :** au domicile ; voiture et vélo garés au domicile.

**Agenda des prochains trajets** :
- [A] 13:09 domicile → leisure (≈10,7 km)   - [C] 16:07 leisure → other (≈4,8 km)
- [B] 15:22 leisure → leisure (≈6,4 km)     - [D] 16:54 other → domicile
[...]

[Si voiture possédée] Votre voiture est au domicile / est avec vous / est restée à <lieu>.
[Si vélo possédé]     Votre vélo est au domicile / est avec vous / est resté à <lieu>.
[Si véhicule sorti]   Ce véhicule doit être revenu au domicile ce soir.

**Options du prochain trajet** ([A] 13:09 domicile → leisure) :
- [0] foot,bus,foot,metro,foot: 57 minutes [...]
- [2] bicycle: 35 minutes [...]
- [4] car: 23 minutes [...]
```

Règles de génération :

- **Agenda glissant** : ne montrer que les trajets restants (au tronçon [C], on
  montre [C] à [F]) — le contexte factuel d'un trajet ne doit pas dépendre de
  l'historique, sous peine de casser le cache.
- **État des véhicules généré depuis `planning_vehicle_at`** à chaque trajet,
  jamais statique : « avec vous » / « au domicile » / « resté à <lieu> ». La
  consigne de retour ne s'énonce que pour un véhicule effectivement sorti.
- Sources : agenda = `identity.activities` + `_road_distance_km` ;
  état véhicules = `planning_vehicle_at` (invariant clé absente ⇒ domicile).

Ce qui est préservé : batching 8 personas/appel (+~8 lignes par bloc), tirage
probabiliste par trajet, verrous en filet de sécurité, granularité de mesure.
Coût de transition : nouvelle version de prompt + changement de forme des
enregistrements du corpus de calibration ⇒ nouveau jeu gelé, à lancer après
`v4`/`ref2` (même logique que le ticket 013, T4).

### Améliorations validées (2026-08-19, les quatre adoptées par l'utilisateur)

1. **Météo aux heures de l'agenda.** La météo du run est rejouée depuis un
   historique déterministe (`weather_loader.get_weather(t)`, appelable à tout
   horaire futur) : mentionner sur chaque ligne d'agenda la météo prévue quand
   elle diffère de celle du départ (« pluie prévue en soirée »). Sans cela,
   l'anticipation est aveugle les jours où elle compte le plus.
2. **Signature d'agenda dans `state_hash`** (leçon ticket 013, caches
   aveugles) : l'état des véhicules transite indirectement par les options,
   mais l'agenda restant n'est dans aucune clé — deux contextes identiques aux
   agendas différents rejoueraient la même décision en silence. Concaténer une
   signature (motifs + seaux de distance + seaux d'heure) dans le `raw` de
   `_make_state_hash`.
3. **Bloc conditionnel.** Ne générer agenda + état des véhicules que pour les
   agents qui ont quelque chose à chaîner : `[Si voiture possédée]` devient
   `[Si conducteur·trice]` (un passager a « voiture toujours disponible », une
   ligne positionnelle le contredirait), et le bloc agenda/véhicules est sauté
   pour les non-motorisés sans vélo — économie de tokens sur une part
   substantielle de la population. **Amendement utilisateur : la météo du jour
   (« Contexte du jour ») reste, elle, générée pour tous les agents** — elle
   informe aussi les choix marche/TC des non-motorisés.
4. **Chiffrer la myopie avant d'implémenter.** moves.csv suffit : part des
   trajets `sortie_bloquee` où le mode bloqué était le plus rapide (colonnes
   « Contrainte de chaîne » / « Plus rapide » / « Modes proposés au LLM »).
   Marginale ⇒ l'amélioration ne vaut pas un jeu gelé ; massive ⇒ c'est le
   critère d'acceptation (elle doit baisser après implémentation).

### Mesure de myopie — référence avant implémentation (2026-08-19)

Run `experiments/current` (référence moves.csv `2026-08-19_09_40`), 3 592
trajets, 1 127 journées-agents :

| Mesure | Valeur |
|---|---|
| Trajets sous contrainte de chaîne | 50,4 % (sortie_bloquee 19,8 % · retour_force 20,1 % · passager 10,5 %) |
| `sortie_bloquee` : distance médiane | 2,81 km (59 % > 2 km, 35 % > 5 km) |
| `retour_force` : distance médiane | 6,04 km (85 % > 2 km) |
| Journées-agents avec ≥1 `sortie_bloquee` | 40,0 % |
| Journées-agents avec ≥1 `sortie_bloquee` sur trajet > 2 km | 25,8 % |
| Mode choisi sur les `sortie_bloquee` > 2 km | TC 292 · voiture 60 · marche 36 · vélo 33 |
| `sortie_bloquee` où le choix n'était pas même le plus rapide restant | 121/712 |

Lecture : **une journée-agent sur quatre subit au moins un verrou de sortie sur
un trajet de plus de 2 km** — l'ordre de grandeur justifie l'implémentation.
Réserve d'interprétation : `sortie_bloquee` est une **borne supérieure** de la
myopie — un agent anticipant parfaitement ne peut pas non plus avoir son
véhicule partout ; une partie de ces verrous est le prix normal d'un choix
amont légitime. Le critère d'acceptation reste : ces parts doivent **baisser**
après l'option 1, pas s'annuler — un zéro serait suspect, pas parfait.

### Impacts secondaires identifiés (2026-08-19)

1. **Recalibration du champion.** Le prompt calibré l'a été sur des contextes
   sans agenda : son optimalité ne se transfère pas. Prévoir une passe de
   recalibration et des mutations ciblant le bloc agenda/véhicules (sinon ce
   bloc reste hors de portée de la calibration). Attendu favorable : les
   références (enquêtes réelles) décrivent des personnes qui anticipent — le
   fit L1/EMD/JSD devrait s'améliorer, argument pour la publication.
2. **+30 à 45 % de tokens d'entrée** (~100–150 tokens par bloc persona de ~190
   aujourd'hui, batch de 8) : à croiser avec les plafonds TPM de
   `providers.yaml` et `make capacity` avant/après — en pénurie, ce budget se
   paie en attente, jamais en dégradation.
3. **Sémantique du « restant » sous précalcul.** Le bootstrap planifie 24 h
   d'un coup : l'agenda restant se définit par la position du trajet dans la
   journée planifiée, jamais par l'heure de calcul — sinon prompts incohérents
   silencieux (agenda complet en milieu de journée, vide au bootstrap).
4. **Colonne de traçabilité dans moves.csv** (bloc anticipation présent/absent
   pour ce trajet) : indispensable pour segmenter l'A/B, les non-motorisés
   n'ayant pas le bloc (même veine que `Contrainte de chaîne`, ticket 008).
5. **Comparabilité / archivage.** Changement de modèle comportemental : runs
   avant/après non comparables ; tout run cité dans la publication doit avoir
   ses traces archivées et committées au moment du run.

Non-impacts vérifiés : rien côté GAMA (changement entièrement backend) ; rien
sur la reproductibilité (agenda et état véhicules déterministes, tirage seedé
inchangé).

**Statut : IMPLÉMENTÉ le 2026-08-19** (décision utilisateur : ne pas attendre
`v4`/`ref2` ; la référence « avant » est le dernier run sain, `2026-08-19_09_40`).
Forme retenue + les quatre améliorations validées :

- `_build_anticipation` / `_agenda_lines` / `_vehicle_status_text` /
  `_chain_stake_modes` (simulation_controller.py), `day_weather_outlook`
  (weather_loader.py) ;
- rendu par bloc dans `itinary_multi_agent.md.j2`, champs déclarés dans
  `AgentSpec` (piège Pydantic : un champ non déclaré est silencieusement perdu
  au `model_dump()`) ;
- signature d'anticipation dans le `state_hash` du cache de décisions
  (`extra_key`, llm/cache.py) — clé inchangée à flag éteint ;
- colonne `Anticipation` dans moves.csv (`agenda` / `meteo` / vide) ;
- flag `settings.agent.agenda_anticipation_enabled` (défaut `True`) ;
- tests : `tests/test_agenda_anticipation.py` (suites complètes llm-agents 238 ✅
  et llm_module 357 ✅).

Critère d'acceptation au prochain run : les parts de `sortie_bloquee` de la
mesure ci-dessus doivent **baisser** par rapport à `2026-08-19_09_40`, pas
s'annuler. Restent à faire après le run : recalibration éventuelle du champion
(impact 1) et passage de `make capacity` (impact 2).

### Premier run avec anticipation — 2026-08-19_11_01 (interrompu, lecture directionnelle)

Run headless conteneurisé, même config que la référence. **Interrompu par un
OOM du conteneur GAMA** (`mem_limit: 8g`, VM Docker 16 Go occupée à ~10 Go par
le reste de la pile) à ~17h30 du jour simulé — la référence du matin tournait,
elle, en GAMA GUI sur l'hôte. Contamination : **4,3 % de décisions dégradées**
(« Default index »), causées par les fournisseurs morts du jour (Mistral et
Cerebras en HTTP 402) laissés en rotation — d'où le levier de blanchiment
ajouté à docker-compose (`PROVIDER_KEYS__mistral="" PROVIDER_KEYS__cerebras=""`).

Sur les décisions de planification antérieures à l'OOM (3 789 trajets, cycle
de planification complet) :

| Mesure | Référence 09_40 | Anticipation 11_01 |
|---|---|---|
| Journées-agents avec verrou > 2 km (critère) | 25,8 % | **19,5 %** |
| Trajets `sortie_bloquee` | 19,8 % | 16,9 % |
| Parts modales | voiture 46,9 · TC 19,1 · vélo 16,9 · marche 14,6 | voiture 45,7 · TC 15,9 · **vélo 22,5** · marche 13,3 |
| Décisions dégradées | 0 % | 4,3 % |

Lecture : le critère d'acceptation est atteint dans le bon sens (−6,3 points,
sans s'annuler). **Point d'attention : le vélo gagne 5,6 points** — mécanisme
plausible (vélo « avec vous », journée enchaînable, beau temps annoncé), mais
l'écart aux parts modales de référence (EMC²) doit être re-mesuré : c'est
l'impact 1 (recalibration) qui tranchera. Chiffres à confirmer par un run
propre : cache de décisions désormais chaud (~2 500 décisions stockées sous
les nouvelles clés), un rejeu est rapide et quasi gratuit en quota.

### Run propre — 2026-08-19_13_17 (VERDICT)

Rejeu complet après correction de l'OOM (VM Docker 24 Go, GAMA 12 Go),
fournisseurs morts blanchis, cache chaud (67 % des décisions servies).
Journée simulée complète en ~18 min, **0,20 % de décisions dégradées** (7,
concentrées dans les premières minutes sur les petits seaux gemma42/qwen),
2 alarmes bénignes. Le run 11_01 est requalifié : ses 19,5 % étaient un
**artefact de dénominateur** (journées-agents gonflées à 1 310 par les
replanifications zombies d'après-OOM) — le run propre tranche.

| Mesure | Référence 09_40 | Anticipation 13_17 |
|---|---|---|
| **Journées-agents avec verrou > 2 km (critère)** | 25,8 % (291/1127) | **25,8 % (259/1002) — INCHANGÉ** |
| Trajets `sortie_bloquee` | 19,8 % | 18,6 % |
| Trajets `retour_force` | 20,1 % | **22,3 %** |
| Parts modales | voiture 46,9 · TC 19,1 · vélo 16,9 · marche 14,6 | voiture 44,4 · TC 16,5 · **vélo 22,4** · marche 14,1 |
| Tokens d'entrée / persona | 835 | 849 (**+1,7 %** — loin des +30-45 % estimés) |
| Décisions dégradées | 0 % | 0,20 % |

**Verdict en deux temps :**

1. **Le critère de myopie n'est PAS amélioré** : la part de journées-agents
   avec verrou > 2 km est strictement inchangée. Lecture cohérente avec la
   réserve « borne supérieure » notée à la mesure : ces verrous semblent
   dominés par des cas structurels qu'aucune anticipation ne peut lever (on ne
   peut pas avoir son véhicule partout), et l'effet est peut-être aussi
   neutralisé par le point 2 — plus de vélos sortis = plus de positions de
   vélo à gérer. À creuser : `retour_force` MONTE (+2,2 pts), signature de
   véhicules davantage sortis.
2. **L'anticipation change réellement les choix** : +5,5 points de vélo,
   robuste sur les deux runs (22,4 / 22,5 %), au détriment des TC (−2,6) et de
   la voiture (−2,5). Mécanisme présumé : la ligne « votre vélo est au
   domicile, avec vous » et la météo du jour rendent le vélo saillant. **C'est
   le vrai effet mesurable du ticket — et il exige l'arbitrage de l'impact 1
   (recalibration / fit EMC²)** avant d'être déclaré amélioration ou biais.

Coût : l'inflation de tokens redoutée est négligeable (+1,7 %/persona).
Incidents du jour documentés : OOM GAMA headless (8 Go insuffisants, VM 16 Go
saturée — corrigés à 12/24 Go), course hypercorn sur le symlink
`GAMA/CityTransport/results` (corrigée dans settings.py), fournisseurs 402
laissés en rotation (levier de blanchiment ajouté à docker-compose).

### Arbitrage EMC² (impact 1) — moteur de synthèse, variante « attendu »

Page régénérée sur le run propre (`make synthesis RUN=experiments/archive/2026-08-19_13_17`,
107 lignes exclues du scoring dont les 7 replis) :

| | Référence 09_40 | Anticipation 13_17 | Cible EMC² |
|---|---|---|---|
| Vélo | 17,9 % (écart +13,8) | **23,7 % (écart +19,6)** | 4,1 % |
| Marche | 13,8 % (−13,0) | 13,0 % (−13,8) | 26,8 % |
| Voiture | 49,1 % (−7,6) | 47,2 % (−9,5) | 56,7 % |
| TC | 19,2 % (+6,9) | 16,0 % (+3,7) | 12,4 % |
| **L1 global** | 41,3 | **46,5 (+5,2)** | — |
| **EMD/JSD composite** | 19,16 | **24,08 (+4,9)** | — |

**L'anticipation dégrade le fit EMC².** Le modèle sur-représentait déjà le vélo
(+13,8 points au-dessus de la cible) ; la ligne « votre vélo est au domicile,
avec vous » amplifie ce biais préexistant (+19,6). Seul l'écart TC s'améliore.
Conclusion d'arbitrage : **le bloc anticipation ne doit pas être déployé en
l'état dans une campagne scorée** — il lui faut une recalibration du champion
AVEC les blocs présents (le catalogue de mutations doit couvrir la formulation
du bloc véhicules, cf. « Améliorations » n°1), ou une reformulation neutre de
la ligne véhicules. Le mécanisme (agenda, météo, position) est validé
techniquement ; c'est sa **formulation** qui est un paramètre de calibration,
pas une constante.

### Correctif du biais (décision utilisateur, 2026-08-19)

- **La ligne « Vos véhicules » est supprimée** du bloc persona (payload,
  gabarit, `AgentSpec`, signature de cache) — sur un cas réel, elle donnait
  50 % de vélo à une retraitée de 87 ans pour une journée de 9 trajets, la
  raison du modèle citant explicitement l'invitation.
- **La règle de chaîne passe au prompt système** : nouvelle variante
  `expert_chaine` (seed `expert`, texte strictement identique + une puce dans
  la matrice de coût : « Chaîne de la journée : en cas d'utilisation d'un
  véhicule personnel (vélo, trottinette, voiture…), pense au stationnement et
  aux déplacements du reste de la journée, jusqu'au retour au domicile »),
  promue via `active:` — le champion `expert` reste intact dans le fichier.
  Cette puce est un **segment calibrable** à couvrir par le catalogue de
  mutations lors de la recalibration.
- L'agenda glissant et la météo du jour restent ; la disponibilité des
  véhicules reste portée par le jeu d'options (verrous). Le changement de
  variante change le checksum actif (`09987f72123e`) : le cache de décisions
  tourne automatiquement sur un répertoire neuf — **prochain run à cache
  froid** (~600-1000 appels LLM), à lancer à quotas frais.
- Attente calibrée : retour de la part vélo vers le niveau de référence
  (~18 %), pas vers la cible EMC² (4,1 %) — le biais vélo de fond est un
  chantier distinct.

## OPTION 2 — Planifier tous les déplacements de la journée dans un seul prompt

Un appel LLM par agent et par jour, le matin : le prompt présente la chaîne complète
d'activités avec les options d'itinéraires de chaque tronçon, le LLM rend un mode
par tronçon, cohérent par construction.

**Pour :**
- Aligné sur l'état de l'art des modèles de demande (choix modal **tour-based** :
  la voiture est une décision de boucle, pas de trajet) — défendable en publication.
- Cohérence de chaîne par construction, verrous réduits à un rôle de garde-fou.
- ~3 à 5 fois moins d'appels LLM par agent-jour — desserre la saturation pipeline.

**Contre :**
- **Explosion combinatoire du prompt** : N tronçons × M options chacun, espace de
  réponse en produit cartésien ; biais de position multiplié, parsing plus fragile,
  prompts beaucoup plus longs (rognant le gain en appels).
- **Les tronçons tardifs sont spéculatifs** : origine réelle, heure réelle de départ
  (retards en cascade, `planning_late_s`), météo du moment — tout est figé le matin.
  Perte de la réactivité intra-journée (feedback de trajet, réflexions).
- **Itinéraires à précalculer pour toute la chaîne** aux heures planifiées : si OTP
  est muet sur un tronçon l'après-midi, il faut replanifier → la complexité revient.
- **Rupture de granularité de toute la chaîne de mesure** : scoring par déplacement,
  corpus de calibration, jeux gelés v3/v4, caches Shapley, comparabilité ref1/ref2.
  C'est un nouveau protocole, pas une évolution.
- **Effondrement probable du cache de décisions** : une clé = une journée entière ;
  les chaînes complètes se répètent beaucoup moins entre agents que les trajets.

## OPTION 3 (hybride) — Ancre de boucle le matin, choix par trajet inchangé

Développée le 2026-08-19. Reproduit la structure **tour-based** des modèles de
demande (le véhicule est une décision de boucle, le mode de chaque tronçon une
décision de trajet) sans toucher à la granularité de mesure.

### Principe : deux niveaux de décision

**Niveau 1 — l'ancre (1 appel LLM léger par agent et par jour).** Au premier
départ du domicile de la journée, avant tout calcul d'itinéraire, le LLM choisit
l'engagement véhicule du jour parmi trois valeurs : `voiture` / `vélo` /
`sans véhicule`. Le prompt est court et **sans aucun itinéraire** (donc sans
appel OTP/OSMnx) : persona, météo du jour, souvenirs LTM, et le **résumé de
l'agenda** — la seule information nouvelle : liste des activités avec heure,
motif et distance à vol d'oiseau × 1,3 depuis le domicile (`_road_distance_km`,
déjà écrit). C'est ici, et seulement ici, que « j'aurai une course éloignée cet
après-midi » pèse sur la décision.

**Niveau 2 — le choix par trajet, inchangé**, sous deux effets de l'ancre :

- **Exclusion dure du véhicule non choisi** : ancre `voiture` ⇒ le vélo n'est
  proposé sur aucun trajet de la journée (il reste au garage) ; ancre `vélo` ⇒
  pas de voiture ; ancre `sans véhicule` ⇒ ni l'un ni l'autre. Implémentation :
  un simple ET avec le verrou de sortie existant, en amont de
  `include_car`/`include_bike` ([simulation_controller.py](../../llm-agents/urban_mobility_agents/simulation_controller.py)).
- **Intention douce pour le véhicule choisi** : une ligne injectée dans le
  prompt par trajet (« Vous avez prévu de prendre la voiture aujourd'hui »),
  qui oriente sans forcer. Le LLM peut prendre le bus au premier tronçon malgré
  une ancre `voiture` ; le verrou de sortie fait alors dégénérer proprement la
  journée en `sans véhicule` — c'est cohérent, pas un bug.

Les **trois verrous du ticket 008 restent intégralement en place** : l'ancre
réduit l'espace des options, les verrous garantissent l'invariant « un véhicule
est un lieu ». Ils deviennent largement redondants (c'est le but) mais restent
le filet contre les chaînes dégénérées.

### Point d'insertion dans l'architecture

Les décisions sont **précalculées en avance de phase** (`precomputed_moves`,
bootstrap 24h puis horizon glissant — [models.py](../../llm-agents/models.py)),
et `planning_vehicle_at` suit déjà la chaîne planifiée, pas la position réelle.
L'ancre s'insère en tête de cette même chaîne :

- Nouveau champ `PersonState.planning_day_anchor: Optional[str]` + jour
  d'application, au même titre que `planning_vehicle_at`.
- Posée par `_precompute_one`/`compute_next_move` quand le trajet planifié est
  le **premier départ du domicile d'un nouveau jour** (attention au bouclage
  J+1 à 86400 s et au report week-end→lundi, déjà gérés à cet endroit).
- Remise à zéro au changement de jour ; `_settle_vehicles_at_home` n'y touche
  pas (rentrer chez soi à midi ne rouvre pas la décision).
- Exclus du dispositif : les **passagers** (`_is_car_passenger` — la voiture ne
  dépend pas d'eux) et les agents ne possédant qu'au plus un véhicule utilisable
  (l'ancre est alors triviale : rien à arbitrer, aucun appel LLM).

### Sortie probabiliste et tirage

Même mécanique que le choix modal probabiliste (ticket 005) : le LLM rend une
distribution sur les trois valeurs, le mode est tiré avec la graine
`mode_draw_seed` — reproductibilité et hétérogénéité de population préservées.

### Caches

- **Cache de l'ancre** : nouvelle collection, clé factuelle petite — agent,
  catégorie de jour (Weekday/Weekend), météo en seaux, **signature d'agenda**
  (motifs + seaux de distance triés). Les agendas se répètent d'un jour sur
  l'autre ⇒ taux de hit élevé attendu.
- **Cache des décisions par trajet : aucune nouvelle clé nécessaire.** L'ancre
  agit en excluant des options, donc elle change `get_code()` des options
  présentées, donc `state_hash` change tout seul
  ([cache.py](../../llm-agents/llm/cache.py)). Deux ancres différentes ne
  peuvent pas se servir mutuellement des décisions en cache. Seule vigilance :
  la ligne d'intention douce modifie le prompt sans modifier la clé factuelle —
  acceptable tant qu'elle est fonction déterministe de l'ancre (elle-même
  corrélée au jeu d'options), à vérifier sur `test_llm_cache_redraw`.
- Le checksum de prompt isole déjà le cache par version : l'ajout de la ligne
  d'intention invalide le cache une fois, comme tout changement de prompt.

### Ce que l'option préserve (l'argument décisif face à l'option 2)

- **Granularité de mesure intacte** : moves.csv, L1/EMD/JSD, corpus
  `itinary_multi_agent`, jeux gelés, caches Shapley — rien ne change de forme.
  Le prompt champion par trajet n'est pas recalibré, seulement enrichi d'une
  ligne conditionnelle.
- **Réactivité intra-journée intacte** : chaque trajet reste planifié à sa
  position réelle, son heure réelle, sa météo du moment.
- **Coût quasi neutre** : +1 appel court par agent-jour, partiellement compensé
  par les trajets devenus mono-option après exclusion (choix sans LLM).

### Instrumentation et validation

- Colonne `day_anchor` dans moves.csv (même veine que `chain_constraint`, A4).
- Compteur Prometheus `DAY_ANCHOR{mode, event}` (posée / cache / triviale /
  dégénérée) ; alarme `[ALARME]` si la part de journées dégénérées (ancre
  véhicule jamais suivie d'effet) dépasse un seuil.
- Validation attendue : baisse de `_vehicle_orphan_returns` et des
  `forced_return` ; parts modales toujours comparées à la référence eqasim ;
  A/B derrière `settings.agent.day_anchor_enabled` (défaut `False`).

### Questions ouvertes

1. **Dure ou douce sur le premier tronçon ?** Le design ci-dessus est doux
   (l'ancre n'oblige pas à prendre le véhicule). L'alternative dure — premier
   tronçon forcé au mode ancré — simplifie mais écrase des chaînes réalistes
   (partir en bus un jour de pluie malgré l'intention voiture).
2. **Le prompt d'ancre entre-t-il dans `prompt_calibration` ?** Nouvelle
   catégorie à calibrer, ou paramètre exogène gelé dans un premier temps
   (l'esprit de T2, ticket 013) ? Recommandation : exogène d'abord, calibrable
   ensuite si l'A/B montre que la formulation pèse.
3. **Agents ne démarrant pas la journée au domicile** (chaîne héritée de la
   veille, véhicule orphelin) : ancre triviale héritée de la position des
   véhicules, ou décision quand même ?
4. **Quand ?** Après le gel de `v4` et la campagne `ref2` — c'est un changement
   de modèle comportemental, il doit être mesuré contre une référence stable.
