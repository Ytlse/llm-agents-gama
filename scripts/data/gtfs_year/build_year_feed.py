"""
Construit un feed GTFS couvrant une année entière à partir d'exports partiels.

POURQUOI
--------
Les exports Tisséo sont « glissants » : chacun couvre environ 35 jours et n'est
complet que sur les premières semaines. Le feed en service ne couvre que 58
jours ; hors de cette fenêtre, la simulation ne trouve aucun transport en commun
et se contente d'un avertissement. Ce script produit un feed annuel où chaque
journée porte soit l'offre réelle publiée par l'opérateur, soit la copie
verbatim d'une journée réelle de même signature — même jour de semaine, même
classe de période scolaire. Aucun horaire n'est synthétisé.

CE QU'IL GARANTIT
-----------------
  * Une seule source par date. Prendre l'union de deux exports qui se
    recouvrent sur-sert : le feed actuellement en service donne 13 250 trips le
    08/04/2026 là où ses deux sources en donnent 12 652 et 12 660.
  * L'offre des dates réelles est préservée. Le contrôle V2 recalcule, en
    relisant les fichiers écrits, l'empreinte de chaque journée réelle et exige
    l'égalité stricte avec sa source.
  * Rien n'est extrapolé en silence. Chaque journée du feed est tracée dans un
    manifeste : d'où elle vient, avec quel écart saisonnier, à quel niveau de
    confiance.
  * Les journées que la source déclare sans service (le 1er mai) restent vides
    plutôt que d'être inventées.

USAGE
-----
    make gtfs-year                         # Tisséo + TER + liO, 2026 et 2027
    make gtfs-year ANNEES=2026 RESEAU=tisseo
    make gtfs-year DRY=1                   # plan et manifeste seulement
    make gtfs-year HOLDOUT=202605          # masque mai 2026 et mesure l'écart

    python -m scripts.data.gtfs_year.build_year_feed --annee 2026 --annee 2027

CODES DE SORTIE
---------------
    0  feed construit et tous les invariants tenus
    1  ressource absente (exports introuvables, calendrier injoignable)
    2  invariant bloquant démenti — le feed produit ne doit pas être publié
    4  feed construit, mais confiance dégradée (trop de journées extrapolées
       sans donneur de même nature, ou hold-out hors tolérance)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from scripts.data.gtfs_year import assemblage, calendar_fr, donneurs, gtfs_io, offre, validation  # noqa: E402
from scripts.data.gtfs_year.donneurs import BASSE, EXTRAPOLE, REEL, SANS_SERVICE  # noqa: E402
from scripts.data.gtfs_year.validation import BLOQUANT  # noqa: E402

CONFIG_DEFAUT = Path(__file__).resolve().parent / "feed_year.yaml"

CODE_OK = 0
CODE_RESSOURCE = 1
CODE_INVARIANT = 2
CODE_CONFIANCE = 4

IDENTITES = {
    "tisseo": {"feed_id": "tisseo", "publisher": "Tisséo", "url": "https://www.tisseo.fr"},
    "ter": {"feed_id": "ter", "publisher": "SNCF Voyageurs", "url": "https://www.sncf.com"},
    "lio": {
        "feed_id": "lio",
        "publisher": "Région Occitanie / Pyrénées-Méditerranée",
        "url": "https://www.lio-occitanie.fr",
    },
}

RESEAUX = tuple(IDENTITES)


def relatif(chemin: Path) -> str:
    """Chemin relatif au dépôt quand c'est possible, absolu sinon."""
    try:
        return str(chemin.relative_to(REPO_ROOT))
    except ValueError:
        return str(chemin)


def journal_horodate(message: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {message}", flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# Contexte calendaire
# ──────────────────────────────────────────────────────────────────────────────


def contexte_calendaire(
    annees: set[int], config: dict, rafraichir: bool, journal
) -> tuple[list[calendar_fr.Periode], dict[str, str]]:
    """Périodes de vacances et jours fériés couvrant toutes les années en jeu.

    Les donneurs d'une année cible peuvent venir d'une autre année : il faut
    donc pouvoir classer les dates des deux.
    """
    periodes: dict[tuple[str, dt.date, dt.date], calendar_fr.Periode] = {}
    feries: dict[str, str] = {}
    for annee in sorted(annees):
        for periode in calendar_fr.vacances(
            annee, config["calendrier"]["localite"], rafraichir, journal
        ):
            periodes[(periode.classe, periode.debut, periode.fin)] = periode
        feries.update(calendar_fr.feries(annee, rafraichir, journal))
    ordonnees = sorted(periodes.values(), key=lambda p: p.debut)
    journal(
        f"    calendrier : {len(ordonnees)} période(s) de vacances, {len(feries)} jour(s) férié(s) "
        f"sur {sorted(annees)}"
    )
    return ordonnees, feries


# ──────────────────────────────────────────────────────────────────────────────
# Traces
# ──────────────────────────────────────────────────────────────────────────────


def ecrire_manifeste(
    trace: Path,
    reseau: str,
    annee: int,
    plan: dict[str, donneurs.Provenance],
    exports: list[gtfs_io.Export],
    stats: assemblage.Statistiques | None,
    violations: list[validation.Violation],
    empreintes: dict[str, str],
    decalages: dict[str, int],
) -> Path:
    trace.mkdir(parents=True, exist_ok=True)
    base = f"{reseau}_{annee}"

    with open(trace / f"provenance_{base}.csv", "w", encoding="utf-8", newline="") as fichier:
        colonnes = list(next(iter(plan.values())).en_dict().keys())
        writer = csv.DictWriter(fichier, fieldnames=colonnes, lineterminator="\n")
        writer.writeheader()
        for date in sorted(plan):
            writer.writerow(plan[date].en_dict())

    resume = {
        "reseau": reseau,
        "annee": annee,
        "exports": [
            {
                "etiquette": e.etiquette,
                "chemin": relatif(e.chemin),
                "md5": e.empreinte,
                "date_min": e.date_min,
                "date_max": e.date_max,
                "fin_fiable": e.fin_fiable,
                "jours_fiables": len(e.jours_fiables),
            }
            for e in exports
        ],
        "decalages_periodes_appris": decalages,
        "journees": {
            "reelles": sum(1 for p in plan.values() if p.mode == REEL),
            "extrapolees": sum(1 for p in plan.values() if p.mode == EXTRAPOLE),
            "sans_service": sum(1 for p in plan.values() if p.mode == SANS_SERVICE),
            "confiance_basse": sum(1 for p in plan.values() if p.confiance == BASSE),
        },
        "statistiques": stats.__dict__ if stats else None,
        "violations": [{"code": v.code, "gravite": v.gravite, "message": v.message} for v in violations],
        "empreintes_offre": empreintes,
    }
    chemin = trace / f"manifeste_{base}.json"
    chemin.write_text(
        json.dumps(resume, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return chemin


def dates_sans_service(parametres: dict, annee: int, journal) -> set[str]:
    """Journées à laisser vides dans l'année cible.

    Une date que la source déclare sans service vaut aussi pour les autres
    années : le 1er mai, omis par les deux exports de 2026 qui l'englobent, ne
    doit pas plus rouler en 2027. La reconduction se fait sur le jour et le mois,
    et jamais sur autre chose qu'une date explicitement constatée.
    """
    declarees = list(parametres.get("dates_sans_service_confirme") or [])
    sortie: set[str] = set()
    for declaree in declarees:
        reportee = f"{annee}{declaree[4:]}"
        if reportee not in sortie:
            sortie.add(reportee)
            if reportee == declaree:
                continue
            journal(
                f"    sans service : {reportee} reconduit depuis {declaree}, constaté sans service à la source"
            )
    return sortie


# ──────────────────────────────────────────────────────────────────────────────
# Construction d'un réseau pour une année
# ──────────────────────────────────────────────────────────────────────────────


def construire_reseau(
    reseau: str,
    annee: int,
    config: dict,
    racine_sortie: Path,
    trace: Path,
    dry_run: bool,
    holdout_mois: str | None,
    rafraichir: bool,
    journal,
) -> int:
    debut = time.time()
    journal(f"══ {reseau} — année {annee} ══")

    parametres = config["reseaux"][reseau]
    racines = [REPO_ROOT / chemin for chemin in parametres["exports"]]
    exports = gtfs_io.decouvrir(racines, journal)
    if not exports:
        journal(f"[ALARME] {reseau} : aucun export trouvé dans {', '.join(str(r) for r in racines)}")
        return CODE_RESSOURCE

    index_par_export: dict[str, offre.IndexExport] = {}
    dates_fiables: dict[str, list[str]] = {}
    for export in exports:
        index = offre.indexer(export, journal)
        agences = {a.get("agency_id", "") for a in index.agences}
        attendue = parametres["agency_id_attendu"]
        if attendue not in agences:
            journal(
                f"[ALARME] {export.etiquette} : agence {sorted(agences)} au lieu de {attendue!r} — export écarté"
            )
            continue
        retenues = offre.fenetre_fiable(index, config["fiabilite"], journal)
        if not retenues:
            continue
        index_par_export[export.etiquette] = index
        dates_fiables[export.etiquette] = retenues

    if not index_par_export:
        journal(f"[ALARME] {reseau} : aucun export exploitable après contrôle de fiabilité")
        return CODE_RESSOURCE

    source_par_date = donneurs.autorite(index_par_export, dates_fiables, journal)

    # Le hold-out masque un mois réel pour mesurer ce que l'extrapolation aurait
    # produit à sa place.
    verite_holdout: dict[str, int] = {}
    if holdout_mois:
        masquees = [d for d in source_par_date if d.startswith(holdout_mois)]
        for date in masquees:
            verite_holdout[date] = index_par_export[source_par_date[date]].nb_trips(date)
            del source_par_date[date]
        journal(f"    hold-out : {len(masquees)} journée(s) de {holdout_mois} masquée(s)")

    annees_en_jeu = {annee} | {int(d[:4]) for d in source_par_date}
    try:
        periodes, feries = contexte_calendaire(annees_en_jeu, config, rafraichir, journal)
    except RuntimeError as err:
        journal(str(err))
        return CODE_RESSOURCE

    offre_reelle = {
        date: index_par_export[etiquette].nb_trips(date)
        for date, etiquette in source_par_date.items()
    }
    decalages = calendar_fr.ajuster_bornes(
        periodes, feries, offre_reelle, config["calendrier"]["decalages_debut_testes"], journal
    )

    plan = donneurs.plan_annee(
        annee=annee,
        dates_annee=calendar_fr.dates_annee(annee),
        source_par_date=source_par_date,
        index_par_export=index_par_export,
        periodes=periodes,
        feries=feries,
        decalages=decalages,
        config_extrap=config["extrapolation"],
        dates_sans_service=dates_sans_service(parametres, annee, journal),
        journal=journal,
    )

    if dry_run:
        chemin = ecrire_manifeste(trace, reseau, annee, plan, exports, None, [], {}, decalages)
        journal(f"    à blanc : aucun feed écrit, manifeste dans {relatif(chemin)}")
        journal(f"══ {reseau} {annee} terminé à blanc en {time.time() - debut:.1f} s ══")
        return CODE_OK

    sortie = racine_sortie / f"{reseau}_{annee}"
    # Version dérivée des EXPORTS, pas de la date du jour : un feed_version daté
    # ferait différer le zip d'un jour à l'autre à entrées identiques, alors que le
    # build est annoncé reproductible au bit près.
    empreinte_entrees = hashlib.sha256(
        "|".join(sorted(e.empreinte for e in exports)).encode("utf-8")
    ).hexdigest()[:12]
    version = f"{annee}-{empreinte_entrees}"
    stats = assemblage.construire(
        sortie=sortie,
        plan=plan,
        index_par_export=index_par_export,
        config=config,
        identite_feed={**IDENTITES[reseau], "version": version},
        journal=journal,
    )
    journal(
        f"    écrit : {stats.trips_ecrits:,} trips, {stats.horaires_ecrits:,} horaires, "
        f"{stats.services:,} services, {stats.lignes_calendrier:,} lignes de calendrier "
        f"({stats.trips_fusionnes:,} trips fusionnés par contenu, {stats.trips_forkes} forks, "
        f"{stats.doublons_de_contenu:,} doublons de contenu préservés, "
        f"{stats.shapes_dupliquees} géométries dupliquées)"
    )

    violations, empreintes, index_sortie = validation.controler(sortie, plan, index_par_export, config, journal)

    code = CODE_OK
    for violation in violations:
        journal(f"    {violation}")
    if any(v.gravite == BLOQUANT for v in violations):
        code = CODE_INVARIANT

    if holdout_mois and verite_holdout:
        rapport, pire = validation.holdout(
            plan, index_sortie, verite_holdout, float(config["controles"]["holdout_ecart_max"]), journal
        )
        (trace / f"holdout_{reseau}_{annee}_{holdout_mois}.json").write_text(
            json.dumps({"pire_ecart": pire, "journees": rapport}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if pire > float(config["controles"]["holdout_ecart_max"]) and code == CODE_OK:
            code = CODE_CONFIANCE

    basses = sum(1 for p in plan.values() if p.confiance == BASSE)
    if basses > int(config["controles"]["dates_confiance_basse_max"]) and code == CODE_OK:
        journal(
            f"[ALARME] {basses} journée(s) en confiance basse, au-delà du seuil "
            f"{config['controles']['dates_confiance_basse_max']} — feed utilisable mais à déclarer comme tel"
        )
        code = CODE_CONFIANCE

    archive = gtfs_io.zipper(sortie, racine_sortie / f"{reseau}_{annee}.zip")
    taille_mo = archive.stat().st_size / 1_048_576
    chemin_manifeste = ecrire_manifeste(
        trace, reseau, annee, plan, exports, stats, violations, empreintes, decalages
    )

    journal(
        f"══ {reseau} {annee} terminé en {time.time() - debut:.1f} s — "
        f"{relatif(archive)} ({taille_mo:.1f} Mo), "
        f"manifeste {relatif(chemin_manifeste)}, code {code} ══"
    )
    return code


# ──────────────────────────────────────────────────────────────────────────────
# Entrée
# ──────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.add_argument("--config", type=Path, default=CONFIG_DEFAUT, help="paramètres du build")
    parseur.add_argument(
        "--reseau", action="append", choices=list(RESEAUX),
        help="réseau à construire (défaut : tous ceux déclarés)",
    )
    parseur.add_argument(
        "--annee", action="append", type=int, help="année cible, répétable (défaut : 2026 et 2027)"
    )
    parseur.add_argument("--sortie", type=Path, default=REPO_ROOT / "data" / "gtfs_year")
    parseur.add_argument("--trace", type=Path, default=None, help="répertoire des traces de build")
    parseur.add_argument("--dry-run", action="store_true", help="planifier sans écrire de feed")
    parseur.add_argument(
        "--holdout", metavar="AAAAMM", help="masquer ce mois réel et mesurer l'écart d'extrapolation"
    )
    parseur.add_argument(
        "--rafraichir-calendrier", action="store_true", help="réinterroger les APIs de calendrier"
    )
    args = parseur.parse_args(argv)

    if not args.config.exists():
        journal_horodate(f"[ALARME] configuration introuvable : {args.config}")
        return CODE_RESSOURCE
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    reseaux = args.reseau or list(RESEAUX)
    annees = args.annee or [2026, 2027]
    trace = args.trace or (REPO_ROOT / "docs" / "traces" / f"{dt.date.today():%Y-%m-%d}_gtfs_annee")

    journal_horodate(
        f"début — réseaux {reseaux}, années {annees}, sortie {args.sortie}, traces {trace}"
    )
    depart = time.time()
    codes: list[int] = []
    for reseau in reseaux:
        for annee in annees:
            codes.append(
                construire_reseau(
                    reseau=reseau,
                    annee=annee,
                    config=config,
                    racine_sortie=args.sortie,
                    trace=trace,
                    dry_run=args.dry_run,
                    holdout_mois=args.holdout,
                    rafraichir=args.rafraichir_calendrier,
                    journal=journal_horodate,
                )
            )

    pire = max(codes) if codes else CODE_RESSOURCE
    # Un invariant démenti prime sur une confiance dégradée.
    if CODE_INVARIANT in codes:
        pire = CODE_INVARIANT
    elif CODE_RESSOURCE in codes:
        pire = CODE_RESSOURCE

    journal_horodate(
        f"fin — {len(codes)} build(s) en {time.time() - depart:.1f} s, code de sortie {pire}"
    )
    return pire


if __name__ == "__main__":
    raise SystemExit(main())
