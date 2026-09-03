# Ticket 028 — Le temps terminal classe encore les points par distance ; l'enquête classe par commune

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité. Ce qui suit est une **spécification**. C'est le ticket « distinct » que le
> [ticket 021](ticket_021_couronne_residence_post_traitement.md) a explicitement renvoyé :
> aligner le **temps terminal** sur la définition communale des couronnes, ce qui demande
> de **ré-exporter** la ressource et non de changer un `if`.

## Le problème, en une mesure

Depuis le ticket 021, la couronne d'un **domicile** est lue sur le persona (`residence_zone`,
posé par liste de communes), et le journal ne recalcule plus rien. Mais le **temps terminal**
— l'accès au véhicule à l'origine, le stationnement à la destination — classe toujours ses
points par **distance à l'hypercentre** (8 / 20 / 40 km, `geo_reference.residence_zone`).
Deux définitions coexistent donc dans la même simulation :

| Ce qui est classé | Définition | Appelant |
|---|---|---|
| le domicile d'une personne | liste de communes (celle de l'enquête) | `move_logger`, scoring, publication |
| l'origine et la destination d'un trajet | anneaux métriques | [`osmnx_direct._make_travel_plan`](../../llm-agents/trip_helper/osmnx_direct.py) |
| les 785 zones fines qui **stratifient les lois** | anneaux métriques sur les centroïdes | [`export_terminal_time.crown_by_zone`](../../scripts/progedo_logit/export_terminal_time.py) |

Le ticket 020 a mesuré l'écart entre les deux définitions : **24,4 % des personas** changent
de couronne, l'erreur est unidirectionnelle (le disque de 8 km mord sur Blagnac, Balma,
Colomiers, Tournefeuille, Ramonville — de 1ʳᵉ couronne dans l'enquête). Le ticket 021 a borné
la conséquence sur le temps terminal — **34 s par bout de trajet** sur le pire couple observé —
et l'a déclarée acceptable *à condition de rester écrite*. L'audit de périmètre
(`make audit-perimetre`, axe A2) la rend donc `à corriger` à chaque exécution, et c'est
voulu : une divergence bornée est une décision, la même divergence non écrite est le bug
de demain.

Un second défaut vit au même endroit (axe A4). Le classement métrique n'a **pas de borne
supérieure** : un point à 114 km du Capitole reçoit « 3ᵉ couronne » et se voit facturer la
loi de cette couronne, alors qu'il n'est dans aucune couronne de l'enquête. La loi `default`
existe pour ça (`TerminalProfile._law_for`), mais rien ne l'atteint jamais et rien ne compte
ces points.

## Ce que ce ticket fait

1. **Les strates des lois** sont recalculées par la table de l'enquête —
   `CouronneTable.couronne_of_zf` (zone fine → secteur de tirage → couronne), mesurée
   identique à 100 % au classement géométrique (ticket 021, lot 0). `meta.crown_definition`
   de `terminal_time_emc2.json` cesse de nommer la fonction métrique.
2. **La ressource est ré-exportée** (`make terminal-time`, `--emit-config`) et le bloc
   `modes:` de `terminal_time.yaml` remplacé. **`version: tt3 → tt4`.** Le bump invalide le
   cache de plans OTP et le cache de décisions LLM — c'est le comportement voulu : des
   décisions prises sur d'autres durées ne doivent pas être resservies. `routing_version: r1`
   ne bouge pas : les durées réseau ne changent pas.
3. **Le classement des points** dans `_make_travel_plan` passe par `CommunalZones.classify`
   (appartenance aux couronnes, emprise normative de l'enquête). Un point **hors périmètre**
   reçoit la loi `default`, **est compté**, et déclenche une alarme sur front montant : ce
   n'est plus un repli silencieux sur la couronne la plus externe.
4. **`geo_reference.residence_zone` survit comme comparateur d'audit**, avec **zéro appelant
   de production**, et un test l'exige — `osmnx_direct` et `export_terminal_time` ne
   l'importent plus, sur le modèle de `test_aucun_repli_a_la_distance_nest_possible`.
5. **L'audit A2** vérifie désormais ce qui compte : que `meta.crown_definition` nomme la
   définition communale, et que le trait `residence_zone` de chaque persona coïncide avec
   `CommunalZones.classify(domicile)`. **A9** ne publie plus de colonne « classement
   métrique ».

## Ce que ce ticket ne fait pas

- Il ne touche pas aux **valeurs** des lois autrement que par la re-stratification : aucune
  minute n'est choisie en regardant une part modale (décision T2 du ticket 013).
- Il ne supprime pas la fonction métrique : `measure_couronne_v7.py`,
  `enrich_residence_zone.audit` et `test_residence_zone.py` s'en servent comme **témoin**,
  et une trace archivée doit rester rejouable.
- Il ne rejoue aucun run. L'effet sur les parts modales se mesure au prochain run scellé.

## Critères d'acceptation

- [x] `terminal_time_emc2.json` porte `meta.crown_definition` communal et un `exported_at`
      du 2026-09-02 ; le nombre de trajets par couronne avant/après est publié dans l'en-tête
      `tt4` de `terminal_time.yaml` (accès : 6 439 / 6 995 / 4 383 / 409 → 6 130 / 10 576 /
      3 447 / 3 370 ; hors strates 6 256 → 959).
- [x] `terminal_time.yaml` est en `tt4`, son bloc `modes:` est celui émis par l'export, et
      `trip_helper.terminal_time._load()` le valide (`data_version() == "tt4"`).
- [x] Aucun module de production n'importe `geo_reference.residence_zone` —
      `test_les_deux_classements_convergent_depuis_tt4` lit les sources de `osmnx_direct` et
      `export_terminal_time`.
- [x] Un point hors périmètre est compté (`terminal_time_out_of_perimeter_total`) et alarmé
      une fois ; il reçoit la loi `default` — `test_hors_perimetre_est_compte_et_tombe_sur_la_loi_default`.
- [x] `make audit-perimetre` rend A2 `conforme` sur `toulouse_population_1000.json`
      (1 021/1 021 traits, temps terminal stratifié par la table de l'enquête).
- [x] `test_terminal_time.py` + `test_move_logger_hypercenter.py` : 70 passés ;
      `test_residence_zone.py` + `test_population_reference.py` : 38 passés.
      `test_les_deux_classements_sont_desormais_distincts` est devenu
      `test_les_deux_classements_convergent_depuis_tt4`, et son docstring dit pourquoi.

## Sources

- [Ticket 020](ticket_020_perimetre_population_cerema.md) — la mesure des 24,4 %.
- [Ticket 021](ticket_021_couronne_residence_post_traitement.md) — la bascule du journal,
  les deux équivalences du lot 0, la divergence de 34 s (§ « Hors périmètre »).
- [Ticket 013](ticket_013_temps_terminal_itineraires.md) — le temps terminal comme paramètre exogène.
- `docs/arch/score-synthesis.md` § classement, `docs/arch/perimetre-population.md` § A2.
