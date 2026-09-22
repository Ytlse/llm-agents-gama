"""L'événement en vigueur pour ce run, et ce qu'il a fait — ticket 100, lot 1.

Un seul événement à la fois, volontairement. Deux événements superposés rendraient l'attribution
impossible — c'est exactement ce que le protocole cherche à établir, et le mécanisme ne doit pas
fabriquer lui-même la confusion qu'il sert à lever.

Le registre compte TROIS choses distinctes et ne les mélange jamais : les exposés, les épargnés,
et ceux qui l'étaient déjà aujourd'hui sous `cadence: jour`. Le deuxième est le TÉMOIN INTERNE du
run et il doit se lire ; le troisième n'est ni l'un ni l'autre, et le confondre avec un épargné
ferait passer un événement appliqué une fois pour un événement qui rate trois trajets sur quatre.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from llm.evenements import calendrier
from llm.evenements.declaration import Evenement, EvenementApplique
from llm.evenements.exposition import expose, lecteurs
from sim_clock import wall_clock


@dataclass
class CompteursJournee:
    jour_run: int = 0
    exposes: int = 0
    epargnes: int = 0
    retard_injecte_s: int = 0
    # Arrivées éligibles NON touchées parce que l'agent l'avait déjà été le jour même
    # (`cadence: jour`). Comptées à part : ce n'est ni une exposition, ni un agent épargné.
    deja_touches: int = 0
    # Décisions servies DEPUIS LE CACHE ce jour-là. Comptées pour une raison précise : la
    # coupure du cache porte sur le jour de l'événement, mais ce qu'on mesure est la fenêtre
    # d'APRÈS. Ce compteur dit, jour par jour, sur combien de décisions la réserve porte.
    decisions_depuis_cache: int = 0
    # Décisions pour lesquelles le cache a été volontairement contourné (jour d'événement).
    decisions_cache_coupe: int = 0


class RegistreEvenements:
    """Ce que l'événement déclaré a fait, journée par journée."""

    def __init__(self, evenement: Evenement, journal: Path | None = None) -> None:
        self.evenement = evenement
        self._journal = journal
        self._compteurs = CompteursJournee()
        self._exposes_vus: set[str] = set()
        # `cadence: jour` — qui a déjà été touché DANS la journée en cours. Remis à zéro au
        # basculement de journée, jamais accumulé sur le run : un agent est touché une fois par
        # jour d'événement, pas une fois pour tout le run.
        self._touches_du_jour: set[str] = set()
        # ── Prise `reveil` (lot 2) ───────────────────────────────────────────────────────
        # Les lecteurs, tirés UNE FOIS sur la population chargée, et qui a déjà lu. Un article
        # se lit une fois : le relire chaque matin ferait du stimulus une répétition, et la
        # persistance du souvenir ne se distinguerait plus de la répétition de sa cause.
        self._lecteurs: dict[str, tuple[str, str]] | None = None
        self._ont_lu: set[str] = set()

    @property
    def choc(self) -> Evenement:
        """Compatibilité 079 — part au lot 6 avec `llm/chocs.py`."""
        return self.evenement

    # ── Temps ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def jour_du_run(timestamp: int) -> int:
        """1 pour le premier jour simulé du run.

        Reste une méthode de classe déléguant à `calendrier.jour_du_run` : les tests du 079 la
        remplacent sur la CLASSE pour jouer une journée donnée sans simulateur, et déplacer
        l'appel dans le module leur retirerait ce point de prise.
        """
        return calendrier.jour_du_run(timestamp)

    def jour_relatif(self, timestamp: int) -> int:
        """Jours écoulés depuis le PREMIER jour de l'événement : −2, −1, 0, +1…

        Défini tous les jours du run, y compris avant et longtemps après : c'est l'abscisse de
        toutes les courbes de décrochage et de retour, et une abscisse qui n'existe que les
        jours d'événement ne tracerait rien.
        """
        return self.jour_du_run(timestamp) - self.evenement.premier_jour

    # ── Exposition ───────────────────────────────────────────────────────────────────────
    def _expose(self, person_id: str, mode: str | None) -> tuple[bool, str]:
        return expose(
            self.evenement.exposition, self.evenement.evenement_id, person_id, mode
        )

    def applique(
        self, person_id: str, mode: str | None, timestamp: int
    ) -> EvenementApplique | None:
        """Ce que cet agent subit à cette arrivée, ou `None` s'il ne subit rien.

        Rend `None` dans trois cas parfaitement distincts, et les compte séparément : la journée
        n'est pas une journée d'événement, l'agent n'est pas exposé, ou le profil du jour ne fait
        rien subir.
        """
        jour = self.jour_du_run(timestamp)
        if jour != self._compteurs.jour_run:
            self._basculer_de_journee(jour)
        profil = self.evenement.jours.get(jour)
        if profil is None:
            return None
        est_expose, raison = self._expose(str(person_id), mode)
        if not est_expose:
            self._compteurs.epargnes += 1
            return None
        if self.evenement.cadence == "jour" and str(person_id) in self._touches_du_jour:
            self._compteurs.deja_touches += 1
            return None
        self._touches_du_jour.add(str(person_id))
        self._compteurs.exposes += 1
        self._compteurs.retard_injecte_s += profil.retard_s
        self._exposes_vus.add(str(person_id))
        return EvenementApplique(
            evenement_id=self.evenement.evenement_id,
            canal=self.evenement.canal,
            moment=self.evenement.moment,
            jour_run=jour,
            jour_relatif=jour - self.evenement.premier_jour,
            retard_injecte_s=profil.retard_s,
            texte=profil.texte,
            incident_reseau=profil.incident_reseau,
            correspondance_ratee=profil.correspondance_ratee,
            raison=raison,
        )

    # ── Prise `reveil` ───────────────────────────────────────────────────────────────────
    def lecteurs(self, population) -> dict[str, tuple[str, str]]:
        """Qui reçoit cet événement, et pour quelle raison. Calculé une fois, puis gardé."""
        if self._lecteurs is not None:
            return self._lecteurs
        e = self.evenement
        if e.exposition.regle == "foyers":
            self._lecteurs = lecteurs(e.exposition, e.evenement_id, population)
        else:
            retenus: dict[str, tuple[str, str]] = {}
            for personne in population:
                if getattr(personne, "immobile", False):
                    continue
                touche, raison = expose(
                    e.exposition, e.evenement_id, str(personne.person_id), None
                )
                if touche:
                    retenus[str(personne.person_id)] = (
                        str(getattr(personne, "household_id", "") or ""), raison,
                    )
            self._lecteurs = retenus
        logger.info(
            f"[evenements] « {e.evenement_id} » : {len(self._lecteurs)} lecteur(s) retenu(s) "
            f"sur {sum(1 for _ in population)} agent(s) — règle {e.exposition.regle}"
        )
        return self._lecteurs

    def role_de(self, person_id: str) -> tuple[str, str]:
        """Le rôle de cet agent dans le dispositif, et la raison. Ticket 100, lot 5.

        Trois rôles, et ils ne se déduisent pas l'un de l'autre :

        - `expose` — l'événement l'a atteint ;
        - `co_resident` — il vit sous le même toit qu'un exposé, et n'a RIEN reçu. C'est chez
          lui que se lit ce qui se transmet, et sans lui l'étage de diffusion n'a pas d'objet ;
        - `temoin` — ni l'un ni l'autre. C'est la ligne de base du run.

        Vide quand le dispositif ne sait pas encore qui lit : une colonne vide n'est pas un
        rôle, et l'écrire `temoin` ferait passer une ignorance pour une mesure.
        """
        if self._lecteurs is None:
            # Prise `arrivee` : l'exposition se résout trajet par trajet, jamais à l'avance.
            # Le rôle se lit alors dans `evenements.jsonl`, pas ici.
            return ("", "")
        pid = str(person_id)
        if pid in self._lecteurs:
            return ("expose", self._lecteurs[pid][1])
        foyers_exposes = {h for h, _ in self._lecteurs.values() if h}
        from llm import foyer as _foyer

        mien = _foyer.foyer_de(pid)
        if mien and mien in foyers_exposes:
            return ("co_resident", f"foyer:{mien}")
        return ("temoin", "")

    def jour_de(self, person_id: str, household_id: str) -> int:
        """Le jour où CET agent reçoit l'événement.

        La cible du tirage est le MÉNAGE quand la règle est `foyers` : les membres d'un même
        foyer doivent recevoir le même jour, sans quoi le co-résident témoin ne serait plus
        comparable au lecteur sur la même journée.
        """
        e = self.evenement
        if e.calendrier is None:
            return e.premier_jour
        cible = household_id if e.exposition.regle == "foyers" and household_id else person_id
        return e.calendrier.jour_de(e.evenement_id, cible)

    def dus_au_reveil(self, timestamp: int, population) -> list:
        """Les agents qui reçoivent l'événement ce matin, et ce qu'ils reçoivent.

        Rend une liste de `(person_id, EvenementApplique)`, vide les autres jours. Idempotente
        par agent : rappelée trois fois dans la même journée, elle ne rend rien la deuxième.
        """
        e = self.evenement
        if e.moment != "reveil":
            return []
        jour = self.jour_du_run(timestamp)
        if jour != self._compteurs.jour_run:
            self._basculer_de_journee(jour)
        dus = []
        for person_id, (household_id, raison) in self.lecteurs(population).items():
            if person_id in self._ont_lu:
                continue
            if self.jour_de(person_id, household_id) != jour:
                continue
            self._ont_lu.add(person_id)
            self._compteurs.exposes += 1
            dus.append((
                person_id,
                EvenementApplique(
                    evenement_id=e.evenement_id,
                    canal=e.canal,
                    moment=e.moment,
                    jour_run=jour,
                    jour_relatif=0,  # le jour de réception EST l'origine, par agent
                    retard_injecte_s=0,
                    texte=e.texte_cite.servi if e.texte_cite else "",
                    incident_reseau=False,
                    correspondance_ratee=False,
                    raison=raison,
                ),
            ))
        if dus:
            restants = len(self.lecteurs(population)) - len(self._ont_lu)
            logger.info(
                f"[evenements] jour {jour} — « {e.evenement_id} » servi à {len(dus)} "
                f"lecteur(s) au réveil ; {restants} lecteur(s) attendent encore leur jour de "
                f"parution. Les co-résidents non tirés sont le TÉMOIN INTERNE : ils ne "
                f"reçoivent rien, et c'est ce qui rend l'étage de diffusion observable."
            )
        return dus

    # ── Cache de décisions ───────────────────────────────────────────────────────────────
    def cache_coupe(self, timestamp: int) -> bool:
        """Le cache de décisions doit-il être contourné à cet instant ? (Q5, 2026-09-22)

        Vrai les JOURS D'ÉVÉNEMENT, et seulement ceux-là. La coupure est automatique : elle ne
        dépend pas d'un `CACHE=0` qu'on penserait à poser, et le run du 19 septembre a montré
        ce que coûte une garde qui dépend de la mémoire de l'opérateur.

        ⚠ **Ce que cette coupure ne protège pas.** Le jour de l'événement n'est pas le jour
        qu'on mesure : c'est la fenêtre d'après. La clé exacte du cache ne porte ni la date ni
        la mémoire de l'agent — une décision prise au jour 5, mêmes options, même météo, mêmes
        traits, même tranche horaire, reste servable au jour 20. Ce qui protège la fenêtre est
        la branche SÉMANTIQUE du cache, qui exige 0,95 de similarité entre le bloc de mémoire
        d'aujourd'hui et celui qui avait produit la décision. Quinze jours d'écart déplacent
        beaucoup ce bloc — probablement assez. Probablement : personne ne l'a mesuré. D'où les
        deux compteurs, qui rendent la réserve lisible au lieu de la laisser se discuter.
        """
        jour = self.jour_du_run(timestamp)
        if self.evenement.jours:
            return jour in self.evenement.jours
        # Forme B : les jours de parution sont tirés par cible. La coupure porte sur toute la
        # FENÊTRE, faute de savoir, à cet instant et sans la population, de qui il s'agit.
        # Couper large vaut mieux que couper à côté : le coût est quelques journées d'appels,
        # le risque inverse est une décision resservie le matin même de la parution.
        return self.evenement.premier_jour <= jour <= self.evenement.dernier_jour

    def noter_decision(self, timestamp: int, depuis_cache: bool) -> None:
        """Une décision vient d'être prise ; dire si le cache l'a servie. Ne lève jamais."""
        try:
            jour = self.jour_du_run(timestamp)
            if jour != self._compteurs.jour_run:
                self._basculer_de_journee(jour)
            if depuis_cache:
                self._compteurs.decisions_depuis_cache += 1
            else:
                self._compteurs.decisions_cache_coupe += 1
        except Exception:  # noqa: BLE001 — un compteur ne fait jamais tomber une décision
            pass

    # ── Journal ──────────────────────────────────────────────────────────────────────────
    def _basculer_de_journee(self, jour: int) -> None:
        if self._compteurs.jour_run:
            self.journaliser_compteurs()
        self._compteurs = CompteursJournee(jour_run=jour)
        self._touches_du_jour.clear()

    def journaliser_compteurs(self) -> None:
        """Compteurs de la journée écoulée, journalisés MÊME À ZÉRO.

        Un compteur muet ne distingue pas « rien ne s'est passé » de « le mécanisme ne tourne
        pas », et c'est précisément la confusion qui a coûté trente jours au ticket 075.
        """
        c = self._compteurs
        if not c.jour_run:
            return
        actif = (
            c.jour_run in self.evenement.jours
            if self.evenement.jours
            else self.evenement.premier_jour <= c.jour_run <= self.evenement.dernier_jour
        )
        deja = f", {c.deja_touches} déjà touché(s) ce jour" if c.deja_touches else ""
        relatif = c.jour_run - self.evenement.premier_jour
        logger.info(
            f"[evenements] jour {c.jour_run} du run "
            f"(relatif {c.jour_run - self.evenement.premier_jour:+d}) — "
            f"{'JOUR D_EVENEMENT' if actif else 'nominal'} : {c.exposes} exposé(s), "
            f"{c.epargnes} épargné(s){deja}, {c.retard_injecte_s // 60} min de retard injecté au "
            f"total (canal « {self.evenement.canal} », cadence « {self.evenement.cadence} »)"
        )
        # Le cache, jour par jour. Journalisé MÊME À ZÉRO sur toute la fenêtre d'après :
        # c'est le seul chiffre qui dise si la réserve du § « coupure au jour de l'événement »
        # a un objet, et il ne sert à rien s'il n'est relevé qu'en cas de problème.
        if actif:
            logger.info(
                f"[evenements] jour {c.jour_run} — cache de décisions COUPÉ (jour "
                f"d'événement) : {c.decisions_cache_coupe} décision(s) passée(s) par le modèle"
            )
        elif relatif > 0:
            logger.info(
                f"[evenements] jour {c.jour_run} (relatif {relatif:+d}, fenêtre d'après) — "
                f"{c.decisions_depuis_cache} décision(s) servie(s) DEPUIS LE CACHE sur "
                f"{c.decisions_depuis_cache + c.decisions_cache_coupe}. Un compte non nul ne "
                f"prouve rien à lui seul : la branche sémantique exige 0,95 de similarité de "
                f"mémoire. Il dit sur quoi porte le doute avant de publier la courbe."
            )
        if actif and c.exposes == 0:
            # Une journée d'événement qui ne touche personne est un protocole qui n'a pas eu
            # lieu. Le run du 19 septembre en a eu une — second choc restreint aux trajets en
            # voiture, sur un agent qui ne conduisait plus — dite en INFO, donc lue par
            # personne, et le rapport a continué d'annoncer deux jours de choc.
            logger.error(
                f"[ALARME] [evenements] jour {c.jour_run} du run déclaré JOUR D'ÉVÉNEMENT et "
                f"clos avec 0 exposé sur {c.epargnes} arrivée(s) éligible(s) examinée(s) : "
                f"l'événement « {self.evenement.evenement_id} » n'a PAS eu lieu ce jour-là. "
                f"Ne pas le compter comme une journée d'événement dans l'analyse."
            )

    def tracer(self, applique: EvenementApplique, person_id: str, timestamp: int,
               gravite: float, detail: Any, jugement: Any = None) -> None:
        """Une ligne par application dans `evenements.jsonl`. Jamais d'exception vers l'appelant.

        ⚠ **Les champs du ticket 079 sont CONSERVÉS, les nouveaux sont AJOUTÉS.** `choc_id` et
        `vecu` restent écrits à côté de `evenement_id` et `texte`, le temps d'une version. C'est
        la condition du test en or — un `evenements.jsonl` égal champ à champ à l'ancien
        `chocs.jsonl` — et c'est ce qui laisse les dépouilleurs des runs déjà archivés lire les
        runs neufs sans être touchés. Les alias partent au lot 6, avec `llm/chocs.py`.
        """
        if not self._journal:
            return
        try:
            ligne = {
                "person_id": str(person_id),
                "timestamp": int(timestamp),
                "horodatage_simule": wall_clock(int(timestamp)).isoformat(),
                "choc_id": applique.evenement_id,
                "jour_run": applique.jour_run,
                "jour_relatif": applique.jour_relatif,
                "raison_exposition": applique.raison,
                "retard_injecte_s": applique.retard_injecte_s,
                "incident_reseau": applique.incident_reseau,
                "correspondance_ratee": applique.correspondance_ratee,
                "vecu": applique.texte,
                "gravite": round(float(gravite), 4),
                "gravite_detail": {
                    "retard": round(float(getattr(detail, "retard", 0.0)), 4),
                    "correspondance_ratee": round(
                        float(getattr(detail, "correspondance_ratee", 0.0)), 4
                    ),
                    "incident_reseau": round(
                        float(getattr(detail, "incident_reseau", 0.0)), 4
                    ),
                    "mode_contraint": round(float(getattr(detail, "mode_contraint", 0.0)), 4),
                },
                # ── Ajouts du ticket 100 ────────────────────────────────────────────────
                "evenement_id": applique.evenement_id,
                "canal": applique.canal,
                "moment": applique.moment,
                "texte": applique.texte,
                # Ticket 100, lot 3 — ce que l'AGENT en a dit, à côté de ce que la simulation
                # a mesuré. Les deux, jamais l'un à la place de l'autre : sans les deux
                # colonnes, on ne saurait plus dire si une gravité vient d'un fait ou d'un avis.
                # Vides — jamais zéro — quand aucun jugement n'a été demandé : zéro est la
                # valeur d'un trajet parfait, et l'absence de mesure ne doit pas la porter.
                "importance_estimee": (
                    round(float(jugement.importance_estimee), 4) if jugement else None
                ),
                "intensite_jugee": jugement.intensite if jugement else None,
                "valence": jugement.valence if jugement else None,
                "modes_touches": list(jugement.modes) if jugement else None,
                "importance_retenue": round(float(gravite), 4),
                # D7 — la gravité est l'estimation seule. L'écart au fait mesuré est
                # journalisé et JAMAIS appliqué : c'est la garde qui remplace le plancher.
                # Sans cette colonne, une campagne où le modèle sous-estime systématiquement
                # ressemblerait trait pour trait à une campagne où rien ne s'est passé.
                "ecart_au_fait": (
                    round(float(jugement.ecart_au_fait), 4) if jugement else None
                ),
            }
            self._journal.parent.mkdir(parents=True, exist_ok=True)
            with self._journal.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        except Exception as err:  # noqa: BLE001 — une trace ne fait jamais tomber un run
            logger.warning(f"[evenements] trace non écrite ({err})")
