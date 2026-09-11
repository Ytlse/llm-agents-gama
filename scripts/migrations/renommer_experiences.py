"""Renomme les expériences existantes d'après leurs paramètres (spec `nommage-canonique-experiences`).

Le nom d'une expérience EST son identité : dossier `data/experiences/<nom>/`, clé de la file
FIFO, cible de `pause`/`arreter`. Les noms saisis à la main ne disaient pas les paramètres —
`Prompt_Minimaliste_GPT-OSS-120b` servait `mistral-small-latest`, `Light_GBM` affichait une
variante de prompt qui ne décidait rien, et deux dossiers `…qwen3.6-27b` portaient deux noms
pour une définition strictement identique. Ce script les aligne sur le nom calculé (N12).

Il ne renomme rien sans qu'on le demande : sans `--appliquer`, il DIT ce qu'il ferait, fichier
par fichier. Avec `--fusionner`, deux dossiers de même signature sont réunis (une expérience,
plusieurs exécutions) au lieu d'être distingués par un indice.

    llm-agents/.venv/bin/python scripts/migrations/renommer_experiences.py           # vérifie
    llm-agents/.venv/bin/python scripts/migrations/renommer_experiences.py --appliquer --fusionner

Ce qui est réécrit : la définition (`nom`, `renomme_de`, `derive_de`), la copie figée de chaque
exécution (`execution.yaml`), les restitutions de données (`synthese.json`, `scores.json`) et
leurs rendus HTML, le registre des masques, la file d'attente, le brouillon du formulaire. Les
journaux (`execution.log`) ne sont PAS touchés : ils disent ce qui s'est passé, et ça s'est
passé sous l'ancien nom.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "llm-agents"))

from experiences import nommage as N  # noqa: E402

DOSSIER = RACINE / "data" / "experiences"
FICHIER_MASQUES = DOSSIER / ".masques.json"
FICHIER_FILE = DOSSIER / ".file.json"
FICHIER_RENOMMAGES = DOSSIER / ".renommages.json"
BROUILLON = RACINE / "experiments" / ".dashboard" / "formulaire_experience.yaml"

# Une progression écrite il y a moins de ça : un runner tient peut-être encore ce dossier.
FRAICHEUR_VIVANTE_S = 120

RENDUS = ("synthese.html", "synthese_scores.html")
DONNEES = ("synthese.json", "scores.json")


def _log(niveau: str, message: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {niveau:<7} {message}")


@dataclass
class Plan:
    """Ce qu'une expérience va devenir."""

    dossier: Path
    ancien: str
    nouveau: str
    signature: str
    definition: dict
    fusion_vers: str | None = None  # dossier canonique qui absorbe celui-ci
    executions: list[str] = field(default_factory=list)

    @property
    def inchange(self) -> bool:
        return self.fusion_vers is None and self.ancien == self.nouveau


def _lire_yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        _log("ERROR", f"{p} illisible ({e}) : expérience ignorée")
        return {}


def _executions(dossier: Path) -> list[str]:
    d = dossier / "executions"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def _vivantes(dossier: Path) -> list[str]:
    """Les exécutions dont la progression est encore fraîche — on ne déplace pas sous leurs pieds."""
    vivantes = []
    for nom in _executions(dossier):
        p = dossier / "executions" / nom / "progression.json"
        if p.is_file() and (time.time() - p.stat().st_mtime) < FRAICHEUR_VIVANTE_S:
            vivantes.append(nom)
    return vivantes


def construire_plans(fusionner: bool) -> tuple[list[Plan], list[str]]:
    """Un plan par expérience, plus les refus qui empêchent d'appliquer."""
    refus: list[str] = []
    plans: list[Plan] = []
    # Les noms déjà pris se remplissent au fur et à mesure : deux définitions différentes de
    # même nom canonique reçoivent des indices distincts (N10), la première servie d'abord.
    prises: dict[str, str] = {}
    for dossier in sorted(p for p in DOSSIER.iterdir() if (p / "experience.yaml").is_file()):
        definition = _lire_yaml(dossier / "experience.yaml")
        if not definition:
            refus.append(f"{dossier.name} : experience.yaml illisible ou vide")
            continue
        ancien = str(definition.get("nom") or dossier.name)
        try:
            attribution = N.attribuer_nom(definition, DOSSIER, existantes=prises)
        except N.NommageImpossible as e:
            refus.append(f"{ancien} : {e}")
            continue
        signature = N.signature(definition)
        plan = Plan(dossier, ancien, attribution.nom, signature, definition,
                    executions=_executions(dossier))
        if attribution.reutilise:
            if not fusionner:
                refus.append(
                    f"{ancien} : même définition que « {attribution.reutilise} » (signature "
                    f"{signature[:8]}) → relancez avec --fusionner pour réunir leurs exécutions, "
                    f"ou changez un paramètre de l'une des deux")
                continue
            plan.fusion_vers = attribution.reutilise
            plan.nouveau = attribution.reutilise
        else:
            prises[attribution.nom] = signature
        vivantes = _vivantes(dossier)
        if vivantes and not plan.inchange:
            refus.append(
                f"{ancien} : l'exécution {vivantes[0]} écrit encore (progression fraîche) → "
                f"attendez sa fin, ou mettez-la en pause avant de renommer")
        plans.append(plan)
    return plans, refus


def _remplacer_dans_json(chemin: Path, cle: str, correspondance: dict[str, str], appliquer: bool) -> bool:
    if not chemin.is_file():
        return False
    try:
        data = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _log("ERROR", f"{chemin} illisible ({e}) : laissé tel quel")
        return False
    change = False
    entrees = data if isinstance(data, list) else [data]
    for entree in entrees:
        if isinstance(entree, dict) and entree.get(cle) in correspondance:
            if appliquer:
                entree[cle] = correspondance[entree[cle]]
            change = True
    if change and appliquer:
        chemin.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return change


def _reecrire_execution(dossier_exec: Path, ancien: str, nouveau: str, appliquer: bool) -> list[str]:
    """La copie figée de la définition et les restitutions citent le nouveau nom."""
    touches: list[str] = []
    conf = dossier_exec / "execution.yaml"
    if conf.is_file():
        data = _lire_yaml(conf)
        if ((data.get("experience") or {}).get("nom")) == ancien:
            touches.append(str(conf.relative_to(RACINE)))
            if appliquer:
                data["experience"]["nom"] = nouveau
                # `renomme_de` dans l'archive : l'exécution reste retrouvable par son ancien nom.
                data["experience"]["renomme_de"] = ancien
                conf.write_text(
                    yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
                )
    for fichier in DONNEES:
        if _remplacer_dans_json(dossier_exec / fichier, "experience", {ancien: nouveau}, appliquer):
            touches.append(str((dossier_exec / fichier).relative_to(RACINE)))
    for fichier in RENDUS:
        p = dossier_exec / fichier
        if p.is_file():
            texte = p.read_text(encoding="utf-8")
            if ancien in texte:
                touches.append(str(p.relative_to(RACINE)))
                if appliquer:
                    p.write_text(texte.replace(ancien, nouveau), encoding="utf-8")
    return touches


def appliquer_plans(plans: list[Plan], appliquer: bool) -> dict[str, int]:
    correspondance = {p.ancien: p.nouveau for p in plans if p.ancien != p.nouveau}
    compteurs = {"renommees": 0, "fusionnees": 0, "inchangees": 0, "executions": 0, "fichiers": 0}

    for plan in plans:
        if plan.inchange:
            compteurs["inchangees"] += 1
            _log("INFO", f"inchangée : {plan.ancien}")
            continue

        cible = DOSSIER / plan.nouveau
        if plan.fusion_vers:
            _log("INFO", f"fusion : {plan.ancien} → {plan.fusion_vers} "
                         f"({len(plan.executions)} exécution(s), signature {plan.signature[:8]})")
        else:
            _log("INFO", f"renommage : {plan.ancien} → {plan.nouveau}")

        for nom_exec in plan.executions:
            touches = _reecrire_execution(
                plan.dossier / "executions" / nom_exec, plan.ancien, plan.nouveau, appliquer
            )
            compteurs["executions"] += 1
            compteurs["fichiers"] += len(touches)
            for t in touches:
                _log("INFO", f"  ↳ {t}")

        if plan.fusion_vers:
            if appliquer:
                (cible / "executions").mkdir(parents=True, exist_ok=True)
                for nom_exec in plan.executions:
                    destination = cible / "executions" / nom_exec
                    if destination.exists():
                        _log("ERROR", f"  ↳ {destination} existe déjà : exécution laissée en place")
                        continue
                    shutil.move(str(plan.dossier / "executions" / nom_exec), str(destination))
                # `executions_connues` de la cible = l'union, sinon le registre annonce des
                # archives manquantes pour celles qui viennent d'arriver.
                fichier_cible = cible / "experience.yaml"
                definition_cible = _lire_yaml(fichier_cible)
                connues = set(definition_cible.get("executions_connues") or []) | set(plan.executions)
                definition_cible["executions_connues"] = sorted(connues)
                fichier_cible.write_text(
                    yaml.safe_dump(definition_cible, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                shutil.rmtree(plan.dossier)
            compteurs["fusionnees"] += 1
            continue

        if appliquer:
            if cible.exists():
                _log("ERROR", f"{cible} existe déjà : {plan.ancien} laissée en place")
                continue
            definition = dict(plan.definition)
            definition["nom"] = plan.nouveau
            definition["renomme_de"] = plan.ancien
            if definition.get("derive_de") in correspondance:
                definition["derive_de"] = correspondance[definition["derive_de"]]
            (plan.dossier / "experience.yaml").write_text(
                yaml.safe_dump(definition, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            plan.dossier.rename(cible)
        compteurs["renommees"] += 1
        compteurs["fichiers"] += 1

    # Les registres qui désignent une expérience par son nom.
    for fichier, cle in ((FICHIER_MASQUES, "experience"), (FICHIER_FILE, "exp")):
        if _remplacer_dans_json(fichier, cle, correspondance, appliquer):
            compteurs["fichiers"] += 1
            _log("INFO", f"registre mis à jour : {fichier.relative_to(RACINE)}")

    # La file peut nommer une expérience disparue : une entrée fantôme n'est jamais promue et
    # reste affichée indéfiniment dans le tableau de bord.
    if FICHIER_FILE.is_file():
        try:
            entrees = json.loads(FICHIER_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entrees = []
        vivantes = [e for e in entrees
                    if (DOSSIER / str(e.get("exp") or "") / "experience.yaml").is_file()]
        if len(vivantes) != len(entrees):
            fantomes = [str(e.get("exp")) for e in entrees if e not in vivantes]
            _log("INFO", f"file : {len(entrees) - len(vivantes)} entrée(s) fantôme(s) retirée(s) "
                         f"({', '.join(fantomes)})")
            if appliquer:
                FICHIER_FILE.write_text(
                    json.dumps(vivantes, ensure_ascii=False, indent=1), encoding="utf-8"
                )
                compteurs["fichiers"] += 1

    # Le brouillon du formulaire retenait un nom : le champ n'existe plus (N1).
    if BROUILLON.is_file():
        brouillon = _lire_yaml(BROUILLON)
        if "nom" in brouillon:
            _log("INFO", f"brouillon : champ `nom` retiré de {BROUILLON.relative_to(RACINE)}")
            if appliquer:
                brouillon.pop("nom")
                BROUILLON.write_text(
                    yaml.safe_dump(brouillon, allow_unicode=True, sort_keys=True), encoding="utf-8"
                )
                compteurs["fichiers"] += 1

    if appliquer and correspondance:
        historique = []
        if FICHIER_RENOMMAGES.is_file():
            try:
                historique = json.loads(FICHIER_RENOMMAGES.read_text(encoding="utf-8"))
            except ValueError:
                historique = []
        historique.append({
            "le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "regle": "nommage-canonique-experiences",
            "renommages": correspondance,
            "fusions": {p.ancien: p.fusion_vers for p in plans if p.fusion_vers},
        })
        FICHIER_RENOMMAGES.write_text(
            json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        _log("INFO", f"historique écrit : {FICHIER_RENOMMAGES.relative_to(RACINE)}")
    return compteurs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--appliquer", action="store_true",
                    help="écrit et renomme ; sans lui, rien n'est touché")
    ap.add_argument("--fusionner", action="store_true",
                    help="réunit deux dossiers de définition identique (une expérience, "
                         "plusieurs exécutions) au lieu de refuser")
    a = ap.parse_args(argv)

    debut = time.monotonic()
    mode = "APPLICATION" if a.appliquer else "VÉRIFICATION (rien n'est écrit)"
    _log("INFO", f"renommage des expériences — {mode}, dossier {DOSSIER}")
    if not DOSSIER.is_dir():
        _log("ERROR", f"[ALARME] dossier d'expériences introuvable : {DOSSIER}")
        return 2

    plans, refus = construire_plans(a.fusionner)
    for r in refus:
        _log("ERROR", f"[ALARME] refus : {r}")
    if refus:
        _log("ERROR", f"{len(refus)} refus : rien n'a été renommé (levez-les d'abord)")
        return 1
    if not plans:
        _log("INFO", "aucune expérience à renommer")
        return 0

    compteurs = appliquer_plans(plans, a.appliquer)
    duree = time.monotonic() - debut
    _log("INFO", f"terminé en {duree:.1f} s — {compteurs['renommees']} renommée(s), "
                 f"{compteurs['fusionnees']} fusionnée(s), {compteurs['inchangees']} inchangée(s), "
                 f"{compteurs['executions']} exécution(s) revue(s), "
                 f"{compteurs['fichiers']} fichier(s) {'écrits' if a.appliquer else 'à écrire'}")
    if not a.appliquer and (compteurs["renommees"] or compteurs["fusionnees"]):
        _log("INFO", "relancez avec --appliquer pour écrire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
