#!/usr/bin/env python3
"""Choisit des personas dont les décisions sont OBSERVABLES (ticket 093, lot 1).

POURQUOI
--------
Le ticket 075 a choisi cinq agents sur leurs TRAITS : un pendulaire motorisé, un cycliste urbain,
un scolaire… Des profils contrastés sur le papier. Mesuré sur dix jours simulés, trois des cinq
n'apprennent rien d'observable : `609` et `41275` n'ont qu'un seul itinéraire proposé une fois sur
deux — la moitié de leurs « décisions » n'en sont pas — et prennent la voiture à 100 % le reste du
temps ; `11195` ne vit que 19 trajets contre 34-35 aux autres. On observe la mémoire de deux
agents et on paie le modèle pour cinq.

Un trait ne dit pas si l'agent DÉCIDERA. Ce script ne regarde donc pas qui est l'agent, mais ce
que le monde lui a effectivement proposé, sur une journée de référence déjà jouée.

⚠ **« Journée » désigne la chaîne d'activités d'une journée type, pas une date.** Mesuré sur le
run de référence du ticket : les départs s'étalent du 16 mars 04 h 13 au 18 mars 06 h 47, parce
qu'une chaîne commencée tard déborde sur le lendemain. Filtrer sur la date du premier jour
amputerait les fins de soirée — exactement les trajets où un mode bascule. Le critère porte donc
sur TOUS les trajets du run de référence, et le MANIFEST écrit les journées couvertes pour que
le lecteur voie sur quoi il a porté.

⚠ **Une sélection ne vaut que pour son run de référence.** `41275` passe le critère sur le run de
mille agents (deux modes sur quatre trajets) et le manque sur le run à cinq personas du
2026-09-16 (voiture seule, un itinéraire une fois sur deux) — autre modèle, autre variante de
prompt. C'est pourquoi le run est nommé et son empreinte écrite : sans lui, le critère aurait
l'air d'une propriété de l'agent alors qu'il est une mesure d'un run.

LE CRITÈRE
----------
Sur cette journée : au moins quatre trajets, **toujours** plus d'un itinéraire proposé, et au
moins deux modes réellement choisis. Les trois conditions sont mesurables AVANT le run à observer,
donc reproductibles et opposables. Passé au crible du run de référence du ticket, ce critère
retient 234 candidats sur mille agents.

⚠ Le critère porte sur les modes **choisis**, jamais sur les modes proposés. Un agent à qui l'on
propose neuf options et qui prend toujours la voiture est parfaitement visible — et parfaitement
inutile : sa mémoire n'aura rien à faire basculer.

DÉTERMINISME
------------
Aucun tirage. Les candidats sont ordonnés par identifiant numérique, et la couverture des quatre
modes dominants se fait en tourniquet dans un ordre fixe. Deux exécutions sur les mêmes entrées
rendent les mêmes identifiants, dans le même ordre.

CE QUE CE N'EST PAS
-------------------
Le fichier produit n'est **pas un sceau AAMAS**, et son MANIFEST le dit. Dix agents ne
représentent rien : ils servent à observer un mécanisme, jamais à mesurer une part modale.
`data/population/population_1000_AAMAS_v6` reste la référence de l'article.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from scripts.analysis.memoire.sources import MODE_LIBELLES, Trajet, lire_moves


@dataclass(frozen=True)
class Critere:
    """Les trois conditions, nommées. Un seuil nu dans une condition ne se discute pas."""

    trajets_min: int = 4
    options_min: int = 2
    modes_min: int = 2


CRITERE = Critere()

# Modes dont on veut qu'un persona au moins porte l'habitude. Ce sont les quatre modes dominants
# de l'agglomération ; le train et le deux-roues motorisé sont trop rares pour qu'un agent les
# porte dix jours d'affilée, et exiger leur couverture ferait échouer la sélection sur une
# question de décor.
MODES_CIBLES: tuple[str, ...] = ("car", "walking", "public_transport", "cycling")


@dataclass(frozen=True)
class Mesure:
    """Ce que la journée de référence dit d'un agent."""

    person_id: str
    trajets: int
    options_min: int | None
    options_max: int | None
    options_inconnues: int
    modes: Counter = field(default_factory=Counter)
    mode_dominant: str | None = None
    jours: tuple[str, ...] = ()

    @property
    def modes_distincts(self) -> int:
        return len([m for m in self.modes if m])


@dataclass(frozen=True)
class Retenu:
    person_id: str
    persona: dict
    mesure: Mesure | None
    mode_dominant: str | None
    passe_le_critere: bool
    motif: str  # « critère » ou « conservé »


# ── Mesure ────────────────────────────────────────────────────────────────────────────


def mesurer(chemin_run: Path | str) -> dict[str, Mesure]:
    """Une mesure par agent, depuis le `moves.csv` d'un run déjà joué.

    La lecture passe par `sources.lire_moves`, qui écarte les trajets REJOUÉS après un
    redémarrage. Sans cette déduplication, un run repris compterait deux fois les journées
    rejouées et gonflerait le nombre de trajets de chaque agent.
    """
    trajets, _rejeu, _detail = lire_moves(Path(chemin_run))
    par_agent: dict[str, list[Trajet]] = {}
    for trajet in trajets:
        par_agent.setdefault(trajet.person_id, []).append(trajet)
    return {agent: _mesure_agent(agent, liste) for agent, liste in par_agent.items()}


def _mesure_agent(person_id: str, trajets: Sequence[Trajet]) -> Mesure:
    ordonnes = sorted(trajets, key=lambda t: (t.jour, t.depart, t.trajet_id))
    options = [t.options_presentees for t in ordonnes if t.options_presentees is not None]
    modes = Counter(t.mode for t in ordonnes if t.mode)
    return Mesure(
        person_id=person_id,
        trajets=len(ordonnes),
        options_min=min(options) if options else None,
        options_max=max(options) if options else None,
        options_inconnues=sum(1 for t in ordonnes if t.options_presentees is None),
        modes=modes,
        mode_dominant=_mode_dominant(ordonnes, modes),
        jours=tuple(sorted({t.jour for t in ordonnes if t.jour})),
    )


def _mode_dominant(trajets: Sequence[Trajet], modes: Counter) -> str | None:
    """Le mode le plus choisi ; à égalité, celui qui part le PREMIER dans la journée.

    Départager par une table d'ordre canonique aurait fabriqué une hiérarchie des modes là où
    l'agent n'en exprime aucune — et aurait rangé sous « voiture » tous les ex æquo, donc sous
    un seul mode toute la couverture. Le premier départ, lui, est un fait de la journée.
    """
    if not modes:
        return None
    premier_rang = {}
    for rang, trajet in enumerate(trajets):
        if trajet.mode and trajet.mode not in premier_rang:
            premier_rang[trajet.mode] = rang
    return min(modes, key=lambda mode: (-modes[mode], premier_rang.get(mode, len(trajets))))


def est_candidat(mesure: Mesure, critere: Critere = CRITERE) -> bool:
    """Les trois conditions, sans repli ni tolérance.

    Un trajet dont le nombre d'options est INCONNU disqualifie l'agent : il ne prouve pas qu'il y
    avait un choix, et le compter comme s'il en avait un ferait entrer dans la sélection
    exactement les décisions qui n'en étaient pas.
    """
    if mesure.options_inconnues:
        return False
    if mesure.trajets < critere.trajets_min:
        return False
    if mesure.options_min is None or mesure.options_min < critere.options_min:
        return False
    return mesure.modes_distincts >= critere.modes_min


# ── Choix ─────────────────────────────────────────────────────────────────────────────


def _cle_agent(person_id: str) -> tuple[int, int, str]:
    return (0, int(person_id), "") if person_id.isdigit() else (1, 0, person_id)


def _cle_richesse(mesure: Mesure) -> tuple:
    """Le plus observable d'abord : modes, puis trajets, puis choix offert.

    ⚠ Le critère est un PLANCHER, pas un objectif. Prendre les candidats dans l'ordre des
    identifiants donnait dix agents à quatre trajets et deux modes — tous conformes, tous
    minimaux, et `41275` parmi eux : l'agent même que le ticket écarte pour ne rien apprendre.
    Un agent qui fait quinze trajets sur quatre modes offre à la mémoire quinze occasions de
    peser ; un agent qui en fait quatre lui en offre quatre. À richesse égale, l'identifiant
    numérique tranche, et la sélection reste reproductible.
    """
    return (
        -mesure.modes_distincts,
        -mesure.trajets,
        -(mesure.options_min or 0),
        _cle_agent(mesure.person_id),
    )


def choisir(
    mesures: dict[str, Mesure],
    population: Sequence[dict],
    conserver: Sequence[str],
    combien: int,
    critere: Critere = CRITERE,
) -> list[Retenu]:
    """Les agents retenus, conservés d'abord, puis les candidats en tourniquet par mode.

    Les candidats sont pris du plus observable au moins observable (cf. `_cle_richesse`), en
    tourniquet sur les quatre modes dominants pour qu'aucun mode ne manque.

    Les agents de `conserver` sont retenus **de droit** : ils portent le choc et son témoin, et
    les remplacer changerait le sujet de l'étude. Mais leur mesure est écrite, et le MANIFEST dit
    s'ils passent le critère — une conservation muette serait une sélection truquée.
    """
    par_id = {str(p.get("person_id")): p for p in population}
    retenus: list[Retenu] = []
    deja: set[str] = set()

    for person_id in conserver:
        if person_id not in par_id:
            raise SystemExit(
                f"L'agent conservé « {person_id} » est absent de la population source : "
                f"il ne peut pas être écrit dans une population qui prétend en sortir."
            )
        mesure = mesures.get(person_id)
        retenus.append(Retenu(
            person_id=person_id,
            persona=par_id[person_id],
            mesure=mesure,
            mode_dominant=mesure.mode_dominant if mesure else None,
            passe_le_critere=bool(mesure) and est_candidat(mesure, critere),
            motif="conservé",
        ))
        deja.add(person_id)

    candidats = [
        mesure.person_id
        for mesure in sorted(mesures.values(), key=_cle_richesse)
        if mesure.person_id not in deja
        and mesure.person_id in par_id
        and est_candidat(mesure, critere)
    ]
    if len(retenus) + len(candidats) < combien:
        raise SystemExit(
            f"{len(candidats)} candidat(s) satisfont le critère et {combien} sont demandés. "
            f"La sélection ne complète PAS hors critère : changez de run de référence, ou "
            f"assouplissez le critère en le disant."
        )

    # Tourniquet : un mode dominant à la fois, jusqu'à ce que le compte y soit. Couvrir les
    # quatre modes AVANT de compléter, plutôt que de prendre les dix premiers identifiants,
    # est ce qui empêche une sélection entièrement motorisée par accident d'ordre.
    restants = list(candidats)
    while len(retenus) < combien:
        pris_ce_tour = False
        for mode in MODES_CIBLES:
            if len(retenus) >= combien:
                break
            for person_id in restants:
                if mesures[person_id].mode_dominant != mode:
                    continue
                retenus.append(_retenu_par_critere(person_id, par_id, mesures))
                restants.remove(person_id)
                pris_ce_tour = True
                break
        if not pris_ce_tour:
            break

    for person_id in list(restants):
        if len(retenus) >= combien:
            break
        retenus.append(_retenu_par_critere(person_id, par_id, mesures))
        restants.remove(person_id)
    return retenus


def _retenu_par_critere(person_id: str, par_id: dict, mesures: dict) -> Retenu:
    return Retenu(
        person_id=person_id,
        persona=par_id[person_id],
        mesure=mesures[person_id],
        mode_dominant=mesures[person_id].mode_dominant,
        passe_le_critere=True,
        motif="critère",
    )


# ── Écriture ──────────────────────────────────────────────────────────────────────────


def sha256(chemin: Path) -> str:
    empreinte = hashlib.sha256()
    with chemin.open("rb") as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def ecrire(
    chemin_run: Path | str,
    source: Path | str,
    sortie: Path | str,
    conserver: Sequence[str],
    combien: int,
    critere: Critere = CRITERE,
) -> list[Retenu]:
    """Écrit `population.json` et `MANIFEST.yaml`, et rend les retenus."""
    chemin_run, source, sortie = Path(chemin_run), Path(source), Path(sortie)
    population = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(population, dict):
        population = population.get("personas") or population.get("population") or []
    mesures = mesurer(chemin_run)
    retenus = choisir(mesures, population, conserver, combien, critere)

    sortie.mkdir(parents=True, exist_ok=True)
    fichier = sortie / "population.json"
    # Recopiés TELS QUELS : aucune normalisation, aucun champ ajouté. Une population de test qui
    # diverge du sceau dont elle sort ne prouve plus rien.
    fichier.write_text(
        json.dumps([r.persona for r in retenus], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (sortie / "MANIFEST.yaml").write_text(
        _manifeste(chemin_run, source, fichier, population, mesures, retenus, critere),
        encoding="utf-8",
    )
    return retenus


def _manifeste(
    chemin_run: Path,
    source: Path,
    fichier: Path,
    population: Sequence[dict],
    mesures: dict[str, Mesure],
    retenus: Sequence[Retenu],
    critere: Critere,
) -> str:
    candidats = sum(1 for m in mesures.values() if est_candidat(m, critere))
    moves = chemin_run / "moves.csv"
    lignes = [
        "# Population de TEST — ticket 093. Ce n'est PAS un sceau AAMAS.",
        "#",
        "# Dix agents ne représentent rien : ils servent à LIRE l'évolution d'une mémoire et",
        "# la rupture d'une habitude, jamais à mesurer une part modale. La référence de",
        "# l'article reste data/population/population_1000_AAMAS_v6.",
        f"nom: {fichier.parent.name}",
        f"extrait_le: '{datetime.now(timezone.utc).isoformat()}'",
        "source:",
        f"  fichier: {source.as_posix()}",
        f"  sha256: {sha256(source)}",
        f"  n: {len(population)}",
        "population:",
        "  fichier: population.json",
        f"  sha256: {sha256(fichier)}",
        f"  n: {len(retenus)}",
        "run_de_reference:",
        f"  chemin: {chemin_run.as_posix()}",
        f"  moves_sha256: {sha256(moves) if moves.is_file() else 'absent'}",
        f"  agents_mesures: {len(mesures)}",
        f"  candidats: {candidats}",
        # Les journées COUVERTES, et non « la » journée : une chaîne commencée tard déborde sur
        # le lendemain, et le lecteur doit voir l'assiette exacte du critère.
        f"  journees_couvertes: {json.dumps(sorted({j for m in mesures.values() for j in m.jours}))}",
        "critere:",
        f"  trajets_min: {critere.trajets_min}",
        f"  options_min: {critere.options_min}",
        f"  modes_min: {critere.modes_min}",
        "  enonce: >-",
        "    Sur la journée de référence : au moins trajets_min trajets, TOUJOURS au moins",
        "    options_min itinéraires proposés, et au moins modes_min modes réellement CHOISIS.",
        "    Le critère porte sur les modes choisis et jamais sur les modes proposés : un agent",
        "    à qui l'on propose tout et qui prend toujours la voiture est visible et inutile.",
        "selection:",
        "  methode: >-",
        "    Aucun tirage. Les agents conservés sont retenus de droit ; les autres sont pris",
        "    parmi les candidats, en tourniquet sur les quatre modes dominants, du plus",
        "    observable au moins observable — modes, puis trajets, puis choix offert — et",
        "    l'identifiant numérique départage les ex æquo. Reproductible par",
        "    scripts/data/population/selectionner_personas_mesurables.py.",
        "  agents:",
    ]
    for retenu in retenus:
        mesure = retenu.mesure
        lignes += [
            f"    - person_id: '{retenu.person_id}'",
            f"      motif: {retenu.motif}",
            f"      passe_le_critere: {str(retenu.passe_le_critere).lower()}",
            f"      mode_dominant: {retenu.mode_dominant or 'inconnu'}",
        ]
        if mesure is None:
            lignes.append("      mesure: absente du run de référence")
            continue
        modes = " · ".join(
            f"{MODE_LIBELLES.get(mode, mode)} {compte}"
            for mode, compte in mesure.modes.most_common()
        )
        lignes += [
            f"      trajets: {mesure.trajets}",
            f"      options: {mesure.options_min}-{mesure.options_max}",
            f"      modes_distincts: {mesure.modes_distincts}",
            f"      modes: {json.dumps(modes, ensure_ascii=False)}",
        ]
    return "\n".join(lignes) + "\n"


def verifier(dossier: Path | str) -> list[str]:
    """Anomalies entre une population produite et son MANIFEST. Liste vide = intacte.

    ⚠ Ce n'est PAS un sceau AAMAS, et ça ne prétend pas l'être : `scripts.AAMAS.seal_population`
    tire des ménages par strates et contrôle treize marges à ± 1 point, ce qui n'a aucun sens à
    dix agents et n'est pas le but — ces dix-là servent à observer un mécanisme, jamais à
    représenter une population.

    Ce que cette vérification garantit est plus modeste et suffit ici : le fichier livré est bien
    celui que le MANIFEST décrit, il sort bien de la source annoncée, et le compte y est. Sans
    elle, une population modifiée à la main continuerait de se réclamer d'un critère mesuré.
    """
    dossier = Path(dossier)
    manifeste = dossier / "MANIFEST.yaml"
    fichier = dossier / "population.json"
    anomalies: list[str] = []
    if not manifeste.is_file() or not fichier.is_file():
        return [f"{dossier} ne porte pas population.json ET MANIFEST.yaml"]

    declare: dict[str, str] = {}
    section = ""
    for ligne in manifeste.read_text(encoding="utf-8").splitlines():
        if ligne and not ligne.startswith((" ", "#")) and ligne.rstrip().endswith(":"):
            section = ligne.rstrip()[:-1]
        elif ligne.startswith("  ") and ":" in ligne and not ligne.startswith("    "):
            clef, _, valeur = ligne.strip().partition(":")
            declare[f"{section}.{clef}"] = valeur.strip()

    empreinte = sha256(fichier)
    if declare.get("population.sha256") not in (None, empreinte):
        anomalies.append(
            f"population.json a changé depuis son manifeste : {empreinte[:12]}… au lieu de "
            f"{declare['population.sha256'][:12]}…")
    agents = json.loads(fichier.read_text(encoding="utf-8"))
    attendu = declare.get("population.n")
    if attendu and attendu.isdigit() and int(attendu) != len(agents):
        anomalies.append(f"{len(agents)} agent(s) dans le fichier, {attendu} annoncés")

    source = declare.get("source.fichier")
    if source:
        chemin_source = Path(source)
        if not chemin_source.is_file():
            anomalies.append(f"source introuvable : {source} — la sélection n'est plus rejouable")
        elif declare.get("source.sha256") != sha256(chemin_source):
            anomalies.append(f"la source {source} a changé depuis l'extraction")
    return anomalies


def main(argv: Sequence[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--verifier", type=Path, default=None,
                         help="vérifie une population déjà produite contre son MANIFEST, "
                              "et sort")
    parseur.add_argument("--run", type=Path,
                         help="répertoire d'un run déjà joué, contenant moves.csv")
    parseur.add_argument("--source", type=Path,
                         help="population.json scellée d'où les agents sont prélevés")
    parseur.add_argument("--sortie", type=Path, help="répertoire à créer")
    parseur.add_argument("--conserver", default="",
                         help="identifiants retenus de droit, séparés par des virgules")
    parseur.add_argument("-n", "--combien", type=int, default=10)
    args = parseur.parse_args(argv)

    if args.verifier:
        anomalies = verifier(args.verifier)
        if not anomalies:
            print(f"✔ {args.verifier} est intacte : empreinte, effectif et source concordent.")
            return 0
        print(f"✘ {args.verifier} — {len(anomalies)} anomalie(s) :")
        for anomalie in anomalies:
            print(f"  · {anomalie}")
        return 1

    manquants = [nom for nom in ("run", "source", "sortie") if getattr(args, nom) is None]
    if manquants:
        parseur.error("arguments requis : " + ", ".join(f"--{nom}" for nom in manquants))

    conserver = [x.strip() for x in args.conserver.split(",") if x.strip()]
    retenus = ecrire(args.run, args.source, args.sortie, conserver, args.combien)

    print(f"{len(retenus)} agents écrits → {args.sortie / 'population.json'}")
    for retenu in retenus:
        mesure = retenu.mesure
        detail = (
            f"{mesure.trajets:>3} trajets · {mesure.modes_distincts} modes · "
            f"{mesure.options_min}-{mesure.options_max} options"
            if mesure else "non mesuré sur le run de référence"
        )
        marque = "" if retenu.passe_le_critere else "  ⚠ NE PASSE PAS LE CRITÈRE"
        print(f"  {retenu.person_id:>8s}  {retenu.motif:9s} {detail}{marque}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
