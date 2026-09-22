"""Famille B — les deux prompts, et rien d'autre (ticket 100, tests fonctionnels).

Le ticket n'ajoute que **deux** demandes au modèle : le jugement d'un événement, et la
provenance d'une croyance dans la réflexion du soir. Tout le reste de sa mécanique est
déterministe et couvert par la famille A, pour zéro appel. Le budget va donc entièrement à
ces deux-là.

    python -m scripts.experiment.banc_fonctionnel.famille_b --test B2
    python -m scripts.experiment.banc_fonctionnel.famille_b            # B2, puis B3, puis B1

ORDRE D'EXÉCUTION, ET IL N'EST PAS ARBITRAIRE
----------------------------------------------
**B2 d'abord** (4 appels) : c'est le test dont l'échec est SILENCIEUX en production. Si le
modèle ignore le champ de provenance, rien ne plante — les croyances circulent simplement sans
origine, `origine` reste `vecu` partout, la règle du saut unique ne s'engage jamais et la
décision D2 devient décorative. Le passer en premier permet de s'arrêter là.

**B3 ensuite** (8 appels) : le plancher de bruit du jugement. Depuis D7, la gravité EST le
jugement ; si le jugement varie d'une répétition à l'autre, la durée de vie du souvenir varie
avec lui, et B1 ne s'interprète plus.

**B1 enfin** (15 appels) : l'échelle, qui est aussi la première observation publiable.

Chaque étape écrit ses observations AVANT de passer à la suivante : une interruption de quota
ne doit pas faire perdre ce qui a été payé.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
AGENTS = RACINE / "services" / "llm-agents"
for chemin in (str(RACINE), str(AGENTS)):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

from scripts.experiment.banc_fonctionnel import stubs  # noqa: E402
from scripts.experiment.banc_fonctionnel.clients import (  # noqa: E402
    GROQ,
    BudgetEpuise,
    ClientEpingle,
    Journal,
)

ARTICLES = ("a07_greve_eboueurs", "a09_vent_autan", "a13_punaises_metro",
            "a18_la_machine", "a25_velotoulouse")


def _texte_evenement(nom: str) -> str:
    """Le texte réellement servi, lu par le chargeur — jamais recopié à la main."""
    from llm.evenements import charger

    e = charger(AGENTS / "config" / "evenements" / f"{nom}.yaml")
    if e.texte_cite is not None:
        return e.texte_cite.servi
    return e.jours[e.premier_jour].texte


# ── B1 — l'échelle du jugement est-elle utilisée ? ──────────────────────────────────────────
async def b1_echelle(client: ClientEpingle, sortie: Path, *, personas: int = 3) -> dict:
    """3 personas × 5 textes. Quinze appels, et la première observation publiable.

    ⚠ **Ce que ce test peut invalider :** depuis D7, la gravité EST le jugement. Un modèle qui
    répond `noticeable` à tout rend toutes les durées de vie identiques, et l'expérience E3 du
    ticket 095 ne mesurerait plus rien. Une réponse constante quel que soit le texte dirait que
    le jugement mesure le prompt, pas le texte.
    """
    from llm.evenements.jugement import JugementRefuse, juger

    population = stubs.population_de_banc()[:personas]
    lignes = []
    for agent in population:
        for article in ARTICLES:
            texte = _texte_evenement(article)
            try:
                j = await juger(
                    client, agent.person_id, stubs.perception_stub(agent), texte,
                    gravite_deterministe=0.0, evenement_id=article, jour=10,
                )
                lignes.append({
                    "agent_id": agent.person_id, "article": article,
                    "intensite": j.intensite, "gravite": j.importance_retenue,
                    "valence": j.valence, "modes": "|".join(j.modes),
                    "instance": client.journal.appels[-1].instance,
                })
            except JugementRefuse as err:
                dernier = client.journal.appels[-1]
                # « SANS RÉPONSE » et « HORS GRILLE » ne disent pas la même chose : le premier
                # accuse la passerelle, le second le modèle. Les confondre enverrait corriger
                # le mauvais bout.
                vide = "VIDE" in (dernier.erreur or "") or "vide" in str(err)
                dernier.hors_schema = not vide
                lignes.append({
                    "agent_id": agent.person_id, "article": article,
                    "intensite": "SANS RÉPONSE" if vide else "HORS GRILLE",
                    "gravite": "", "valence": "",
                    "modes": "", "instance": dernier.instance,
                    "erreur": (dernier.erreur or str(err))[:140],
                })
            _ecrire_csv(sortie / "jugements.csv", lignes)

    niveaux = Counter(l["intensite"] for l in lignes)
    return {
        "appels": len(lignes),
        "niveaux": dict(niveaux),
        "echelons_distincts": len([k for k in niveaux if k != "HORS GRILLE"]),
        "hors_grille": niveaux.get("HORS GRILLE", 0),
        "constant": len(niveaux) == 1,
    }


# ── B2 — le modèle dit-il `heard` ? ─────────────────────────────────────────────────────────
async def b2_provenance(client: ClientEpingle, sortie: Path) -> dict:
    """2 agents × 2 conditions. LE test dont l'échec est silencieux en production.

    Si le modèle ne dit jamais `heard`, `origine` reste `vecu` partout, une croyance née d'un
    ouï-dire redevient indiscernable d'une croyance née d'un trajet, et **tout le lot 4 est
    inerte sans que rien ne plante**.
    """
    from llm import foyer
    from settings import settings
    from urban_mobility_agents.utils.routage import instances_pour  # noqa: F401

    population = stubs.population_de_banc()
    foyer.reinitialiser()
    settings.agent.memoire__partage_foyer_enabled = True
    lignes = []
    try:
        foyer.initialiser(population)
        ltm = stubs.MemoireLongueStub()
        for receveur, autre in ((population[1], population[0]), (population[3], population[2])):
            ltm.ajouter(stubs.reflexion_stub(
                autre.person_id,
                "The 62 bus never turned up this morning; I waited twenty minutes and walked.",
                1))
            ltm.ajouter(stubs.concept_stub(
                autre.person_id, "The 62 bus is unreliable before 9am", 1,
                observations=3, origine="vecu"))
            bloc = foyer.bloc_du_soir(ltm, receveur, stubs.ANCRE)
            for condition, contenu in (("avec_foyer", bloc), ("sans_foyer", "")):
                rendu = await _reflechir(client, receveur, contenu, condition)
                lignes.append(rendu)
                _ecrire_csv(sortie / "provenance.csv", lignes)
    finally:
        settings.agent.memoire__partage_foyer_enabled = False
        foyer.reinitialiser()

    avec = [l for l in lignes if l["condition"] == "avec_foyer"]
    sans = [l for l in lignes if l["condition"] == "sans_foyer"]
    return {
        "appels": len(lignes),
        "heard_avec_bloc": sum(int(l["n_heard"] or 0) for l in avec),
        "heard_sans_bloc": sum(int(l["n_heard"] or 0) for l in sans),
        "schema_refuse": sum(1 for l in lignes if l["erreur"]),
    }


async def _reflechir(client: ClientEpingle, agent, bloc: str, condition: str) -> dict:
    """Un appel de réflexion, sur une journée STUBÉE. Aucune journée simulée n'est attendue."""
    from urban_mobility_agents.utils.routage import instances_pour

    journee = stubs.journee_stub(agent.person_id, 1)
    contexte = {
        "today": [{"purpose": "work", "observations": [m.content for m in journee]}],
        "known_beliefs": [],
    }
    if bloc:
        contexte["household"] = bloc
    payload = {
        "category": "stm_reflection",
        "instances_admises": instances_pour("stm_reflection"),
        "agents": [{
            "agent_id": str(agent.person_id),
            "perception": stubs.perception_stub(agent),
            "context": json.dumps(contexte, indent=2, ensure_ascii=False),
        }],
        "parameters": {"temperature": 0.2, "max_tokens": 1024},
    }
    ligne = {"agent_id": agent.person_id, "condition": condition,
             "n_concepts": "", "n_heard": "", "n_lived": "", "sources": "",
             "instance": "", "erreur": ""}
    try:
        reponse = await client.execute(payload, etiquette=f"B2:{condition}")
    except BudgetEpuise:
        raise
    except Exception as err:  # noqa: BLE001
        ligne["erreur"] = f"{type(err).__name__}: {err}"[:150]
        return ligne
    ligne["instance"] = client.journal.appels[-1].instance
    concepts = list(getattr((getattr(reponse, "agents", []) or [None])[0], "concepts", []) or [])
    sources = [str((c.get("source") if isinstance(c, dict)
                    else getattr(c, "source", "")) or "") for c in concepts]
    ligne["n_concepts"] = len(concepts)
    ligne["n_heard"] = sum(1 for s in sources if s == "heard")
    ligne["n_lived"] = sum(1 for s in sources if s == "lived")
    ligne["sources"] = "|".join(sources)
    if concepts and not any(sources):
        # Le champ est REQUIS par le schéma : absent, c'est que le fournisseur ne l'impose pas.
        client.journal.appels[-1].hors_schema = True
        ligne["erreur"] = "champ `source` absent de tous les concepts"
    return ligne


# ── B3 — le plancher de bruit du JUGEMENT ───────────────────────────────────────────────────
async def b3_plancher(client: ClientEpingle, sortie: Path, *, repetitions: int = 4) -> dict:
    """2 couples × 4 répétitions, mêmes entrées, température 0,2.

    Le ticket 095 a mesuré un plancher de bruit sur les DÉCISIONS : 3,2 %. Depuis D7, il en
    faut un second, sur les JUGEMENTS — parce que la gravité, donc la durée de vie du souvenir,
    en dépend désormais entièrement.

    ⚠ Ce qui falsifierait E3 du 095 : une variation d'un échelon d'une répétition à l'autre.
    `notable` → `genant` fait passer la durée de vie de 7,8 à 11,2 jours, soit plus que l'écart
    que E3 cherche à mesurer entre deux chocs déclarés.
    """
    from llm.evenements.jugement import JugementRefuse, juger
    from llm.gravite import force_initiale

    population = stubs.population_de_banc()
    couples = ((population[0], "a13_punaises_metro"), (population[2], "c6_voiture_suspecte"))
    lignes = []
    for agent, article in couples:
        texte = _texte_evenement(article)
        for essai in range(repetitions):
            try:
                j = await juger(client, agent.person_id, stubs.perception_stub(agent), texte,
                                gravite_deterministe=0.0, evenement_id=article, jour=10)
                lignes.append({"agent_id": agent.person_id, "article": article,
                               "essai": essai, "intensite": j.intensite,
                               "gravite": j.importance_retenue,
                               "duree_jours": round(force_initiale(j.importance_retenue), 2),
                               "instance": client.journal.appels[-1].instance})
            except JugementRefuse as err:
                dernier = client.journal.appels[-1]
                vide = "VIDE" in (dernier.erreur or "") or "vide" in str(err)
                lignes.append({"agent_id": agent.person_id, "article": article,
                               "essai": essai,
                               "intensite": "SANS RÉPONSE" if vide else "HORS GRILLE",
                               "gravite": "", "duree_jours": "",
                               "instance": dernier.instance,
                               "erreur": (dernier.erreur or str(err))[:140]})
            _ecrire_csv(sortie / "plancher_jugement.csv", lignes)

    amplitudes = {}
    for agent, article in couples:
        durees = [float(l["duree_jours"]) for l in lignes
                  if l["article"] == article and l["duree_jours"] != ""]
        echelons = {l["intensite"] for l in lignes if l["article"] == article
                    and l["intensite"] not in ("SANS RÉPONSE", "HORS GRILLE")}
        amplitudes[article] = {
            "echelons": sorted(echelons),
            "stable": len(echelons) == 1,
            "amplitude_jours": round(max(durees) - min(durees), 2) if durees else None,
        }
    (sortie / "plancher_jugement.md").write_text(
        _rapport_plancher(amplitudes), encoding="utf-8")
    return {"appels": len(lignes), "amplitudes": amplitudes}


def _rapport_plancher(amplitudes: dict) -> str:
    lignes = [
        "# Plancher de bruit du JUGEMENT — ticket 100, D7",
        "",
        "Le ticket 095 § 7 bis a mesuré un plancher sur les **décisions** : 3,2 %. Depuis la",
        "décision D7, la gravité d'une entrée est l'estimation de l'agent, et elle seule. Il",
        "faut donc un second plancher, sur les **jugements** : si le jugement varie, la durée",
        "de vie du souvenir varie avec lui.",
        "",
        "**Ce chiffre se déclare avec tout résultat de gravité**, comme les 3,2 % se déclarent",
        "avec tout écart de part modale.",
        "",
    ]
    for article, mesure in sorted(amplitudes.items()):
        verdict = "STABLE" if mesure["stable"] else "⚠ INSTABLE"
        lignes.append(
            f"- **{article}** — {verdict} : échelons rendus {mesure['echelons']}, "
            f"amplitude de durée de vie **{mesure['amplitude_jours']} jour(s)**"
        )
    if any(not m["stable"] for m in amplitudes.values()):
        lignes += [
            "",
            "⚠ **Un échelon d'écart entre deux répétitions falsifie E3 du ticket 095** : "
            "`notable` → `genant` fait passer la durée de vie de 7,8 à 11,2 jours, soit plus "
            "que l'écart que E3 cherche à mesurer entre deux chocs déclarés. Le protocole de "
            "E3 doit alors être réécrit sur la gravité JUGÉE, ou joué sous `jugement: aucun`.",
        ]
    return "\n".join(lignes) + "\n"


# ── Plomberie ───────────────────────────────────────────────────────────────────────────────
def _ecrire_csv(chemin: Path, lignes: list[dict]) -> None:
    """Réécrit après CHAQUE appel : une interruption de quota ne doit rien faire perdre."""
    if not lignes:
        return
    colonnes: list[str] = []
    for l in lignes:
        for c in l:
            if c not in colonnes:
                colonnes.append(c)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes)
        w.writeheader()
        for l in lignes:
            w.writerow(l)


async def _jouer(args) -> int:
    journal = Journal()
    client = ClientEpingle(
        instances=tuple(args.instances), base_url=args.passerelle,
        budget_jetons=args.budget, pause=args.pause, journal=journal,
    )
    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    print(f"Banc fonctionnel — famille B. Instances déclarées : {list(client.instances)}")
    print(f"Budget : {args.budget} jetons de sortie, pause {args.pause}s entre appels.")
    print(f"Sorties : {sortie}\n")

    etapes = [("B2", b2_provenance), ("B3", b3_plancher), ("B1", b1_echelle)]
    if args.test:
        etapes = [(n, f) for n, f in etapes if n == args.test]
    code = 0
    for nom, etape in etapes:
        print(f"── {nom} ──")
        try:
            bilan = await etape(client, sortie)
            print(f"   {json.dumps(bilan, ensure_ascii=False)}")
        except BudgetEpuise as err:
            print(f"   ⏸ {err}")
            code = 2
            break
        except Exception as err:  # noqa: BLE001
            print(f"   💥 {type(err).__name__}: {err}")
            code = 1
            break
        finally:
            journal.ecrire(sortie / "passerelle.csv")
    print(f"\n{journal.resume()}")
    print(f"Journal des appels : {sortie / 'passerelle.csv'}")
    return code


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--test", choices=("B1", "B2", "B3"),
                   help="n'en jouer qu'un. Sans, l'ordre est B2 → B3 → B1")
    p.add_argument("--instances", nargs="+", default=list(GROQ),
                   help="les instances ADMISES. Aujourd'hui Groq seul ; les runs longs "
                        "passeront ailleurs, et chaque résultat dit laquelle a servi")
    p.add_argument("--passerelle", default="http://localhost:8000")
    p.add_argument("--budget", type=int, default=6000,
                   help="jetons de SORTIE. Au-delà, le banc s'arrête : il ne déborde pas sur "
                        "le quota des campagnes")
    p.add_argument("--pause", type=float, default=12.0,
                   help="secondes entre deux appels. Groq plafonne à ~1000 jetons de sortie "
                        "par minute, et cette limite est invisible hors du corps des 429")
    p.add_argument("--sortie", default="docs/traces/banc_fonctionnel_100")
    return asyncio.run(_jouer(p.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
