"""Onglet « 🔁 Campagne » (ticket 074, lot E) : où en est le lot, et quand reprend-il ?

Une campagne dure des jours et passe l'essentiel de son temps à attendre un renouvellement de
quota. La question que se pose celui qui ouvre cette page n'est donc pas « ça tourne ? » mais
**« qu'est-ce qui reste, et quand ? »**. Tout le volet répond à celle-là : l'avancement par
phase, l'expérience en cours et depuis combien de temps, le temps restant avant la prochaine
fenêtre, l'historique des sommeils, et les échecs avec leur motif.

LECTURE SEULE, SAUF DEUX BOUTONS. Le volet lit `campagnes/<nom>.yaml`, `campagnes/<nom>/etat.json`
et les `etat.json` des exécutions — des fichiers, sur le disque de l'hôte. Il n'importe pas la
pile du contrôleur (comme `experiences.py`, et pour la même raison : le tableau de bord doit
s'ouvrir même quand les conteneurs sont éteints). Lancer et arrêter passent par le registre de
jobs suivi dans « 📟 Activités en cours ».

CE QU'IL NE FAIT PAS. Il ne recalcule rien. Si `etat.json` dit qu'une expérience est faite,
elle est affichée faite — la vérité de l'avancement vit dans le pilote, pas dans la page, et
deux sources de vérité pour un même chiffre finissent toujours par diverger.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOSSIER_CAMPAGNES = REPO_ROOT / "campagnes"
DOSSIER_EXPERIENCES = REPO_ROOT / "data" / "experiences"

# `experiences.archive` nomme les états ; on ne les recopie pas. Le paquet n'est pas
# installé côté tableau de bord : on l'importe par son chemin, et on retombe sur les
# littéraux si l'import échoue — une page qui ne s'ouvre pas ne dit rien du tout.
_CHEMIN_PAQUET = REPO_ROOT / "services" / "llm-agents"
try:  # pragma: no cover - dépend de l'arborescence
    if str(_CHEMIN_PAQUET) not in sys.path:
        sys.path.insert(0, str(_CHEMIN_PAQUET))
    from experiences.archive import ETAT_EN_ATTENTE_QUOTA, ETAT_TERMINEE
except Exception:  # noqa: BLE001
    ETAT_TERMINEE, ETAT_EN_ATTENTE_QUOTA = "terminee", "en_attente_quota"

#: Comment chaque état se montre. Un état inconnu garde son nom plutôt que de disparaître
#: derrière une icône par défaut : c'est ce nom qui permet d'aller voir.
ICONE = {
    ETAT_TERMINEE: "✅",
    "en_cours": "▶️",
    ETAT_EN_ATTENTE_QUOTA: "💤",
    "en_attente_agent": "💤",
    "en_pause": "⏸️",
    "epuisee": "🪫",
    "arretee": "⏹️",
    "interrompue": "💥",
    "definie": "⚪",
}


# ── Rendre un nom calculé lisible ────────────────────────────────────────────

#: Segment de nom → ce qu'il veut dire, en clair. La table est VOLONTAIREMENT incomplète :
#: un segment inconnu est rendu tel quel plutôt que tu. Une glose qui avale ce qu'elle ne
#: connaît pas ment par omission, et c'est précisément sur un nom d'expérience qu'on ne peut
#: pas se le permettre.
#: Type de décideur déterministe → ce qu'il fait, en clair. Un type inconnu garde son nom :
#: une glose qui avale ce qu'elle ne connaît pas ment par omission, et c'est précisément sur
#: un décideur qu'on ne peut pas se le permettre.
GLOSE = {
    "aleatoire": "aléatoire",
    "duree_minimale": "durée minimale",
    "majoritaire_voiture": "tout-voiture",
}


def libelle(nom: str) -> str:
    """Un nom d'expérience, rendu lisible — depuis sa DÉFINITION, pas depuis son nom.

    Le nom est calculé et abrégé (`pop-1000_AAMAS_v6`, `proexp04`, `nochn`) : le relire pour
    le gloser reviendrait à écrire un second décodeur, qui dériverait du premier. On lit donc
    `experience.yaml`, qui porte les valeurs entières, et on n'invente rien.

    Repli sur le nom brut quand la définition manque — une expérience archivée, un nom lu dans
    un état de campagne plus vieux que le disque. Mieux vaut un nom brut qu'une glose fausse.
    """
    doc = _lire_yaml(DOSSIER_EXPERIENCES / nom / "experience.yaml")
    if not doc:
        return nom
    bouts: list[str] = []

    dec = doc.get("decideur") or {}
    type_dec = str(dec.get("type") or "")
    if type_dec in ("passerelle", "antigravity"):
        modele = str(dec.get("modele") or "modèle inconnu")
        bouts.append(modele + (" via Antigravity" if type_dec == "antigravity" else ""))
        params = dec.get("parametres") or {}
        if params.get("temperature") is not None:
            bouts.append(f"T={params['temperature']}")
    elif type_dec == "modele":
        artefact = Path(str(dec.get("artefact") or "")).stem or "artefact inconnu"
        bouts.append(f"modèle ajusté {artefact}")
    else:
        bouts.append(f"témoin {GLOSE.get(type_dec, type_dec) or 'inconnu'}")

    variante = (doc.get("gabarit") or {}).get("variante")
    if variante:
        bouts.append(f"prompt {variante}")

    population = Path(str((doc.get("population") or {}).get("chemin") or "")).name
    if population:
        bouts.append(f"cohorte {population}")
    jeu = (doc.get("jeu") or {}).get("nom")
    if jeu:
        bouts.append(f"jeu {jeu}")

    if doc.get("vehicule_chaine") is False:
        bouts.append("chaîne des véhicules coupée")
    if doc.get("verrou_retour") is False:
        bouts.append("verrou de retour coupé")
    if str(doc.get("mode") or "") == "sans_simulateur":
        bouts.append("sans simulateur")
    return " · ".join(bouts)


# ── Lecture ──────────────────────────────────────────────────────────────────


def campagnes_connues() -> list[str]:
    if not DOSSIER_CAMPAGNES.is_dir():
        return []
    return sorted(p.stem for p in DOSSIER_CAMPAGNES.glob("*.yaml"))


def _lire_yaml(chemin: Path) -> dict:
    try:
        return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _lire_json(chemin: Path) -> dict:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def etat_execution(exp: str) -> dict:
    """État de la dernière exécution d'une expérience (dossiers horodatés → ordre lexical)."""
    executions = DOSSIER_EXPERIENCES / exp / "executions"
    if not executions.is_dir():
        return {"etat": "definie", "raison": None, "maj": None}
    dossiers = sorted(p for p in executions.iterdir() if p.is_dir())
    if not dossiers:
        return {"etat": "definie", "raison": None, "maj": None}
    brut = _lire_json(dossiers[-1] / "etat.json")
    return {"etat": brut.get("etat", "en_cours"), "raison": brut.get("raison"),
            "maj": brut.get("maj")}


def vue(nom: str) -> dict:
    """Tout ce que la page affiche, en une lecture. `definition` vide = campagne illisible."""
    definition = _lire_yaml(DOSSIER_CAMPAGNES / f"{nom}.yaml")
    pilote = _lire_json(DOSSIER_CAMPAGNES / nom / "etat.json")
    phases = []
    for brut in definition.get("phases") or []:
        exps = [str(e) for e in (brut.get("experiences") or [])]
        etats = {e: etat_execution(e) for e in exps}
        phases.append({
            "nom": str(brut.get("nom") or "?"),
            "raison": str(brut.get("raison") or ""),
            "experiences": exps,
            "etats": etats,
            "faites": [e for e, s in etats.items() if s["etat"] == ETAT_TERMINEE],
        })
    toutes = [e for p in phases for e in p["experiences"]]
    faites = [e for p in phases for e in p["faites"]]
    return {
        "nom": str(definition.get("nom") or nom),
        "note": str(definition.get("note") or ""),
        "substrat": definition.get("substrat") or {},
        "phases": phases,
        "total": len(toutes),
        "faites": faites,
        "pilote": pilote,
        "arret_demande": (DOSSIER_CAMPAGNES / nom / "STOP").exists(),
        "lisible": bool(phases),
    }


def secondes_avant_renouvellement(maintenant: datetime | None = None) -> tuple[str, int]:
    """Prochaine réouverture de quota. Repli sur minuit UTC si la passerelle n'est pas là.

    Le repli est honnête plutôt que muet : une page qui afficherait « — » laisserait croire
    qu'il n'y a pas de fenêtre, quand il y en a une qu'on n'a pas su calculer.
    """
    now = maintenant or datetime.now(timezone.utc)
    try:
        from llm_gateway.core.quota import next_quota_reset

        from experiences.ressources import FUSEAU_QUOTA_DEFAUT

        tot = min(next_quota_reset(f, now) for f in (FUSEAU_QUOTA_DEFAUT, None))
    except Exception:  # noqa: BLE001 — passerelle absente : minuit UTC, et on le dit
        jour = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tot = jour.replace(day=jour.day) if now == jour else jour
        from datetime import timedelta

        tot = jour + timedelta(days=1)
    return tot.isoformat(timespec="seconds"), max(0, int((tot - now).total_seconds()))


def _duree(depuis: str | None, maintenant: datetime | None = None) -> str:
    if not depuis:
        return "—"
    try:
        t = datetime.fromisoformat(depuis)
    except ValueError:
        return "—"
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    secondes = max(0, int(((maintenant or datetime.now(timezone.utc)) - t).total_seconds()))
    if secondes < 90:
        return f"{secondes} s"
    if secondes < 5400:
        return f"{secondes // 60} min"
    return f"{secondes / 3600:.1f} h"


# ── Rendu ────────────────────────────────────────────────────────────────────


def render(st, pd, *, lancer: Optional[Callable[[str, dict], None]] = None,
           jobs: Optional[Callable[[], list]] = None) -> None:
    """`lancer(cible, variables)` démarre un job make ; `jobs()` liste ceux du registre."""
    st.subheader("🔁 Campagne")

    connues = campagnes_connues()
    if not connues:
        st.info(
            "Aucune campagne définie. Une campagne est un fichier `campagnes/<nom>.yaml` : "
            "un lot nommé d'expériences, en phases, mené jusqu'au bout à travers les "
            "renouvellements de quota."
        )
        st.caption("Voir `docs/tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md`, lot D.")
        return

    nom = st.selectbox("Campagne", connues, key="campagne-choix")
    v = vue(nom)
    if not v["lisible"]:
        st.error(f"`campagnes/{nom}.yaml` est illisible ou ne porte aucune phase.")
        return

    if v["note"]:
        st.caption(v["note"])

    pilote = v["pilote"]
    total, faites = v["total"], len(v["faites"])

    # ── Bandeau ───────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avancement", f"{faites}/{total}")
    en_cours = (pilote or {}).get("courante")
    c2.metric("En cours", libelle(en_cours).split(" · ")[0] if en_cours else "—",
          help=(libelle(en_cours) + f"\n\n`{en_cours}`") if en_cours else "aucune expérience en vol")
    quand, secondes = secondes_avant_renouvellement()
    c3.metric("Quota dans", f"{secondes / 3600:.1f} h", help=f"prochain renouvellement : {quand}")
    sommeils = (pilote or {}).get("sommeils") or []
    cumul = sum(s.get("duree_s") or 0 for s in sommeils) / 3600
    c4.metric("Sommeils", len(sommeils), help=f"{cumul:.1f} h cumulées" if sommeils else "aucun")

    st.progress(faites / total if total else 0.0, text=f"{faites} sur {total} expériences")

    if v["arret_demande"]:
        st.warning("⏹ Arrêt demandé — l'exécution en cours se termine, aucune autre ne sera lancée.")
    if pilote and pilote.get("terminee_le"):
        st.success(f"Campagne terminée le {pilote['terminee_le']}.")
    elif not pilote:
        st.info("Cette campagne n'a jamais été lancée.")

    # ── Boutons ───────────────────────────────────────────────────────────────
    b1, b2, b3 = st.columns(3)
    if b1.button("▶️ Lancer", key="campagne-lancer", disabled=not lancer, width="stretch",
                 help="`make campagne-lancer` — tourne sur l'hôte, suivi dans 📟 Activités en cours"):
        lancer("campagne-lancer", {"NOM": nom})
        st.toast(f"Campagne {nom} lancée — suivi dans 📟 Activités en cours")
    if b2.button("⏹ Arrêter", key="campagne-arreter", disabled=not lancer, width="stretch",
                 help="`make campagne-arreter` — l'exécution en cours se termine seule"):
        lancer("campagne-arreter", {"NOM": nom})
        st.toast(f"Arrêt demandé pour {nom}")
    if b3.button("💰 Budget", key="campagne-estimer", disabled=not lancer, width="stretch",
                 help="`make campagne-lancer ESTIMER=1` — dit le coût sans rien enfiler"):
        lancer("campagne-lancer", {"NOM": nom, "ESTIMER": "1"})
        st.toast("Estimation lancée — résultat dans 📟 Activités en cours")

    # ── Phases ────────────────────────────────────────────────────────────────
    phase_courante = (pilote or {}).get("phase_courante")
    for phase in v["phases"]:
        fait, tot = len(phase["faites"]), len(phase["experiences"])
        marque = " ← en cours" if phase["nom"] == phase_courante else ""
        with st.expander(f"Phase « {phase['nom']} » — {fait}/{tot}{marque}",
                         expanded=phase["nom"] == phase_courante or not pilote):
            if phase["raison"]:
                st.caption(phase["raison"])
            lignes = []
            for exp in phase["experiences"]:
                st_exp = phase["etats"][exp]
                lignes.append({
                    "": ICONE.get(st_exp["etat"], "❔"),
                    "expérience": libelle(exp),
                    "état": st_exp["etat"],
                    "depuis": _duree(st_exp.get("maj")),
                    "motif": st_exp.get("raison") or "",
                    "nom (EXP=)": exp,
                })
            st.dataframe(
                pd.DataFrame(lignes), hide_index=True, width="stretch",
                column_config={
                    "expérience": st.column_config.TextColumn(
                        "expérience", help="Le nom calculé, rendu lisible. La colonne "
                        "« nom (EXP=) » porte le nom brut, celui qui sert en ligne de commande."),
                    "nom (EXP=)": st.column_config.TextColumn("nom (EXP=)", width="small"),
                })

    # ── Échecs ────────────────────────────────────────────────────────────────
    echecs = (pilote or {}).get("echouees") or {}
    if echecs:
        st.error(f"{len(echecs)} expérience(s) en échec — la campagne a continué sans elles.")
        st.dataframe(
            pd.DataFrame([{"expérience": e, "motif": d.get("motif"),
                           "tentatives": d.get("tentatives"), "le": d.get("le")}
                          for e, d in echecs.items()]),
            hide_index=True, width="stretch")

    # ── Sommeils ──────────────────────────────────────────────────────────────
    if sommeils:
        with st.expander(f"💤 Mises en sommeil ({len(sommeils)}, {cumul:.1f} h cumulées)"):
            st.caption(
                "Chaque ligne est un moment où TOUTES les exécutions en vol attendaient la "
                "fenêtre de quota. La campagne reprend ensuite sur l'expérience courante, "
                "jamais au début.")
            st.dataframe(
                pd.DataFrame([{"depuis": s.get("depuis"), "jusqu'à": s.get("jusqu"),
                               "durée (h)": round((s.get("duree_s") or 0) / 3600, 1),
                               "motif": s.get("motif")} for s in sommeils]),
                hide_index=True, width="stretch")

    # ── Substrat ──────────────────────────────────────────────────────────────
    if v["substrat"]:
        with st.expander("Substrat de la campagne"):
            for cle, valeur in v["substrat"].items():
                st.write(f"**{cle}** : `{valeur}`")


__all__ = ["campagnes_connues", "etat_execution", "libelle", "render",
           "secondes_avant_renouvellement", "vue"]
