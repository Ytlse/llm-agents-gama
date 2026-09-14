# 8. Limites et implications hybrides (brouillon)

<!-- Dernière mise à jour : 2026-09-12 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), § 6, Concept & Perspectives — « Concept & Perspectives : L'Architecture Hybride en Cascade ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Trois choses à reprendre avant d'en faire un chapitre : le vocabulaire « Tier 1 / 2 / 3 », que les chapitres rédigés remplacent par *exploratory / robust / transferable* (étapes de certification de SILICA) ; les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Ni maître anglais ni rendu LaTeX à ce stade.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

**À écrire — [ticket 049](../../../tickets/ticket_049_itineraire_mixte_limite_a_publier.md) :**
ce chapitre ne dit pas encore la **limite de l'itinéraire mixte**. OTP est interrogé *mode par
mode* : le jeu d'options présenté à l'agent ne contient aucun trajet combiné — ni « voiture
jusqu'au parking-relais puis métro », ni « vélo jusqu'à la gare puis TER » — alors que l'enquête
en compte et les range presque tous en transports collectifs. Deux paragraphes à ajouter, qui
doivent porter **les deux moitiés**, l'une sans l'autre étant trompeuse :

1. **L'amplitude, par strate.** 1,41 point de part modale globalement, mais **64 %** de la cible
   TC hors d'atteinte au-delà de 50 km, **59 %** sur 20-50 km, **31 %** en 2ᵉ couronne. Le seul
   chiffre global est trompeusement rassurant.
2. **Le sens.** Mesuré le 2026-09-12 sur 17 exécutions archivées (trace
   `docs/traces/2026-09-12_10-10_sens_limite_rabattement/`) : la limite **ne pénalise pas** le
   modèle aujourd'hui, car la simulation sur-produit déjà les transports collectifs sur les
   longues distances. La neutraliser n'aurait rien rapporté aux bras LLM (0,000 pt) et **+2,2 pt**
   aux deux baselines dégénérés. Une limite publiée sans son signe laisse croire au lecteur
   qu'elle joue contre le modèle.

Deux points à trancher avant d'écrire : la version `en/` de ce chapitre **n'existe pas** (le
dossier s'arrête au chapitre 2), et écrire le sens de la limite expose la sur-production de TC
sur les longues distances (36 % contre une cible de 13 % sur 20-50 km), qu'aucun ticket ne couvre
à ce jour.

---

### 6.1 Formulation de la Cascade comme Perspective de Recherche
Au terme de cet audit empirique, nous formalisons la prospective d'une **architecture hybride en cascade** pour concilier la vitesse et la fidélité statistique de LightGBM avec l'intelligence contextuelle du LLM :

```
                          [ Requête de Déplacement ]
                                       │
                                       ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ÉTAGE 1 : FILTRE DÉTERMINISTE (Règles Physiques & Légales)             │
 │ - Pas de permis ? Pas de voiture possédée ? Véhicule garé ailleurs ?   │
 │ ──► Élimination préalable stricte des alternatives impossibles         │
 └────────────────────────────────────┬───────────────────────────────────┘
                                      │ Options éligibles
                                      ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ÉTAGE 2 : ORACLE STATISTIQUE LIGHTGBM (90 % du flux nominal)           │
 │ - Trajet de routine, réseau nominal, météo standard, certitude ML      │
 │ ──► Décision instantanée, 0 token, alignement EMC² garanti             │
 └────────────────────────────────────┬───────────────────────────────────┘
                                      │ Détection d'événement / Exception
                                      ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ÉTAGE 3 : AGENT GÉNÉRATIF LLM (10 % des situations complexes)          │
 │ - Événement d'actualité presse, alerte météo, bagage qualitatif,      │
 │   arbitrage ménage ou forte incertitude ML (max P_mode < 0.50)         │
 │ ──► Raisonnement sémantique, négociation, mise à jour mémoire J+1      │
 └────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Cadre Comparatif Multidimensionnel

| Dimension évaluée | Simulation 100 % LightGBM | Simulation 100 % LLM | Architecture Hybride en Cascade |
|---|---|---|---|
| **Temps d'exécution (10 000 trajets)** | $< 1\text{ seconde}$ | $\approx 45\text{ minutes}$ | $\approx 4\text{ minutes}$ (Gain $10\times$) |
| **Volume de requêtes / Coût Tokens** | $0\text{ token}$ | $10\,000\text{ requêtes}$ | Réduction de $90\,\%$ ($1\,000\text{ req}$) |
| **Fidélité Macro (Erreur L1, argmax)** | $7,30\text{ pt}$ — $2,69\text{ pt}$ en masse de probabilité, non comparable | Dégradée ($29,81\text{ pt}$) | À mesurer |
| **Rappel sur classe minoritaire (vélo)** | $13,8\,\%$ — angle mort assumé | À mesurer | À mesurer |
| **Réaction aux Actualités & Hystérésis**| Nulle (Aveugle / Amnésique) | Réaliste (Inertie cognitive) | **Préservée sur les 10 % d'exceptions** |

### 6.3 Échelle du Foyer et Chaînes Spatiales
La prospective s'étend à l'intégration des contraintes intra-ménage : arbitrage du véhicule partagé, dépose scolaire et conservation stricte de la chaîne spatiale des véhicules (`vehicle-chain.md`).

---

### Tickets associés à ce chapitre
- [Ticket 049](../../../tickets/ticket_049_itineraire_mixte_limite_a_publier.md) — L'itinéraire mixte n'existe pas : publier la limite, et dire dans quel sens elle penche
- [Ticket 060](../../../tickets/ticket_060_formalisation_architecture_hybride_et_perspectives.md) — Formalisation de l'architecture hybride en cascade, cadre comparatif et perspectives
