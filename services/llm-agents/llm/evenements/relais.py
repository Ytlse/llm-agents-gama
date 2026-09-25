"""Le lecteur le dit à sa famille — ticket 111, lot 3.

CE QUE CE MODULE FAIT
---------------------
Un appel LLM par foyer exposé. Le lecteur a lu l'article ; il reçoit la fiche de chacun des
autres membres et écrit, pour chacun, ce qu'il lui en dit — avec ses mots — ou choisit de ne
rien dire. Pour un mineur, il écrit ce que les parents ont décidé pour lui (décision D5) : dans
la réalité ce sont eux qui décident du trajet d'un enfant, et une version simplifiée de
l'article ne le ferait pas changer.

Le résultat est FIGÉ dès sa production : il sert aux décisions des membres pendant leurs jours
de service ET à l'écriture en mémoire à 00:00. Il est écrit dans `relais_foyer.jsonl`, qui fait
foi pour savoir qui a été informé, et relu à la reprise — jamais régénéré : une reprise qui
régénérerait le relais produirait un autre texte pour la même expérience.

LE REFUS EST FRANC
------------------
Réponse vide, identifiant inconnu, membre manquant ou présent deux fois, `speaks` vrai avec un
message vide : `RelaisRefuse`, une `[ALARME]`, et AUCUN message n'est servi dans le foyer. Pas
de texte de repli — un message que nous écririons à la place du lecteur serait un stimulus, pas
une transmission. Pas de délai de repli non plus : en pénurie de quota, on attend.

LES GARDES TRACENT, ELLES NE REFUSENT PAS
-----------------------------------------
Les familles de gardes de contenu (adresse, verdict, intention) tournent sur chaque message et
sont tracées sous `directif`. Le message est la cognition du lecteur ; le réécrire ou le refuser
reviendrait à décider à sa place de ce qu'il dit. Une décision parentale est directive par
nature, et c'est dit.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from llm.evenements.exposition import AGE_ADULTE, age_de
from llm.evenements.gardes import familles_directives

CATEGORIE = "evenement_relais"
# Une panne du fournisseur n'est pas un refus du lecteur : elle se retente à la reprise, deux fois
# au plus (décision de l'auteur, 2026-09-25). Trois tentatives en tout, puis le refus est gravé.
TENTATIVES_MAX = 3


class RelaisRefuse(ValueError):
    """La réponse du modèle ne donne pas un relais complet. Aucun message n'est servi.

    `technique` : la réponse n'est pas arrivée (réponse vide, exception) — la reprise retente.
    Sinon, c'est le contenu qui est refusé, et le refus est définitif.
    """

    def __init__(self, raison: str, technique: bool = False) -> None:
        super().__init__(raison)
        self.technique = technique


@dataclass(frozen=True)
class Message:
    """Ce que le lecteur dit à UN membre de son foyer, ou le fait qu'il ne dit rien."""

    destinataire_id: str
    parle: bool
    texte: str
    mineur: bool
    directif: bool = False
    familles: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelaisFoyer:
    """Le relais d'un foyer, tel qu'il a été produit. Fait foi : relu, jamais régénéré."""

    household_id: str
    lecteur_id: str
    lecteur_prenom: str
    evenement_id: str
    jour_run: int
    messages: tuple[Message, ...] = ()
    fournisseur: str = ""
    produit_a: str = ""
    duree_s: float = 0.0
    # Non vide = relais REFUSÉ. Gardé dans la trace pour qu'une reprise ne retente pas — sauf
    # un refus `technique` dont la `tentative` est sous `TENTATIVES_MAX`.
    refus: str = ""
    technique: bool = False
    tentative: int = 1

    @property
    def a_retenter(self) -> bool:
        """Échec technique qu'une reprise doit retenter."""
        return bool(self.refus) and self.technique and self.tentative < TENTATIVES_MAX

    def message_pour(self, person_id: str) -> Message | None:
        if self.refus:
            return None
        for m in self.messages:
            if m.destinataire_id == str(person_id):
                return m
        return None

    @property
    def informes(self) -> list[str]:
        return [m.destinataire_id for m in self.messages if m.parle and not self.refus]


# ── La charge utile ─────────────────────────────────────────────────────────────────────────
def prenom_de(personne) -> str:
    traits = getattr(getattr(personne, "identity", None), "traits_json", None) or {}
    nom = str(traits.get("name") or "").strip()
    return nom.split()[0] if nom else ""


def est_mineur(personne) -> bool:
    """Mineur si l'âge déclaré est sous `AGE_ADULTE`. Âge absent : adulte, avec un WARNING (H2)."""
    age = age_de(personne)
    if age is None:
        logger.warning(
            f"[evenements] relais : âge inconnu pour {getattr(personne, 'person_id', '?')}, "
            f"traité en adulte faute de pouvoir le dire mineur."
        )
        return False
    return age < AGE_ADULTE


def _heure(secondes: float) -> str:
    s = int(secondes) % 86400
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"


def trajets_du_jour(personne) -> list[str]:
    """Les activités du programme type, dans l'ordre : « 08:30 work ». Rien n'est inventé."""
    activites = getattr(getattr(personne, "identity", None), "activities", None) or []
    lignes = []
    for a in activites[1:]:  # la première est le domicile du matin, pas un trajet
        debut = a.scheduled_start_time if a.scheduled_start_time is not None else a.start_time
        motif = getattr(a.purpose, "value", a.purpose)
        lignes.append(f"{_heure(float(debut))} {motif}")
    return lignes


def fiche_membre(personne, modes_habituels: list[str] | None = None) -> dict:
    """Ce que le lecteur sait d'un membre de son foyer, et rien de plus.

    ⚠ Aucun lien de parenté : la population donne l'appartenance au ménage et l'âge, pas la
    filiation. Dire « ton fils » fabriquerait une donnée (même règle que `llm/foyer.py`).
    """
    traits = getattr(getattr(personne, "identity", None), "traits_json", None) or {}
    return {
        "agent_id": str(personne.person_id),
        "prenom": prenom_de(personne) or str(personne.person_id),
        "age": age_de(personne),
        "mineur": est_mineur(personne),
        "occupation": str(
            traits.get("professional_activity") or traits.get("main_occupation") or ""
        ),
        "modes_habituels": list(modes_habituels or []),
        "trajets_du_jour": trajets_du_jour(personne),
    }


def modes_habituels(journal: dict) -> list[str]:
    """Les modes effectivement pris, du plus au moins fréquent, depuis le journal des trajets.

    Même seuil que « Mes habitudes » (`OCCURRENCES_MIN_HABITUDE`) : une occurrence n'est pas
    une habitude, et le lecteur ne doit pas prêter à un membre une routine qu'il n'a pas.
    """
    from llm.noyau import OCCURRENCES_MIN_HABITUDE

    totaux: dict[str, int] = {}
    for entree in (journal or {}).values():
        for mode, n in (entree.get("modes") or {}).items():
            totaux[mode] = totaux.get(mode, 0) + int(n)
    return [
        m for m, n in sorted(totaux.items(), key=lambda kv: kv[1], reverse=True)
        if n >= OCCURRENCES_MIN_HABITUDE
    ]


def charge_utile(lecteur_id: str, perception: str, article: str, membres: list[dict]) -> dict:
    from urban_mobility_agents.utils.routage import instances_pour

    return {
        "category": CATEGORIE,
        "instances_admises": instances_pour(CATEGORIE),
        "agents": [
            {
                "agent_id": str(lecteur_id),
                "perception": perception,
                "article": article,
                "membres": membres,
            }
        ],
        "parameters": {
            "temperature": 0.2,
            # 2048 : les modèles de raisonnement dépensent leur réflexion DANS ce budget (le
            # jugement a dû passer de 256 à 1024 le 2026-09-22 pour cette raison), et la
            # sortie porte un message par membre.
            "max_tokens": 2048,
        },
    }


# ── La validation ───────────────────────────────────────────────────────────────────────────
def _refuser(household_id: str, evenement_id: str, raison: str,
             technique: bool = False) -> RelaisRefuse:
    genre = "ÉCHEC TECHNIQUE" if technique else "REFUSÉ"
    logger.error(
        f"[ALARME] [evenements] « {evenement_id} » : relais du foyer {household_id} {genre} — "
        f"{raison}. Aucun message n'est servi dans ce foyer, et aucun texte de repli n'est "
        f"écrit : les membres de ce foyer ne sont PAS informés. Ne pas les compter comme tels."
    )
    return RelaisRefuse(raison, technique=technique)


def _champ(obj, nom: str):
    if isinstance(obj, dict):
        return obj.get(nom)
    return getattr(obj, nom, None)


def valider(reponse, lecteur_id: str, membres: list[dict], household_id: str,
            evenement_id: str) -> tuple[Message, ...]:
    """Les messages, un par membre, ou `RelaisRefuse`. Aucun repli."""
    agents = getattr(reponse, "agents", None) if reponse is not None else None
    if not agents:
        erreur = getattr(reponse, "error", None) if reponse is not None else None
        raise _refuser(
            household_id, evenement_id, f"réponse vide ({erreur or 'aucun agent'})",
            technique=True,
        )
    rendu = next((a for a in agents if str(_champ(a, "agent_id")) == str(lecteur_id)), None)
    if rendu is None:
        ids = [str(_champ(a, "agent_id")) for a in agents]
        raise _refuser(
            household_id, evenement_id,
            f"agent_id {ids} rendu(s), le lecteur attendu est {lecteur_id}",
        )
    destinataires = _champ(rendu, "recipients") or _champ(rendu, "destinataires") or []
    attendus = {str(m["agent_id"]): m for m in membres}
    vus: dict[str, Message] = {}
    for d in destinataires:
        pid = str(_champ(d, "agent_id") or "")
        if pid not in attendus:
            raise _refuser(
                household_id, evenement_id,
                f"destinataire inconnu « {pid} » (membres attendus {sorted(attendus)})",
            )
        if pid in vus:
            raise _refuser(household_id, evenement_id, f"membre {pid} présent deux fois")
        parle_brut = _champ(d, "speaks")
        if parle_brut is None:
            parle_brut = _champ(d, "parle")
        parle = bool(parle_brut)
        texte = str(_champ(d, "message") or "").strip()
        if parle and not texte:
            raise _refuser(
                household_id, evenement_id, f"`speaks` vrai et message vide pour {pid}"
            )
        mineur = bool(attendus[pid].get("mineur"))
        familles = familles_directives(texte) if parle else ()
        vus[pid] = Message(
            destinataire_id=pid,
            parle=parle,
            texte=texte if parle else "",
            mineur=mineur,
            # Une décision parentale est directive par nature : elle dit ce que l'enfant fera.
            directif=bool(parle and (familles or mineur)),
            familles=familles,
        )
    manquants = sorted(set(attendus) - set(vus))
    if manquants:
        raise _refuser(household_id, evenement_id, f"membre(s) {manquants} sans réponse")
    return tuple(vus[str(m["agent_id"])] for m in membres)


async def produire(
    llm_client,
    lecteur,
    perception: str,
    membres: list[dict],
    texte: str,
    evenement_id: str,
    jour: int,
    household_id: str,
) -> RelaisFoyer:
    """Un appel, un foyer. Lève `RelaisRefuse` plutôt que de rendre un message inventé."""
    lecteur_id = str(lecteur.person_id)
    mineurs = sum(1 for m in membres if m.get("mineur"))
    logger.info(
        f"[evenements] relais du foyer {household_id} — DÉBUT : lecteur {lecteur_id}, "
        f"{len(membres)} membre(s) dont {mineurs} mineur(s), « {evenement_id} » jour {jour}"
    )
    t0 = time.monotonic()
    reponse = await llm_client.execute(charge_utile(lecteur_id, perception, texte, membres))
    duree = time.monotonic() - t0
    messages = valider(reponse, lecteur_id, membres, household_id, evenement_id)
    relais = RelaisFoyer(
        household_id=str(household_id),
        lecteur_id=lecteur_id,
        lecteur_prenom=prenom_de(lecteur),
        evenement_id=evenement_id,
        jour_run=int(jour),
        messages=messages,
        fournisseur=str(getattr(reponse, "provider_used", "") or ""),
        produit_a=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        duree_s=round(duree, 2),
    )
    informes = relais.informes
    logger.info(
        f"[evenements] relais du foyer {household_id} — FIN en {duree:.1f} s : "
        f"{len(informes)}/{len(membres)} membre(s) informé(s) "
        f"({sum(1 for m in messages if m.parle and m.mineur)} mineur(s)), "
        f"{sum(1 for m in messages if m.directif)} message(s) directif(s), longueurs "
        f"{[len(m.texte) for m in messages if m.parle]} caractères, fournisseur "
        f"{relais.fournisseur or 'inconnu'}"
    )
    return relais


# ── La trace, qui fait foi ──────────────────────────────────────────────────────────────────
def ecrire(chemin: Path | None, relais: RelaisFoyer) -> None:
    """Une ligne par foyer dans `relais_foyer.jsonl`. Jamais d'exception vers l'appelant."""
    if chemin is None:
        return
    try:
        ligne = asdict(relais)
        ligne["messages"] = [asdict(m) for m in relais.messages]
        ligne["informes"] = relais.informes
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except Exception as err:  # noqa: BLE001 — une trace ne fait jamais tomber un run
        logger.error(
            f"[ALARME] [evenements] relais du foyer {relais.household_id} non écrit dans "
            f"{chemin} ({err}) : une reprise le RÉGÉNÉRERAIT, avec un autre texte."
        )


def relire(chemin: Path | None) -> dict[str, RelaisFoyer]:
    """Les relais déjà produits par ce run. La dernière ligne d'un foyer fait foi."""
    if chemin is None or not Path(chemin).is_file():
        return {}
    relus: dict[str, RelaisFoyer] = {}
    for n, brut in enumerate(Path(chemin).read_text(encoding="utf-8").splitlines(), 1):
        if not brut.strip():
            continue
        try:
            d = json.loads(brut)
            messages = tuple(
                Message(
                    destinataire_id=str(m["destinataire_id"]),
                    parle=bool(m["parle"]),
                    texte=str(m.get("texte") or ""),
                    mineur=bool(m.get("mineur")),
                    directif=bool(m.get("directif")),
                    familles=tuple(m.get("familles") or ()),
                )
                for m in d.get("messages") or []
            )
            relus[str(d["household_id"])] = RelaisFoyer(
                household_id=str(d["household_id"]),
                lecteur_id=str(d["lecteur_id"]),
                lecteur_prenom=str(d.get("lecteur_prenom") or ""),
                evenement_id=str(d.get("evenement_id") or ""),
                jour_run=int(d.get("jour_run") or 0),
                messages=messages,
                fournisseur=str(d.get("fournisseur") or ""),
                produit_a=str(d.get("produit_a") or ""),
                duree_s=float(d.get("duree_s") or 0.0),
                refus=str(d.get("refus") or ""),
                technique=bool(d.get("technique")),
                tentative=int(d.get("tentative") or 1),
            )
        except Exception as err:  # noqa: BLE001
            logger.error(
                f"[ALARME] [evenements] {chemin}, ligne {n} illisible ({err}) : ce foyer "
                f"serait relayé une seconde fois, avec un autre texte."
            )
    if relus:
        a_retenter = sum(1 for r in relus.values() if r.a_retenter)
        logger.info(
            f"[evenements] {len(relus)} relais relu(s) depuis {Path(chemin).name} — "
            f"{sum(1 for r in relus.values() if r.refus and not r.a_retenter)} refusé(s) "
            f"définitivement, {a_retenter} échec(s) technique(s) à retenter (au plus "
            f"{TENTATIVES_MAX} tentatives), les autres ne seront pas régénérés"
        )
    return relus


__all__ = [
    "CATEGORIE", "TENTATIVES_MAX", "Message", "RelaisFoyer", "RelaisRefuse", "charge_utile", "ecrire",
    "fiche_membre", "produire", "relire", "valider",
]
