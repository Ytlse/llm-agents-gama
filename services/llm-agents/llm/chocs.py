"""Chocs déclarés, subis par les agents — ticket 079.

POURQUOI CE MODULE EXISTE
-------------------------
L'Étape 3a de l'article mesure l'**hystérésis** : l'agent évite-t-il encore un mode une fois la
situation rétablie ? Cela suppose un choc qui laisse une trace. Or la simulation ne savait
provoquer aucun incident : `experiences/experience.py` accepte un format d'événement, l'archive,
et **refuse l'exécution**. Aucun choc n'était jouable, donc aucune hystérésis n'était mesurable.

Ce module pose la brique manquante, et elle est petite : un choc, c'est **un retard chiffré** plus
**une phrase vécue**, posés sur des agents désignés, à des jours désignés.

CE QU'IL NE FAIT PAS, ET C'EST LE POINT
---------------------------------------
Il ne coupe aucune ligne, ne dégrade aucune fréquence, ne touche ni OTP, ni GTFS, ni OSMnx. C'est
le **régime subi** : l'agent décide en voyant l'offre nominale, puis encaisse. Deux raisons, et la
seconde est scientifique avant d'être économique.

1. C'est réaliste pour un incident imprévu — personne ne connaît la panne avant de la subir.
2. **Le jour du choc ne mesure alors aucun choix.** Tout l'effet observé les jours suivants est
   imputable au souvenir, et à rien d'autre. Un choc qui dégraderait aussi l'offre mêlerait
   inextricablement l'adaptation à la contrainte et l'inertie de la mémoire.

⚠ Le manuscrit (§ 5.3) exige que l'événement soit « le même événement déclaré deux fois, une fois
en langue et une fois en graphe ». Le régime subi ne le déclare **qu'une fois**, en langue. C'est
légitime pour un imprévu, mais cela doit être ÉCRIT dans l'article, pas laissé implicite.

POURQUOI C'EST SI PEU DE CODE
-----------------------------
Le ticket 071 a câblé la gravité d'un souvenir de bout en bout — paramètre, détail, compteur,
journal — en laissant une composante vide **exprès** : `incident_reseau`, poids 0,20, rangée dans
`COMPOSANTES_INACTIVES` avec le commentaire « il n'y a qu'une source à brancher le jour venu ».
**Ce module est cette source.** Une fois le retard ajouté et la composante portée, tout le reste
suit sans une ligne : force du souvenir, vivier des chocs, consolidation sur gravité cumulée,
bloc « Ce qui a changé récemment » du prompt.

Chiffré sur le cas du bouchon : 60 minutes de retard saturent la composante retard à 0,50 ;
`incident_reseau` ajoute 0,20 ; total 0,70, soit exactement le seuil du vivier des chocs. La force
passe de 2,8 à 14,6 jours. C'est cela, et rien d'autre, qui rend l'hystérésis observable.

LA RÈGLE QUI NE SE NÉGOCIE PAS
------------------------------
**Le retard injecté et le retard mesuré ne se confondent jamais.** Deux champs distincts, partout
où ils passent. Sans cette séparation, aucune trace ne permettrait plus jamais de dire ce que la
simulation a produit et ce qu'on lui a fait dire — et une mesure d'hystérésis sans cette
distinction n'est pas publiable.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from settings import settings
from sim_clock import wall_clock

# Règles d'exposition admises. Trois, et rien d'autre : une règle inconnue est refusée au
# chargement plutôt qu'ignorée, sans quoi une faute de frappe produirait un choc qui ne touche
# personne et un run entier sans le moindre symptôme.
REGLES_EXPOSITION: tuple[str, ...] = ("mode", "tirage", "agents")

# Cadence d'application, par agent et par journée de choc. `trajet` = chaque arrivée éligible
# subit le choc (un bouchon dure toute la journée) ; `jour` = seule la PREMIÈRE arrivée éligible
# de la journée le subit (une panne réparée ne se reproduit pas à l'identique trois heures plus
# tard). Le run du 19 septembre a appliqué quatre fois le même dépannage de trente minutes dans
# la même journée, là où le protocole en comptait un : l'intensité réelle valait quatre fois
# l'intensité annoncée, et rien ne le disait.
CADENCES: tuple[str, ...] = ("trajet", "jour")
CADENCE_PAR_DEFAUT = "trajet"

# Marqueurs d'une CONSIGNE déguisée en vécu. Le format `Evenement` du ticket 035 portait déjà la
# règle sur son champ `description` — « texte porté aux agents, jamais consigne » — mais elle n'y
# était qu'une phrase de documentation. Ici elle devient vérifiable, et elle REFUSE.
#
# Pourquoi refuser et non avertir : un avertissement au milieu d'un journal de run n'alerte
# personne (le ticket 077 l'a mesuré — deux WARNING sur le vocabulaire des modes noyés dans
# 355 000 lignes, et le mécanisme des concepts est resté cassé trente jours). Et une consigne qui
# passe ne biaise pas un peu : elle fabrique exactement le résultat qu'on prétend mesurer.
MARQUEURS_CONSIGNE: tuple[str, ...] = (
    "you should", "you must", "you'd better", "you ought", "you need to",
    "avoid ", "remember to", "consider ", "try to", "don't ", "do not ",
    "make sure", "next time you", "from now on",
    "tu devrais", "tu dois", "évite ", "evite ", "pense à", "pense a",
    "il faut que tu", "n'oublie pas", "la prochaine fois", "désormais tu",
)

# Marqueurs d'un VERDICT — une croyance durable sur un mode ou un véhicule. R9.
#
# La croyance est exactement ce que l'étape de réflexion existe pour produire : l'écrire à la
# main court-circuite le seul mécanisme que l'expérience prétend mesurer. Le run du 19 septembre
# l'a payé — `vecu` : « I no longer trust this car at all » ; concept « appris » le soir même :
# « My car is unreliable ». Le second n'est que la reformulation du premier.
#
# La liste est calibrée sur le corpus du dépôt, pas devinée : les cinq chocs c1 à c5 passent
# sans modification, et « I am starting to wonder whether this is worth it » (c1, jour 14) reste
# accepté — un doute n'est pas un verdict.
MARQUEURS_VERDICT: tuple[str, ...] = (
    "no longer trust", "cannot trust", "can't trust", "never trust",
    "is unreliable", "are unreliable", "'s unreliable", "was unreliable",
    "is not reliable", "isn't reliable", "not reliable at all",
    "can't rely on", "cannot rely on", "can no longer rely",
    "ne fais plus confiance", "n'ai plus confiance", "plus confiance en",
    "n'est pas fiable", "pas fiable du tout", "ne peux plus compter sur",
)

# Marqueurs d'une INTENTION MODALE — ce que l'agent fera demain. R10.
#
# Famille distincte de la précédente, et refusée par un message distinct : les deux se relâchent
# séparément le jour où l'auteur voudra discuter la ligne. Un fait PASSÉ, même modal, reste
# accepté — « I had to sort out another way of getting around » (c2, jour 13) décrit une journée
# vécue, pas une résolution.
MARQUEURS_INTENTION: tuple[str, ...] = (
    "thinking about not using", "thinking of not using", "considering not using",
    "thinking about not taking", "considering not taking",
    "i will not use", "i won't use", "i will stop using", "i'll stop using",
    "i am not going to use", "i'm not going to use", "i will never use",
    "i will never drive", "i will never take", "i will stop driving",
    "from now on i", "i will take the", "i'll take the", "i will use the",
    "alternative transport", "another mode of transport", "switch to the",
    " prendrai", "je vais arrêter", "je vais arreter", "je ne conduirai",
    "désormais je", "desormais je", "un autre mode de transport",
)

# Adresse à la deuxième personne, en tête de phrase ou isolée. Un vécu se raconte à la première
# personne ; s'adresser à l'agent, c'est lui parler, donc lui dicter.
_DEUXIEME_PERSONNE = re.compile(
    r"\b(you|your|yours|tu|toi|ton|ta|tes|vous|votre|vos)\b", re.IGNORECASE
)

# Marques de première personne. Leur ABSENCE n'est pas refusée — « Flat tyre on the way, hands
# covered in grease » est un vécu parfaitement valide sans un seul « I » — mais elle est signalée.
_PREMIERE_PERSONNE = re.compile(
    r"\b(i|i'm|i've|i'd|my|mine|me|je|j'ai|j'|mon|ma|mes|moi)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class JourDeChoc:
    """Ce que le choc fait subir un jour donné.

    Le profil est déclaré JOUR PAR JOUR et non par une durée plus une intensité : un bouchon
    n'est pas le même le premier et le troisième jour, et l'agent doit pouvoir le dire dans ses
    mots. C'est la demande d'origine, et c'est aussi ce qui permet une décrue — 60, 40, 25
    minutes — que rien d'autre ne saurait produire.
    """

    jour: int  # rang dans le run, 1 = premier jour simulé
    retard_min: int
    vecu: str
    incident_reseau: bool = True
    correspondance_ratee: bool = False

    @property
    def retard_s(self) -> int:
        return int(self.retard_min) * 60


@dataclass(frozen=True)
class Exposition:
    """Qui est touché.

    `mode` — tout agent dont le trajet qui arrive a été fait dans l'un des modes déclarés.
    `tirage` — une part des agents, tirée de façon DÉTERMINISTE et stable d'un run à l'autre.
    `agents` — des identifiants nommés, pour un incident individuel reproductible.
    """

    regle: str
    modes: frozenset[str] = frozenset()
    part: float = 1.0
    graine: int = 79
    agents: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Choc:
    choc_id: str
    libelle: str
    source: str | None
    exposition: Exposition
    jours: dict[int, JourDeChoc]
    cadence: str = CADENCE_PAR_DEFAUT
    empreinte: str = ""

    @property
    def premier_jour(self) -> int:
        return min(self.jours)

    @property
    def dernier_jour(self) -> int:
        return max(self.jours)


@dataclass(frozen=True)
class ChocApplique:
    """Ce qu'un agent subit réellement, à une arrivée donnée."""

    choc_id: str
    jour_run: int
    jour_relatif: int
    retard_injecte_s: int
    vecu: str
    incident_reseau: bool
    correspondance_ratee: bool
    raison: str


@dataclass
class CompteursJournee:
    jour_run: int = 0
    exposes: int = 0
    epargnes: int = 0
    retard_injecte_s: int = 0
    # Arrivées éligibles NON touchées parce que l'agent l'avait déjà été le jour même
    # (`cadence: jour`). Comptées à part : ce n'est ni une exposition, ni un agent épargné.
    deja_touches: int = 0


class RefusDeChoc(ValueError):
    """Déclaration invalide. Refuser au chargement vaut mieux qu'un choc fantôme au run."""


def _modes_admis() -> frozenset[str]:
    """Les modes canoniques, DÉRIVÉS de la hiérarchie du dépôt et jamais recopiés ici.

    Une liste écrite dans ce module divergerait de la hiérarchie le jour où elle bouge, sans que
    rien ne le dise — c'est la leçon du lot A du ticket 077, où deux vocabulaires de modes
    coexistaient sans que personne ne le sache.
    """
    from llm.axes import mode_canonique

    candidats = (
        "walking", "cycling", "car", "public_transport", "train", "motorbike",
    )
    return frozenset(m for m in candidats if mode_canonique(m) == m)


def _verifier_vecu(texte: str, choc_id: str, jour: int) -> None:
    """R7 et R8 : un vécu se raconte, il ne se commande pas."""
    nu = (texte or "").strip()
    if not nu:
        raise RefusDeChoc(
            f"choc « {choc_id} », jour {jour} : `vecu` vide — un choc sans texte vécu ne "
            f"laisse aucun souvenir, il ne sert à rien"
        )
    bas = nu.lower()
    # R9 et R10 AVANT R7 : « from now on I will take the metro » est une intention à la première
    # personne, pas une consigne à la deuxième. L'ordre décide du message rendu, et un message
    # qui nomme la mauvaise faute envoie corriger le mauvais mot.
    for marqueur in MARQUEURS_VERDICT:
        if marqueur in bas:
            raise RefusDeChoc(
                f"choc « {choc_id} », jour {jour} : `vecu` porte un VERDICT sur un mode — "
                f"« {marqueur.strip()} ». La croyance est ce que la réflexion de l'agent doit "
                f"produire ; l'écrire ici revient à mesurer sa propre consigne. "
                f"Racontez le fait : « the engine stalled twice », jamais « this car is unreliable »"
            )
    for marqueur in MARQUEURS_INTENTION:
        if marqueur in bas:
            raise RefusDeChoc(
                f"choc « {choc_id} », jour {jour} : `vecu` annonce une INTENTION modale — "
                f"« {marqueur.strip()} ». Ce que l'agent fera demain est le résultat qu'on "
                f"mesure, pas une donnée d'entrée. Un fait passé reste permis : "
                f"« I had to sort out another way of getting around »"
            )
    for marqueur in MARQUEURS_CONSIGNE:
        if marqueur in bas:
            raise RefusDeChoc(
                f"choc « {choc_id} », jour {jour} : `vecu` contient « {marqueur.strip()} », "
                f"qui s'adresse à l'agent au lieu de raconter ce qu'il a vécu. Un texte qui "
                f"dicte une conduite fabrique le résultat qu'on prétend mesurer. "
                f"Racontez le fait : « I was stuck for an hour », jamais « avoid the ring road »"
            )
    if _DEUXIEME_PERSONNE.search(nu):
        raise RefusDeChoc(
            f"choc « {choc_id} », jour {jour} : `vecu` s'adresse à l'agent à la deuxième "
            f"personne. Un vécu se raconte à la première personne"
        )
    if not _PREMIERE_PERSONNE.search(nu):
        logger.warning(
            f"[chocs] choc « {choc_id} », jour {jour} : `vecu` ne porte aucune marque de "
            f"première personne — vérifiez que c'est bien un vécu et non une description "
            f"extérieure : « {nu[:70]}… »"
        )


def charger(chemin: str | Path) -> Choc:
    """Lit et VÉRIFIE une déclaration de choc. Lève `RefusDeChoc` au moindre doute."""
    p = Path(chemin)
    if not p.is_file():
        raise RefusDeChoc(f"fichier de choc introuvable : {p}")
    brut = p.read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()
    data: dict[str, Any] = yaml.safe_load(brut.decode("utf-8")) or {}

    choc_id = str(data.get("choc") or "").strip()
    if not choc_id:
        raise RefusDeChoc(f"{p} : champ `choc` (identifiant) absent ou vide")

    exp_brut = data.get("exposition") or {}
    regle = str(exp_brut.get("regle") or "").strip()
    if regle not in REGLES_EXPOSITION:
        raise RefusDeChoc(
            f"choc « {choc_id} » : règle d'exposition « {regle} » inconnue — "
            f"attendu l'une de {REGLES_EXPOSITION}"
        )

    modes = frozenset(str(m).strip() for m in (exp_brut.get("modes") or []) if str(m).strip())
    admis = _modes_admis()
    inconnus = modes - admis
    if inconnus:
        raise RefusDeChoc(
            f"choc « {choc_id} » : mode(s) {sorted(inconnus)} hors de la hiérarchie du dépôt — "
            f"attendu parmi {sorted(admis)}"
        )
    if regle == "mode" and not modes:
        raise RefusDeChoc(f"choc « {choc_id} » : règle `mode` sans aucun mode déclaré")

    part = float(exp_brut.get("part", 1.0))
    if regle == "tirage" and not (0.0 < part <= 1.0):
        raise RefusDeChoc(
            f"choc « {choc_id} » : `part` = {part} hors de ]0, 1] — un tirage qui ne touche "
            f"personne ou qui touche plus que tout le monde n'a pas de sens"
        )

    agents = frozenset(str(a).strip() for a in (exp_brut.get("agents") or []) if str(a).strip())
    if regle == "agents" and not agents:
        raise RefusDeChoc(f"choc « {choc_id} » : règle `agents` sans aucun identifiant")

    exposition = Exposition(
        regle=regle,
        modes=modes,
        part=part,
        graine=int(exp_brut.get("graine", 79)),
        agents=agents,
    )

    cadence_brute = str(data.get("cadence") or "").strip().lower()
    if cadence_brute and cadence_brute not in CADENCES:
        raise RefusDeChoc(
            f"choc « {choc_id} » : `cadence` « {cadence_brute} » inconnue — "
            f"attendu {' ou '.join(CADENCES)}. Une cadence mal orthographiée changerait "
            f"silencieusement l'intensité du choc."
        )
    cadence = cadence_brute or CADENCE_PAR_DEFAUT
    logger.info(
        f"[chocs] choc « {choc_id} » : cadence « {cadence} »"
        + ("" if cadence_brute else f" (non déclarée, valeur par défaut {CADENCE_PAR_DEFAUT})")
    )

    jours_bruts = data.get("jours") or []
    if not jours_bruts:
        raise RefusDeChoc(f"choc « {choc_id} » : aucune journée déclarée dans `jours`")

    jours: dict[int, JourDeChoc] = {}
    for entree in jours_bruts:
        jour = int(entree.get("jour", 0))
        if jour < 1:
            raise RefusDeChoc(
                f"choc « {choc_id} » : `jour` = {jour} — le premier jour du run porte le n° 1"
            )
        if jour in jours:
            raise RefusDeChoc(
                f"choc « {choc_id} » : deux entrées pour le jour {jour} — une journée porte "
                f"un profil et un seul"
            )
        retard_min = int(entree.get("retard_min", 0))
        if retard_min < 0:
            raise RefusDeChoc(
                f"choc « {choc_id} », jour {jour} : `retard_min` = {retard_min} — un retard "
                f"négatif serait une avance, ce que la gravité ne sait pas représenter"
            )
        vecu = str(entree.get("vecu") or "").strip()
        _verifier_vecu(vecu, choc_id, jour)
        jours[jour] = JourDeChoc(
            jour=jour,
            retard_min=retard_min,
            vecu=vecu,
            incident_reseau=bool(entree.get("incident_reseau", True)),
            correspondance_ratee=bool(entree.get("correspondance_ratee", False)),
        )

    return Choc(
        choc_id=choc_id,
        libelle=str(data.get("libelle") or choc_id),
        source=data.get("source"),
        exposition=exposition,
        jours=jours,
        cadence=cadence,
        empreinte=empreinte,
    )


class RegistreChocs:
    """Le choc en vigueur pour ce run, et ce qu'il a fait.

    Un seul choc à la fois, volontairement. Deux chocs superposés rendraient l'attribution
    impossible — c'est exactement ce que le protocole cherche à établir, et le mécanisme ne doit
    pas fabriquer lui-même la confusion qu'il sert à lever.
    """

    def __init__(self, choc: Choc, journal: Path | None = None) -> None:
        self.choc = choc
        self._journal = journal
        self._compteurs = CompteursJournee()
        self._exposes_vus: set[str] = set()
        # `cadence: jour` — qui a déjà été touché DANS la journée en cours. Remis à zéro au
        # basculement de journée, jamais accumulé sur le run : un agent est touché une fois
        # par jour de choc, pas une fois pour tout le run.
        self._touches_du_jour: set[str] = set()

    # ── Temps ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def jour_du_run(timestamp: int) -> int:
        """1 pour le premier jour simulé du run.

        Lu sur l'ANCRE du ticket 075 et non sur le premier timestamp observé : après une reprise
        à chaud, GAMA rejoue depuis son t0, et se réancrer ferait reculer le choc de plusieurs
        jours au milieu du run.
        """
        from urban_mobility_agents.utils.ancre_run import jours_ecoules

        return int(jours_ecoules(int(timestamp))) + 1

    def jour_relatif(self, timestamp: int) -> int:
        """Jours écoulés depuis le PREMIER jour du choc : −2, −1, 0, +1…

        Défini tous les jours du run, y compris avant et longtemps après : c'est l'abscisse de
        toutes les courbes d'hystérésis, et une abscisse qui n'existe que les jours de choc ne
        tracerait rien.
        """
        return self.jour_du_run(timestamp) - self.choc.premier_jour

    # ── Exposition ───────────────────────────────────────────────────────────────────────
    def _expose(self, person_id: str, mode: str | None) -> tuple[bool, str]:
        e = self.choc.exposition
        if e.regle == "mode":
            if mode and mode in e.modes:
                return True, f"mode:{mode}"
            return False, f"mode:{mode or 'inconnu'}"
        if e.regle == "agents":
            if str(person_id) not in e.agents:
                return False, "non_designe"
            # `modes` était PARSÉ, validé, puis ignoré par cette branche : un champ accepté et
            # sans effet est pire qu'un champ refusé, car rien ne le signale. Déclaré, il
            # restreint désormais l'agent désigné aux trajets faits dans ces modes.
            # Le cas qui l'exige : un incident de VOITURE posé sur un agent multimodal. Sans
            # cette restriction, il lisait « the engine made a grinding noise » au retour d'un
            # trajet en bus, et sa mémoire enregistrait une histoire impossible — exactement le
            # bruit que le dispositif sert à écarter.
            if e.modes and (not mode or mode not in e.modes):
                return False, f"designe:mode:{mode or 'inconnu'}"
            return True, "designe"
        # tirage : déterministe, stable d'un run à l'autre et indépendant de l'ordre d'arrivée
        # des observations. Un tirage qui dépendrait de l'ordre ferait de deux rejeux du même
        # scénario deux expériences différentes.
        graine = f"{e.graine}:{self.choc.choc_id}:{person_id}"
        tire = int(hashlib.sha256(graine.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        if tire < e.part:
            return True, f"tirage:{e.part:.2f}"
        return False, "tirage:epargne"

    def applique(
        self, person_id: str, mode: str | None, timestamp: int
    ) -> ChocApplique | None:
        """Ce que cet agent subit à cette arrivée, ou `None` s'il ne subit rien.

        Rend `None` dans trois cas parfaitement distincts, et les compte séparément : la journée
        n'est pas une journée de choc, l'agent n'est pas exposé, ou le profil du jour ne fait
        rien subir. Le deuxième cas est le TÉMOIN INTERNE du run et il doit se lire.
        """
        jour = self.jour_du_run(timestamp)
        if jour != self._compteurs.jour_run:
            self._basculer_de_journee(jour)
        profil = self.choc.jours.get(jour)
        if profil is None:
            return None
        expose, raison = self._expose(str(person_id), mode)
        if not expose:
            self._compteurs.epargnes += 1
            return None
        if self.choc.cadence == "jour" and str(person_id) in self._touches_du_jour:
            # Ni exposé, ni épargné : l'agent EST exposé, il a déjà subi le choc aujourd'hui.
            # Confondre ce cas avec un épargné ferait passer un choc appliqué une fois pour un
            # choc qui rate trois trajets sur quatre.
            self._compteurs.deja_touches += 1
            return None
        self._touches_du_jour.add(str(person_id))
        self._compteurs.exposes += 1
        self._compteurs.retard_injecte_s += profil.retard_s
        self._exposes_vus.add(str(person_id))
        return ChocApplique(
            choc_id=self.choc.choc_id,
            jour_run=jour,
            jour_relatif=jour - self.choc.premier_jour,
            retard_injecte_s=profil.retard_s,
            vecu=profil.vecu,
            incident_reseau=profil.incident_reseau,
            correspondance_ratee=profil.correspondance_ratee,
            raison=raison,
        )

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
        actif = c.jour_run in self.choc.jours
        deja = f", {c.deja_touches} déjà touché(s) ce jour" if c.deja_touches else ""
        logger.info(
            f"[chocs] jour {c.jour_run} du run (relatif {c.jour_run - self.choc.premier_jour:+d}) "
            f"— {'JOUR DE CHOC' if actif else 'nominal'} : {c.exposes} exposé(s), "
            f"{c.epargnes} épargné(s){deja}, {c.retard_injecte_s // 60} min de retard injecté au "
            f"total (cadence « {self.choc.cadence} »)"
        )
        if actif and c.exposes == 0:
            # Une journée de choc qui ne touche personne est un protocole qui n'a pas eu lieu.
            # Le run du 19 septembre en a eu une — second choc restreint aux trajets en voiture,
            # sur un agent qui ne conduisait plus — dite en INFO, donc lue par personne, et le
            # rapport a continué d'annoncer deux jours de choc.
            logger.error(
                f"[ALARME] [chocs] jour {c.jour_run} du run déclaré JOUR DE CHOC et clos avec "
                f"0 exposé sur {c.epargnes} arrivée(s) éligible(s) examinée(s) : le choc « "
                f"{self.choc.choc_id} » n'a PAS eu lieu ce jour-là. Ne pas le compter comme "
                f"une journée de choc dans l'analyse."
            )

    def tracer(self, applique: ChocApplique, person_id: str, timestamp: int,
               gravite: float, detail: Any) -> None:
        """Une ligne par application dans `chocs.jsonl`. Jamais d'exception vers l'appelant."""
        if not self._journal:
            return
        try:
            ligne = {
                "person_id": str(person_id),
                "timestamp": int(timestamp),
                "horodatage_simule": wall_clock(int(timestamp)).isoformat(),
                "choc_id": applique.choc_id,
                "jour_run": applique.jour_run,
                "jour_relatif": applique.jour_relatif,
                "raison_exposition": applique.raison,
                "retard_injecte_s": applique.retard_injecte_s,
                "incident_reseau": applique.incident_reseau,
                "correspondance_ratee": applique.correspondance_ratee,
                "vecu": applique.vecu,
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
            }
            self._journal.parent.mkdir(parents=True, exist_ok=True)
            with self._journal.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        except Exception as err:  # noqa: BLE001 — une trace ne fait jamais tomber un run
            logger.warning(f"[chocs] trace non écrite ({err})")


# ── Registre du processus ───────────────────────────────────────────────────────────────────
_registre: RegistreChocs | None = None
_initialise = False


def registre() -> RegistreChocs | None:
    return _registre


def incident_reseau_a_une_source() -> bool:
    """Vrai dès qu'un choc chargé porte la composante `incident_reseau`.

    C'est ce que `llm/gravite.py` consulte pour cesser de la déclarer inactive. Sans choc, elle
    reste déclarée inactive : une composante sans source doit continuer de le dire, sans quoi
    zéro se confondrait avec « trajet parfait ».
    """
    if _registre is None:
        return False
    return any(j.incident_reseau for j in _registre.choc.jours.values())


def initialiser(workdir: Path | None = None) -> RegistreChocs | None:
    """Charge le choc déclaré, s'il y en a un. Sans fichier, RIEN ne change.

    Le refus est FRANC : une déclaration invalide arrête le chargement au lieu de laisser courir
    un run de soixante jours qui ne fera rien et dont personne ne saura pourquoi.
    """
    global _registre, _initialise
    if _initialise:
        return _registre
    _initialise = True
    chemin = getattr(settings.chocs, "fichier", None)
    if not getattr(settings.chocs, "enabled", False) or not chemin:
        logger.info("[chocs] aucun choc déclaré — le run se comporte comme sans ce mécanisme.")
        return None
    choc = charger(chemin)
    journal = None
    if workdir is not None:
        journal = Path(workdir) / "chocs.jsonl"
        try:
            Path(workdir).mkdir(parents=True, exist_ok=True)
            (Path(workdir) / "choc.yaml").write_bytes(Path(chemin).read_bytes())
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[chocs] déclaration non archivée dans le run ({err})")
    _registre = RegistreChocs(choc, journal=journal)
    jours = ", ".join(
        f"j{j.jour}:+{j.retard_min}min" for j in sorted(choc.jours.values(), key=lambda x: x.jour)
    )
    logger.info(
        f"[chocs] « {choc.libelle} » ({choc.choc_id}) chargé — exposition "
        f"{choc.exposition.regle}"
        + (f" {sorted(choc.exposition.modes)}" if choc.exposition.modes else "")
        + f", jours {choc.premier_jour}→{choc.dernier_jour} [{jours}], "
        f"empreinte {choc.empreinte[:12]}, source : {choc.source or 'non déclarée'}"
    )
    if getattr(settings.cache, "enabled", False):
        logger.error(
            "[ALARME] un choc est déclaré ALORS QUE le cache de décisions est actif : la clé du "
            "cache ne porte aucune durée, une décision prise avant le choc peut être resservie "
            "pendant. Coupez le cache (`make run CACHE=0`) pour toute campagne à choc."
        )
    return _registre


def reinitialiser() -> None:
    """Oublie le choc. Réservé aux tests et à la fin d'un run."""
    global _registre, _initialise
    if _registre is not None:
        _registre.journaliser_compteurs()
    _registre = None
    _initialise = False
