# Ticket 088 — Jeu corrigé et rejeu complet : le départ du matin était daté du lendemain

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-16 sur décision de l'auteur, à la suite du [ticket 057](ticket_057_audit_et_reflexion_double_lecture_tabulaire.md).
>
> **Nature du ticket** : **reprise de substrat.** Le correctif de code est fait ; ce ticket porte
> ce qu'il entraîne — un jeu de déplacements à re-préparer, et toutes les mesures à rejouer.

---

## 1. Ce qui était faux

`experiences/jeu.py:deplacements_attendus()` résolvait l'heure de départ contre
`maintenant = base + precedente.start_time`. Pour la première paire de la journée, `precedente`
est l'activité « home », qui **enjambe minuit** — `start_time` 72 449 s (20:07) chez la
personne 609 de la v6. Le curseur se posait donc à 20:07 du jour simulé, et la cible du matin
(08:59) lui étant antérieure, la ligne de report `if depart < maintenant: depart += 86400`
datait le départ du **lendemain**.

**797 des 894 personas mobiles** de la cohorte v6 étaient dans ce cas, soit 866 déplacements
sur 3 299.

### Deux conséquences, pas une

1. **Le périmètre de score.** La coupe au premier jour simulé écartait ces 866 décisions — des
   départs libres, en voiture une fois sur deux. Traité et clos au ticket 057 : la coupe ne
   s'applique plus qu'aux journaux qui portent des répétitions, et les 25 exécutions ont été
   rescorées hors ligne.
2. **Le substrat lui-même.** C'est l'objet de ce ticket, et il ne se corrige pas par un
   rescoring. Deux choses ont été calculées avec la mauvaise date :
   - **l'offre d'itinéraires du jeu enregistré.** `jeu.py:preparer()` appelle
     `trip_helper.get_itineraries(departure_time=dep.depart_ts)` : les 797 premiers
     déplacements du jeu `population_1000_AAMAS_v6_20260316_EN` portent une offre calculée pour
     le **17 mars**. Tous les décideurs l'ont lue, tabulaires compris ;
   - **la météo servie au prompt.** `_build_anticipation` appelle
     `day_weather_outlook(departure_time)`, et les deux jours diffèrent : `afternoon 12°C ·
     evening 13°C` le 16 contre `afternoon 15°C · evening 16°C` le 17. Seuls les bras à
     décideur LLM sont concernés — le décideur `modele` ne lit jamais `ctx.anticipation`.

## 2. Le correctif, déjà appliqué

Une activité qui enjambe minuit se reconnaît à son `start_time` postérieur à son `end_time` ;
le curseur recule alors d'une journée. La correction ne touche rien d'autre : la règle de
report continue de jouer quand la cible précède réellement l'arrivée.

Vérifié sur la cohorte v6 : **3 299 déplacements, tous dans le jour simulé**, dont les 894 de
rang 0. Trois tests (`tests/test_057_horodatage_depart_du_matin.py`), 1 408 tests de la suite
`llm-agents` au vert.

## 3. Ce que ce ticket demande

### 3.1 Re-préparer le jeu
Un jeu neuf sur la même cohorte et la même date, avec les horaires corrigés. Il portera une
empreinte différente, donc un nom d'expérience différent (`jeu-…`). L'ancien jeu
`population_1000_AAMAS_v6_20260316_EN` n'est pas détruit : il reste la source des mesures
publiées jusqu'ici, et c'est ce qui permettra de chiffrer l'écart.

**Fait le 2026-09-16** — `population_1000_AAMAS_v6_20260316_EN_c`, clos à 15:32, empreinte
`e8f9eab14fb4…`, 4 041 s de préparation (cache froid : 3 299 déplacements à calculer contre
1 489 lors de la dernière reprise du jeu précédent). Le segment de nom devient
`jeu-20260316_EN_c`.

Le périmètre est identique au déplacement près — la correction a redaté et recalculé, elle n'a
rien ajouté ni retiré :

| | ancien jeu | jeu corrigé |
|---|---:|---:|
| déplacements attendus | 3 299 | 3 299 |
| couverts | 3 161 | 3 161 |
| personnes avec déplacement | 869 / 894 | 869 / 894 |
| `origine_egale_destination` | 138 | 138 |
| erreurs de moteur | 0 | 0 |
| **départs datés du 17 mars** | **866** | **0** |
| dont rang 0 | 797 | 0 |

### 3.2 Mesurer l'écart d'offre avant de tout relancer
Le 16 et le 17 mars 2026 sont deux jours ouvrés consécutifs, lundi et mardi : les horaires TC
peuvent être identiques. **Comparer les deux jeux avant de rejouer** dit combien de
déplacements voient réellement leur offre changer, et donc si le rejeu des témoins
déterministes s'impose ou non. Mesure gratuite, à faire en premier.

**Mesuré le 2026-09-16 — l'écart n'est pas nul.** Trace complète dans
`docs/traces/2026-09-16_15-33_ticket088_ecart_offre_jeux_v6/`.

| mesure | déplacements | part |
|---|---:|---:|
| départs redatés (17 mars → 16 mars) | 866 / 3 299 | 26,3 % |
| dont rang 0 | 797 | |
| nombre de propositions différent | 14 | 0,4 % |
| ensemble des modes offerts différent | 9 | 0,3 % |
| **signature d'offre différente** | **95** | **2,9 %** |

La signature retient par proposition le mode et la ligne TC de chaque leg, la durée à la
minute, la distance à 10 m : deux offres de même signature sont interchangeables pour tout
décideur. L'intuition était bonne — les deux jours ouvrés se ressemblent — mais 95 déplacements
sur 3 299 changent d'offre, soit 11 % des redatés.

Le second canal est indépendant et touche **les 866, pas les 95** — vérifié, pas repris :

    16 mars 08:21 UTC : evening 13°C, Clear/Sunny
    17 mars 08:21 UTC : evening 16°C, Clear/Sunny

**Conséquence.** La porte de sortie du critère de clôture (« l'écart d'offre montré nul et le
rejeu déclaré inutile ») est fermée. Les bras LLM sont atteints par les deux canaux, les
témoins déterministes par le seul premier.

### 3.3 Câbler le témoin random forest — avant le rejeu, pas après

`exp_rf_…_EN_nosim` porte un chemin de population absolu de l'hôte là où les trois autres
témoins portent le chemin conteneur, et n'est lançable que depuis l'hôte. La cause est écrite
dans `scripts/progedo_logit/lancer_experience_rf.py` : la famille RF n'est pas déclarée, le
lanceur remplace `load_policy` dans l'espace de noms au moment de l'exécution, et il réécrit le
chemin de population (`_chemin_population_hote`) à chaque définition. Le script dit lui-même ce
qu'il faudrait faire — une entrée dans `FAMILLES` (`experiences/decideur_modele.py`) et une dans
`POLICY_FORMATS` / `load_policy` (`scripts/synthesis/model_on_common_set.py`) — et pourquoi il
ne l'a pas fait : le ticket 043 modifiait ces deux fichiers en parallèle. **Le 043 est
terminé ; l'obstacle a disparu.**

Le faire **avant** le rejeu, pour que les quatre témoins soient rejoués par le même chemin —
c'est la parité stricte que le § 4.4 du chapitre 4 affirme. Ensuite, normaliser le chemin de
population des deux définitions `rf` et retirer `_chemin_population_hote` du lanceur.

#### Fait le 2026-09-16 — la famille est déclarée, la forêt reste sur l'hôte

**Le câblage.** `rf_mode_choice_policy` entre dans `FAMILLES`
(`experiences/decideur_modele.py`) et dans `POLICY_FORMATS` avec son aiguillage dans
`load_policy` (`scripts/synthesis/model_on_common_set.py`, import paresseux de `charger_rf`).
Le lanceur ne remplace plus rien : `enregistrer_famille_rf()` devient `verifier_famille_rf()`,
qui contrôle la déclaration et lève un message lisible si quelqu'un retire une des deux lignes.
L'expérience se lance désormais par la CLI :

```bash
PYTHONPATH="$PWD:$PWD/services/llm-agents" \
  services/llm-agents/.venv/bin/python -m experiences lancer --experience exp_rf_…
```

**L'équivalence, mesurée sur le jeu corrigé plutôt que sur l'ancien.** La forêt y avait tourné
le matin même par le lanceur dédié : comparer les deux exécutions du **même** jeu isole le
câblage, ce que la comparaison avec l'ancien substrat n'aurait pas fait. Écart sur les cinq
grandeurs publiées, à la dixième décimale :

| grandeur | lanceur dédié | CLI officielle | écart |
|---|---:|---:|---:|
| composite EMD–JSD | 4,0877216433 | 4,0877216433 | 0 |
| hors choix unique | 5,8138287719 | 5,8138287719 | 0 |
| modes tirés | 4,3972510961 | 4,3972510961 | 0 |
| composite L1 | 38,3315522777 | 38,3315522777 | 0 |
| L1 parts globales | 5,2840348783 | 5,2840348783 | 0 |

Les 3 299 décisions retenues sont identiques une à une. Seules les distributions bougent, sur
1 334 lignes et d'au plus **2,22 × 10⁻¹⁶** — un ULP de double précision, c'est-à-dire l'ordre
de sommation de la renormalisation, pas une décision. 1 449 tests au vert.

**Ce qui n'est PAS fait, et pourquoi.** Le chemin de population des trois définitions `rf`
reste le chemin hôte, et `_chemin_population_hote` reste dans le lanceur. Normaliser vers le
chemin conteneur supposerait d'exécuter la forêt dans `controller`, qui porte scikit-learn
1.9.1 quand elle a été estimée sous 1.8.0 — et elle se **réajuste** au chargement, aucun arbre
n'étant sérialisé. Aligner la version dans l'image a été écarté le 2026-09-16 : cela
déplacerait le réajustement de macOS arm64 vers un conteneur Linux, où rien ne garantit une
forêt bit-à-bit identique même à version égale, et ferait donc courir aux chiffres publiés du
§ 4.4 un risque que rien n'oblige à prendre.

**Le § 4.4 n'affirme pas ce que ce ticket lui prêtait.** Sa phrase est « Elles sont *estimées*
à parité stricte : même fichier de données, même découpage par ménage, mêmes poids de
redressement, même encodage, mêmes métriques issues d'un module partagé. » C'est une parité
d'estimation, vraie quel que soit l'endroit où la forêt s'exécute. Rien dans le chapitre ne
prétend que les quatre méthodes sont *lancées* par le même chemin, et le § 3.3 tel qu'il était
rédigé surestimait donc l'enjeu. Le câblage valait quand même d'être fait — il retire un
remplacement d'espace de noms et rend l'expérience rejouable — mais il ne corrigeait aucune
affirmation fausse de l'article.

Trois risques, tous bornés :

- **écraser un travail en cours** sur `FAMILLES` ou `POLICY_FORMATS` — à vérifier avant
  d'écrire, le 043 est clos mais une autre session peut y être ;
- **changer silencieusement les décisions du témoin** : le câblage pourrait charger l'artefact
  autrement que le remplacement d'espace de noms. La garde est de rejouer `rf nosim` sur
  l'ANCIEN jeu après câblage et de comparer au `scores.json` du 2026-09-16 — un écart au
  centième signe une non-équivalence ;
- **ne rien faire** : le rejeu du § 3.4 passerait alors par le lanceur hôte pour ce seul bras,
  ce qui fonctionne mais maintient l'asymétrie que le chapitre nie.

### 3.4 Rejouer
Toutes les expériences de la cohorte v6, **sauf celles déjà jouées sur le jeu corrigé**. Les
quatre témoins tabulaires et les trois planchers ne coûtent rien ; les huit bras à décideur LLM
coûtent de l'ordre de 2 500 sollicitations chacun, cache désactivé (`config.yaml`,
`cache.enabled: false`), soit ≈ 20 000 appels.

L'ordre importe : tabulaires et planchers d'abord, ils valident la chaîne à coût nul.

#### Inventaire de rejeu — arrêté le 2026-09-16

Les 27 définitions sont dérivées et rangées (`jeu-20260316_EN_c`), la campagne
`campagnes/rejeu_jeu_corrige_v6.yaml` les porte en deux phases. `derive_de` pointe la
définition de l'ancien substrat.

**Faits — 18 témoins et planchers, sans appel LLM (2026-09-16, 15:35 → 15:57)**

Les 18 sont `terminee`, 3 299 décisions archivées chacune, 3 154 scorées.

| bras | ancien jeu | jeu corrigé | écart |
|---|---:|---:|---:|
| `alea_nosim` | 50,2859 | 50,1644 | −0,1215 |
| `alea_nochn_noret` | 40,8319 | 40,8338 | +0,0019 |
| `durmin_nosim` | 26,9661 | 26,9661 | **0,0000** |
| `durmin_nochn_noret` | 28,1550 | 28,1550 | **0,0000** |
| `majvoiture_nosim` | 30,4161 | 30,7290 | +0,3129 |
| `majvoiture_nochn_noret` | 30,1466 | 30,8526 | **+0,7059** |
| `klr_nosim` | 3,5705 | 3,6053 | +0,0348 |
| `klr_noret` | 3,7218 | 3,7934 | +0,0717 |
| `klr_nochn_noret` | 3,6630 | 3,6850 | +0,0221 |
| `lgbm_nosim` | 3,6329 | 3,6036 | −0,0293 |
| `lgbm_noret` | 3,7625 | 3,7733 | +0,0108 |
| `lgbm_nochn_noret` | 3,7177 | 3,6979 | −0,0198 |
| `mnl_nosim` | 4,0128 | 4,0187 | +0,0059 |
| `mnl_noret` | 4,2958 | 4,3587 | +0,0629 |
| `mnl_nochn_noret` | 3,9113 | 3,9129 | +0,0016 |
| `rf_nosim` | 4,1907 | 4,0877 | −0,1030 |
| `rf_noret` | 4,3946 | 4,3138 | −0,0808 |
| `rf_nochn_noret` | 4,1843 | 4,1759 | −0,0084 |

Composite `emd_jsd`, formule `v1_reference` (`0aeee565…`), référentiel CEREMA
(`9ac34597…`) — identiques des deux côtés : seul le substrat change.

**⚠ Le socle change d'ordre.** Sur `nosim`, `klr` devançait `lgbm` de 0,0624. Sur le jeu
corrigé, `lgbm` passe devant de 0,0017 — c'est-à-dire que les deux sont **à égalité au
millième**, et que l'ordre entre eux n'est plus une propriété du socle mais du bruit. Toute
phrase du § 4.4 qui hiérarchise ces deux témoins est à reprendre. Voir le signalement d'impact.

`durmin` ne bouge **pas du tout**, aux quatre décimales : le plancher de durée minimale prend
l'itinéraire le plus court, et il reste le plus court quand l'offre change à la marge.
`majvoiture` bouge le plus (+0,71) — c'est le seul plancher dont la décision dépend de la
présence d'une option voiture dans l'offre.

**À faire — 9 bras à décideur LLM**, ≈ 2 500 sollicitations chacun, cache désactivé,
**≈ 22 500 appels**. Phase `llm` de la campagne, non lancée au 2026-09-16 (décision de
l'auteur). `gemini-35-fl_promin02` passe en premier : c'est le seul dont on n'ait aucune
mesure, même fausse (arrêté à 53/3299 le 2026-09-16).

| bras | état sur l'ancien jeu |
|---|---|
| `gemini-35-fl_promin02` | jamais abouti — 53/3299 |
| `gemini-35-fl_proexp04` | `terminee` 2026-09-15 |
| `gemini-35-fl_proexp05` | `terminee` 2026-09-15 |
| `gemini-35-fl_proexp06` | `terminee` 2026-09-15 |
| `gemini-35-fl_proexp08` | `terminee` 2026-09-15 |
| `gemini-31-fl_promin02` | `terminee` 2026-09-15 |
| `gemini-31-fl_proexp05` | `terminee` 2026-09-15 |
| `mistral-l-25_promin02` | `terminee` 2026-09-15 |
| `mistral-l-25_proexp05` | `terminee` 2026-09-15 |

**Hors rejeu — les 5 bras Antigravity.** Décision de l'auteur du 2026-09-16 : plus aucun run
Antigravity. `agy-claude-o-4-6` (×2), `agy-claude-o-5` (×2), `agy-gemini-38-f` (×1) ne sont
pas dérivés vers le jeu corrigé ; leurs définitions restent sur l'ancien substrat. Aucun n'a
jamais produit de mesure : quatre sans exécution, le cinquième arrêté à 0/3299.

### 3.5 Rescorer et reprendre les chiffres publiés
Les chapitres 4 et 6 viennent d'être repris sur les scores du 2026-09-16 (périmètre corrigé,
ancien jeu). Ils devront l'être une seconde fois sur le jeu corrigé. Le signalement d'impact du
057 liste les passages concernés : § 6.1 tableau et différences appariées, § 4.4 tableau du
socle et mécanisme mesuré.

## 4. Les campagnes

Trois campagnes portaient l'ancien jeu et étaient arrêtées. Elles ne pouvaient pas reprendre en
l'état : leurs `restantes` désignaient des expériences dont le nom contient `jeu-20260316`,
c'est-à-dire l'ancien substrat.

| campagne | état au 2026-09-16 | reste |
|---|---|---|
| `bascule_anglaise_v6` | terminée le 16/09 à 11:32 | 2 échouées |
| `bascule_anglaise_v6_sans_gemini31` | arrêtée (fichier STOP) | 3 restantes, 4 échouées |
| `multimodeles_v6` | terminée le 15/09 à 20:32 | 4 échouées |

**Supprimées le 2026-09-16** sur décision de l'auteur, et remplacées par
`campagnes/rejeu_jeu_corrige_v6.yaml` (phases `temoins` 18 / `llm` 9, lanceur dédié pour les
trois `rf`). Leurs définitions, états et journaux sont archivés dans
`docs/traces/2026-09-16_14-24_avant_rejeu_jeu_corrige/`, avec les 32 définitions v6 et leurs
30 exécutions — la procédure de restauration est dans le `README.md` de ce dossier.

La campagne neuve saute ce qui est déjà `terminee` : la relancer ne fera que la phase `llm`.

## Critères de clôture
- [x] `jeu.py` corrigé, testé, sans régression sur la suite.
- [x] Jeu re-préparé sur la cohorte v6 et la date du 2026-03-16 —
      `population_1000_AAMAS_v6_20260316_EN_c`, clos le 2026-09-16, 3 299/3 299, 0 erreur.
- [x] Écart d'offre entre les deux jeux mesuré et publié — 95 déplacements sur 3 299 (2,9 %)
      changent d'offre ; la météo change pour les 866 redatés.
- [x] Famille random forest câblée, équivalence vérifiée — écart nul sur les cinq grandeurs,
      3 299 décisions identiques, 1 449 tests au vert. **Le chemin de population n'est PAS
      normalisé** et ne le sera pas : il supposerait d'exécuter la forêt dans le conteneur,
      sous une autre version de scikit-learn que celle de son estimation. Le § 4.4 affirme une
      parité d'*estimation*, qui reste vraie — la clause « chemin de population normalisé » du
      critère visait une parité d'exécution que le chapitre ne revendique pas.
- [x] Témoins tabulaires et planchers rejoués sur le jeu corrigé — 18/18 `terminee`,
      3 299 décisions chacun.
- [ ] Bras à décideur LLM rejoués, ou l'écart d'offre montré nul et le rejeu déclaré inutile.
      **La seconde branche est fermée** (§ 3.2) : les 9 bras doivent être rejoués. Campagne
      prête, non lancée au 2026-09-16 sur décision de l'auteur.
- [ ] Scores régénérés, chapitres 4 et 6 repris.
- [x] Campagne neuve définie sur le jeu corrigé (`rejeu_jeu_corrige_v6`) ; les trois anciennes
      supprimées après archivage, aucune relancée.

## Ce que ce ticket ne fait pas
Il ne rejoue pas ce qui a été joué **après** la correction. Aucune exécution n'est dans ce cas
au moment de l'ouverture : les quatre bras `noret` du 2026-09-16 ont été joués le matin, avant
le correctif, et sont donc à reprendre comme les autres.
