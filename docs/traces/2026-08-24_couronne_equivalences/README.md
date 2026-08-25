# 2026-08-24 — Les deux équivalences du ticket 021, mesurées

Trace du **lot 0** du [ticket 021](../../tickets/ticket_021_couronne_residence_post_traitement.md).
Elle existe parce que la première rédaction du ticket annonçait un « contrôle décisif, déjà
passé » qui ne l'était pas : ce qui était établi était l'intégrité de la jointure
`ZF → NUM_DTIR`, pas l'accord de deux classements sur des domiciles.

## Ce qui est mesuré, et pourquoi ce n'est pas tautologique

| Porte | Question | Pourquoi la réponse n'allait pas de soi |
|---|---|---|
| A | Les 785 zones fines se rattachent-elles aux 88 secteurs par leur préfixe, et les 88 sont-ils tous atteints ? | L'export vérifiait l'absence d'orpheline, pas la surjectivité |
| B | Classement par **préfixe** == classement par **appartenance géométrique**, sur les 785 zones ? | Deux chemins distincts : un rattachement par code contre une jointure spatiale |
| C | Le même accord sur les 1 021 **domiciles** de la population de référence ? | Un domicile n'est pas un centroïde de zone : il peut tomber près d'une frontière |
| D | « Hors de la **couche de zones fines** » == « hors des **quatre couronnes** » ? | Deux emprises construites séparément : union des 785 zones fines contre dissolution des 88 secteurs |
| E | Le classement recalculé ici retrouve-t-il la colonne `zone_communale` du ticket 020 ? | **Recoupement indépendant** : l'autre chemin, mesuré le 2026-08-24, sur les mêmes personas |
| F | La **commune** est-elle reproductible depuis le code de zone fine ? | `zf_zones.gpkg` ne porte ni `INSEE` ni `COM` : c'est ce qui décide du grain de la table du lot 1 |

## Résultat — les sept portes passent

| Porte | Mesure |
|---|---|
| A | 88 secteurs, 88 préfixes distincts, **0 zone orpheline**, **0 secteur sans zone**, aucune modalité hors `COURONNES` |
| B | **785 / 785 = 100,00 %**, au centroïde publié comme au point représentatif du polygone |
| C | **1 021 / 1 021 = 100,00 %** — répartitions identiques : Toulouse 376, 1ʳᵉ 366, 2ᵉ 141, 3ᵉ 93, hors périmètre 45 |
| D | 45 hors couche, 45 hors périmètre, **différence symétrique vide**. Couverture du resolver : 976 / 1 021, 4,41 % dehors, alarme non déclenchée (seuil 15 %) |
| E | **1 021 / 1 021** d'accord avec `agents_reclassement.csv` du ticket 020 |
| F | **0** zone fine sans `INSEE`, **0** écart de commune sur les 976 domiciles du périmètre |

**Conséquence pour le ticket.** Les lots 1 à 5 gardent la forme prévue. En particulier :

- le classement par préfixe peut servir de chemin de production, et le test du lot 1 le
  contrôlera contre la géométrie sur ressources committées — c'est exactement la porte B,
  reproduite au grain zone fine ;
- `resolve() is None` peut servir de détecteur de hors-périmètre, l'emprise normative
  restant le géojson des couronnes ;
- la table du lot 1 se publie bien au grain **zone fine** avec `insee` et `commune` : la
  porte F établit que la commune est reproductible par ce chemin, ce qu'une table
  `secteur → couronne` de 88 lignes n'aurait pas permis.

Ce que le lot 0 **ne** dit pas : rien sur A4 hors de cette population. Les 45 domiciles hors
périmètre n'existent que sur `toulouse_population_1000.json` ; les populations bbox-filtrées
(dont celle des jeux gelés `v5`–`v8`) n'en contiennent aucun.

## Reproduire

```
make audit-couronnes TRACE=docs/traces/2026-08-24_couronne_equivalences
```

Codes de sortie : `0` les portes passent, `2` une porte échoue — le ticket est à reconcevoir,
`3` une porte est **NON MESURABLE** (une porte non mesurée est une porte qui passe, le script
refuse de le taire), `1` ressource versionnée absente.

Les portes A, B et F exigent aujourd'hui la couche SIG d'accès restreint
(`data/PROGEDO 2023/`, lil-1750). Après le lot 1 elles liront la table versionnée
`llm_module/data/zf_couronne.json` et l'audit tournera sans données restreintes — le script
préfère déjà la table quand elle existe.

## Fichiers

| Fichier | Contenu |
|---|---|
| `couronne_equivalences.json` | Le rapport complet : compte de chaque porte, listes de désaccords (vides), couverture du resolver, source du classement par secteur |
