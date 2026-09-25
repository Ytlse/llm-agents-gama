"""Ce qu'un événement déclare, et ce qu'on lui refuse — ticket 100, lot 1.

UN SEUL CANAL, DEUX PRISES
--------------------------
Un événement, c'est **un texte** posé dans la mémoire d'agents désignés à des jours désignés,
avec **au plus un fait mesuré**. Le reste de la mécanique est celle de la mémoire, inchangée :
gravité, force, durée de service, consolidation, croyance, contradiction.

Ce que le canal dit, c'est d'où vient le texte — `vecu` (l'agent l'a subi) ou `lu` (il l'a lu).
Ce que le moment dit, c'est quand il entre — `arrivee` (après la décision, l'agent a choisi en
voyant l'offre nominale puis encaisse) ou `reveil` (avant la première décision, il sait avant de
choisir). Les deux couples qui comptent sont `vecu`/`arrivee`, le choc du ticket 079, et
`lu`/`reveil`, l'article du ticket 059.

CE QUE LE LOT 1 LIVRE, ET CE QU'IL REFUSE EN LE NOMMANT
-------------------------------------------------------
Le lot 1 est une MIGRATION : il ne livre aucune fonction nouvelle. Il déplace le ticket 079 dans
ce paquet, sans changer un seul de ses comportements, et le prouve par un rejeu à l'identique.
Tout ce qui appartient aux lots suivants — canal `lu`, prise `reveil`, règle `foyers`, texte cité,
fenêtre tirée, jugement à l'injection — est donc **refusé**, avec un message qui nomme le lot où
la chose arrive. Un champ accepté et sans effet est pire qu'un champ refusé : rien ne le signale.

LA RÈGLE QUI NE SE NÉGOCIE PAS, REPRISE DU 079
-----------------------------------------------
Le retard **injecté** et le retard **mesuré** ne se confondent jamais. Deux champs distincts,
partout où ils passent. Sans cette séparation, aucune trace ne permettrait plus de dire ce que la
simulation a produit et ce qu'on lui a fait dire.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from llm.evenements.calendrier import jour_tire
from llm.evenements.exposition import REGLES_EXPOSITION, REGLES_LIVREES
from llm.evenements.gardes import verifier_empreinte, verifier_texte

# D'où vient le texte.
CANAUX: tuple[str, ...] = ("vecu", "lu")
CANAUX_LIVRES: tuple[str, ...] = ("vecu", "lu")

# Quand il entre dans la mémoire, par rapport à la décision de l'agent.
MOMENTS: tuple[str, ...] = ("arrivee", "reveil")
MOMENTS_LIVRES: tuple[str, ...] = ("arrivee", "reveil")

# L'agent juge-t-il ce qu'il vient de vivre ou de lire ? `aucun` est l'ABLATION DÉCLARÉE du
# ticket 100 (Q4) : elle mesure ce que le jugement ajoute, et c'est sous elle que tourne le test
# en or de la migration. `a_l_injection` arrive au lot 3.
JUGEMENTS: tuple[str, ...] = ("aucun", "a_l_injection")
JUGEMENTS_LIVRES: tuple[str, ...] = ("aucun", "a_l_injection")

# Cadence d'application, par agent et par journée. `trajet` = chaque arrivée éligible subit
# l'événement (un bouchon dure toute la journée) ; `jour` = seule la PREMIÈRE arrivée éligible de
# la journée le subit (une panne réparée ne se reproduit pas à l'identique trois heures plus
# tard). Le run du 19 septembre a appliqué quatre fois le même dépannage de trente minutes dans
# la même journée, là où le protocole en comptait un : l'intensité réelle valait quatre fois
# l'intensité annoncée, et rien ne le disait.
CADENCES: tuple[str, ...] = ("trajet", "jour")
CADENCE_PAR_DEFAUT = "trajet"

# Ticket 111 — comment le lecteur transmet à son foyer. Un seul mode livré : un message par
# membre, écrit par le lecteur avec ses mots, et pour un mineur la décision des parents.
RELAIS_MODES: tuple[str, ...] = ("par_destinataire",)


class RefusDEvenement(ValueError):
    """Déclaration invalide. Refuser au chargement vaut mieux qu'un événement fantôme au run."""


@dataclass(frozen=True)
class EffetPhysique:
    """Ce que le monde fait subir, ce jour-là, à l'agent exposé.

    `None` à la place de cet objet signifie que le monde ne bouge pas — c'est le cas d'un
    article lu. Ce n'est PAS la même chose qu'un effet à zéro, qui dit qu'on a mesuré et trouvé
    zéro. La distinction porte toute la différence entre les deux régimes, et elle se perd si on
    la range dans un entier.
    """

    retard_min: int = 0
    incident_reseau: bool = True
    correspondance_ratee: bool = False

    @property
    def retard_s(self) -> int:
        return int(self.retard_min) * 60


@dataclass(frozen=True)
class JourDEvenement:
    """Ce que l'événement dépose un jour donné.

    Le profil est déclaré JOUR PAR JOUR et non par une durée plus une intensité : un bouchon
    n'est pas le même le premier et le troisième jour, et l'agent doit pouvoir le dire dans ses
    mots. C'est aussi ce qui permet une décrue — 60, 40, 25 minutes — que rien d'autre ne saurait
    produire.
    """

    jour: int  # rang dans le run, 1 = premier jour simulé
    texte: str
    effet: EffetPhysique | None = None

    # ── Compatibilité 079, le temps d'une version ────────────────────────────────────────
    # Ces quatre propriétés existent pour que `llm/chocs.py` reste un adaptateur MINCE et que
    # les 36 tests du ticket 079 tournent sans que leur attendu bouge d'un caractère. Elles
    # partent avec `chocs.py`, au lot 6.
    @property
    def vecu(self) -> str:
        return self.texte

    @property
    def retard_min(self) -> int:
        return self.effet.retard_min if self.effet else 0

    @property
    def retard_s(self) -> int:
        return self.effet.retard_s if self.effet else 0

    @property
    def incident_reseau(self) -> bool:
        return bool(self.effet.incident_reseau) if self.effet else False

    @property
    def correspondance_ratee(self) -> bool:
        return bool(self.effet.correspondance_ratee) if self.effet else False


@dataclass(frozen=True)
class TexteCite:
    """Un texte qu'on CITE, avec de quoi prouver qu'on ne l'a pas réécrit.

    C'est la forme du canal `lu` : un article de presse, le même pour tous les lecteurs et tous
    les jours. Elle s'oppose au texte déclaré jour par jour, que nous écrivons nous-mêmes et
    qui n'a aucune source à trahir.

    `mention` est portée À L'INTÉRIEUR de l'entrée, visible du modèle — « Translated from
    French ». Ce n'est pas un commentaire de dépôt : c'est une information que l'agent a, et le
    dispositif n'a pas à la lui cacher (059, lot 1).
    """

    fichier: str
    sha256: str
    contenu: str
    mention: str = ""

    @property
    def servi(self) -> str:
        """Le texte tel qu'il entre en mémoire, mention comprise."""
        if not self.mention:
            return self.contenu
        return f"({self.mention})\n{self.contenu}"


@dataclass(frozen=True)
class Calendrier:
    """Quand l'événement atteint une cible donnée.

    Deux formes. `jours` : les mêmes jours pour tout le monde, c'est le choc du 079. `fenetre`
    plus `graine` : un jour TIRÉ par cible, dans la fenêtre déclarée — deux foyers ne lisent
    pas le même matin, et un effet de calendrier cesse de pouvoir se confondre avec celui de
    l'article.
    """

    jours: tuple[int, ...] = ()
    fenetre: tuple[int, int] | None = None
    graine: int = 59

    def jour_de(self, evenement_id: str, cible: str) -> int:
        """Le jour de CETTE cible. Sans fenêtre, le premier jour déclaré."""
        if self.fenetre is not None:
            return jour_tire(self.graine, evenement_id, str(cible), self.fenetre)
        return min(self.jours)

    @property
    def premier_jour_possible(self) -> int:
        return self.fenetre[0] if self.fenetre is not None else min(self.jours)

    @property
    def dernier_jour_possible(self) -> int:
        return self.fenetre[1] if self.fenetre is not None else max(self.jours)


@dataclass(frozen=True)
class Exposition:
    """Qui est touché.

    `mode` — tout agent dont le trajet qui arrive a été fait dans l'un des modes déclarés.
    `tirage` — une part des agents, tirée de façon DÉTERMINISTE et stable d'un run à l'autre.
    `agents` — des identifiants nommés, pour un incident individuel reproductible.
    `foyers` — un ou plusieurs membres par ménage désigné (lot 2). `lecteurs`, s'il est
    déclaré, nomme qui lit dans chaque foyer à la place du tirage (2026-09-25).
    """

    regle: str
    modes: frozenset[str] = frozenset()
    part: float = 1.0
    graine: int = 79
    agents: frozenset[str] = frozenset()
    foyers: frozenset[str] = frozenset()
    lecteurs_par_foyer: int = 1
    lecteurs: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Service:
    """Combien de temps l'article reste GARANTI au prompt — ticket 111.

    Compté en jours de DÉPLACEMENT : le jour de lecture est le jour 1, et les week-ends ne
    comptent pas quand aucun départ n'a lieu le week-end. Pendant ces jours, la ligne est
    servie quelle que soit la gravité jugée ; après, la mémoire décide seule — c'est ce qu'on
    mesure.
    """

    jours_de_deplacement: int


@dataclass(frozen=True)
class Relais:
    """Ce que le lecteur dit à son foyer — ticket 111."""

    mode: str


@dataclass(frozen=True)
class Evenement:
    evenement_id: str
    libelle: str
    source: str | None
    canal: str
    moment: str
    jugement: str
    exposition: Exposition
    jours: dict[int, JourDEvenement]
    # Forme B (canal `lu`) : un texte unique, cité, et un calendrier tiré par cible. `jours`
    # est alors vide, et c'est `calendrier` qui dit quand chacun le reçoit.
    texte_cite: TexteCite | None = None
    calendrier: Calendrier | None = None
    cadence: str = CADENCE_PAR_DEFAUT
    empreinte: str = ""
    # Format du fichier d'où vient cette déclaration : « 100 », ou « 079 » pour une déclaration
    # de choc lue par le chemin de compatibilité. Journalisé, jamais interprété : il sert à
    # savoir, en relisant un run, sous quelle forme le protocole avait été écrit.
    format_source: str = "100"
    # Ticket 111. `None` = clé absente : comportement d'avant le ticket, journalisé au
    # chargement (un fichier muet ne doit pas changer de comportement en silence).
    service: Service | None = None
    relais: Relais | None = None

    @property
    def premier_jour(self) -> int:
        if self.calendrier is not None:
            return self.calendrier.premier_jour_possible
        return min(self.jours)

    @property
    def dernier_jour(self) -> int:
        if self.calendrier is not None:
            return self.calendrier.dernier_jour_possible
        return max(self.jours)

    @property
    def texte_unique(self) -> bool:
        """Un seul texte pour tous et tous les jours (canal `lu`), ou un texte par jour ?"""
        return self.texte_cite is not None

    @property
    def choc_id(self) -> str:
        """Compatibilité 079 — part au lot 6 avec `llm/chocs.py`."""
        return self.evenement_id


@dataclass(frozen=True)
class EvenementApplique:
    """Ce qu'un agent subit ou lit réellement, à une injection donnée."""

    evenement_id: str
    canal: str
    moment: str
    jour_run: int
    jour_relatif: int
    retard_injecte_s: int
    texte: str
    incident_reseau: bool
    correspondance_ratee: bool
    raison: str

    @property
    def choc_id(self) -> str:
        """Compatibilité 079 — part au lot 6."""
        return self.evenement_id

    @property
    def vecu(self) -> str:
        """Compatibilité 079 — part au lot 6."""
        return self.texte


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


def _lire_exposition(brut: dict, evenement_id: str) -> Exposition:
    regle = str(brut.get("regle") or "").strip()
    if regle not in REGLES_EXPOSITION:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : règle d'exposition « {regle} » inconnue — "
            f"attendu l'une de {REGLES_EXPOSITION}"
        )
    if regle not in REGLES_LIVREES:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : la règle d'exposition « {regle} » est déclarée "
            f"mais n'est pas encore livrée — elle arrive au lot 2 du ticket 100, avec "
            f"`Person.household_id`. Utilisez `agents` en attendant, ou attendez le lot"
        )

    modes = frozenset(str(m).strip() for m in (brut.get("modes") or []) if str(m).strip())
    admis = _modes_admis()
    inconnus = modes - admis
    if inconnus:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : mode(s) {sorted(inconnus)} hors de la hiérarchie "
            f"du dépôt — attendu parmi {sorted(admis)}"
        )
    if regle == "mode" and not modes:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : règle `mode` sans aucun mode déclaré"
        )

    part = float(brut.get("part", 1.0))
    if regle == "tirage" and not (0.0 < part <= 1.0):
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `part` = {part} hors de ]0, 1] — un tirage qui ne "
            f"touche personne ou qui touche plus que tout le monde n'a pas de sens"
        )

    agents = frozenset(str(a).strip() for a in (brut.get("agents") or []) if str(a).strip())
    if regle == "agents" and not agents:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : règle `agents` sans aucun identifiant"
        )

    foyers = frozenset(str(f).strip() for f in (brut.get("foyers") or []) if str(f).strip())

    # Lecteurs DÉSIGNÉS (2026-09-25) : quand l'article vise un mode, le lecteur doit en être
    # usager, et un tirage parmi les adultes peut tomber sur celui qui ne le prend jamais.
    lecteurs = frozenset(str(a).strip() for a in (brut.get("lecteurs") or []) if str(a).strip())
    lecteurs_par_foyer = int(brut.get("lecteurs_par_foyer", 1))
    if lecteurs and regle != "foyers":
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `lecteurs` déclaré avec la règle `{regle}` — il ne "
            f"désigne quelqu'un que sous la règle `foyers`, et resterait sans effet"
        )
    if lecteurs and lecteurs_par_foyer != 1:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `lecteurs` et `lecteurs_par_foyer` = "
            f"{lecteurs_par_foyer} disent tous deux combien lisent — désigner les lecteurs suffit"
        )

    return Exposition(
        regle=regle,
        modes=modes,
        part=part,
        graine=int(brut.get("graine", 79)),
        agents=agents,
        foyers=foyers,
        lecteurs_par_foyer=lecteurs_par_foyer,
        lecteurs=lecteurs,
    )


def _lire_cadence(brut: Any, evenement_id: str) -> str:
    cadence_brute = str(brut or "").strip().lower()
    if cadence_brute and cadence_brute not in CADENCES:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `cadence` « {cadence_brute} » inconnue — "
            f"attendu {' ou '.join(CADENCES)}. Une cadence mal orthographiée changerait "
            f"silencieusement l'intensité de l'événement."
        )
    cadence = cadence_brute or CADENCE_PAR_DEFAUT
    logger.info(
        f"[evenements] « {evenement_id} » : cadence « {cadence} »"
        + ("" if cadence_brute else f" (non déclarée, valeur par défaut {CADENCE_PAR_DEFAUT})")
    )
    return cadence


def _lire_jours(brut: list, evenement_id: str, canal: str) -> dict[int, JourDEvenement]:
    if not brut:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : aucune journée déclarée dans `jours`"
        )
    jours: dict[int, JourDEvenement] = {}
    for entree in brut:
        jour = int(entree.get("jour", 0))
        if jour < 1:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `jour` = {jour} — le premier jour du run "
                f"porte le n° 1"
            )
        if jour in jours:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : deux entrées pour le jour {jour} — une "
                f"journée porte un profil et un seul"
            )
        # `texte` est le nom du ticket 100, `vecu` celui du 079. Les deux sont lus ; un fichier
        # qui porte les deux est refusé, parce qu'on ne saurait pas lequel a servi.
        if "texte" in entree and "vecu" in entree:
            raise RefusDEvenement(
                f"événement « {evenement_id} », jour {jour} : `texte` ET `vecu` déclarés — "
                f"gardez `texte` (ticket 100) ou `vecu` (ticket 079), pas les deux"
            )
        texte = str(entree.get("texte", entree.get("vecu", "")) or "").strip()
        verifier_texte(texte, evenement_id, jour, RefusDEvenement)

        retard_min = int(entree.get("retard_min", 0))
        if retard_min < 0:
            raise RefusDEvenement(
                f"événement « {evenement_id} », jour {jour} : `retard_min` = {retard_min} — un "
                f"retard négatif serait une avance, ce que la gravité ne sait pas représenter"
            )
        # Un `canal: lu` ne touche ni OTP, ni GTFS, ni OSMnx, et ne fait subir aucun retard :
        # le monde ne change pas parce qu'on a lu le journal. L'effet physique est donc ABSENT,
        # et non nul — la distinction est celle du § 9 du ticket.
        effet = None
        if canal == "vecu":
            effet = EffetPhysique(
                retard_min=retard_min,
                incident_reseau=bool(entree.get("incident_reseau", True)),
                correspondance_ratee=bool(entree.get("correspondance_ratee", False)),
            )
        elif retard_min or entree.get("incident_reseau") or entree.get("correspondance_ratee"):
            raise RefusDEvenement(
                f"événement « {evenement_id} », jour {jour} : effet physique déclaré sur un "
                f"`canal: lu`. Lire le journal ne retarde personne — le monde ne change pas "
                f"avant la décision (§ 9 du ticket 100)"
            )
        jours[jour] = JourDEvenement(jour=jour, texte=texte, effet=effet)
    return jours


def _lire_texte_cite(brut: dict, evenement_id: str) -> TexteCite:
    """Le texte cité, lu UNE FOIS au chargement et vérifié deux fois."""
    chemin = str(brut.get("fichier") or "").strip()
    if not chemin:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `texte.fichier` absent. Un canal `lu` cite un "
            f"texte du dépôt, il ne le porte pas dans sa déclaration"
        )
    contenu = verifier_empreinte(
        chemin, str(brut.get("sha256") or ""), evenement_id, RefusDEvenement
    )
    # Exemptions déclarées, sur le modèle des mots interdits de la paraphrase (059, lot 1) :
    # un marqueur ne s'exempte que s'il FIGURE dans le texte, et jamais sans motif écrit.
    # Sans la première garde, on exempterait par précaution des marqueurs absents et la liste
    # se viderait de son sens sans que personne ne le voie.
    exemptes: dict[str, str] = {}
    for entree in brut.get("marqueurs_exemptes") or []:
        marqueur = str(entree.get("marqueur") or "").strip().lower()
        motif = str(entree.get("motif") or "").strip()
        if not marqueur:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : une exemption sans marqueur"
            )
        if not motif:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : le marqueur « {marqueur} » est exempté sans "
                f"motif. Une exemption qui ne dit pas pourquoi ne se relit pas"
            )
        if marqueur not in contenu.lower():
            raise RefusDEvenement(
                f"événement « {evenement_id} » : le marqueur « {marqueur} » est exempté mais "
                f"NE FIGURE PAS dans le texte cité. On n'exempte pas ce qui n'est pas là — "
                f"une liste d'exemptions préventives se viderait de son sens sans que rien ne "
                f"le signale"
            )
        exemptes[marqueur] = motif

    # Les gardes de contenu du 079 s'appliquent AUSSI au texte cité. Un article qui dirait au
    # lecteur quel mode prendre fabriquerait le résultat qu'on prétend mesurer, exactement
    # comme un vécu qui conclut à la place de l'agent. Une seule liste pour les deux canaux.
    verifier_texte(
        contenu, evenement_id, 0, RefusDEvenement,
        exemptes=exemptes,
        attendre_premiere_personne=False,
    )
    return TexteCite(
        fichier=chemin,
        sha256=str(brut.get("sha256") or "").strip().lower(),
        contenu=contenu.strip(),
        mention=str(brut.get("mention") or "").strip(),
    )


def _lire_calendrier(brut: dict, evenement_id: str) -> Calendrier:
    jours = tuple(int(j) for j in (brut.get("jours") or []))
    fenetre_brute = brut.get("fenetre_jours")
    if jours and fenetre_brute:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `calendrier.jours` ET `calendrier.fenetre_jours` "
            f"déclarés — un jour fixe et un jour tiré sont deux protocoles, pas deux façons "
            f"d'écrire le même"
        )
    if fenetre_brute:
        if len(fenetre_brute) != 2:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `fenetre_jours` attend deux bornes, "
                f"« {fenetre_brute} » en porte {len(fenetre_brute)}"
            )
        debut, fin = int(fenetre_brute[0]), int(fenetre_brute[1])
        if debut < 1:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `fenetre_jours` commence au jour {debut} — le "
                f"premier jour du run porte le n° 1"
            )
        if fin < debut:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `fenetre_jours` = [{debut}, {fin}] est vide. "
                f"Une fenêtre vide ne tire aucun jour, et l'événement n'aurait lieu pour "
                f"personne sans qu'aucun symptôme n'apparaisse"
            )
        return Calendrier(fenetre=(debut, fin), graine=int(brut.get("graine", 59)))
    if not jours:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `calendrier` sans `jours` ni `fenetre_jours`"
        )
    if any(j < 1 for j in jours):
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `calendrier.jours` porte un jour < 1 — le premier "
            f"jour du run porte le n° 1"
        )
    return Calendrier(jours=jours, graine=int(brut.get("graine", 59)))


def _lire_service(brut: Any, evenement_id: str) -> Service:
    if not isinstance(brut, dict):
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `service` attend un bloc portant "
            f"`jours_de_deplacement`, pas « {brut} »"
        )
    valeur = brut.get("jours_de_deplacement")
    # `bool` est un `int` en Python : `True` passerait pour un jour. Refusé comme le reste.
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 1:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `service.jours_de_deplacement` = {valeur!r} — "
            f"attendu un entier ≥ 1. Zéro jour de service reviendrait à ne rien garantir en "
            f"ayant l'air de le faire"
        )
    return Service(jours_de_deplacement=valeur)


def _lire_relais(brut: Any, evenement_id: str) -> Relais:
    mode = str((brut or {}).get("mode") or "").strip() if isinstance(brut, dict) else ""
    if mode not in RELAIS_MODES:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `relais.mode` « {mode} » inconnu — attendu "
            f"{' ou '.join(RELAIS_MODES)}"
        )
    return Relais(mode=mode)


def _refuser_les_champs_des_lots_suivants(data: dict, evenement_id: str) -> None:
    """Un champ du lot 2 ou du lot 3 dans un dépôt au lot 1 : refusé, et le lot est nommé.

    L'accepter en l'ignorant serait la pire des trois options : la déclaration aurait l'air de
    dire quelque chose que le code ne fait pas, et un run partirait sur un protocole qui n'est
    pas celui qu'on a écrit.
    """
    if "effet_physique" in data:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `effet_physique` en tête n'est pas lu — l'effet se "
            f"déclare jour par jour, sous `jours`, parce qu'il change d'un jour à l'autre"
        )
    if "gravite" in data:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : un champ `gravite` est posé à la main. La gravité "
            f"se CALCULE — sur ce que la simulation a mesuré, et sur ce que l'agent en juge. "
            f"La poser ici rétablirait le paramètre que la décision D4 supprime, et reviendrait "
            f"à mesurer sa propre consigne"
        )


def _depuis_le_format_079(data: dict, chemin: Path) -> dict:
    """Une déclaration de choc du ticket 079, relue comme un événement.

    Le chemin existe pour une raison précise : le test en or du lot 1 doit pouvoir rejouer LE
    FICHIER D'ORIGINE, pas sa traduction. Une migration qui ne se vérifie que sur des fichiers
    réécrits ne vérifie que la réécriture.
    """
    logger.warning(
        f"[evenements] {chemin.name} est au format du ticket 079 (clé `choc:`). Il est lu et "
        f"converti — canal `vecu`, moment `arrivee`, jugement `aucun`. Ce chemin de "
        f"compatibilité part avec `llm/chocs.py`, au lot 6 du ticket 100 : migrez le fichier "
        f"vers `config/evenements/` quand vous y toucherez."
    )
    converti = dict(data)
    converti["evenement"] = data.get("choc")
    converti.pop("choc", None)
    converti.setdefault("canal", "vecu")
    converti.setdefault("moment", "arrivee")
    converti.setdefault("jugement", "aucun")
    return converti


def charger(chemin: str | Path) -> Evenement:
    """Lit et VÉRIFIE une déclaration d'événement. Lève `RefusDEvenement` au moindre doute.

    Accepte les deux formats : `evenement:` (ticket 100) et `choc:` (ticket 079, converti à la
    volée avec un avertissement nommant le fichier).
    """
    p = Path(chemin)
    if not p.is_file():
        raise RefusDEvenement(f"fichier d'événement introuvable : {p}")
    brut = p.read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()
    data: dict[str, Any] = yaml.safe_load(brut.decode("utf-8")) or {}

    format_source = "100"
    if "choc" in data and "evenement" not in data:
        data = _depuis_le_format_079(data, p)
        format_source = "079"

    evenement_id = str(data.get("evenement") or "").strip()
    if not evenement_id:
        raise RefusDEvenement(
            f"{p} : champ `evenement` (identifiant) absent ou vide — une déclaration du ticket "
            f"079 porte `choc:` à la place"
        )

    _refuser_les_champs_des_lots_suivants(data, evenement_id)

    canal = str(data.get("canal") or "vecu").strip().lower()
    if canal not in CANAUX:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `canal` « {canal} » inconnu — attendu "
            f"{' ou '.join(CANAUX)}"
        )
    moment = str(data.get("moment") or "arrivee").strip().lower()
    if moment not in MOMENTS:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `moment` « {moment} » inconnu — attendu "
            f"{' ou '.join(MOMENTS)}"
        )
    jugement = str(data.get("jugement") or "aucun").strip().lower()
    if jugement not in JUGEMENTS:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : `jugement` « {jugement} » inconnu — attendu "
            f"{' ou '.join(JUGEMENTS)}"
        )
    exposition = _lire_exposition(data.get("exposition") or {}, evenement_id)
    cadence = _lire_cadence(data.get("cadence"), evenement_id)

    # ── Les deux formes de texte, et ce qui les sépare ──────────────────────────────────
    texte_cite = None
    calendrier = None
    jours: dict[int, JourDEvenement] = {}
    if "texte" in data:
        texte_cite = _lire_texte_cite(data.get("texte") or {}, evenement_id)
        if data.get("jours"):
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `texte` (un texte cité) ET `jours` (un texte "
                f"par jour) déclarés. Un article est le même tous les matins ; un vécu change "
                f"d'un jour à l'autre. Choisissez la forme du régime que vous jouez"
            )
        calendrier = _lire_calendrier(data.get("calendrier") or {}, evenement_id)
    else:
        if canal == "lu":
            raise RefusDEvenement(
                f"événement « {evenement_id} » : un `canal: lu` cite un texte — déclarez un "
                f"bloc `texte` avec son fichier et son empreinte. Un article écrit par nous "
                f"dans la déclaration ne serait pas de la presse locale, ce serait nous"
            )
        jours = _lire_jours(data.get("jours") or [], evenement_id, canal)
        calendrier = Calendrier(jours=tuple(sorted(jours)))

    # ── Refus croisés, et leurs raisons ─────────────────────────────────────────────────
    if moment == "reveil" and any(j.effet is not None for j in jours.values()):
        raise RefusDEvenement(
            f"événement « {evenement_id} » : effet physique déclaré sur une injection au "
            f"RÉVEIL. Le monde ne change pas avant la décision : ce que l'agent sait en "
            f"choisissant ne lui fait subir aucun retard, sans quoi le jour de l'événement "
            f"mesurerait à la fois une anticipation et une contrainte (§ 9 du ticket 100)"
        )
    if canal == "lu" and moment != "reveil":
        raise RefusDEvenement(
            f"événement « {evenement_id} » : un `canal: lu` posé au moment « {moment} ». Un "
            f"article se lit AVANT de décider — c'est ce qui le sépare du choc, et tout le "
            f"contraste que le chapitre 7 mesure"
        )
    if exposition.regle == "foyers" and not exposition.foyers:
        raise RefusDEvenement(
            f"événement « {evenement_id} » : règle `foyers` sans aucun identifiant de ménage"
        )
    if exposition.regle == "foyers" and moment != "reveil":
        raise RefusDEvenement(
            f"événement « {evenement_id} » : la règle `foyers` tire des lecteurs, et un "
            f"lecteur lit au réveil. Sur une arrivée, utilisez `agents` ou `mode`"
        )

    # ── Ticket 111 : service garanti et relais au foyer ─────────────────────────────────
    service = None
    relais = None
    if "service" in data:
        if moment != "reveil":
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `service` sur un événement du moment "
                f"« {moment} ». Le service garanti porte sur ce qui est su AVANT de décider ; "
                f"un choc s'applique après la décision, et c'est voulu"
            )
        service = _lire_service(data.get("service"), evenement_id)
    if "relais" in data:
        if canal != "lu":
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `relais` sur un `canal: {canal}`. Seul un "
                f"article LU se raconte au foyer le matin même"
            )
        if exposition.regle != "foyers":
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `relais` sans la règle d'exposition "
                f"`foyers`. Le relais va du lecteur aux autres membres de SON foyer : sans "
                f"foyer tiré, il n'a pas de destinataire"
            )
        if service is None:
            raise RefusDEvenement(
                f"événement « {evenement_id} » : `relais` sans `service`. Le message reçu est "
                f"servi pendant les jours de service du destinataire ; sans leur nombre, il "
                f"n'aurait aucune présence garantie, et rien ne le dirait"
            )
        relais = _lire_relais(data.get("relais"), evenement_id)
    if moment == "reveil":
        absentes = [c for c, v in (("service", service), ("relais", relais)) if v is None]
        if absentes:
            logger.info(
                f"[evenements] « {evenement_id} » : clé(s) {absentes} absente(s) — "
                f"comportement d'avant le ticket 111 : "
                + ("aucune présence garantie au prompt, la gravité et le rappel décident seuls"
                   if service is None else f"service {service.jours_de_deplacement} j")
                + ("" if relais is not None else ", aucun relais au foyer")
                + "."
            )
        else:
            logger.info(
                f"[evenements] « {evenement_id} » : servi {service.jours_de_deplacement} jour(s) "
                f"de déplacement au lecteur et aux informés, relais « {relais.mode} »"
            )

    # ── Jugement : accepté à la lecture, refusé à l'armement d'un run (lot 3) ───────────
    if canal == "lu" and jugement == "aucun":
        # Chiffré, pas argumenté : un article ne fait subir aucun retard, sa gravité
        # déterministe vaut 0,00, et `force_initiale(0,00)` vaut 2,8 jours. L'entrée sort du
        # bloc « Ce qui a changé récemment » le surlendemain, et son silence passerait pour
        # une absence d'effet — alors qu'il ne mesure que la durée de vie qu'on lui a donnée.
        logger.error(
            f"[ALARME] [evenements] « {evenement_id} » : canal `lu` SANS jugement. L'article "
            f"entrera en mémoire avec une gravité de 0,00, donc une durée de vie de 2,8 jours "
            f"— il aura disparu du prompt le surlendemain, et aucune mesure longitudinale "
            f"n'est possible. Cette combinaison sert à exercer l'injection, pas à jouer une "
            f"campagne. Pour une campagne : `jugement: a_l_injection` (lot 3)."
        )

    return Evenement(
        evenement_id=evenement_id,
        libelle=str(data.get("libelle") or evenement_id),
        source=data.get("source"),
        canal=canal,
        moment=moment,
        jugement=jugement,
        exposition=exposition,
        jours=jours,
        texte_cite=texte_cite,
        calendrier=calendrier,
        cadence=cadence,
        empreinte=empreinte,
        format_source=format_source,
        service=service,
        relais=relais,
    )
