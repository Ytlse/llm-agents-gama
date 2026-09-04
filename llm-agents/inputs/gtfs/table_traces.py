"""La table des tracés : ce que la recette publie et ce que le runtime lit.

POURQUOI CE FICHIER ANNEXE EXISTE
---------------------------------
Pour faire monter un agent dans un véhicule, `Inhabitant.gaml` compare le
`shape_id` du véhicule à la liste que le côté Python a posée sur la jambe de
l'itinéraire (`shape_id_list contains each.shape_id`). Cette liste vient de
`GTFSData.get_shape_id_from_route_info`, qui consulte
`route_id_shape_lookup_map`.

Jusqu'au 2026-09-04, cette table était construite à partir du **seul feed
primaire** (`settings.gtfs.gtfs_file`, Tisséo), alors que les couches et les
courses portent **trois** réseaux depuis la veille. Mesuré : **80 `route_id`**
(17 TER, 58 cars régionaux liO, 5 lignes circulaires Tisséo) et **2 277
courses** roulaient dans GAMA sans qu'aucun itinéraire ne puisse les désigner —
`get_shape_id_from_route_info` rendait `[]`, ce qui est **indistinguable** de
« cette ligne n'a pas de tracé pour ce couple d'arrêts ».

POURQUOI LA RECETTE PUBLIE, ET NE LAISSE PAS LE RUNTIME REFABRIQUER
-------------------------------------------------------------------
Le TER ne publie **aucune géométrie** (`shapes.txt` réduit à son en-tête) : ses
`shape_id` sont *fabriqués* par `scripts/data/gama/gtfs_traces.py`
(`<route_id>:<sens>:<empreinte de la suite d'arrêts>`). Si le runtime les
refabriquait de son côté, deux implémentations de la même règle vivraient dans
le dépôt et dériveraient au premier changement — le défaut qui vient d'être
fermé sur la loi d'équipement vélo (ticket 034, lot 2).

Et refabriquer ne suffirait pas : la recette **écarte** des courses (tracé non
reconstructible, arrêt répété, moins de deux arrêts, tracé hors du périmètre de
`routes.shp`). Le runtime devrait reproduire ces écarts à l'identique pour
rester d'accord avec la couche. C'est donc la recette qui publie la
correspondance qu'elle a **réellement** utilisée, et le runtime qui la lit.

LE CONTRÔLE DE FRAÎCHETÉ
------------------------
Le fichier annexe est écrit à côté de ses deux frères — `routes.shp` (la
géométrie que GAMA dessine) et `trip_info.json` (les courses) — dans
`GAMA/CityTransport/includes/`, par la même exécution de la recette. Il note
pour chacun sa **taille** et son **empreinte sha256**, sous leur seul nom de
fichier : la vérification se fait relativement au répertoire du fichier annexe
lui-même, donc elle vaut à l'identique sur l'hôte et dans le conteneur
`controller` (qui monte `./GAMA` sur `/GAMA`) sans qu'aucun chemin absolu ne
soit gravé.

Refaire les couches seules (`make gama-layers`) change l'empreinte de
`routes.shp` : la paire est dépareillée, et le runtime l'alarme au chargement au
lieu de servir une table qui ne désigne plus les bons tracés. C'est ce contrôle
qui a manqué pendant cinq mois.

Les compteurs sont vérifiés en plus des empreintes : un fichier tronqué ou
retouché à la main a les bonnes empreintes de ses frères et une table
incomplète. Une table dont le contenu ne correspond pas à ses propres compteurs
est refusée.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Version du format. À incrémenter dès que la STRUCTURE change : un runtime qui
# lit un format qu'il ne connaît pas doit le dire, pas l'interpréter de travers.
FORMAT = 1

NOM_FICHIER = "shape_lookup.json"

# Les frères dont l'empreinte fait la fraîcheur. `routes.dbf` porte les attributs
# de la couche (dont `shape_id`) ; `routes.shp` les géométries. Les deux comptent :
# une couche dont seuls les attributs changent désigne d'autres tracés.
TEMOINS = ("routes.shp", "routes.dbf", "trip_info.json")

_BLOC = 1 << 20


class TableTracesInvalide(Exception):
    """La table annexe est inutilisable — avec le motif, pour que l'alarme le dise.

    `motif` est une étiquette courte et stable (`absente`, `illisible`,
    `format`, `temoin_absent`, `depareillee`, `comptes`) : elle sert à écrire
    un message d'alarme actionnable, pas à décider d'un repli.
    """

    def __init__(self, motif: str, detail: str):
        super().__init__(detail)
        self.motif = motif
        self.detail = detail


def empreinte_fichier(chemin: Path) -> tuple[int, str] | None:
    """(taille en octets, sha256 hexadécimal) — `None` si le fichier n'existe pas."""
    chemin = Path(chemin)
    if not chemin.exists():
        return None
    digest = hashlib.sha256()
    taille = 0
    with open(chemin, "rb") as fh:
        while True:
            bloc = fh.read(_BLOC)
            if not bloc:
                break
            taille += len(bloc)
            digest.update(bloc)
    return taille, digest.hexdigest()


def empreintes_des_temoins(dossier: Path, temoins=TEMOINS) -> dict[str, dict]:
    """Les empreintes des frères présents dans `dossier`, par nom de fichier.

    Un témoin absent n'est pas noté : la recette ne peut pas promettre la
    fraîcheur d'un fichier qu'elle n'a pas vu. Le chargement, lui, exige que
    tout témoin **noté** soit présent et identique.
    """
    dossier = Path(dossier)
    releve: dict[str, dict] = {}
    for nom in temoins:
        mesure = empreinte_fichier(dossier / nom)
        if mesure is not None:
            releve[nom] = {"octets": mesure[0], "sha256": mesure[1]}
    return releve


def comptes_de_la_table(table: dict) -> dict[str, int]:
    """Les compteurs qui décrivent la table — ceux que le chargement recoupe."""
    traces = sum(len(par_trace) for par_trace in table.values())
    arrets_notes = sum(len(stops) for par_trace in table.values()
                       for stops in par_trace.values())
    return {"route_id": len(table), "traces": traces, "couples_trace_arret": arrets_notes}


def construire(
    *,
    table: dict,
    arrets: dict,
    dossier_temoins: Path,
    genere_le: str,
    recette: str,
    noms_temoins=TEMOINS,
    reseaux: dict | None = None,
    comptes_supplementaires: dict | None = None,
) -> dict:
    """Le document à écrire — table, catalogue d'arrêts et concordance.

    `noms_temoins` porte les noms de fichiers dont la fraîcheur sera recoupée.
    La recette les passe explicitement plutôt que de s'en remettre à `TEMOINS` :
    un essai qui nomme sa couche autrement doit voir sa VRAIE couche vérifiée,
    et non zéro témoin — c'est-à-dire une fraîcheur qui ne mesurerait rien.
    """
    comptes = comptes_de_la_table(table)
    comptes["arrets_catalogue"] = len(arrets)
    if comptes_supplementaires:
        comptes.update(comptes_supplementaires)
    return {
        "format": FORMAT,
        "genere_le": genere_le,
        "recette": recette,
        "concordance": {
            "temoins": empreintes_des_temoins(dossier_temoins, noms_temoins),
            "comptes": comptes,
        },
        "reseaux": reseaux or {},
        "table": table,
        "arrets": arrets,
    }


def ecrire(chemin: Path, document: dict) -> int:
    """Écrit le document et rend sa taille en octets."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump(document, fh, ensure_ascii=False)
    return chemin.stat().st_size


def charger(chemin: Path) -> tuple[dict, dict, dict]:
    """Lit la table annexe, ou lève `TableTracesInvalide` avec son motif.

    Rend `(table, arrets, journal)` où `table` est
    `route_id → {shape_id → {stop_id: stop_sequence}}` — la structure exacte que
    consomme `GTFSData.get_shape_id_from_route_info` — et `arrets` le catalogue
    `stop_id → {stop_name, stop_lat, stop_lon}` des arrêts servis par ces
    tracés, tous réseaux confondus.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise TableTracesInvalide(
            "absente",
            f"{chemin} n'existe pas — la recette scripts/data/gama/export_trip_info.py "
            f"(make gama-trip-info) ne l'a jamais écrite, ou le montage ./GAMA ne la "
            f"rend pas visible")
    try:
        document = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TableTracesInvalide("illisible", f"{chemin} : {exc}") from exc
    if not isinstance(document, dict):
        raise TableTracesInvalide("illisible", f"{chemin} : le document n'est pas un objet JSON")

    format_lu = document.get("format")
    if format_lu != FORMAT:
        raise TableTracesInvalide(
            "format",
            f"{chemin} : format {format_lu!r}, ce runtime lit le format {FORMAT} — "
            f"relancez la recette")

    concordance = document.get("concordance") or {}
    temoins = concordance.get("temoins") or {}
    if not temoins:
        raise TableTracesInvalide(
            "depareillee",
            f"{chemin} : aucun témoin de fraîcheur noté — impossible de vérifier que la "
            f"table vient de la même génération que routes.shp et trip_info.json")
    ecarts = []
    for nom, attendu in sorted(temoins.items()):
        mesure = empreinte_fichier(chemin.parent / nom)
        if mesure is None:
            raise TableTracesInvalide(
                "temoin_absent",
                f"{chemin.parent / nom} noté par la table mais absent du disque")
        if mesure[0] != attendu.get("octets") or mesure[1] != attendu.get("sha256"):
            ecarts.append(f"{nom} (noté {attendu.get('octets')} o "
                          f"{str(attendu.get('sha256'))[:12]}…, trouvé {mesure[0]} o "
                          f"{mesure[1][:12]}…)")
    if ecarts:
        raise TableTracesInvalide(
            "depareillee",
            f"{chemin} ne vient pas de la même génération que : {', '.join(ecarts)} — "
            f"relancez make gama-trip-info, qui refait les couches PUIS les courses")

    table_brute = document.get("table")
    if not isinstance(table_brute, dict) or not table_brute:
        raise TableTracesInvalide("illisible", f"{chemin} : table absente ou vide")
    table = {
        str(route_id): {
            str(shape_id): {str(stop_id): int(rang) for stop_id, rang in stops.items()}
            for shape_id, stops in par_trace.items()
        }
        for route_id, par_trace in table_brute.items()
    }

    notes = (concordance.get("comptes") or {})
    mesures = comptes_de_la_table(table)
    desaccords = {cle: (notes[cle], mesures[cle]) for cle in mesures
                  if cle in notes and notes[cle] != mesures[cle]}
    if desaccords:
        raise TableTracesInvalide(
            "comptes",
            f"{chemin} : la table lue ne correspond pas à ses propres compteurs "
            f"(noté, lu) {desaccords} — fichier tronqué ou retouché")

    arrets = {
        str(stop_id): {
            "stop_name": str(valeur.get("stop_name", stop_id)),
            "stop_lat": float(valeur["stop_lat"]),
            "stop_lon": float(valeur["stop_lon"]),
        }
        for stop_id, valeur in (document.get("arrets") or {}).items()
    }

    journal = {
        "chemin": str(chemin),
        "genere_le": document.get("genere_le"),
        "recette": document.get("recette"),
        "reseaux": document.get("reseaux") or {},
        "comptes": mesures,
        "arrets_catalogue": len(arrets),
        "temoins": sorted(temoins),
    }
    return table, arrets, journal
