# LLM Agents & GAMA platform

Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse.

## Architecture

![architecture](docs/paper/figures/architecture.png)

Vue d'ensemble technique : [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Documentation

### Mise en place

| Document | Description |
|----------|-------------|
| [docs/setup/population.md](docs/setup/population.md) | Génération de la population synthétique (EQUASIM) |
| [docs/setup/data-pipeline.md](docs/setup/data-pipeline.md) | GTFS, OpenTripPlanner, OSMnx — données géospatiales |
| [docs/setup/llm-providers.md](docs/setup/llm-providers.md) | Configuration des providers LLM et clés API |
| [docs/setup/quickstart.md](docs/setup/quickstart.md) | Lancer la simulation, ports, scripts disponibles |

### Architecture par sujet

- [Plateforme d'expériences](docs/arch/plateforme-experiences.md) — jeu de déplacements enregistré, décision unique, exécution sans simulateur, registre (ticket 035) ; commandes dans le [guide de démarrage](docs/setup/quickstart.md#plateforme-dexpériences-ticket-035)

| Document | Description |
|----------|-------------|
| [docs/arch/agents-lifecycle.md](docs/arch/agents-lifecycle.md) | Cycle de planification des agents, bootstrap, WebSocket |
| [docs/arch/population-post-traitements.md](docs/arch/population-post-traitements.md) | Population synthétique : les quatre étages de post-traitement entre eqasim et le `traits_json` de l'agent |
| [docs/arch/llm-inference.md](docs/arch/llm-inference.md) | Batching, SWRR, circuit breaker, load balancing LLM |
| [docs/arch/routing.md](docs/arch/routing.md) | OTP (transit) et OSMnx (marche/vélo/voiture) |
| [docs/synthesis/](docs/synthesis/) — pages `<AAAA-MM-JJ_HH-MM>_*.html` | Pages de mesure **horodatées et archivées** (`make terminal-page`) : une mesure sur jeux gelés garde la sienne, aucune n'écrase la précédente — contrairement à `index.html`, régénérée en place parce qu'elle suit l'état courant |
| [docs/traces/](docs/traces/) | Traces archivées des expériences citées ailleurs — `index.html` lisible au navigateur, `README.md` dans le dépôt, `results.json` pour un script. Le store de calibration étant régénérable et hors dépôt, c'est ici que les mesures survivent |
| [docs/arch/protocole-parametre-exogene.md](docs/arch/protocole-parametre-exogene.md) | Méthode pour corriger un paramètre exogène (temps terminal, attente…) **sans rejouer de simulation** : mesurer dans l'enquête, réécrire un jeu gelé, valider par le moteur de calibration, archiver, puis porte de décision |
| [docs/arch/velo-equipement.md](docs/arch/velo-equipement.md) | Équipement vélo du persona : les trois étages appris sur EMC² (stock du ménage, attribution nominative, VAE), et les cibles réellement opposables à une population synthétique |
| [docs/arch/vehicle-chain.md](docs/arch/vehicle-chain.md) | Cohérence de chaîne vélo/voiture : le véhicule reste où l'agent l'a garé |
| [docs/arch/cache-memory.md](docs/arch/cache-memory.md) | Mémoire court/long terme, cache sémantique LLM |
| [docs/arch/llm-module-package-refactor.md](docs/arch/llm-module-package-refactor.md) | CR de juillet 2026 (historique) : restructuration de l'ancien `llm_module` en package (ports, injection, pyproject) |
| [packages/llm_gateway/README.md](packages/llm_gateway/README.md) · [docs mkdocs](packages/llm_gateway/docs/) | **Gateway LLM générique** (paquet `llm-gateway`, ticket 037) : micro-batching, SWRR, disjoncteur, catégories enfichables par entry point, SDK. Aucun mot de mobilité dedans |
| [packages/mobility_core/README.md](packages/mobility_core/README.md) | **Domaine EMC² Toulouse** (paquet `mobility-core`) : couronnes, zones fines, hiérarchie des modes, vélo, logement, cadrage de population et leurs ressources `data/` |
| [packages/mobility_llm/README.md](packages/mobility_llm/README.md) | **Catégories LLM de la mobilité** (paquet `mobility-llm`) : persona, templates, schémas, variantes de prompt, choix modal, métriques métier — le bundle que le gateway charge |

### Observabilité et mesure

| Document | Description |
|----------|-------------|
| [docs/arch/dashboard.md](docs/arch/dashboard.md) | Tableau de bord `make dashboard` : vue d'ensemble du projet, pilotage du run GAMA (lancement/arrêt, progression, top erreurs), providers LLM (quotas temps réel, `make providers`), cibles `make` des sous-projets, tickets et métriques (Docker, run, synthèse, calibration) |
| [docs/arch/monitoring.md](docs/arch/monitoring.md) | Métriques Prometheus, dashboards Grafana 01→08, alarmes & alertes |
| [docs/arch/score-synthesis.md](docs/arch/score-synthesis.md) | Page de synthèse `make synthesis` : simulation, calibration et modèle PROGEDO face à l'enquête EMC². `make common-set-eval` produit la mesure du volet calibration sur le jeu commun et `make heldout-eval` son score de généralisation sur le jeu de test gelé — **les deux seules cibles qui consomment du quota LLM** (chiffrer d'abord : `DRY_RUN=1`) ; `make common-set-predict` produit celle du volet modèle, hors ligne et déterministe. `make model-compare RUN=…` ventile le score d'un run **modèle par modèle** (page dédiée sous `docs/synthesis/models/<run>/`), sans appel LLM. `make logit` estime le **second oracle** (logit multinomial, parité stricte sur les 21 variables), `make klr` la **troisième famille** (régression logistique à noyau RBF + Nyström — non linéaire comme le booster, lisse comme le logit) et `make bi-oracle` publie le score à deux oracles — accord désagrégé du prompt à chaque arbitre, et cohérence du sens de ses variations jugée par les **deux arbitres** : une transition où le logit et la KLR divergent sort du score au lieu d'être imputée au prompt. Poids nuls dans le composite ; tous hors ligne et déterministes. `make forest` ajoute un **témoin** random forest qui dit d'où vient l'avantage du booster sur le logit — arbres ou boosting — et n'écrit que des chiffres, sans modèle sérialisé |
| [docs/arch/report-marche-tc.md](docs/arch/report-marche-tc.md) | Report marche → transports collectifs : les 495 décisions du run épinglé où le LLM a retenu un collectif **alors que la marche était proposée**, rejouées sous dix prompts modifiés et réinjectées dans le volet 1. `make alt-prompt-subset` sélectionne (aucun appel), `make alt-prompt-replay` rejoue (**consomme du quota LLM**, chiffrer avec `DRY_RUN=1`), `make alt-prompt-pages` écrit les dix pages `detail_simulation_26_08_alternative<N>.html` avec le prompt modifié complet |
| [docs/arch/perimetre-population.md](docs/arch/perimetre-population.md) | Périmètre de population : les neuf écarts de base entre la population interrogée par l'enquête EMC² et la population simulée, chacun chiffré et tranché. `make audit-perimetre` rejoue les mesures (code de sortie **3** = axe non mesurable), `make communes-couronnes` produit la correspondance commune → couronne des 453 communes, `make audit-couronnes` mesure les deux équivalences sur lesquelles repose la correction du ticket 021 |
| [docs/arch/controle-population-jeu-de-test.md](docs/arch/controle-population-jeu-de-test.md) | Contrôle et scellement de la population du jeu de test (article AAMAS) : `make control-population POP=…` compare une population aux marges de l'EMC² 2023 (IC95, TOST à ± 1 pt, χ² + V de Cramér, EMD/JSD, croisement couronne × motorisation, journal de recoupement, synthèse des écarts — code **1** s'il reste un « à corriger ») ; `make select-population POOL=… N=1000` tire 1 000 personas pile par allocation stratifiée dans un vivier ; `make seal-population POP=…` contrôle puis produit un dossier immuable (`MANIFEST.yaml`, `CONTROLE.md`) et **refuse** sur un « à corriger ». `make reference-marges` liste les cibles et leur source |

---

## Dépôts externes

| Module | Emplacement local | Dépôt git séparé | Lien avec ce dépôt |
|--------|------------------|-----------------|--------------------|
| EQUASIM Toulouse | `services/eqasim-toulouse/` | repo indépendant (voir [docs/setup/population.md](docs/setup/population.md)) | aucun — dossier exclu du suivi git (`.gitignore`) |
| Calibration de prompt | `prompt_calibration/` | [Ytlse/prompt_calibration](https://github.com/Ytlse/prompt_calibration) | **sous-module** — ce dépôt épingle le commit utilisé |

### Cloner

```bash
git clone --recursive <url-de-ce-depot>
```

Sur un clone déjà fait sans `--recursive` :

```bash
git submodule update --init
```

**Pourquoi un sous-module, et pas une simple copie côte à côte.** `scripts/synthesis/`
importe `calibration.metrics` du dépôt de calibration (par `sys.path`, cf.
`import_calibration()` dans `scripts/synthesis/sources.py`) : la *loss* affichée sur une page
de score est celle du moteur, jamais une copie. `model_compare.py` inscrit d'ailleurs
`prompt_calibration/calibration/metrics.py` au manifeste des sources d'une page — mais rien
n'y disait, avant le ticket 039, **quelle version** l'avait produite. Le sous-module
enregistre ce commit dans le parent : un score republié reste rattachable au code qui l'a
calculé.

Conséquences au quotidien : `git status` du dépôt parent signale désormais que le
sous-module a bougé (nouveau commit, ou modifications non commitées) — c'est le signal, pas
du bruit. Pour déplacer l'épingle après avoir avancé dans `prompt_calibration/` :
`git add prompt_calibration` depuis la racine.

---

## Reference

```
@misc{vu2025modelingrealistichumanbehavior,
      title={Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse}, 
      author={Trung-Dung Vu and Benoit Gaudou and Kamaldeep Singh Oberoi},
      year={2025},
      eprint={2510.19497},
      archivePrefix={arXiv},
      primaryClass={cs.MA},
      url={https://arxiv.org/abs/2510.19497}, 
}
```
