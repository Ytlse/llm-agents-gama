#!/usr/bin/env python3
"""Ticket 027, sonde — dériver un substrat où le motif `other` s'appelle `escort`.

Spec : `specs/ticket_027/sonde-motif-escort.md`.

La question posée, et c'est la seule : **le modèle réagit-il au libellé du motif ?** On tire
au hasard 66,2 % des activités `other` — la part que l'EMC² 2023 attribue à l'accompagnement
dans ce fourre-tout (4 503 / 6 797) — et on les renomme `escort`. Un bras LLM sur ce substrat,
apparié au bras témoin sur le substrat d'origine, borne le gain narratif atteignable.

Ce que la sonde NE dit PAS : la justesse de l'affectation. Elle ne sait pas *lesquels* des
`other` sont des accompagnements — cette information est détruite en amont, dans eqasim
(`data/hts/entd/cleaned.py`, famille 6 repliée sur `other`). Seule l'option A du ticket 027 la
rétablit, au prix d'une régénération de population.

Deux objets sont fabriqués, et il en faut deux (S1, `jeu.py:896`) :

- une **population dérivée**, parce que le motif servi au décideur vient de la population et
  non du jeu (`runner.py:478`) — réécrire le jeu seul ne changerait rien au prompt ;
- un **jeu dérivé**, parce qu'un jeu est lié à sa population par empreinte et serait refusé.

Le jeu dérivé se fabrique par **copie**, jamais par recalcul (S2) : rejouer les moteurs à
68 minutes d'intervalle ferait dériver les itinéraires, et cette dérive se confondrait avec le
traitement. La copie est licite parce que `purpose` n'entre dans aucun calcul de proposition —
deux emplois seulement en préparation, l'étiquette recopiée (`jeu.py:623`) et l'option bus
scolaire, qui ne se déclenche que sur `education` (`school_bus.py:164`). Le script le vérifie
au lieu de le supposer (S3).

La population dérivée n'est **pas scellée** (S5) : pas de `MANIFEST.yaml`, donc `populations()`
ne la liste pas et `population_par_defaut()` ne peut pas la choisir. Une sonde ne doit pas se
trouver à un clic du formulaire de lancement.

Usage :
    python scripts/deriver_sonde_escort.py --verifier   # n'écrit rien, dit ce qui serait fait
    python scripts/deriver_sonde_escort.py              # exécute
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]
# Le contrôle d'indépendance du motif (S3) inspecte le CODE, pas les données : il vise
# toujours le dépôt où vit ce script, même quand `RACINE` est détourné (tests sur tmp).
DEPOT_CODE = Path(__file__).resolve().parents[1]
POP = RACINE / "data" / "population"
JEUX = RACINE / "data" / "jeux"

POPULATION_SOURCE = "data/population/population_1000_AAMAS_v5"
JEU_SOURCE = "data/jeux/population_1000_AAMAS_v5_20260316"

MOTIF_SOURCE = "other"
MOTIF_CIBLE = "escort"

# Part d'accompagnement dans `other`, MESURÉE sur les 54 585 déplacements de l'EMC² Toulouse
# 2023 (`D5A`) : codes 61, 64, 71, 74 contre l'ensemble des motifs repliés sur `other`.
# Elle ne se règle pas à la main — c'est une mesure, pas un paramètre.
EMC2_ACCOMPAGNEMENT = 4503
EMC2_AUTRES_DANS_OTHER = 6797

# Le tirage doit être le même sur n'importe quelle machine et à n'importe quelle date.
GRAINE = 27

# Chemin vu depuis le contrôleur (`./data/population:/data/eqasim-output` dans le compose).
PREFIXE_CONTENEUR = "/data/eqasim-output"


# ── outils ───────────────────────────────────────────────────────────────────


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _maintenant_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _relatif(chemin: Path) -> str:
    """Chemin lisible : relatif au dépôt quand c'est possible, absolu sinon."""
    try:
        return str(chemin.relative_to(RACINE))
    except ValueError:
        return str(chemin)


def _humain(octets: int) -> str:
    for unite in ("o", "Ko", "Mo", "Go"):
        if octets < 1024 or unite == "Go":
            return f"{octets:.1f} {unite}" if unite != "o" else f"{octets} o"
        octets /= 1024.0
    return f"{octets:.1f} Go"


def _ecrire_json_atomique(chemin: Path, donnees) -> None:
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    tmp.replace(chemin)


def _ecrire_yaml_atomique(chemin: Path, donnees: dict) -> None:
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    tmp.replace(chemin)


# ── S4 : le tirage ───────────────────────────────────────────────────────────


def activites_candidates(population: list[dict], motif: str) -> list[tuple[str, str]]:
    """Clés `(person_id, activity_id)` des activités portant ce motif, en ordre stable.

    L'ordre est celui du tri, pas celui du fichier : deux populations aux mêmes activités
    rangées autrement doivent rendre le MÊME tirage.
    """
    cles: list[tuple[str, str]] = []
    for personne in population:
        pid = str(personne.get("person_id"))
        for activite in (personne.get("identity") or {}).get("activities") or []:
            if str(activite.get("purpose") or "") == motif:
                cles.append((pid, str(activite.get("id"))))
    return sorted(cles)


def tirer(cles: list[tuple[str, str]], part: float, graine: int) -> set[tuple[str, str]]:
    """Sous-ensemble reproductible, de taille `round(part × n)`."""
    k = round(part * len(cles))
    return set(random.Random(graine).sample(cles, k))


# ── S3 : la copie doit être justifiée ────────────────────────────────────────


def verifier_independance_du_motif() -> list[str]:
    """Le motif influence-t-il encore le calcul d'une proposition ? (S3)

    Deux emplois connus et inoffensifs. Si le code en acquiert un troisième, la sonde doit
    casser bruyamment plutôt que rendre une mesure fausse — d'où une vérification ici, et pas
    seulement dans un test que personne ne relance avant de dériver.
    """
    alarmes: list[str] = []
    school_bus = DEPOT_CODE / "services" / "llm-agents" / "trip_helper" / "school_bus.py"
    if school_bus.is_file():
        texte = school_bus.read_text(encoding="utf-8")
        emplois = [
            l.strip() for l in texte.splitlines() if ".purpose" in l and "#" not in l[:2]
        ]
        for ligne in emplois:
            if "education" not in ligne:
                alarmes.append(
                    f"[ALARME] `school_bus.py` consulte le motif hors du cas `education` : {ligne!r} — "
                    f"la copie du jeu (S2) n'est plus justifiée, il faut recalculer ou corriger la spec"
                )
    else:
        alarmes.append(f"[ALARME] introuvable : {school_bus} — indépendance du motif non vérifiée")
    return alarmes


# ── la dérivation ────────────────────────────────────────────────────────────


def deriver_population(
    source: Path, tirage: set[tuple[str, str]], motif_cible: str
) -> tuple[list[dict], dict]:
    """Population dérivée en mémoire + compteurs. Seul `purpose` change (S9)."""
    brut = json.loads(source.read_text(encoding="utf-8"))
    compteurs = {"personnes": len(brut), "activites": 0, "reetiquetees": 0, "laissees": 0}
    for personne in brut:
        pid = str(personne.get("person_id"))
        for activite in (personne.get("identity") or {}).get("activities") or []:
            compteurs["activites"] += 1
            if (pid, str(activite.get("id"))) in tirage:
                activite["purpose"] = motif_cible
                compteurs["reetiquetees"] += 1
    compteurs["laissees"] = len(tirage) - compteurs["reetiquetees"]
    return brut, compteurs


def deriver_propositions(
    source: Path, cible: Path, tirage: set[tuple[str, str]], motif_cible: str
) -> dict:
    """Copie ligne à ligne : une ligne hors tirage est recopiée **verbatim** (S1, S8).

    Recopier l'octet plutôt que de re-sérialiser garantit que les deux jeux ne diffèrent que
    par les lignes tirées — pas par une virgule de formatage.
    """
    compteurs = {"lignes": 0, "reecrites": 0, "plans_reecrits": 0, "verbatim": 0}
    tmp = cible.with_suffix(cible.suffix + ".tmp")
    with open(source, encoding="utf-8") as entree, open(tmp, "w", encoding="utf-8") as sortie:
        for ligne in entree:
            if not ligne.strip():
                continue
            compteurs["lignes"] += 1
            objet = json.loads(ligne)
            cle = (str(objet.get("person_id")), str(objet.get("activity_id")))
            if cle not in tirage:
                sortie.write(ligne)
                compteurs["verbatim"] += 1
                continue
            objet["purpose"] = motif_cible
            for proposition in objet.get("propositions") or []:
                plan = proposition.get("plan") or {}
                if "purpose" in plan:
                    plan["purpose"] = motif_cible
                    compteurs["plans_reecrits"] += 1
            sortie.write(json.dumps(objet, ensure_ascii=False) + "\n")
            compteurs["reecrites"] += 1
    tmp.replace(cible)
    return compteurs


def manifeste_jeu_derive(
    manifeste_source: dict,
    nom: str,
    info_population: dict,
    empreinte_propositions: str,
    derive_de: dict,
) -> dict:
    """Manifeste du jeu dérivé (S7) : identité neuve, dépendances héritées.

    `dependances` est repris tel quel : ce sont bien ces GTFS, ce graphe et ce commit qui ont
    produit ces propositions-là. Les réécrire avec l'état du jour serait un mensonge.
    """
    manifeste = dict(manifeste_source)
    manifeste["nom"] = nom
    manifeste["cree_le"] = _maintenant_iso()
    manifeste["clos_le"] = _maintenant_iso()
    manifeste["clos"] = True
    manifeste["population"] = info_population
    manifeste["propositions_sha256"] = empreinte_propositions
    manifeste["derive_de"] = derive_de
    return manifeste


# ── vérification ─────────────────────────────────────────────────────────────


def comparer_populations(a: list[dict], b: list[dict]) -> list[str]:
    """Chemins de TOUTES les feuilles qui diffèrent entre deux populations.

    Exhaustif, et c'est le point : le critère d'acceptation demande « aucune autre différence »,
    pas « aucune parmi les vingt premières ». Un contrôle qui s'arrête tôt laisserait passer
    exactement ce qu'il est censé attraper — une valeur touchée loin dans le fichier.
    """
    ecarts: list[str] = []

    def parcourir(x, y, chemin: str) -> None:
        if type(x) is not type(y):
            ecarts.append(f"{chemin}: {type(x).__name__} ≠ {type(y).__name__}")
        elif isinstance(x, dict):
            if set(x) != set(y):
                ecarts.append(f"{chemin}: clés {sorted(set(x) ^ set(y))}")
                return
            for k in x:
                parcourir(x[k], y[k], f"{chemin}.{k}")
        elif isinstance(x, list):
            if len(x) != len(y):
                ecarts.append(f"{chemin}: {len(x)} ≠ {len(y)} éléments")
                return
            for i, (xi, yi) in enumerate(zip(x, y)):
                parcourir(xi, yi, f"{chemin}[{i}]")
        elif x != y:
            ecarts.append(f"{chemin}: {x!r} → {y!r}")

    parcourir(a, b, "population")
    return ecarts


def executions_en_cours() -> list[str]:
    """Exécutions dont l'état est `en_cours` — S10 ne porte que sur le LANCEMENT, pas sur
    la dérivation, mais on le dit ici pour que personne n'enchaîne sans le savoir."""
    en_cours: list[str] = []
    for etat in (RACINE / "data" / "experiences").glob("*/executions/*/etat.json"):
        try:
            if (json.loads(etat.read_text(encoding="utf-8")) or {}).get("etat") == "en_cours":
                en_cours.append(str(etat.parent.relative_to(RACINE / "data" / "experiences")))
        except (json.JSONDecodeError, OSError):
            continue
    return en_cours


# ── programme ────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    debut = time.monotonic()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--population", default=POPULATION_SOURCE, help="cohorte source")
    p.add_argument("--jeu", default=JEU_SOURCE, help="jeu clos source")
    p.add_argument("--suffixe", default="escort66", help="suffixe des objets dérivés")
    p.add_argument("--graine", type=int, default=GRAINE)
    p.add_argument(
        "--part",
        type=float,
        default=EMC2_ACCOMPAGNEMENT / EMC2_AUTRES_DANS_OTHER,
        help="part des `other` à réétiqueter (défaut : la part mesurée dans l'EMC² 2023)",
    )
    p.add_argument("--verifier", action="store_true", help="n'écrit rien, dit ce qui serait fait")
    a = p.parse_args(argv)

    pop_source = RACINE / a.population
    jeu_source = RACINE / a.jeu
    fichier_pop_source = pop_source / "population.json" if pop_source.is_dir() else pop_source
    manifeste_jeu_source = jeu_source / "MANIFEST.yaml"
    propositions_source = jeu_source / "propositions.jsonl"

    entete = "Ticket 027 — sonde `escort`" + (" (VÉRIFICATION, rien ne sera écrit)" if a.verifier else "")
    print(f"{entete}\n")

    refus: list[str] = []
    for chemin, quoi in (
        (fichier_pop_source, "population source"),
        (manifeste_jeu_source, "manifeste du jeu source"),
        (propositions_source, "propositions du jeu source"),
    ):
        if not chemin.is_file():
            refus.append(f"{quoi} introuvable : {chemin}")
    if refus:
        print("REFUS — préalables non tenus :")
        for r in refus:
            print(f"  · {r}")
        return 2

    manifeste_source = yaml.safe_load(manifeste_jeu_source.read_text(encoding="utf-8")) or {}
    if not manifeste_source.get("clos"):
        print(f"REFUS — le jeu source {manifeste_source.get('nom')!r} n'est pas clos : rien à dériver")
        return 2

    # L'empreinte annoncée doit être celle du fichier, sinon on dériverait d'un jeu altéré (J12).
    empreinte_source = sha256_fichier(propositions_source)
    if manifeste_source.get("propositions_sha256") != empreinte_source:
        print(
            f"REFUS — jeu source altéré : MANIFEST annonce "
            f"{str(manifeste_source.get('propositions_sha256'))[:12]}…, le fichier fait {empreinte_source[:12]}…"
        )
        return 2

    alarmes = verifier_independance_du_motif()
    for alarme in alarmes:
        print(alarme)
    if alarmes:
        print("\nREFUS — la copie du jeu (S2) n'est plus justifiée.")
        return 3

    sha_pop_source = sha256_fichier(fichier_pop_source)
    nom_pop_source = pop_source.name if pop_source.is_dir() else pop_source.stem
    nom_pop_cible = f"{nom_pop_source}_{a.suffixe}"
    nom_jeu_cible = str(manifeste_source.get("nom")).replace(
        nom_pop_source, nom_pop_cible, 1
    )
    if nom_jeu_cible == manifeste_source.get("nom"):  # le nom du jeu ne cite pas la population
        nom_jeu_cible = f"{manifeste_source.get('nom')}_{a.suffixe}"
    dossier_pop_cible = POP / nom_pop_cible
    dossier_jeu_cible = JEUX / nom_jeu_cible

    population_source = json.loads(fichier_pop_source.read_text(encoding="utf-8"))
    candidates = activites_candidates(population_source, MOTIF_SOURCE)
    tirage = tirer(candidates, a.part, a.graine)

    activites_totales = sum(
        len((p_.get("identity") or {}).get("activities") or []) for p_ in population_source
    )
    print(
        f"Source : {nom_pop_source} ({len(population_source)} personnes, {activites_totales} activités, "
        f"sha {sha_pop_source[:12]}…)\n"
        f"         jeu {manifeste_source.get('nom')} ({manifeste_source.get('couverts', {}).get('deplacements')} "
        f"déplacements couverts, sha {empreinte_source[:12]}…)\n"
    )
    print(
        f"Tirage : {len(tirage)} / {len(candidates)} activités `{MOTIF_SOURCE}` → `{MOTIF_CIBLE}` "
        f"({100 * len(tirage) / max(1, len(candidates)):.1f} %, part demandée {100 * a.part:.1f} %, graine {a.graine})\n"
        f"         soit {100 * len(tirage) / max(1, activites_totales):.1f} % des activités de la journée"
    )

    if a.verifier:
        _, compteurs = deriver_population(fichier_pop_source, tirage, MOTIF_CIBLE)
        print(
            f"\n[vérif] écrirait {_relatif(dossier_pop_cible)}/population.json "
            f"({compteurs['reetiquetees']} activités réétiquetées)"
        )
        print(f"[vérif] écrirait {_relatif(dossier_pop_cible)}/PROVENANCE.yaml")
        print(
            f"[vérif] écrirait {_relatif(dossier_jeu_cible)}/ "
            f"(MANIFEST.yaml + propositions.jsonl copiées de {_humain(propositions_source.stat().st_size)})"
        )
        en_cours = executions_en_cours()
        if en_cours:
            print(
                f"\n⚠ {len(en_cours)} exécution(s) en cours : la dérivation est hors ligne et peut se faire, "
                f"mais AUCUN bras LLM ne se lance avant leur fin (S10) — {', '.join(en_cours)}"
            )
        print(f"\nRien écrit. Durée {time.monotonic() - debut:.1f} s.")
        return 0

    # ── écriture ──
    dossier_pop_cible.mkdir(parents=True, exist_ok=True)
    dossier_jeu_cible.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    population_cible, compteurs_pop = deriver_population(fichier_pop_source, tirage, MOTIF_CIBLE)
    fichier_pop_cible = dossier_pop_cible / "population.json"
    _ecrire_json_atomique(fichier_pop_cible, population_cible)
    sha_pop_cible = sha256_fichier(fichier_pop_cible)
    print(
        f"\npopulation dérivée : {compteurs_pop['reetiquetees']} activités réétiquetées sur "
        f"{compteurs_pop['activites']}, {len(candidates) - len(tirage)} laissées en `{MOTIF_SOURCE}` — "
        f"{_humain(fichier_pop_cible.stat().st_size)}, sha {sha_pop_cible[:12]}… ({time.monotonic() - t0:.1f} s)"
    )

    # Critère d'acceptation : aucune autre différence que le motif, vérifié feuille à feuille.
    ecarts = comparer_populations(population_source, json.loads(fichier_pop_cible.read_text(encoding="utf-8")))
    hors_motif = [e for e in ecarts if not e.endswith(f"{MOTIF_SOURCE!r} → {MOTIF_CIBLE!r}")]
    if hors_motif:
        print(
            f"[ALARME] la population dérivée diffère AILLEURS que sur le motif : "
            f"{len(hors_motif)} écart(s), dont {hors_motif[:5]}"
        )
        return 4
    if len(ecarts) != compteurs_pop["reetiquetees"]:
        print(
            f"[ALARME] {len(ecarts)} écarts constatés pour {compteurs_pop['reetiquetees']} activités "
            f"réétiquetées — la dérivation n'a pas fait ce qu'elle annonce"
        )
        return 4
    print(
        f"                     contrôle EXHAUSTIF : {len(ecarts)} écarts, tous sur le motif — "
        f"aucun autre champ touché"
    )

    t0 = time.monotonic()
    compteurs_props = deriver_propositions(
        propositions_source, dossier_jeu_cible / "propositions.jsonl", tirage, MOTIF_CIBLE
    )
    empreinte_cible = sha256_fichier(dossier_jeu_cible / "propositions.jsonl")
    print(
        f"jeu dérivé         : {compteurs_props['reecrites']} lignes réécrites "
        f"({compteurs_props['plans_reecrits']} plans), {compteurs_props['verbatim']} recopiées verbatim, "
        f"{compteurs_props['lignes']} au total — sha {empreinte_cible[:12]}… ({time.monotonic() - t0:.1f} s)"
    )
    if compteurs_props["reecrites"] > len(tirage):
        print(
            f"[ALARME] {compteurs_props['reecrites']} lignes réécrites pour {len(tirage)} activités tirées — "
            f"clés en double dans le jeu ?"
        )
        return 4
    non_couvertes = len(tirage) - compteurs_props["reecrites"]
    if non_couvertes:
        print(
            f"                     {non_couvertes} activités tirées absentes du jeu "
            f"(déplacements non couverts, p. ex. origine = destination) — attendu, elles gardent leur libellé de population"
        )

    info_population_cible = {
        "nom": nom_pop_cible,
        "chemin": f"{PREFIXE_CONTENEUR}/{nom_pop_cible}/population.json",
        "sha256": sha_pop_cible,
        "fichier_sha256": sha_pop_cible,
        "scellee": False,
        "n": len(population_cible),
    }
    derive_de = {
        "jeu": manifeste_source.get("nom"),
        "jeu_propositions_sha256": empreinte_source,
        "population": nom_pop_source,
        "population_sha256": (manifeste_source.get("population") or {}).get("sha256"),
        "population_fichier_sha256": sha_pop_source,
        "regle": (
            f"{len(tirage)} des {len(candidates)} activités de motif `{MOTIF_SOURCE}` réétiquetées "
            f"`{MOTIF_CIBLE}`, tirées par graine {a.graine} sur la clé triée (person_id, activity_id) ; "
            f"part {a.part:.6f} mesurée sur l'EMC² 2023 ({EMC2_ACCOMPAGNEMENT}/{EMC2_AUTRES_DANS_OTHER})"
        ),
        "propositions": "copiées, jamais recalculées (spec S2) : le motif n'entre dans aucun calcul d'itinéraire",
        "derive_le": _maintenant_iso(),
        "ticket": "027",
        "spec": "specs/ticket_027/sonde-motif-escort.md",
    }
    _ecrire_yaml_atomique(
        dossier_jeu_cible / "MANIFEST.yaml",
        manifeste_jeu_derive(
            manifeste_source, nom_jeu_cible, info_population_cible, empreinte_cible, derive_de
        ),
    )

    _ecrire_yaml_atomique(
        dossier_pop_cible / "PROVENANCE.yaml",
        {
            "avertissement": (
                "Substrat de SONDE, pas une cohorte de référence. Il ne se scelle pas, ne se compare "
                "pas aux mesures de la v5 autrement que par appariement, et ne doit jamais servir de défaut."
            ),
            "nom": nom_pop_cible,
            "derive_de": derive_de,
            "mesure": (
                "sensibilité du modèle au LIBELLÉ du motif, et rien d'autre. Le tirage est ALÉATOIRE : "
                "la sonde ne sait pas lesquels des `other` sont des accompagnements. Elle borne le gain "
                "narratif atteignable ; elle ne mesure pas la justesse de l'affectation."
            ),
            "lecture": (
                "l'écart se lit contre le plancher de reformulation du ticket 024 (2,03 de composite), "
                "jamais contre zéro"
            ),
            "effectifs": {
                "personnes": compteurs_pop["personnes"],
                "activites": compteurs_pop["activites"],
                "candidates_other": len(candidates),
                "reetiquetees_escort": compteurs_pop["reetiquetees"],
                "restees_other": len(candidates) - len(tirage),
                "lignes_de_jeu_reecrites": compteurs_props["reecrites"],
            },
            "scellee": False,
            "sha256": sha_pop_cible,
        },
    )

    print(
        f"\nSUCCÈS — substrat de sonde écrit en {time.monotonic() - debut:.1f} s :\n"
        f"  population {_relatif(dossier_pop_cible)} (non scellée, invisible du formulaire)\n"
        f"  jeu        {_relatif(dossier_jeu_cible)} (clos, dérivé, dépendances héritées)"
    )
    en_cours = executions_en_cours()
    if en_cours:
        print(
            f"\n⚠ RIEN NE SE LANCE MAINTENANT : {len(en_cours)} exécution(s) en cours (S10, protocole exogène §0) — "
            f"{', '.join(en_cours)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
