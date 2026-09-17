# Ticket 081 — Un journal tronqué ne doit jamais produire un score : garde-fou du scoreur et régénération du journal après reprise à froid

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-15, à la suite du [ticket 080](ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
>
> **Catégorie** : Ingénierie & Système (⚙️)
>
> **Touche l'article** : aucune écriture ; mais il conditionne le critère d'acceptation du 080
> « aucun chiffre d'une exécution dont `lecture.total` s'écarte de 3 161 ».

## Le fait

L'exécution `2026-09-12_11_24_28` de `exp_gemini-35-fl_expgem38v2_jtir_pop-1000_AAMAS_v5_t0_nosim`
a été scorée à **5,35** de composite sur **274 lignes** de `moves.csv`, alors que `decisions.jsonl`
en porte 3 299 et que tous les autres bras sont scorés sur 3 161 lignes. Ce chiffre a été repris
dans le ticket 080, le ticket 073 et le chapitre 6 avant d'être identifié comme invalide. Rescoré
sur le journal reconstitué, le bras vaut 6,17.

Chaîne des causes, établie sur `synthese.json` :

1. l'exécution est interrompue par `arret_force` (13/09, 07:04:47) ;
2. la reprise à froid resserre les 3 299 décisions archivées depuis `decisions.jsonl`
   (`resservies: 3299`, `sollicitations: 0`, `duree_s: 1.15`) ; les décisions resservies
   **n'écrivent pas de ligne dans `moves.csv`** (`runner.py`, boucle principale : `moves.ecrire`
   n'est appelé que sur le chemin d'une décision nouvelle, l. ~754) ;
3. `moves.csv` reste tel que le processus initial l'avait laissé : 274 lignes ;
4. `score.calculer` lit `moves.csv` (`frames.read_moves`), trouve 274 lignes, en garde 198 pour
   le premier jour, et écrit `scores.json` sans comparer ce compte à
   `couverture.decides` (3 154) qu'il recopie pourtant dans le même fichier ;
5. `scorer_a_la_cloture` publie la page ; aucun `[ALARME]`.

Il y avait déjà un compte prévu pour cela (`choix_forces.n_scorees` contre `n_execution`),
publié côte à côte « chacun nommant son périmètre » — mais publié, pas comparé.

## Ce que le ticket livre

### Lot A — le scoreur refuse un journal incomplet (règle, pas heuristique)

- Dans `services/llm-agents/experiences/score.py::calculer`, après `frames.read_moves` :
  comparer `stats["total"]` (lignes du journal) à `couverture.decides` de `synthese.json`.
  Si `total < decides − tolérance` (tolérance = les 14 à 19 lignes déjà documentées dans le
  code, à borner à 2 %) : journaliser en **ERROR `[ALARME] Journal des mouvements incomplet`**
  avec les deux comptes, le nom de l'exécution et la cause probable (interruptions présentes
  dans `synthese.json`), et **lever `ValueError`** comme pour une exécution non terminée (R21) :
  pas de `scores.json`, pas de page.
- Le même contrôle s'applique au rescoring hors ligne (`rescorer_tout`) et invalide un
  `scores.json` existant dont le `moves.csv` est incomplet (extension de `scores_perimes`).
- `scores.json` porte un champ `perimetre_verifie: {"lignes_journal": …, "decides": …,
  "ecart": …}` pour que la page et le dashboard puissent l'afficher.

### Lot B — la reprise régénère le journal

- À la reprise (`runner.py`, `reprise = deja > 0`), les décisions resservies passent aussi par
  `moves.ecrire`, **ou** le journal est régénéré intégralement depuis `decisions.jsonl` avant la
  première nouvelle décision. La seconde voie est préférable : elle rend le journal
  indépendant de l'histoire des interruptions et corrige aussi les exécutions déjà archivées.
- Une commande `python -m experiences journal --regenerer <execution>` reconstruit `moves.csv`
  depuis `decisions.jsonl` et la population (les colonnes persona ne sont pas dans les
  décisions ; le script de trace `docs/traces/2026-09-15_09-20_ticket080_…/scripts/rebuild_moves.py`
  les empruntait à une exécution sœur, ce qui n'est pas acceptable en production : il faut les
  lire dans la population scellée de l'expérience).
- La distance de l'itinéraire retenu vient de `presente.payload.agents[0].trajectories[index]`
  ; pour un `choix_unique` sans charge utile, elle est absente et la ligne est écrite sans
  distance (la dimension `distance` l'ignore), jamais inventée.

### Lot C — rescorer et corriger les traces

- Régénérer le journal de `2026-09-12_11_24_28` dans l'archive froide v5 et le rescorer ; le
  composite attendu est 6,17 ± l'effet des 592 distances approximées de la trace.
- Balayer toutes les exécutions (`data/experiences` et l'archive du 14/09) : lister celles
  dont `lecture.total` s'écarte de `couverture.decides` ; les rescorer ou les marquer.

## Tests attendus

- Une exécution dont le `moves.csv` est tronqué à 10 % n'obtient pas de `scores.json`, et le
  journal porte une ligne `[ALARME]` unique (front montant : pas une par appel de rescoring).
- Une exécution complète (écart ≤ 2 %) se score comme avant, `composite` inchangé au centième
  sur les 14 témoins v6 (non-régression).
- Reprise à froid simulée sur une exécution de test : `moves.csv` compte autant de lignes que
  `decisions.jsonl` moins les `inexploitable`.
- `journal --regenerer` sur une exécution complète produit un fichier dont le score est
  identique au centième à celui du journal d'origine.

## Critères d'acceptation

- [ ] Aucun `scores.json` ne peut être écrit pour un journal dont le compte s'écarte de plus de
      2 % des décisions archivées ; le refus est un `[ALARME]` visible par `make error`.
- [ ] Une reprise à froid laisse un `moves.csv` complet.
- [ ] L'exécution du 12/09 est rescorée dans l'archive, et son ancien `scores.json` n'est plus
      lisible comme valide (champ `perimetre_verifie` ou fichier renommé).
- [ ] `docs/arch/score-synthesis.md` (ou le document qui décrit le scoreur) mentionne la règle ;
      entrée au changelog.

## Liens

- [Ticket 080](ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — origine ; le 5,35 et ses conséquences.
- [Ticket 047](ticket_047_offre_a_mode_unique_ce_qui_compte_comme_decision.md) — les deux comptes publiés côte à côte.
- [Ticket 035](ticket_035_plateforme_gestion_experiences_decouplage_spec_fonctionnelle.md) — reprise à froid (spec 05, Q5/Q6).
- Trace : `docs/traces/2026-09-15_09-20_ticket080_idee_directrice_chapitre6/` (hors git).
