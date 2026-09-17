# Ticket 082 — Les couronnes de résidence de la cohorte v6 ne sont pas reconnues : une dimension entière disparaît des pages de score

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-15, à la suite du [ticket 080](ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
>
> **Catégorie** : Ingénierie & Système (⚙️) / Données & Population (🗂️)
>
> **Touche l'article** : aucune écriture. La dimension `lieu_residence` est hors composite
> (`scored: false`) : **aucun chiffre publié ne bouge.** Mais toute lecture par couronne sur v6
> — et notamment le contrôle « hors calibration » du ticket 080 § 3 — est aujourd'hui impossible.

## Le fait

Depuis la bascule anglaise (ticket 074), la colonne `Lieu de résidence` de `moves.csv` vaut
`Toulouse`, `1st ring`, `2nd ring`, `3rd ring` (population v6 : 363 / 341 / 142 / 154 personas).
`scripts/synthesis/frames.py::normalize_place` ne fait que remplacer les espaces par `_` :
`1st_ring` ne joint aucune clé de `cerema_values.yaml` (`1ere_couronne`, `2eme_couronne`,
`3eme_couronne`). Résultat, sur les 15 exécutions v6 scorées au 15/09 : la dimension
`lieu_residence` ne publie que la strate `Toulouse` ; les trois couronnes sont absentes des
`scores.json` et des pages, sans compteur ni avertissement (la ligne tombe dans la voie
« référencée » puisque `normalize_place` renvoie `True`).

`OCCUPATION_MAP` a, lui, été complété pour les libellés anglais (« v6 et après ») ; la
résidence a été oubliée. La même question se pose pour `Type de logement` (les quatre strates
sont présentes sur v6 : vérifier que c'est bien par correspondance et non par hasard) et pour
`hors périmètre` (`population_reference.OUT_OF_PERIMETER`), dont la forme anglaise doit être
alignée si la population v6 peut la produire.

## Ce que le ticket livre

1. **Table de correspondance explicite** dans `frames.py`, sur le modèle d'`OCCUPATION_MAP` :
   `Toulouse → Toulouse`, `1st ring → 1ere_couronne`, `2nd ring → 2eme_couronne`,
   `3rd ring → 3eme_couronne`, plus les libellés v5 (`1ere couronne`, …) et la modalité hors
   périmètre dans ses deux langues. **Un libellé inconnu ne traverse plus** : il est compté
   (`lieu_residence_inconnu`) et journalisé en `[ALARME]` à la première occurrence, au lieu de
   rejoindre silencieusement une clé fantôme.
2. **Audit des autres colonnes traduites** consommées par `read_moves` : `Type de logement`,
   `Motifs de déplacement` (le `MOTIF_MAP` porte déjà `work/education/shop/escort`), `Mode de
   transport Choisi`, `Modes proposés au LLM`. Un test paramétré passe une ligne v5 et une ligne
   v6 et vérifie qu'elles produisent la même clé.
3. **Rescoring des exécutions v6** (`python -m experiences score --toutes`) : le composite ne
   doit pas bouger au centième (dimension hors composite) ; les pages regagnent trois strates.
4. **Reprise du contrôle hors calibration** du ticket 080 § 3 avec les quatre couronnes :
   L1 pondéré par couronne pour `pe04` face aux quatre tabulaires v6 (sur v5 : LLM 23 à 25
   contre 10 à 13 pour les tabulaires).

## Tests attendus

- `normalize_place("1st ring") == ("1ere_couronne", True)` ; `normalize_place("2eme couronne")`
  idem ; `normalize_place("Mars")` → compteur `lieu_residence_inconnu` incrémenté, second
  membre `False`.
- Sur `exp_lgbm_jtir_pop-1000_AAMAS_v6_…_nosim`, `detail.lieu_residence.strates` compte quatre
  entrées avec `n` = **311 / 304 / 125 / 127** (ordre Toulouse, 1ʳᵉ, 2ᵉ, 3ᵉ).
- Composite des 14 témoins v6 inchangé au centième après rescoring.

> **Rectificatif 2026-09-15.** Ce ticket annonçait d'abord `n` = 311 / ≈1 110 / ≈433 / ≈460.
> Ces chiffres mélangeaient deux grandeurs : `n` compte des **agents distincts**, pas des
> lignes, et la coupe au premier jour simulé s'applique avant le comptage. Les trois derniers
> étaient des comptes de lignes bruts du `moves.csv` entier (1 158 / 1 110 / 433 / 460) ; seul
> le premier était un effectif d'agents, et il tombait juste par coïncidence. Après coupe, la
> trame porte 863 / 825 / 316 / 343 **lignes** pour 311 / 304 / 125 / 127 **agents**.

## Critères d'acceptation

- [x] Les quatre couronnes apparaissent dans les `scores.json` et les pages de toutes les
      exécutions v6. **Vérifié le 2026-09-15** : 15 exécutions sur 15, quatre strates peuplées,
      plus aucune masse de résidence en « hors référentiel ». Rescoring `--toutes` : 15 calculées,
      0 rejouées, aucun composite déplacé au centième.
- [x] Un libellé de résidence inconnu produit un `[ALARME]` et un compteur, jamais une clé
      silencieuse. Étendu au logement, à l'occupation et au motif ; alarme à front montant,
      compteur par libellé, et « vide » gardé distinct d'« illisible ».
- [x] Le test v5/v6 paramétré couvre les six colonnes traduites
      (`scripts/tests/test_residence_couronnes_synthesis.py`, 41 cas).
- [x] `docs/arch/score-synthesis.md` documente la table ; `specs/scoring_composite_experiences.md`
      étend R17 ; entrée au changelog.

## Ce que le contrôle a donné (livrable 4)

Trace : `docs/traces/2026-09-15_12-05_ticket082_couronnes_hors_calibration/`.

L1 moyen pondéré par zone, cohorte v6, 867 agents :

| Bras | Couronne | Type de logement | Composite EMD |
|---|---:|---:|---:|
| **pe04** (LLM, gemini-3.5-fl) | **20,67** | **24,40** | 5,30 |
| lgbm | 13,28 | 16,64 | 4,40 |
| mnl | 11,97 | 18,45 | 4,82 |
| rf | 11,44 | 17,35 | 5,05 |
| klr | 11,13 | 15,47 | 4,44 |

Le retard du LLM sur les dimensions hors calibration tient sur v6 : +7,4 à +9,5 points sur la
couronne, quand les cinq bras se tiennent en 0,9 point sur le composite. L'écart « +8 » du
ticket 080 § 0.5 est confirmé sans extrapolation. **Réserve** : une exécution par bras, aucune
mesure de dispersion — le § 3.1 du ticket 080 reste bloquant pour toute phrase publiable.

## Liens

- [Ticket 074](ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) — la bascule anglaise qui a introduit les libellés.
- [Ticket 021](ticket_021_couronne_residence_post_traitement.md) — la modalité `hors périmètre`.
- [Ticket 080](ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — origine ; contrôle hors calibration.
