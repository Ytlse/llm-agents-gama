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

import asyncio
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from llm.evenements import calendrier
from llm.evenements import relais as relais_module
from llm.evenements.declaration import Evenement, EvenementApplique
from llm.evenements.exposition import expose, lecteurs
from llm.evenements.injection import ligne_de_foyer, ligne_de_lecture
from settings import settings
from sim_clock import gama_timestamp, wall_clock


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
    # ── Ticket 111 — la présence garantie au prompt ─────────────────────────────────────
    lectures_servies: int = 0            # rendus de `[ PRESSE ]` à un lecteur
    messages_servis: int = 0             # rendus de `[ FOYER ]` à un informé
    servies_avant_injection: int = 0     # dont décisions calculées AVANT l'injection de 00:00
    relais_produits: int = 0
    relais_refuses: int = 0
    relais_sans_membre: int = 0          # lecteur seul (ou seul mobile) : rien à transmettre
    cache_contourne_ligne: int = 0       # décisions qui devaient porter une ligne : jamais du cache
    # Décisions d'un jour de service construites SANS leur ligne. Doit rester à zéro.
    decisions_sans_ligne: int = 0
    reflexions_presse_presentees: int = 0
    reflexions_presse_validees: int = 0
    reflexions_presse_invalides: int = 0


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
        # Front montant de l'alarme « fenêtre ouverte, lecteurs jamais tirés ».
        self._alarme_lecteurs_non_tires = False
        # ── Ticket 111 — la ligne servie au prompt, et le relais au foyer ────────────────
        self._journal_relais = (
            Path(journal).parent / "relais_foyer.jsonl" if journal is not None else None
        )
        self._journal_reflexions_presse = (
            Path(journal).parent / "reflexions_presse.jsonl" if journal is not None else None
        )
        # Relais déjà produits par CE run : relus à la reprise, jamais régénérés.
        self._relais: dict[str, relais_module.RelaisFoyer] = relais_module.relire(
            self._journal_relais
        )
        # Échecs techniques à retenter : sortis de `_relais` pour être redemandés, avec le
        # numéro de la tentative déjà faite.
        self._tentatives: dict[str, int] = {
            hh: r.tentative for hh, r in self._relais.items() if r.a_retenter
        }
        for hh in self._tentatives:
            del self._relais[hh]
        self._relais_taches: dict[str, asyncio.Future] = {}
        self._producteur_relais: Callable[[str, str, int], Awaitable[Any]] | None = None
        self._non_avenus: set[str] = set()
        self._non_avenus_alarmes: set[str] = set()
        self._servies: Counter = Counter()  # (person_id, date ISO) → rendus
        self._servies_avant_injection: Counter = Counter()  # person_id → rendus
        self._entendus: set[str] = set()  # informés déjà écrits en mémoire à 00:00
        self._lecteurs_inconnus_dit = False
        self._producteur_absent_dit = False
        self._jamais_injectes_dits: set[str] = set()
        # À la reprise, qui a DÉJÀ lu et qui a déjà été informé se relit dans le journal : sans
        # cela, un rejeu qui repasse par le 00:00 du jour de lecture rendrait la lecture due une
        # seconde fois, et le gel du rejeu la déclarerait non avenue — une lecture réussie
        # perdrait ses lignes. Le journal ne porte que des injections abouties (`tracer` suit
        # l'écriture en mémoire).
        self._relire_journal()
        # Instant simulé du dernier /sync : c'est ce qui dit qu'une décision a été calculée
        # AVANT l'injection, et de combien.
        self._maintenant: int | None = None

    def _relire_journal(self) -> None:
        if self._journal is None or self.evenement.moment != "reveil":
            return
        chemin = Path(self._journal)
        if not chemin.is_file():
            return
        lus = entendus = 0
        for brute in chemin.read_text(encoding="utf-8").splitlines():
            try:
                ligne = json.loads(brute) if brute.strip() else None
            except json.JSONDecodeError:
                continue  # dernière ligne tronquée par un arrêt brutal : sautée, jamais fatale
            if not ligne or ligne.get("evenement_id") != self.evenement.evenement_id:
                continue
            pid = str(ligne.get("person_id") or "")
            if not pid:
                continue
            if ligne.get("origine") == "entendu":
                self._entendus.add(pid)
                entendus += 1
            else:
                self._ont_lu.add(pid)
                lus += 1
        if lus or entendus:
            logger.info(
                f"[evenements] reprise — « {self.evenement.evenement_id} » : {lus} lecture(s) et "
                f"{entendus} membre(s) informé(s) relus dans {chemin.name} ; ni relus ni "
                f"réinjectés."
            )

    def _injection_manquee(self, lecteur_id: str) -> bool:
        """Le jour de lecture est passé et ce lecteur n'a jamais été injecté.

        Arrive à la reprise, quand l'injection n'a pas abouti avant l'arrêt (le registre neuf ne
        sait pas qu'elle a été déclarée non avenue) : servir la ligne ferait lire un article que
        la mémoire de l'agent ne porte pas. Le jour même, on sert : la décision peut avoir été
        calculée avant l'injection, et c'est tout l'objet du ticket.
        """
        if lecteur_id in self._ont_lu or self._maintenant is None:
            return False
        lecture = self._date_injection(lecteur_id)
        if lecture is None or self._date_de(self._maintenant) <= lecture:
            return False
        if lecteur_id not in self._jamais_injectes_dits:
            self._jamais_injectes_dits.add(lecteur_id)
            logger.error(
                f"[ALARME] [evenements] « {self.evenement.evenement_id} » : le lecteur "
                f"{lecteur_id} devait lire le {lecture:%d/%m} et n'a jamais été injecté (reprise "
                f"après une exposition non avenue ?). Ses lignes et celles de son foyer ne sont "
                f"PAS servies ; {self._servies_avant_injection.get(lecteur_id, 0)} décision(s) "
                f"les avaient déjà portées avant."
            )
        return True

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

    def jour_relatif(self, timestamp: int, person_id: str | None = None) -> int:
        """Jours écoulés depuis l'exposition effective : −2, −1, 0, +1…

        Défini tous les jours du run, y compris avant et longtemps après : c'est l'abscisse de
        toutes les courbes de décrochage et de retour, et une abscisse qui n'existe que les
        jours d'événement ne tracerait rien. Pour une fenêtre tirée par foyer, le jour zéro est
        celui du lecteur du foyer de ``person_id`` ; utiliser le premier jour possible de la
        fenêtre décalait toute la courbe (A13 : exposition J12 affichée +3 car fenêtre J9–J13).

        Sans personne — anciens appels et événements subis résolus trajet par trajet — on garde
        l'origine déclarative historique.
        """
        if person_id is not None:
            date_injection = self._date_injection(str(person_id))
            if date_injection is not None:
                return (self._date_de(timestamp) - date_injection).days
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

    # ── Ticket 111 — ce qui est servi au prompt pendant les jours de service ─────────────
    def noter_instant(self, timestamp: int) -> None:
        """L'instant simulé courant, posé à chaque /sync. Sert au journal, jamais au calcul."""
        self._maintenant = int(timestamp)

    def brancher_producteur_relais(
        self, producteur: Callable[[str, str, int], Awaitable[Any]]
    ) -> None:
        """Le producteur du relais : seul le contrôleur détient population, client et identités."""
        self._producteur_relais = producteur

    def _jours_de_service(self, cible_id: str, household_id: str) -> tuple:
        """Les dates de service de cette cible, déterministes : ni horizon, ni rappel n'y entrent."""
        service = self.evenement.service
        if service is None:
            return ()
        debut = calendrier.date_du_jour_run(self.jour_de(cible_id, household_id))
        if debut is None:
            return ()
        return calendrier.jours_de_service(
            debut,
            service.jours_de_deplacement,
            bool(getattr(settings.agent, "no_weekend_departures", False)),
        )

    def _lecteur_du_foyer(self, household_id: str) -> str | None:
        """Le lecteur qui relaie dans ce foyer. Le premier dans l'ordre numérique, s'il y en a plusieurs."""
        ids = [p for p, (h, _) in (self._lecteurs or {}).items() if h == household_id]
        if not ids:
            return None
        return sorted(ids, key=lambda p: (len(p), p))[0]

    def foyer_expose(self, person_id: str) -> tuple[str, str] | None:
        """`(household_id, lecteur_id)` si cet agent est un NON-lecteur d'un foyer exposé."""
        if self._lecteurs is None:
            return None
        pid = str(person_id)
        if pid in self._lecteurs:
            return None
        from llm import foyer as _foyer

        mien = _foyer.foyer_de(pid)
        if not mien:
            return None
        lecteur = self._lecteur_du_foyer(mien)
        return (mien, lecteur) if lecteur else None

    def relais_connu(self, household_id: str):
        """Le relais de ce foyer s'il est déjà produit (ou refusé), sans rien lancer."""
        return self._relais.get(str(household_id))

    async def relais_du_foyer(self, household_id: str):
        """Le relais de ce foyer, produit à la première demande. Un seul appel par foyer.

        Rend `None` quand il n'y a pas de relais à servir : pas de relais déclaré, pas de
        producteur branché, ou relais refusé (l'alarme a été levée à la production).
        """
        hh = str(household_id)
        if self.evenement.relais is None:
            return None
        deja = self._relais.get(hh)
        if deja is not None:
            return None if deja.refus else deja
        if self._producteur_relais is None:
            if not self._producteur_absent_dit:
                self._producteur_absent_dit = True
                logger.error(
                    f"[ALARME] [evenements] « {self.evenement.evenement_id} » déclare un relais "
                    f"au foyer, mais aucun producteur n'est branché : AUCUN membre de foyer "
                    f"exposé ne sera informé. Ne pas compter les co-résidents comme informés."
                )
            return None
        tache = self._relais_taches.get(hh)
        if tache is None:
            tache = asyncio.ensure_future(self._produire_relais(hh))
            self._relais_taches[hh] = tache
        return await asyncio.shield(tache)

    async def _produire_relais(self, hh: str):
        lecteur = self._lecteur_du_foyer(hh)
        jour = self.jour_de(lecteur or "", hh)
        tentative = self._tentatives.get(hh, 0) + 1
        if tentative > 1:
            logger.warning(
                f"[evenements] relais du foyer {hh} — tentative {tentative}/"
                f"{relais_module.TENTATIVES_MAX} après un échec technique au run précédent"
            )
        try:
            produit = await self._producteur_relais(lecteur, hh, jour)
        except relais_module.RelaisRefuse as err:
            produit = relais_module.RelaisFoyer(
                household_id=hh, lecteur_id=str(lecteur), lecteur_prenom="",
                evenement_id=self.evenement.evenement_id, jour_run=int(jour),
                refus=str(err) or "refusé", technique=err.technique, tentative=tentative,
            )
        except Exception as err:  # noqa: BLE001 — le relais ne fait jamais tomber une décision
            logger.error(
                f"[ALARME] [evenements] relais du foyer {hh} impossible ({type(err).__name__}: "
                f"{err}) — lecteur {lecteur}, jour {jour}. Aucun message n'est servi dans ce "
                f"foyer."
            )
            produit = relais_module.RelaisFoyer(
                household_id=hh, lecteur_id=str(lecteur), lecteur_prenom="",
                evenement_id=self.evenement.evenement_id, jour_run=int(jour),
                refus=f"{type(err).__name__}: {err}", technique=True, tentative=tentative,
            )
        if produit.refus and produit.technique:
            reste = relais_module.TENTATIVES_MAX - produit.tentative
            logger.error(
                f"[ALARME] [evenements] relais du foyer {hh} : échec technique, tentative "
                f"{produit.tentative}/{relais_module.TENTATIVES_MAX}. "
                + (f"Pas de nouvel essai dans ce run ; une reprise retentera ({reste} essai(s) "
                   f"restant(s))." if reste > 0 else
                   "Plus aucun essai : le refus est définitif pour ce run et ses reprises.")
            )
        self._relais[hh] = produit
        if not produit.refus and tentative > 1:
            logger.warning(
                f"[evenements] relais du foyer {hh} produit à la tentative {tentative} : ses "
                f"membres informés voient leur ligne pour les jours de service restants. Si le "
                f"00:00 du jour de lecture est passé, ils n'ont PAS l'entrée en mémoire de ce "
                f"jour-là (coût accepté par l'auteur le 2026-09-25)."
            )
        if produit.refus:
            self._compteurs.relais_refuses += 1
        elif not produit.messages:
            self._compteurs.relais_sans_membre += 1
        else:
            self._compteurs.relais_produits += 1
        relais_module.ecrire(self._journal_relais, produit)
        return None if produit.refus else produit

    def _date_de(self, timestamp: int) -> date:
        return wall_clock(int(timestamp)).date()

    async def lignes_du_jour(
        self, person_id: str, timestamp: int, *, compter: bool = True
    ) -> list[str]:
        """Les lignes GARANTIES au prompt de cet agent pour une décision tenue à `timestamp`.

        `timestamp` est l'instant du TRAJET, pas celui du calcul : une décision du jour de
        lecture se calcule la veille, et c'est précisément ce qui la privait de l'article.

        - lecteur, jour dans ses jours de service → `[ PRESSE ] I read in the paper…` ;
        - membre informé d'un foyer exposé, jour dans ses jours de service → sa ligne
          `[ FOYER ]`, tirée du relais (produit à la demande s'il ne l'est pas encore) ;
        - personne déclarée non avenue, ou non informée → rien.

        `compter=False` pour une enquête : elle voit la même ligne, mais n'est pas une décision.
        """
        e = self.evenement
        if e.service is None or e.moment != "reveil":
            return []
        if self._lecteurs is None:
            if not self._lecteurs_inconnus_dit:
                self._lecteurs_inconnus_dit = True
                logger.error(
                    f"[ALARME] [evenements] « {e.evenement_id} » : une décision demande ses "
                    f"lignes de service alors que les lecteurs ne sont pas encore tirés. Le "
                    f"contrôleur doit appeler `lecteurs(population)` dès le chargement de la "
                    f"population ; sans cela, une lecture du jour 1 serait invisible des "
                    f"décisions du bootstrap."
                )
            return []
        pid = str(person_id)
        if pid in self._non_avenus:
            return []
        jour = self._date_de(timestamp)
        ligne = None
        avant = False
        if pid in self._lecteurs:
            hh = self._lecteurs[pid][0]
            if jour not in self._jours_de_service(pid, hh):
                return []
            if self._injection_manquee(pid):
                return []
            ligne = ligne_de_lecture(e.texte_cite.servi if e.texte_cite else "")
            avant = pid not in self._ont_lu
            genre = "lectures_servies"
        else:
            expose_ = self.foyer_expose(pid)
            if expose_ is None or e.relais is None:
                return []
            hh, lecteur = expose_
            if jour not in self._jours_de_service(pid, hh):
                return []
            if lecteur is not None and self._injection_manquee(str(lecteur)):
                return []
            produit = await self.relais_du_foyer(hh)
            if pid in self._non_avenus or produit is None:
                return []
            message = produit.message_pour(pid)
            if message is None or not message.parle:
                return []
            ligne = ligne_de_foyer(message.texte, produit.lecteur_prenom, message.mineur)
            avant = pid not in self._entendus
            genre = "messages_servis"
        if compter:
            self._noter_service(pid, jour, timestamp, avant, genre)
        return [ligne]

    def _noter_service(self, pid: str, jour: date, timestamp: int, avant: bool,
                       genre: str) -> None:
        cle = (pid, jour.isoformat())
        premier = cle not in self._servies
        self._servies[cle] += 1
        setattr(self._compteurs, genre, getattr(self._compteurs, genre) + 1)
        if avant:
            self._servies_avant_injection[pid] += 1
            self._compteurs.servies_avant_injection += 1
        if not premier:
            return
        quoi = "article du jour" if genre == "lectures_servies" else "message du foyer"
        calcul = ""
        if avant and self._maintenant is not None:
            injection = gama_timestamp(
                datetime.combine(self._date_injection(pid) or jour, datetime.min.time())
            )
            ecart_h = (injection - self._maintenant) / 3600.0
            if ecart_h > 0:
                calcul = f", calculée {ecart_h:.0f} h avant l'injection"
        logger.info(
            f"[evenements] {pid} : {quoi} servi à la décision du "
            f"{wall_clock(int(timestamp)):%d/%m %H:%M}{calcul} "
            f"(jour de service {jour.isoformat()})"
        )

    def _date_injection(self, pid: str) -> date | None:
        hh = (self._lecteurs or {}).get(pid, (None,))[0] or (self.foyer_expose(pid) or (None,))[0]
        if hh is None:
            return None
        return calendrier.date_du_jour_run(self.jour_de(pid, hh))

    def noter_entendu(self, person_id: str) -> None:
        """Le message de cet informé est écrit en mémoire (injection de 00:00)."""
        self._entendus.add(str(person_id))

    def declarer_non_avenue(self, person_id: str, motif: str) -> None:
        """L'exposition de cet agent n'a pas eu lieu. Ses lignes cessent d'être servies.

        Si des décisions ont DÉJÀ porté la ligne — calculées la veille, avant que l'injection
        ne soit refusée —, elles ne se défont pas : une `[ALARME]`, une seule fois par agent,
        dit combien, pour qu'elles soient écartées de l'analyse.
        """
        pid = str(person_id)
        self._non_avenus.add(pid)
        deja = sum(n for (p, _), n in self._servies.items() if p == pid)
        if deja and pid not in self._non_avenus_alarmes:
            self._non_avenus_alarmes.add(pid)
            logger.error(
                f"[ALARME] [evenements] « {self.evenement.evenement_id} » : l'exposition de "
                f"{pid} est déclarée NON AVENUE ({motif}), mais {deja} décision(s) ont déjà vu "
                f"sa ligne au prompt. Elles ne se défont pas : les écarter de l'analyse."
            )
        else:
            logger.warning(
                f"[evenements] « {self.evenement.evenement_id} » : exposition de {pid} non "
                f"avenue ({motif}) — aucune décision n'avait encore vu sa ligne."
            )

    def noter_rendu(self, person_id: str, timestamp: int, lignes, historique) -> None:
        """Une décision d'un jour de service a-t-elle bien porté ses lignes ? Ne lève jamais."""
        try:
            if not lignes:
                return
            rendu = "\n".join(str(h) for h in (historique or []))
            manquantes = [ligne for ligne in lignes if ligne not in rendu]
            if not manquantes:
                return
            self._compteurs.decisions_sans_ligne += 1
            logger.error(
                f"[ALARME] [evenements] décision de {person_id} du "
                f"{wall_clock(int(timestamp)):%d/%m %H:%M} construite SANS sa ligne de "
                f"service ({manquantes[0][:40]}…) — le bloc de mémoire ne l'a pas rendue. La "
                f"garantie du ticket 111 ne tient pas pour cette décision."
            )
        except Exception:  # noqa: BLE001
            pass

    def noter_contournement_cache(self) -> None:
        self._compteurs.cache_contourne_ligne += 1

    def tracer_reflexion_presse(
        self,
        person_id: str,
        timestamp: int,
        lignes: list[str],
        *,
        etape: str,
        prise_en_compte: bool | None = None,
        reflection: str = "",
    ) -> None:
        """Trace la présentation du journal à la consolidation et son accusé de lecture.

        La trace est volontairement séparée du journal des injections : une lecture initiale
        et une présentation quotidienne pendant le service sont deux mécanismes différents.
        """
        if not lignes:
            return
        if etape == "presentee":
            self._compteurs.reflexions_presse_presentees += 1
        elif prise_en_compte:
            self._compteurs.reflexions_presse_validees += 1
        else:
            self._compteurs.reflexions_presse_invalides += 1
        chemin = self._journal_reflexions_presse
        if chemin is None:
            return
        try:
            texte = "\n".join(str(l) for l in lignes)
            ligne = {
                "evenement_id": self.evenement.evenement_id,
                "person_id": str(person_id),
                "timestamp": int(timestamp),
                "date": self._date_de(int(timestamp)).isoformat(),
                "jour_relatif": self.jour_relatif(int(timestamp), str(person_id)),
                "etape": str(etape),
                "prise_en_compte": prise_en_compte,
                "service_sha256": hashlib.sha256(texte.encode("utf-8")).hexdigest(),
                "service_apercu": texte[:240],
                "reflection": str(reflection or ""),
            }
            chemin.parent.mkdir(parents=True, exist_ok=True)
            with chemin.open("a", encoding="utf-8") as flux:
                flux.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        except Exception as err:  # noqa: BLE001 — l'observabilité ne fait pas tomber le run
            logger.error(
                f"[ALARME] [evenements] trace de réflexion presse impossible pour "
                f"{person_id} ({err})"
            )

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
        # Forme B — une fenêtre, et un jour de parution TIRÉ par foyer. Un jour de la fenêtre
        # n'est pas un jour d'événement : seul l'est celui où un lecteur a été tiré. Le run
        # `2026-09-24_17_50` (fenêtre 9-13, un seul foyer tiré au jour 11) levait l'alarme
        # « 0 exposé » les jours 9, 10, 12 et 13, où il n'y avait rien à exposer.
        tire_par_foyer = actif and not self.evenement.jours
        attendus = self._lecteurs_tires_pour(c.jour_run) if tire_par_foyer else None
        if not tire_par_foyer:
            etat = "JOUR D_EVENEMENT" if actif else "nominal"
        elif attendus is None:
            etat = "fenêtre de parution, lecteurs PAS ENCORE TIRÉS"
        elif attendus:
            etat = f"JOUR DE PARUTION ({len(attendus)} lecteur(s) tiré(s) pour ce jour)"
        else:
            etat = "fenêtre de parution, aucun lecteur tiré pour ce jour"
        deja = f", {c.deja_touches} déjà touché(s) ce jour" if c.deja_touches else ""
        relatif = c.jour_run - self.evenement.premier_jour
        repere = "à l'ouverture de la fenêtre" if not self.evenement.jours else "au 1er jour"
        logger.info(
            f"[evenements] jour {c.jour_run} du run "
            f"(relatif {relatif:+d} {repere}) — "
            f"{etat} : {c.exposes} exposé(s), "
            f"{c.epargnes} épargné(s){deja}, {c.retard_injecte_s // 60} min de retard injecté au "
            f"total (canal « {self.evenement.canal} », cadence « {self.evenement.cadence} »)"
        )
        # Le cache, jour par jour. Journalisé MÊME À ZÉRO sur toute la fenêtre d'après :
        # c'est le seul chiffre qui dise si la réserve du § « coupure au jour de l'événement »
        # a un objet, et il ne sert à rien s'il n'est relevé qu'en cas de problème.
        if actif:
            motif_coupure = "fenêtre de parution" if tire_par_foyer else "jour d'événement"
            logger.info(
                f"[evenements] jour {c.jour_run} — cache de décisions COUPÉ ({motif_coupure}) : "
                f"{c.decisions_cache_coupe} décision(s) passée(s) par le modèle"
            )
        elif relatif > 0:
            logger.info(
                f"[evenements] jour {c.jour_run} (relatif {relatif:+d}, fenêtre d'après) — "
                f"{c.decisions_depuis_cache} décision(s) servie(s) DEPUIS LE CACHE sur "
                f"{c.decisions_depuis_cache + c.decisions_cache_coupe}. Un compte non nul ne "
                f"prouve rien à lui seul : la branche sémantique exige 0,95 de similarité de "
                f"mémoire. Il dit sur quoi porte le doute avant de publier la courbe."
            )
        if self.evenement.service is not None:
            # Ticket 111 — journalisé MÊME À ZÉRO : un compteur muet ne distingue pas « rien à
            # servir aujourd'hui » de « le mécanisme ne tourne plus ».
            logger.info(
                f"[evenements] jour {c.jour_run} — service garanti : {c.lectures_servies} "
                f"lecture(s) servie(s), {c.messages_servis} message(s) du foyer servi(s), dont "
                f"{c.servies_avant_injection} dans une décision calculée avant l'injection ; "
                f"relais {c.relais_produits} produit(s), {c.relais_refuses} refusé(s), "
                f"{c.relais_sans_membre} sans autre membre ; "
                f"{c.cache_contourne_ligne} décision(s) tenue(s) hors cache pour porter leur "
                f"ligne ; {c.decisions_sans_ligne} décision(s) de jour de service sans ligne"
            )
            logger.info(
                f"[evenements] jour {c.jour_run} — journal dans la réflexion : "
                f"{c.reflexions_presse_presentees} présentation(s), "
                f"{c.reflexions_presse_validees} prise(s) en compte validée(s), "
                f"{c.reflexions_presse_invalides} réponse(s) invalide(s)"
            )
            if c.decisions_sans_ligne:
                logger.error(
                    f"[ALARME] [evenements] jour {c.jour_run} : {c.decisions_sans_ligne} "
                    f"décision(s) d'un jour de service construite(s) SANS leur ligne. La "
                    f"présence garantie au prompt ne tient pas ce jour-là."
                )
        if tire_par_foyer:
            self._alarmer_parution(c.jour_run, attendus)
        elif actif and c.exposes == 0:
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

    def _lecteurs_tires_pour(self, jour: int) -> list[str] | None:
        """Les lecteurs dont le jour de parution tiré est `jour`. `None` s'ils ne sont pas tirés.

        `None` et `[]` ne se confondent pas : le premier dit que la prise du réveil n'a jamais
        tourné, le second qu'aucun foyer n'a tiré ce jour-là — ce qui est attendu.
        """
        if self._lecteurs is None:
            return None
        return sorted(
            pid for pid, (household_id, _raison) in self._lecteurs.items()
            if self.jour_de(pid, household_id) == jour
        )

    def _alarmer_parution(self, jour: int, attendus: list[str] | None) -> None:
        """L'alarme d'une fenêtre tirée par foyer, comparée aux lecteurs tirés pour CE jour."""
        e = self.evenement
        if attendus is None:
            # Front montant : une fois par run. Chaque jour de fenêtre sans lecteurs tirés est
            # le même défaut, et le redire cinq fois noierait la première occurrence.
            if not self._alarme_lecteurs_non_tires:
                self._alarme_lecteurs_non_tires = True
                logger.error(
                    f"[ALARME] [evenements] jour {jour} du run, dans la fenêtre de parution "
                    f"{e.premier_jour}-{e.dernier_jour} de « {e.evenement_id} », et les lecteurs "
                    f"n'ont jamais été tirés : la prise « {e.moment} » n'a pas tourné. Personne "
                    f"ne lira l'article tant qu'elle ne tourne pas."
                )
            return
        manquants = [pid for pid in attendus if pid not in self._ont_lu]
        if manquants:
            foyers = sorted({(self._lecteurs or {}).get(p, ("",))[0] for p in manquants})
            logger.error(
                f"[ALARME] [evenements] jour {jour} du run, jour de parution tiré pour "
                f"{len(attendus)} lecteur(s) de « {e.evenement_id} » : {len(manquants)} n'ont "
                f"PAS lu — {', '.join(manquants[:10])} (foyer(s) {', '.join(foyers[:10])}). Ne "
                f"pas compter ce jour comme une exposition de ces foyers dans l'analyse."
            )

    def tracer(self, applique: EvenementApplique, person_id: str, timestamp: int,
               gravite: float, detail: Any, jugement: Any = None,
               extra: dict | None = None) -> None:
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
            # Ticket 111 — un informé porte en plus le message reçu, qui l'a dit, et s'il est
            # mineur. Ajoutés, jamais substitués : la ligne du lecteur reste celle d'avant.
            if extra:
                ligne.update(extra)
            self._journal.parent.mkdir(parents=True, exist_ok=True)
            with self._journal.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        except Exception as err:  # noqa: BLE001 — une trace ne fait jamais tomber un run
            logger.warning(f"[evenements] trace non écrite ({err})")
