# Traces — A/B du temps terminal et de la règle de chaîne (2026-08-24)

Résultats **agrégés** extraits du store de calibration, qui est lui-même
gitignoré (régénérable). Généré par `prompt_calibration/archive_ab.py` : ne pas
éditer à la main.

- store d'origine : `calibration_results/ab_chaine.db` (volatil)
- archivé le : 2026-08-24T09:58:54+00:00

## Comment relire ces mesures

Les deux A/B se rejouent **gratuitement** tant que le store existe (cache
content-addressed) ; s'il a disparu, les relancer coûte ~15 appels LLM par bras :

```bash
cd prompt_calibration
../llm-agents/.venv/bin/python ab_chaine.py   --config run_ab_chaine.yaml \
  --dataset rank --dry-run      # prompt à jeu constant
../llm-agents/.venv/bin/python ab_terminal.py --dry-run
                                # temps terminal à prompt constant
```

Les jeux `v6` et `v7` sont dérivés de `v5` par `rewrite_terminal_time.py`
(lui aussi gitignoré) : la commande de dérivation est dans leur
`DERIVATION.md`, et le contenu est reproductible (tirage par hachage).

**Trois bras, pas deux, et la colonne du milieu est celle qui compte.**
`v5` porte les temps de `terminal_time.yaml` ; `v6` aligne la **voiture**
seule sur EMC² ; `v7` aligne **voiture et vélo**, soit le périmètre exact de
ce qui est parti en production sous `tt3`. `v6` mesurait moins que ce qui a
été livré : l'écart `v6` → `v7` est ce que l'alignement du vélo rend du gain,
et il n'est pas petit.

## Résultats

| branche | jeu | composite | global | âge | genre | motif | distance | marche | vélo | voiture | TC | personas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ab_chaine_expert` | rank (v5) | **26.79** | 7.72 | 7.25 | 7.93 | 9.06 | 9.34 | 16.64 | 19.39 | 38.39 | 25.58 | 75 |
| `ab_chaine_expert_chaine` | rank (v5) | **27.00** | 7.80 | 8.28 | 8.16 | 8.21 | 8.37 | 16.07 | 19.50 | 38.88 | 25.55 | 75 |
| `ab_chaine_expert_chaine` | rank (v6) | **22.48** | 4.84 | 7.55 | 5.37 | 9.13 | 11.62 | 14.57 | 15.16 | 48.86 | 21.41 | 75 |
| `ab_chaine_expert_chaine` | rank (v7) | **24.83** | 5.78 | 8.44 | 6.18 | 9.50 | 10.95 | 13.48 | 16.28 | 47.69 | 22.56 | 75 |

Référence EMC² globale, pour lecture : marche 26,0 · vélo 4,0 · voiture 55,0 · TC 12,0 %.

Temps terminal moyen par option, par mode : voiture 7,93 → 0,55 min (÷ 14,4), vélo 2,00 → 0,29 min (÷ 6,9). La moyenne **toutes options confondues** (5,83 → 0,46) dilue les deux et ne décrit ni l'un ni l'autre.

## Régime de mesure

- `prov=google_gemini35|model=gemini-3.5-flash-lite|temp=0.0|policy=weighted|opt=prod|ds=v5` — modèle `gemini-3.5-flash-lite`, T=0.0
- `prov=google_gemini35|model=gemini-3.5-flash-lite|temp=0.0|policy=weighted|opt=prod|ds=v6` — modèle `gemini-3.5-flash-lite`, T=0.0
- `prov=google_gemini35|model=gemini-3.5-flash-lite|temp=0.0|policy=weighted|opt=prod|ds=v7` — modèle `gemini-3.5-flash-lite`, T=0.0

Le comparatif est **apparié** dans les deux cas : mêmes personas, mêmes jeux
d'options des deux côtés. L'effectif opposable est celui des personas
**distincts**, pas des décisions — les déplacements d'un même agent partagent
son profil.

## Ce que ces mesures ne disent pas

Elles portent sur des jeux **gelés** : elles disent ce que le modèle choisirait
dans ces situations, pas ce qu'une simulation produirait. La réécriture du temps
terminal ne rejoue ni l'offre d'options ni les chaînes de véhicule, où le choix
d'un jour se répercute sur les offres du lendemain. Un run neuf reste nécessaire
pour la mesure de bout en bout.
