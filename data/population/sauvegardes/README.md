# Sauvegardes de populations scellées

Archives tar.gz, une par scellement. Chacune contient le **dossier scellé** (population,
MANIFEST, CONTROLE, selection, report) **et le vivier** dont il est tiré : sans le vivier, la
sélection n'est pas rejouable — avec, elle l'est à l'octet (`seal_population select --pool
<vivier zone_enriched> --n 1000` redonne le même sha256).

| Archive | sha256 (archive) | Population | Vivier |
|---|---|---|---|
| `population_1000_AAMAS_2026-09-03.tar.gz` | `1003f1c81980ab8db6ba7b8bb4b3d575d7b06137fe0340ffe01467e5ef6614a5` | `population_1000_AAMAS/population.json` sha256 `f67b07772f3dced9d1058cbf1c29f5779425386cc52ced0f778d1a2c233b0a84` | `Temp/4_zone_enriched/toulouse_population_5000.json` (5 063 personas) sha256 `97b019fa81c6598d1023f8e620e883cfe9b5d447b2e6b76ca1708d9ee3f4c033` + brut eqasim `Temp/1_raw/toulouse_population_5000.json` |

Règle : une archive ne se modifie pas ; un nouveau scellement produit une nouvelle archive datée.
| `population_1000_AAMAS_v3_2026-09-03.tar.gz` | `300eb0c365c2d2e0df43250749cb72c7f27d76b27d81375c19d3b273c1901c4f` | `population_1000_AAMAS_v3/population.json` sha256 `8d8bfa3645fa77fb0bcb8aaac8d02bff57395ae06475701f523ef3c772fbb704` — règle `aamas_seal_v3` (ménages, 8 marges) | `Temp/4_zone_enriched/toulouse_population_10000.json` (11 922 personas, pré-imputé, immobiles gardés) sha256 `c4df91db8732ecaeabd1387149bf71adcfb4c249e3cff047bc704ddec7e5f46b` + brut eqasim `Temp/1_raw/toulouse_population_10000.json` |
| `population_1000_AAMAS_v4_2026-09-03.tar.gz` | `b272d27fb8caa8f4486fa3769c78b0198360b92180a2a6a100d0e717ee14bc1b` | `population_1000_AAMAS_v4/population.json` sha256 `9f05c655c3ad2cf4d8c71cc3c34238417718cec742b42ef94a21eb33f694639f` — règle `aamas_seal_v4` (ménages, 9 marges, périmètre des 453 communes sur six départements, polygone communal) | `Temp/4_zone_enriched/toulouse_population_10000.json` (11 329 personas, pré-imputé) sha256 `487ff00c136743d2b9acb95901d9c4c2a3a04c784f4f74fa67493f5bb0a198b5` + brut eqasim `Temp/1_raw/toulouse_population_10000.json` + sélection `toulouse_population_1000_AAMAS[_selection].json` |

> **Compte des déplacements (2026-09-03, soir).** Les dossiers scellés v3 et v4 ont été rescellés avec le
> rapport corrigé (n déplacements pour n activités, retour au domicile compris) — mêmes populations, mêmes
> empreintes. L'archive v4 a été reconstruite avec ce rapport ; l'archive v3 garde l'ancien rapport
> (2,58 / 2,88 au lieu de 3,47 / 3,88), parce que son vivier n'existe plus sur disque et qu'une archive
> sans vivier ne serait pas rejouable. La population qu'elle contient est identique au dossier scellé.
