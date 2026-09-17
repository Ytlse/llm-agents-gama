"""Journal de mémoire — un Markdown par agent, écrit en continu (ticket 075).

POURQUOI
--------
Le dépôt sait déjà journaliser les ÉCRITURES de mémoire (`agent_memory_events.jsonl`). Il ne
sait dire ni ce qui a **déclenché** une consolidation, ni ce qu'une opération de concept a
changé, ni à quoi la mémoire **ressemblait après**. Sur un run d'un jour, cela n'a pas
d'importance : la mémoire n'a pas le temps de bouger. Sur soixante jours, c'est tout l'objet de
l'observation, et le reconstituer après coup depuis un JSONL est un travail d'archéologue.

CE QUE CE FICHIER GARANTIT
--------------------------
1. **Rien quand c'est éteint.** `agent.journal_memoire_enabled` est faux par défaut : un run à
   mille agents ne paie ni un octet ni un appel disque.
2. **Jamais d'exception vers l'appelant.** Un journal qui fait tomber une simulation de
   soixante jours serait pire que pas de journal du tout. Toute erreur d'écriture est
   journalisée en WARNING et ravalée.
3. **Un agent, un fichier.** Aucun mélange possible entre deux mémoires.
4. **Le gel.** Pendant le rejeu d'une reprise à chaud, le journal est GELÉ : les jours déjà
   écrits ne se réécrivent pas.

CE QU'IL N'EST PAS
------------------
Ce n'est pas une source de mesure. Les chiffres d'un article se prennent dans les métadonnées de
la mémoire et dans `moves.csv`, pas dans un texte formaté pour être lu.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from llm.memory import MemoryEntry
from loguru import logger
from settings import _run_artifacts_disabled, settings
from urban_mobility_agents.utils.reprise import gel_actif

# Longueur d'un contenu affiché dans un tableau. Au-delà, le tableau devient illisible et le
# fichier impossible à parcourir — or il est écrit POUR être parcouru.
_LARGEUR_CONTENU = 110


def _tronquer(texte: Any, largeur: int = _LARGEUR_CONTENU) -> str:
    """Contenu ramené à une cellule de tableau : une ligne, une longueur bornée."""
    plat = " ".join(str(texte or "").split())
    plat = plat.replace("|", "\\|")
    return plat if len(plat) <= largeur else plat[: largeur - 1] + "…"


def _jour_de(quand: datetime) -> str:
    return quand.strftime("%Y-%m-%d")


def _heure_de(quand: datetime) -> str:
    return quand.strftime("%H:%M")


class JournalMemoire:
    """Écrit `<workdir>/memoires/<person_id>.md`, un fichier par agent."""

    _instance: JournalMemoire | None = None

    def __init__(self, repertoire: Path):
        self.repertoire = Path(repertoire)
        # ⚠ Le répertoire est créé à la PREMIÈRE ÉCRITURE, jamais à la construction. Le créer
        # ici fabriquait un répertoire de run à chaque import — une découverte de tests côté
        # hôte en semait un par minute dans `services/llm-agents/experiments/archive/`
        # (constaté le 2026-09-14, pendant le run pilote du ticket 075).
        self._entetes: set[str] = set()
        self._jour_courant: dict[str, str] = {}
        self._gele = False

    # ── Cycle de vie ─────────────────────────────────────────────────────────────────────

    @classmethod
    def get(cls) -> JournalMemoire | None:
        """L'instance, ou `None` si le journal est éteint. Aucun effet de bord dans ce cas."""
        if not getattr(settings.agent, "journal_memoire_enabled", False):
            return None
        if cls._instance is None and _run_artifacts_disabled():
            # Le journal est un ARTEFACT DE RUN : sous test, il ne s'ouvre pas tout seul. Sans
            # cette garde, une suite de tests lancée pendant qu'un run tourne semait un
            # répertoire d'expérience par exécution (constaté le 2026-09-14). Un test qui veut
            # un journal l'injecte lui-même dans `_instance`, sur un répertoire à lui.
            return None
        if cls._instance is None:
            cls._instance = cls(Path(settings.agent.journal_memoire_dir))
            logger.info(
                f"[journal-mémoire] actif — un fichier par agent dans {cls._instance.repertoire}"
            )
        return cls._instance

    @classmethod
    def reinitialiser(cls) -> None:
        """Oublie l'instance. Réservé aux tests."""
        cls._instance = None

    def geler(self, motif: str) -> None:
        """Suspend toute écriture — rejeu d'une reprise à chaud."""
        if not self._gele:
            logger.info(f"[journal-mémoire] GELÉ : {motif}")
        self._gele = True

    def degeler(self, motif: str) -> None:
        if self._gele:
            logger.info(f"[journal-mémoire] dégelé : {motif}")
        self._gele = False

    @property
    def gele(self) -> bool:
        return self._gele

    # ── Écriture ─────────────────────────────────────────────────────────────────────────

    def _fichier(self, person_id: str) -> Path:
        return self.repertoire / f"{person_id}.md"

    def _ecrire(self, person_id: str, texte: str) -> None:
        """Ajoute au fichier de l'agent. Une erreur disque ne remonte JAMAIS à l'appelant."""
        if self._gele or gel_actif():
            return
        try:
            self.repertoire.mkdir(parents=True, exist_ok=True)
            with self._fichier(person_id).open("a", encoding="utf-8") as f:
                f.write(texte)
        except OSError as err:
            logger.warning(
                f"[journal-mémoire] écriture impossible pour {person_id} ({err}) — "
                f"l'événement est perdu, la simulation continue."
            )

    def ouvrir_agent(self, person_id: str, identite: dict | None = None) -> None:
        """En-tête du fichier, écrit une seule fois."""
        if person_id in self._entetes:
            return
        self._entetes.add(person_id)
        if self._fichier(person_id).exists():
            # Reprise à chaud : le fichier restauré continue, il ne recommence pas.
            return
        traits = identite or {}
        lignes = [
            f"# Mémoire de {traits.get('name') or person_id} — agent {person_id}",
            "",
            "> Journal écrit en continu (ticket 075) : une entrée à chaque événement qui",
            "> **modifie** la mémoire, avec ce qui l'a déclenché. Les heures sont en temps",
            "> SIMULÉ. Ce fichier se lit ; il ne se mesure pas.",
            "",
        ]
        if traits:
            lignes += [
                (
                    f"**Profil.** {traits.get('age', '?')} ans · {traits.get('main_occupation', '?')} · "
                    f"{traits.get('residence_commune', '?')} ({traits.get('residence_zone', '?')}) · "
                    f"voiture : {traits.get('car_availability', '?')} · "
                    f"vélo : {traits.get('personal_bike', '?')} · "
                    f"abonnement TC : {'oui' if traits.get('has_pt_subscription') else 'non'}"
                ),
                "",
            ]
        self._ecrire(person_id, "\n".join(lignes))

    def _jour(self, person_id: str, quand: datetime) -> None:
        """Ouvre une section de jour quand la date simulée AVANCE.

        ⚠ Jamais en arrière, et ce n'est pas un détail de présentation. Une ligne d'écriture
        porte l'horodatage de l'ÉVÉNEMENT — souvent la veille, puisqu'une consolidation de 22 h
        écrit des souvenirs datés du matin —, tandis que la section de consolidation porte
        l'heure courante. Sectionner sur chaque changement de date faisait donc osciller
        l'en-tête : 76 sections pour 32 jours simulés, mesuré le 2026-09-15 sur le run du
        ticket 075. Un souvenir daté d'avant reste dans la section ouverte ; sa propre heure est
        de toute façon écrite sur sa ligne.
        """
        jour = _jour_de(quand)
        connu = self._jour_courant.get(person_id)
        if connu is not None and jour <= connu:
            return
        self._jour_courant[person_id] = jour
        self._ecrire(person_id, f"\n## {quand.strftime('%A %d %B %Y')}\n\n")

    # ── Événements ───────────────────────────────────────────────────────────────────────

    def ecriture(self, person_id: str, quand: datetime, entree: MemoryEntry) -> None:
        """Une entrée est écrite en mémoire longue. Ligne compacte : il y en a des milliers."""
        if self._gele:
            return
        self._jour(person_id, quand)
        self._ecrire(
            person_id,
            f"- `{_heure_de(quand)}` **écriture** ({entree.memory_type}) — "
            f"{_tronquer(entree.content)} "
            f"<sub>gravité {float(entree.importance or 0.0):.2f} · "
            f"force {float(entree.force or 0.0):.1f} j</sub>\n",
        )

    def rappel(
        self, person_id: str, quand: datetime, servis: Iterable[MemoryEntry]
    ) -> None:
        """Des souvenirs ont été servis au modèle : leur durée de vie et leur compteur bougent."""
        if self._gele:
            return
        servis = list(servis)
        if not servis:
            return
        self._jour(person_id, quand)
        detail = " · ".join(
            f"{_tronquer(e.content, 46)} (force {float(e.force or 0.0):.1f} j, "
            f"rappels {int(e.rappels or 0)})"
            for e in servis[:4]
        )
        reste = f" · +{len(servis) - 4} autre(s)" if len(servis) > 4 else ""
        self._ecrire(
            person_id,
            f"- `{_heure_de(quand)}` **rappel** — {len(servis)} souvenir(s) servi(s) : "
            f"{detail}{reste}\n",
        )

    def purge(
        self, person_id: str, quand: datetime, supprimes: Iterable[MemoryEntry]
    ) -> None:
        """Des entrées épisodiques sont tombées sous le seuil de poids."""
        if self._gele:
            return
        supprimes = list(supprimes)
        if not supprimes:
            return
        self._jour(person_id, quand)
        lignes = [
            f"- `{_heure_de(quand)}` **purge** — {len(supprimes)} entrée(s) oubliée(s) :"
        ]
        for e in supprimes:
            age = (quand - e.horodatage_de_reference).total_seconds() / 86400.0
            lignes.append(
                f"    - {_tronquer(e.content, 90)} "
                f"<sub>{age:.1f} j depuis le dernier rappel, force {float(e.force or 0.0):.1f} j</sub>"
            )
        self._ecrire(person_id, "\n".join(lignes) + "\n")

    def consolidation_debut(
        self,
        person_id: str,
        quand: datetime,
        motif: str,
        declencheur: str,
        entrees_consommees: Iterable[Any],
    ) -> None:
        """Ouvre la section d'une consolidation, avec ce qui l'a déclenchée."""
        if self._gele:
            return
        self._jour(person_id, quand)
        entrees = list(entrees_consommees)
        lignes = [
            "",
            f"### `{_heure_de(quand)}` CONSOLIDATION — déclencheur : **{motif}**",
            "",
            f"**Ce qui l'a déclenchée.** {declencheur}",
            "",
            f"**Entrées de mémoire courte consommées ({len(entrees)}).**",
            "",
        ]
        for e in entrees:
            horodatage = getattr(e, "timestamp", None)
            heure = (
                _heure_de(horodatage) if isinstance(horodatage, datetime) else "  ?  "
            )
            lignes.append(
                f"- `{heure}` {_tronquer(getattr(e, 'content', e), 100)} "
                f"<sub>gravité {float(getattr(e, 'importance', 0.0) or 0.0):.2f}</sub>"
            )
        self._ecrire(person_id, "\n".join(lignes) + "\n")

    def reflexion(self, person_id: str, texte: str) -> None:
        if self._gele or not texte:
            return
        self._ecrire(person_id, f"\n**Réflexion écrite.** {_tronquer(texte, 600)}\n")

    def operation_concept(
        self,
        person_id: str,
        operation: str,
        *,
        avant: str = "",
        apres: str = "",
        observations: str = "",
        contre_exemples: str = "",
        confiance: str = "",
        note: str = "",
    ) -> None:
        """Une des quatre opérations du lot 3 du ticket 071, avec son avant/après."""
        if self._gele:
            return
        champs = [
            f"opération **{operation}**",
            f"avant : {avant}" if avant else "",
            f"après : {apres}" if apres else "",
            f"observations {observations}" if observations else "",
            f"contre-exemples {contre_exemples}" if contre_exemples else "",
            f"confiance {confiance}" if confiance else "",
            note,
        ]
        self._ecrire(person_id, "- " + " · ".join(c for c in champs if c) + "\n")

    def consolidation_fin(
        self, person_id: str, quand: datetime, entrees: Iterable[MemoryEntry]
    ) -> None:
        """Ferme la section par l'état COMPLET de la mémoire de l'agent."""
        if self._gele:
            return
        entrees = list(entrees)
        lignes = [
            "",
            f"**État de la mémoire après consolidation ({len(entrees)} entrées).**",
            "",
            "| type | contenu | gravité | force (j) | rappels | dernier rappel | confiance | axes | statut |",
            "|---|---|---:|---:|---:|---|---:|---|---|",
        ]
        for e in entrees:
            axes = " / ".join(
                str(a)
                for a in (
                    e.axe_objet,
                    e.axe_lieu,
                    e.axe_creneau,
                    e.axe_motif,
                    e.axe_meteo,
                )
                if a
            )
            if e.est_episodique:
                statut = "épisodique"
                confiance = "—"
            elif e.est_depasse:
                statut = f"**dépassé** (écarté le {str(e.depasse_le)[:16]})"
                confiance = f"{e.confiance:.2f}"
            elif not e.est_servi:
                statut = f"hors service (écarté le {str(e.depasse_le)[:16]})"
                confiance = f"{e.confiance:.2f}"
            else:
                statut = "servi"
                confiance = f"{e.confiance:.2f}"
            lignes.append(
                f"| {e.memory_type} | {_tronquer(e.content)} | "
                f"{float(e.importance or 0.0):.2f} | {float(e.force or 0.0):.1f} | "
                f"{int(e.rappels or 0)} | "
                f"{e.dernier_rappel.strftime('%d/%m %H:%M') if e.dernier_rappel else '—'} | "
                f"{confiance} | {axes or '—'} | {statut} |"
            )
        self._ecrire(person_id, "\n".join(lignes) + "\n")


def journal() -> JournalMemoire | None:
    """Raccourci d'appel : `journal() and journal().ecriture(...)`."""
    return JournalMemoire.get()
