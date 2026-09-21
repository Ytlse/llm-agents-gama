"""audit_unitaire_058.py — L'accord décision par décision, contre le mode déclaré.

Le composite agrégé dit si une population se comporte comme l'enquête. Il ne dit pas si
**ce** déplacement-là a reçu le mode que la personne a déclaré. C'est ce que mesure ce
script, sur les journées réellement décrites par les enquêtés (ticket 058).

## Ce qui est calculé, et pour qui

| Grandeur | Sur quels décideurs |
|---|---|
| Exactitude, pondérée et non pondérée | tous |
| Matrice de confusion 4 × 4, effectifs et pondérée | tous |
| Rappel et précision par mode | tous |
| Exactitude par bande de distance | tous |
| Entropie croisée et GMPCA | **seulement ceux qui rendent une distribution, sur le support commun** |
| Taux de zéro sur mode offert | tous ceux qui rendent une distribution |

L'entropie croisée d'une décision dure est infinie dès la première erreur. Lisser un
plancher pour lui donner un chiffre produirait une valeur qui dépend du lissage et de rien
d'autre : les planchers « toujours la voiture » et « durée minimale » n'en reçoivent donc
pas, et la colonne reste vide pour eux.

**Elle se calcule sur le SUPPORT COMMUN : les décisions arbitrées que tous les décideurs
comparés notent.** Un zéro exact n'a pas d'entropie croisée — le terme vaut moins l'infini, et
la bibliothèque le borne à son seuil de troncature, si bien que la moyenne mesurerait le seuil
plutôt que le décideur. Mesuré sur le gradient boosté : **4,21 nats en comptant les zéros, 0,42
sans eux**. Publier le seul 4,21 serait publier `1e-15`.

Écarter ces décisions décideur par décideur, en revanche, rend les valeurs incomparables :
chacun est alors noté sur l'ensemble qu'il se choisit en tranchant plus ou moins dur, 5 923
décisions pour le prompt expert contre 6 588 pour le gradient boosté, et le plus tranchant
retire le plus de ses propres échecs. D'où l'intersection, et `--definisseur` pour dire qui la
définit. Corrigé le 2026-09-21 : l'ordre des décideurs s'en trouve changé, cf.
`docs/traces/2026-09-21_11-45_ticket058_entropie_support_commun/`.

Ce que le support commun jette est publié à côté, comme résultat : **le taux de décisions où le
mode déclaré était dans les options présentées et où le décideur lui a donné zéro**. Il ne
dépend d'aucun plancher de probabilité, et il oppose deux familles de sorties — une softmax ne
produit pas de zéro exact, une distribution verbalisée si.

Ces zéros ont deux causes, qu'il faut séparer parce qu'elles ne coûtent pas au même :

- **le mode déclaré n'était pas dans les options présentées** — le verrou de chaîne ou le
  plafond d'options l'a retiré, et aucun décideur ne pouvait le trouver ;
- **il y était, et le décideur lui a donné zéro** — c'est son erreur, pas celle de la règle.

## Deux compteurs qui conditionnent la lecture

**Le mode déclaré était-il dans l'offre ?** Sous contrainte de chaîne, la voiture est retirée
de l'offre d'une partie des déplacements. Quand le mode déclaré n'y est pas, aucun décideur ne
peut le trouver : l'erreur appartient à la règle, pas à lui. Le compte est le plafond de
l'audit, et il se publie à côté de l'exactitude.

**Combien de décisions sont arbitrées ?** Le compte se lit sur la décision, pas sur l'offre du
jeu : le filtre véhicule et le plafond d'options passent entre les deux, et ils réduisent
beaucoup. Un déplacement à option unique n'est pas une décision — tous les décideurs y donnent
la même réponse. L'exactitude est donc publiée deux fois : sur l'ensemble, et sur les seules
décisions arbitrées, où les décideurs se départagent réellement.

## Les modes

L'enquête code quatre classes : `walk`, `bike`, `car`, `transit`. La plateforme rend un mode
canonique parmi six, réduit d'une chaîne de tronçons par la hiérarchie EMC² (ticket 022,
`mode_hierarchy.primary_canonical`). La correspondance est celle du recodage de l'enquête, où
les deux-roues motorisés tombent avec la voiture et le train avec les transports collectifs.

Usage :
    services/llm-agents/.venv/bin/python scripts/progedo_logit/audit_unitaire_058.py \
        --experience exp_lgbm_jtir_pop-enquete_058_test_jeu-58_test_20260316_nosim
    # sans --experience : toutes les expériences jouées sur le jeu de l'audit
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE / "packages" / "mobility_core" / "src"))
sys.path.insert(0, str(RACINE / "services" / "llm-agents"))
sys.path.insert(0, str(ICI))

from mobility_core.mode_hierarchy import primary_canonical  # noqa: E402
from mode_choice_eval import evaluate_proba  # noqa: E402

JEU_DEFAUT = "enquete_058_test_20260316"
VERITE_DEFAUT = "verite_058_test.csv"

# Les quatre classes de l'enquête, dans l'ordre du spec (`TARGET_CLASSES`).
CLASSES = ("bike", "car", "transit", "walk")

# Qui définit le support commun de l'entropie croisée. Les planchers en sont exclus :
# `alea` répartit au hasard et laisse des milliers de décisions à zéro sur le mode déclaré,
# qu'il raboterait pour tout le monde ; `durmin` et `majvoiture` tranchent dur et ne rendent
# pas de distribution. Ils sont NOTÉS sur le support quand ils le couvrent, ils ne le
# définissent pas.
PLANCHERS = ("alea", "durmin", "majvoiture")
INDEX = {c: i for i, c in enumerate(CLASSES)}

# Mode canonique de la plateforme → classe de l'enquête. Les deux-roues motorisés tombent avec
# la voiture et le train avec les transports collectifs, comme dans `MODE_GROUP` du
# constructeur du jeu d'entraînement : c'est le recodage de l'enquête qui fait foi, pas le
# nombre de modes que les moteurs savent produire.
CANONIQUE_VERS_CLASSE = {
    "walking": "walk",
    "cycling": "bike",
    "car": "car",
    "motorbike": "car",
    "public_transport": "transit",
    "train": "transit",
}

BANDES = ((1, "0-1km"), (2, "1-2km"), (5, "2-5km"), (10, "5-10km"), (20, "10-20km"),
          (50, "20-50km"))
BANDE_LOINTAINE = "plus_50km"


def bande(km: float) -> str:
    for seuil, nom in BANDES:
        if km < seuil:
            return nom
    return BANDE_LOINTAINE


def classe_du_libelle(libelle: str | None) -> str | None:
    """`foot,bus,foot` → `transit`. Réduction par la hiérarchie, puis recodage enquête."""
    if not libelle:
        return None
    canonique = primary_canonical(str(libelle).split(","))
    return CANONIQUE_VERS_CLASSE.get(canonique or "")


def charger_verite(fichier: Path) -> dict[str, dict[str, Any]]:
    """Les modes déclarés, hors déplacements dont l'enchaînement est rompu."""
    with fichier.open(encoding="utf-8") as flux:
        lignes = [r for r in csv.DictReader(flux) if r["chaine_rompue"] == "0"]
    rompus = 0
    with fichier.open(encoding="utf-8") as flux:
        rompus = sum(1 for r in csv.DictReader(flux) if r["chaine_rompue"] == "1")
    logger.info(
        f"Vérité terrain : {len(lignes)} déplacements déclarés "
        f"({rompus} écarté(s) pour enchaînement rompu)"
    )
    return {r["activity_id"]: r for r in lignes}


def charger_offre(dossier_jeu: Path) -> dict[str, dict[str, Any]]:
    """Par déplacement : les classes offertes et le nombre d'options."""
    offre: dict[str, dict[str, Any]] = {}
    with (dossier_jeu / "propositions.jsonl").open(encoding="utf-8") as flux:
        for ligne in flux:
            enregistrement = json.loads(ligne)
            propositions = enregistrement.get("propositions") or []
            if not propositions:
                continue
            classes = set()
            for proposition in propositions:
                legs = (proposition.get("plan") or {}).get("legs") or []
                classe = classe_du_libelle(",".join(str(leg.get("mode")) for leg in legs))
                if classe:
                    classes.add(classe)
            offre[enregistrement["activity_id"]] = {
                "classes": classes,
                "n_options": len(propositions),
            }
    logger.info(f"Offre du jeu : {len(offre)} déplacements avec au moins une option")
    return offre


def distribution_forcee(decision: dict[str, Any]) -> dict[str, float] | None:
    """La distribution d'un choix forcé : toute la masse sur la seule option présentée.

    Ce n'est pas un lissage. La règle 3 renormalise sur les modes offerts ; quand il n'en
    reste qu'un, la distribution renormalisée EST la masse 1 sur ce mode. La lire ainsi garde
    l'entropie croisée comparable d'un décideur à l'autre, au lieu de la refuser à cause de
    déplacements où personne n'avait le choix.
    """
    presentees = decision.get("presentees") or []
    if decision.get("methode") != "choix_unique" or len(presentees) != 1:
        return None
    canonique = primary_canonical(str(presentees[0].get("mode") or "").split(","))
    return {canonique: 1.0} if canonique else None


def distribution_en_classes(distribution: dict[str, float] | None) -> list[float] | None:
    """La distribution canonique de la décision, repliée sur les quatre classes."""
    if not distribution:
        return None
    masse = [0.0] * len(CLASSES)
    for mode, poids in distribution.items():
        classe = CANONIQUE_VERS_CLASSE.get(mode)
        if classe is None:
            return None  # un mode hors correspondance : on ne devine pas
        masse[INDEX[classe]] += float(poids or 0.0)
    total = sum(masse)
    if total <= 0:
        return None
    return [m / total for m in masse]


def etat_execution(execution: Path) -> str:
    """`terminee`, `en_cours`, `interrompue`… tel que l'exécution le déclare."""
    fichier = execution / "etat.json"
    if not fichier.is_file():
        return "inconnu"
    try:
        return str(json.loads(fichier.read_text(encoding="utf-8")).get("etat") or "inconnu")
    except (OSError, json.JSONDecodeError):
        return "inconnu"


def derniere_execution(dossier_experience: Path) -> Path | None:
    executions = sorted(p for p in (dossier_experience / "executions").glob("*") if p.is_dir())
    return executions[-1] if executions else None


def rappel_precision(matrice: np.ndarray) -> dict[str, dict[str, float]]:
    """Rappel et précision par classe, lus sur la matrice de confusion (vrai × prédit)."""
    resultat = {}
    for i, classe in enumerate(CLASSES):
        vrais_positifs = float(matrice[i, i])
        declares = float(matrice[i, :].sum())
        predits = float(matrice[:, i].sum())
        resultat[classe] = {
            "rappel": vrais_positifs / declares if declares else float("nan"),
            "precision": vrais_positifs / predits if predits else float("nan"),
            "declares": declares,
            "predits": predits,
        }
    return resultat


def auditer(execution: Path, verite: dict, offre: dict) -> dict[str, Any]:
    """Les métriques d'une exécution, contre les modes déclarés."""
    y, yhat, poids, probas, bandes, arbitrees = [], [], [], [], [], []
    identifiants, offert = [], []
    compte = Counter()
    par_bande: dict[str, list[int]] = defaultdict(list)

    with (execution / "decisions.jsonl").open(encoding="utf-8") as flux:
        for ligne in flux:
            decision = json.loads(ligne)
            reference = verite.get(decision.get("activity_id") or "")
            if reference is None:
                compte["hors_verite"] += 1  # fermeture de journée, ou enchaînement rompu
                continue
            retenue = decision.get("retenue") or {}
            classe_choisie = classe_du_libelle(retenue.get("mode"))
            if classe_choisie is None:
                compte["sans_decision"] += 1
                continue
            declare = reference["mode_declare"]
            if declare not in INDEX:
                compte["mode_declare_hors_classes"] += 1
                continue

            info = offre.get(decision["activity_id"]) or {}
            if declare not in (info.get("classes") or set()):
                compte["mode_declare_absent_du_jeu"] += 1
            # Ce qui compte vraiment : les options RÉELLEMENT présentées au décideur, après le
            # verrou de chaîne et le plafond. Le jeu, lui, porte tous les modes sans filtre.
            classes_presentees = {
                classe_du_libelle(o.get("mode"))
                for o in (decision.get("presentees") or [])
            }
            if declare not in classes_presentees:
                compte["mode_declare_absent_des_presentees"] += 1
            if info.get("n_options") == 1:
                compte["option_unique_dans_le_jeu"] += 1
            forcee = decision.get("methode") == "choix_unique"
            if forcee:
                compte["decision_forcee"] += 1
            arbitrees.append(0 if forcee else 1)

            identifiants.append(str(decision["activity_id"]))
            offert.append(declare in classes_presentees)
            y.append(INDEX[declare])
            yhat.append(INDEX[classe_choisie])
            poids.append(float(reference["sample_weight"] or 1.0))
            probas.append(distribution_en_classes(decision.get("distribution")))
            b = bande(float(reference["vol_oiseau_declare_km"] or 0.0))
            bandes.append(b)
            par_bande[b].append(1 if classe_choisie == declare else 0)
            compte["notes"] += 1

    if not y:
        logger.error(f"[ALARME] Aucune décision notable dans {execution} : rien à publier")
        return {}, {}

    y_arr = np.asarray(y)
    yhat_arr = np.asarray(yhat)
    poids_arr = np.asarray(poids)

    matrice = np.zeros((len(CLASSES), len(CLASSES)))
    matrice_ponderee = np.zeros((len(CLASSES), len(CLASSES)))
    for vrai, predit, p in zip(y, yhat, poids, strict=True):
        matrice[vrai, predit] += 1
        matrice_ponderee[vrai, predit] += p

    juste = y_arr == yhat_arr
    arbitrees_arr = np.asarray(arbitrees, dtype=bool)

    resultat: dict[str, Any] = {
        "execution": execution.name,
        "notes": int(compte["notes"]),
        "arbitrees": int(arbitrees_arr.sum()),
        "exactitude_arbitrees": (
            float(juste[arbitrees_arr].mean()) if arbitrees_arr.any() else None
        ),
        "exactitude_forcees": (
            float(juste[~arbitrees_arr].mean()) if (~arbitrees_arr).any() else None
        ),
        "exactitude_non_ponderee": float((y_arr == yhat_arr).mean()),
        "exactitude_ponderee": float(
            poids_arr[y_arr == yhat_arr].sum() / poids_arr.sum()
        ),
        "matrice_effectifs": matrice.astype(int).tolist(),
        "matrice_ponderee": matrice_ponderee.tolist(),
        "par_mode": rappel_precision(matrice),
        "par_bande": {
            b: {"n": len(v), "exactitude": float(np.mean(v))}
            for b, v in sorted(par_bande.items())
        },
        "compteurs": dict(compte),
    }

    # Le détail par décision, rendu à l'appelant pour qu'il construise le support commun :
    # activity_id -> (mode déclaré, distribution, poids), sur les décisions arbitrées qui
    # portent une distribution, ZÉROS COMPRIS. C'est l'appelant qui filtre.
    notables = {
        identifiants[i]: (int(y[i]), probas[i], float(poids[i]))
        for i in range(len(y))
        if arbitrees[i] and probas[i] is not None
    }

    # Entropie croisée par décideur, sur SON propre sous-ensemble : les décisions arbitrées
    # dont sa distribution laisse une masse non nulle au mode déclaré. Cette lecture n'est pas
    # comparable d'un décideur à l'autre — plus il tranche dur, plus elle retire de ses propres
    # échecs — et elle ne sert qu'à mesurer l'écart avec le support commun. C'est
    # `cel_weighted_support_commun` qui se publie.
    retenus = [
        i
        for i, p in enumerate(probas)
        if p is not None and arbitrees[i] and p[y[i]] > 0
    ]
    exclus = [
        i
        for i, p in enumerate(probas)
        if p is not None and arbitrees[i] and p[y[i]] <= 0
    ]
    resultat["mode_declare_a_zero"] = len(exclus)

    # Ce que le support commun jette, et qui est pourtant un résultat : les décisions où le
    # mode déclaré ÉTAIT dans les options présentées et où le décideur lui a donné zéro. Ce
    # n'est pas la règle qui a retiré l'option, c'est lui qui l'a exclue. Le taux se compare
    # d'un décideur à l'autre sans dépendre d'aucun plancher de probabilité.
    offerts_arbitres = [
        i for i in range(len(y)) if arbitrees[i] and offert[i] and probas[i] is not None
    ]
    zeros_propres = [i for i in offerts_arbitres if probas[i][y[i]] <= 0]
    resultat["arbitrees_mode_offert"] = len(offerts_arbitres)
    resultat["zeros_mode_offert"] = len(zeros_propres)
    resultat["taux_zero_mode_offert"] = (
        len(zeros_propres) / len(offerts_arbitres) if offerts_arbitres else None
    )
    # Une distribution dégénérée (toute la masse sur un mode) n'est pas une distribution : le
    # décideur a tranché dur et l'a écrit sous forme de probabilités. Filtrée sur les décisions
    # justes, son entropie croisée vaut 0 par construction — un chiffre qui ne dit rien.
    degeneree = all(
        max(probas[i]) >= 1.0 - 1e-9 for i in retenus
    ) if retenus else False
    if degeneree:
        resultat["entropie_croisee"] = None
        resultat["entropie_croisee_motif"] = (
            "décision dure : la distribution rendue est dégénérée (masse 1 sur un mode)"
        )
        resultat["distribution_degeneree"] = True
        return resultat, notables
    if retenus and len(retenus) >= int(0.5 * arbitrees_arr.sum()):
        resultat["entropie_croisee_notes"] = len(retenus)
        mesures = evaluate_proba(
            np.asarray([probas[i] for i in retenus]),
            y_arr[retenus],
            poids_arr[retenus],
            list(CLASSES),
        )
        for cle in (
            "cel_weighted", "cel_unweighted", "gmpca_weighted", "gmpca_unweighted"
        ):
            if cle in mesures:
                resultat[cle] = mesures[cle]
    else:
        manquantes = sum(1 for i, p in enumerate(probas) if p is None and arbitrees[i])
        resultat["entropie_croisee"] = None
        resultat["entropie_croisee_motif"] = (
            f"décision dure : {manquantes} décision(s) arbitrée(s) sur "
            f"{int(arbitrees_arr.sum())} sans distribution"
        )
    return resultat, notables


# Deux bras LLM ne se distinguent que par leur suffixe de prompt (`…_promin02`,
# `…_proexp05`) : une colonne trop étroite les rendait identiques à l'affichage.
LARGEUR_NOM = 22


def support_commun(
    notables: dict[str, dict[str, tuple[int, list[float], float]]],
    resultats: dict[str, dict[str, Any]],
    definisseurs_demandes: list[str] | None = None,
) -> set[str]:
    """Les décisions que TOUS les décideurs comparés notent, et l'entropie croisée dessus.

    Sans cela, chaque décideur est noté sur les décisions où il laisse une masse non nulle au
    mode déclaré, c'est-à-dire sur un ensemble qu'il choisit lui-même en tranchant plus ou
    moins dur. Deux entropies croisées calculées sur 5 923 et 6 588 décisions ne se comparent
    pas. Le support commun est l'intersection, définie par les décideurs comparés — les
    planchers en sont exclus, cf. PLANCHERS — et tout le monde y est noté.
    """
    # Qui définit le support décide de sa taille : un décideur de plus le rabote pour tout le
    # monde. Par défaut, tous ceux qui rendent une distribution non dégénérée ; --definisseur
    # restreint à la comparaison qu'on publie.
    definisseurs = [
        nom
        for nom, detail in notables.items()
        if detail
        and nom not in PLANCHERS
        and (definisseurs_demandes is None or nom in definisseurs_demandes)
        and not resultats.get(nom, {}).get("distribution_degeneree")
        and resultats.get(nom, {}).get("etat_execution") in (None, "terminee")
    ]
    if not definisseurs:
        logger.warning("Aucun décideur ne peut définir un support commun : entropie non publiée")
        return set()

    support: set[str] | None = None
    for nom in definisseurs:
        avec_masse = {
            cle for cle, (y, proba, _) in notables[nom].items() if proba[y] > 0
        }
        support = avec_masse if support is None else (support & avec_masse)
    support = support or set()

    plancher = min(len(notables[nom]) for nom in definisseurs)
    logger.info(
        f"Support commun de l'entropie croisée : {len(support)} décisions, "
        f"définies par {len(definisseurs)} décideurs ({', '.join(sorted(definisseurs))})"
    )
    if plancher and len(support) < 0.60 * plancher:
        logger.error(
            f"[ALARME] Support commun trop étroit : {len(support)} décisions contre {plancher} "
            f"chez le décideur le moins couvrant ({len(support) / plancher:.0%}) — l'entropie "
            f"croisée ne porterait plus que sur les cas faciles"
        )

    for nom, detail in notables.items():
        resultat = resultats.get(nom)
        if not resultat or resultat.get("distribution_degeneree"):
            continue
        manquantes = support - detail.keys()
        resultat["support_commun_notes"] = len(support) - len(manquantes)
        if manquantes:
            # Un décideur qui ne couvre pas tout le support serait noté sur autre chose que
            # les autres : c'est exactement ce qu'on vient de corriger, on ne le réintroduit pas.
            resultat["cel_weighted_support_commun"] = None
            resultat["support_commun_motif"] = (
                f"{len(manquantes)} décision(s) du support commun absente(s) de ce décideur"
            )
            continue
        mesures = evaluate_proba(
            np.asarray([detail[cle][1] for cle in sorted(support)]),
            np.asarray([detail[cle][0] for cle in sorted(support)]),
            np.asarray([detail[cle][2] for cle in sorted(support)]),
            list(CLASSES),
        )
        for cle in ("cel_weighted", "cel_unweighted", "gmpca_weighted", "gmpca_unweighted"):
            if cle in mesures:
                resultat[f"{cle}_support_commun"] = mesures[cle]
    return support


def rendre(resultats: dict[str, dict[str, Any]]) -> None:
    """Le tableau lu par un humain. Les valeurs vides sont des vides, pas des zéros."""
    entete = (
        f"{'décideur':{LARGEUR_NOM}s} {'notés':>7s} {'exact.':>8s} {'pondérée':>9s} "
        f"{'arbitrées':>10s} {'forcées':>8s} {'entropie':>9s} {'support':>8s} "
        f"{'vélo R':>7s} {'TC R':>7s} {'marche R':>9s} {'hors options':>13s} "
        f"{'0/offert':>9s}"
    )
    print("\n" + entete)
    print("-" * len(entete))
    for nom, r in sorted(resultats.items(), key=lambda kv: -kv[1].get("exactitude_ponderee", 0)):
        if not r:
            continue
        if r.get("etat_execution") not in (None, "terminee"):
            nom = f"{nom[: LARGEUR_NOM - 8]} PARTIEL"
        # Publiée : l'entropie croisée du SUPPORT COMMUN. Celle du support propre reste dans
        # le JSON, elle ne se compare à rien.
        ec = r.get("cel_weighted_support_commun")
        taux_zero = r.get("taux_zero_mode_offert")
        par_mode = r.get("par_mode", {})
        print(
            f"{nom[:LARGEUR_NOM]:{LARGEUR_NOM}s} {r['notes']:7d} {r['exactitude_non_ponderee']:8.1%} "
            f"{r['exactitude_ponderee']:9.1%} "
            f"{(f'{r["exactitude_arbitrees"]:.1%}' if r.get("exactitude_arbitrees") is not None else '—'):>10s} "
            f"{(f'{r["exactitude_forcees"]:.1%}' if r.get("exactitude_forcees") is not None else '—'):>8s} "
            f"{(f'{ec:.4f}' if ec is not None else '—'):>9s} "
            f"{r.get('support_commun_notes', 0):8d} "
            f"{par_mode.get('bike', {}).get('rappel', float('nan')):7.1%} "
            f"{par_mode.get('transit', {}).get('rappel', float('nan')):7.1%} "
            f"{par_mode.get('walk', {}).get('rappel', float('nan')):9.1%} "
            f"{r['compteurs'].get('mode_declare_absent_des_presentees', 0):13d} "
            f"{(f'{taux_zero:.1%}' if taux_zero is not None else '—'):>9s}"
        )
    print(f"\nClasses, dans l'ordre des matrices : {', '.join(CLASSES)}")


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--jeu", default=JEU_DEFAUT)
    parseur.add_argument("--verite", default=VERITE_DEFAUT)
    parseur.add_argument("--experience", action="append", help="répétable ; défaut : toutes")
    parseur.add_argument("--sortie", type=Path, help="fichier JSON des résultats détaillés")
    parseur.add_argument(
        "--definisseur",
        action="append",
        help="répétable ; nom court d'un décideur qui définit le support commun de "
        "l'entropie croisée. Défaut : tous ceux qui rendent une distribution non dégénérée",
    )
    args = parseur.parse_args()

    verite = charger_verite(ICI / args.verite)
    offre = charger_offre(RACINE / "data" / "jeux" / args.jeu)

    dossier_experiences = RACINE / "data" / "experiences"
    if args.experience:
        noms = args.experience
    else:
        noms = [
            p.name
            for p in sorted(dossier_experiences.glob("exp_*"))
            if (p / "experience.yaml").exists() and args.jeu in (p / "experience.yaml").read_text()
        ]
        logger.info(f"Expériences trouvées sur le jeu {args.jeu} : {len(noms)}")

    resultats: dict[str, dict[str, Any]] = {}
    notables: dict[str, dict[str, tuple[int, list[float], float]]] = {}
    for nom in noms:
        dossier = dossier_experiences / nom
        execution = derniere_execution(dossier) if dossier.is_dir() else None
        if execution is None or not (execution / "decisions.jsonl").exists():
            logger.warning(f"{nom} : aucune exécution exploitable, ignorée")
            continue
        court = nom.replace("exp_", "").split("_jtir")[0]
        etat = etat_execution(execution)
        resultats[court], notables[court] = auditer(execution, verite, offre)
        r = resultats[court]
        if r:
            r["etat_execution"] = etat
            # Une exécution non terminée ne couvre qu'un DÉBUT d'échantillon — les premiers
            # enquêtés dans l'ordre des clés, pas un tirage. Ses taux ne se comparent à rien
            # et la ligne est marquée comme telle, plutôt que rangée dans le tableau.
            if etat != "terminee":
                logger.warning(
                    f"[ALARME] {court} : exécution {etat} ({r['notes']} déplacements notés sur "
                    f"{len(verite)}) — chiffres PARTIELS, non comparables aux bras terminés"
                )
            logger.info(
                f"{court:12s} exactitude {r['exactitude_ponderee']:.1%} pondérée "
                f"sur {r['notes']} déplacements"
            )

    if not resultats:
        raise SystemExit("aucun résultat : lancer d'abord les expériences sur ce jeu")

    support_commun(notables, resultats, args.definisseur)

    rendre(resultats)

    if args.sortie:
        args.sortie.write_text(
            json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        logger.success(f"Résultats détaillés écrits : {args.sortie}")


if __name__ == "__main__":
    main()
