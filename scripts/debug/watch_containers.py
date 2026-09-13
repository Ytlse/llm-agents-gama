#!/usr/bin/env python3
"""Sonde la mémoire des conteneurs et prend en flagrant délit celui qui tombe.

Trois runs ont été perdus le 2026-09-07 parce que le conteneur `controller` a été tué (code
137) sans rien laisser dans ses journaux, et sans que Docker signale un OOM. Cette sonde
existe pour répondre après coup à : combien de mémoire consommait-il, qui d'autre en prenait,
et qu'a-t-il dit juste avant de mourir.

Ce qu'elle écrit dans son dossier de sortie :
  memoire.csv        une ligne par conteneur et par tour (horodatage, octets, limite, %)
  chute-<service>.txt l'état d'inspection et les dernières lignes de journal, au moment où un
                      conteneur passe de « running » à autre chose
  evenements.log     les événements Docker (stop, kill, die) des conteneurs du projet
  appelant-<...>.txt la photo des processus de l'hôte au moment d'un arrêt : qui l'a demandé
  sonde.log           le journal de la sonde elle-même : début, fin, durée, compteurs

Elle ne modifie rien : ni conteneur arrêté, ni fichier du dépôt. Interrompue (Ctrl-C, SIGTERM),
elle écrit son bilan avant de sortir.

Usage :
    python scripts/debug/watch_containers.py [--interval 10] [--out DOSSIER]
                                             [--services controller,osmnx1] [--seuil-pct 85]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SORTIE_DEFAUT = RACINE / "experiments" / ".dashboard" / "conteneurs"

# "3.547GiB", "119.6MiB", "12.86kB", "0B" → octets
_UNITES = {"B": 1, "KB": 10**3, "KIB": 2**10, "MB": 10**6, "MIB": 2**20,
           "GB": 10**9, "GIB": 2**30, "TB": 10**12, "TIB": 2**40}
_TAILLE = re.compile(r"^\s*([0-9.]+)\s*([A-Za-z]+)\s*$")


def octets(texte: str) -> int | None:
    """« 3.547GiB » → 3808428032. None si la forme est inattendue (jamais une exception)."""
    m = _TAILLE.match(texte or "")
    if not m:
        return None
    facteur = _UNITES.get(m.group(2).upper())
    try:
        return int(float(m.group(1)) * facteur) if facteur else None
    except (TypeError, ValueError):
        return None


# Les processus susceptibles d'avoir demandé un arrêt. On photographie large : c'est la seule
# occasion de les voir, un `docker compose stop` ne vivant qu'une seconde ou deux.
_SUSPECTS = re.compile(r"docker|compose|make|streamlit|pytest|python", re.IGNORECASE)
PREFIXE_PROJET = "llm-agents-gama-"


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Journal:
    """Un journal minimal : horodaté, sur la sortie standard ET dans un fichier."""

    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.chemin.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, niveau: str, message: str) -> None:
        ligne = f"{_maintenant()} | {niveau:7} | {message}"
        print(ligne, flush=True)
        with self.chemin.open("a", encoding="utf-8") as f:
            f.write(ligne + "\n")


def _docker(*args: str, timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (subprocess.TimeoutExpired, OSError) as e:
        return 1, f"{type(e).__name__}: {e}"


def lire_stats() -> list[dict]:
    """Un dict par conteneur : nom, octets, limite, pourcentage. Liste vide si docker est muet."""
    code, sortie = _docker("stats", "--no-stream", "--format", "json")
    if code != 0:
        return []
    lignes = []
    for brut in sortie.splitlines():
        brut = brut.strip()
        if not brut.startswith("{"):
            continue
        try:
            d = json.loads(brut)
        except ValueError:
            continue
        usage = str(d.get("MemUsage", ""))
        utilise, _, limite = (usage.partition("/") if "/" in usage else (usage, "", ""))
        lignes.append({
            "nom": str(d.get("Name", "")),
            "octets": octets(utilise),
            "limite": octets(limite),
            "pct": str(d.get("MemPerc", "")).rstrip("%"),
            "cpu": str(d.get("CPUPerc", "")).rstrip("%"),
        })
    return lignes


def etat_conteneur(nom: str) -> dict:
    code, sortie = _docker(
        "inspect", nom, "--format",
        "{{.State.Status}}|{{.State.ExitCode}}|{{.State.OOMKilled}}|{{.State.FinishedAt}}|{{.RestartCount}}")
    if code != 0:
        return {}
    morceaux = sortie.strip().split("|")
    if len(morceaux) < 5:
        return {}
    return {"statut": morceaux[0], "code": morceaux[1], "oom": morceaux[2],
            "fini_a": morceaux[3], "redemarrages": morceaux[4]}


def capturer_chute(nom: str, dossier: Path, journal: Journal) -> None:
    """L'état d'inspection et les 200 dernières lignes de journal, au moment de la chute."""
    etat = etat_conteneur(nom)
    _, logs = _docker("logs", "--tail", "200", nom, timeout=30)
    chemin = dossier / f"chute-{nom}.txt"
    chemin.write_text(
        f"# chute détectée à {_maintenant()}\n"
        f"# état : {json.dumps(etat, ensure_ascii=False)}\n\n{logs}",
        encoding="utf-8")
    journal("ERROR", f"[ALARME] {nom} n'est plus en marche — statut={etat.get('statut')} "
                     f"code={etat.get('code')} OOMKilled={etat.get('oom')} "
                     f"redémarrages={etat.get('redemarrages')} · capture : {chemin}")


def photographier_processus() -> str:
    """Les processus de l'hôte, ici et maintenant. Sans quoi l'appelant reste anonyme.

    Docker journalise l'appel (`ContainerStopComposeLinux`) mais pas qui l'a passé. Un
    `docker compose stop` ne vit qu'une seconde : la photo doit être prise à l'instant de
    l'événement, pas au tour de sonde suivant.
    """
    try:
        p = subprocess.run(["ps", "-eo", "pid,ppid,lstart,command"],
                           capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"(photo impossible : {type(e).__name__}: {e})"
    gardees = [l for l in (p.stdout or "").splitlines() if _SUSPECTS.search(l)]
    return "\n".join(gardees[:80]) or "(aucun processus suspect au moment de l'événement)"


def ecouter_evenements(dossier: Path, journal: "Journal", arret: dict, compteurs: dict) -> None:
    """Écoute `docker events` et photographie l'hôte dès qu'un conteneur du projet s'arrête.

    Fil séparé : le flux est bloquant. Toute erreur y est journalisée et le fil s'arrête, sans
    jamais faire tomber la sonde — mesurer ne doit pas casser ce qu'on mesure.
    """
    interessants = {"stop", "kill", "die"}
    try:
        flux = subprocess.Popen(
            ["docker", "events", "--filter", "type=container", "--format", "{{json .}}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    except OSError as e:
        journal("WARNING", f"`docker events` indisponible ({type(e).__name__}) — la sonde continue sans")
        return
    journal("INFO", "écoute de `docker events` en marche (stop, kill, die)")
    try:
        for ligne in flux.stdout or []:
            if arret["demande"]:
                break
            try:
                ev = json.loads(ligne)
            except ValueError:
                continue
            action = str(ev.get("Action", "")).split(":")[0]
            nom = str((ev.get("Actor") or {}).get("Attributes", {}).get("name", ""))
            if action not in interessants or not nom.startswith(PREFIXE_PROJET):
                continue
            compteurs["evenements"] = compteurs.get("evenements", 0) + 1
            with (dossier / "evenements.log").open("a", encoding="utf-8") as f:
                f.write(f"{_maintenant()} {action:5} {nom} "
                        f"{json.dumps(ev.get('Actor', {}), ensure_ascii=False)}\n")
            if action in {"stop", "kill"}:
                photo = photographier_processus()
                cible = dossier / f"appelant-{nom}-{action}-{datetime.now().strftime('%H_%M_%S')}.txt"
                cible.write_text(
                    f"# {action} sur {nom} à {_maintenant()}\n"
                    f"# événement : {json.dumps(ev, ensure_ascii=False)}\n\n"
                    f"# processus de l'hôte à cet instant (pid, ppid, démarré à, commande)\n{photo}\n",
                    encoding="utf-8")
                journal("ERROR", f"[ALARME] {action} demandé sur {nom} — photo des processus : {cible}")
    finally:
        flux.terminate()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--interval", type=float, default=10.0, help="secondes entre deux tours (défaut 10)")
    p.add_argument("--out", default=None, help="dossier de sortie (défaut experiments/.dashboard/conteneurs/<horodatage>)")
    p.add_argument("--services", default="", help="liste séparée par des virgules ; vide = tous les conteneurs vus")
    p.add_argument("--seuil-pct", type=float, default=85.0, help="alarme au-delà de ce %% de la limite mémoire")
    p.add_argument("--duree", type=float, default=0.0, help="s'arrêter après N secondes (0 = jusqu'à interruption)")
    a = p.parse_args(argv)

    dossier = Path(a.out) if a.out else SORTIE_DEFAUT / datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    dossier.mkdir(parents=True, exist_ok=True)
    journal = Journal(dossier / "sonde.log")
    filtre = [s.strip() for s in a.services.split(",") if s.strip()]

    arret = {"demande": False}

    def _sortir(signum, _frame):
        arret["demande"] = True
        journal("INFO", f"signal {signum} reçu — bilan puis sortie")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _sortir)

    journal("INFO", f"début de la sonde · intervalle {a.interval}s · seuil {a.seuil_pct}% · "
                    f"services {filtre or 'tous'} · sortie {dossier}")

    compteurs_ev: dict[str, int] = {}
    threading.Thread(target=ecouter_evenements, args=(dossier, journal, arret, compteurs_ev),
                     daemon=True, name="docker-events").start()

    csv_chemin = dossier / "memoire.csv"
    nouveau = not csv_chemin.exists()
    debut = time.monotonic()
    tours = mesures = alarmes_seuil = chutes = docker_muet = 0
    vus_en_marche: set[str] = set()
    alarme_active: set[str] = set()
    pic: dict[str, int] = {}

    with csv_chemin.open("a", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        if nouveau:
            ecrivain.writerow(["horodatage", "service", "octets", "limite", "pct", "cpu_pct"])
        while not arret["demande"]:
            tours += 1
            stats = lire_stats()
            if not stats:
                docker_muet += 1
                journal("WARNING", "docker n'a rien répondu à `stats` — la sonde continue")
            for s in stats:
                nom = s["nom"]
                if filtre and not any(f in nom for f in filtre):
                    continue
                mesures += 1
                ecrivain.writerow([_maintenant(), nom, s["octets"], s["limite"], s["pct"], s["cpu"]])
                if s["octets"] is not None:
                    pic[nom] = max(pic.get(nom, 0), s["octets"])
                vus_en_marche.add(nom)
                try:
                    pct = float(s["pct"])
                except (TypeError, ValueError):
                    pct = 0.0
                # Alarme sur FRONT MONTANT seulement : un conteneur au plafond ne doit pas
                # noyer le journal à chaque tour.
                if pct >= a.seuil_pct and nom not in alarme_active:
                    alarme_active.add(nom)
                    alarmes_seuil += 1
                    journal("ERROR", f"[ALARME] {nom} à {pct:.0f} % de sa limite mémoire "
                                     f"({s['octets']} / {s['limite']} octets)")
                elif pct < a.seuil_pct * 0.9:
                    alarme_active.discard(nom)
            f.flush()

            # Un conteneur vu en marche puis absent des stats : il est tombé.
            presents = {s["nom"] for s in stats}
            for nom in sorted(vus_en_marche - presents):
                chutes += 1
                capturer_chute(nom, dossier, journal)
                vus_en_marche.discard(nom)

            if a.duree and (time.monotonic() - debut) >= a.duree:
                break
            fin_tour = time.monotonic() + a.interval
            while time.monotonic() < fin_tour and not arret["demande"]:
                time.sleep(min(0.5, max(0.05, fin_tour - time.monotonic())))

    duree = time.monotonic() - debut
    sommet = ", ".join(f"{n} {o / 2**30:.2f} Gio" for n, o in sorted(pic.items(), key=lambda x: -x[1])[:5])
    journal("INFO", f"fin de la sonde · {duree:.0f}s · {tours} tours · {mesures} mesures · "
                    f"{chutes} chute(s) · {alarmes_seuil} alarme(s) de seuil · "
                    f"{compteurs_ev.get('evenements', 0)} événement(s) docker · "
                    f"{docker_muet} tour(s) sans réponse de docker")
    journal("INFO", f"pics de mémoire : {sommet or 'aucune mesure'}")
    journal("INFO", f"succès : mesures écrites dans {csv_chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
