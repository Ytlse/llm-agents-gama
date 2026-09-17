"""Accidents tirés au sort sur les axes — l'existence, pas encore la conséquence.

Ticket 070, première tranche. Ce module tire des accidents, les pose sur une arête du graphe
routier et les journalise. **Il ne modifie aucune durée d'itinéraire.** Le retard subi, les
gardes de cache et le souvenir de l'agent viennent dans une tranche ultérieure.

CE DÉCOUPAGE N'EST PAS UNE FACILITÉ. Tant qu'aucune durée ne change, aucun itinéraire perturbé
ne peut entrer dans le cache d'itinéraires — qui est adressé SANS LA DATE et resservirait
une durée d'accident à tous les mardis 8 h — et aucune décision d'agent ne peut être resservie
à tort par le cache de décisions, dont la clé est construite sur les codes d'options et ignore
les durées. Les deux pièges sont neutralisés par construction, pas par vigilance.

CE QUE LA LOI DE TIRAGE VAUT AUJOURD'HUI. Elle est MESURÉE sur BAAC/ONISR 2019-2024 (3 789
accidents corporels du département 31, 3 414 dans l'emprise du graphe) et conditionne trois
variables : le NOMBRE par le jour de semaine, l'HEURE par la distribution horaire observée, la
CLASSE D'AXE par la distribution en vitesse autorisée — l'arête étant ensuite tirée au prorata
de sa longueur DANS sa classe. Les coefficients vivent dans `config/accidents_baac.yaml`, qui
porte aussi la raison de chaque choix.

⚠ UNE SEULE VARIABLE RESTE NON ÉTABLIE : le facteur météo. Son estimation a été faite et
REJETÉE (les nomenclatures `atm` et celle de la source météo locale ne découpent pas le même
monde), il vaut donc 1. Le fichier de coefficients conserve le calcul rejeté pour que le refus
soit vérifiable.

⚠ UN COMPTAGE À ZÉRO N'EST PAS UNE PANNE, et l'inverse est vrai aussi : à 1,56 accident par
jour sur l'emprise simulée, beaucoup de journées simulées n'en verront aucun. C'est le
comportement correct. C'est pourquoi le journal dit toujours combien ont été tirés, y compris
zéro — sans ce compteur, « aucun accident » et « le tirage ne tourne pas » se ressemblent trop.
"""

from __future__ import annotations

import pathlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import yaml
from loguru import logger
from settings import settings
from sim_clock import wall_clock

# Coefficients estimés sur BAAC/ONISR. Mesurés, rejouables, et documentés dans le fichier
# lui-même : ce module ne fait que les appliquer.
_LOI_PATH = pathlib.Path(__file__).resolve().parent.parent / "config" / "accidents_baac.yaml"

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

# Un accident est posé sur une arête orientée du graphe `drive`, désignée par ses deux nœuds
# OSM. La clé (u, v) suffit : les arêtes parallèles d'un même couple partagent la voie.
CleArete = tuple[int, int]

# Au-delà, on refuse de tirer : un état du monde qui enfle sans borne est un bug, pas un
# scénario. Le seuil est très au-dessus de tout tirage plausible (1,56/jour mesuré).
MAX_ACCIDENTS_PAR_JOUR = 200


# Classes de vitesse autorisée, bornes identiques à celles de la mesure BAAC. Chaque arête
# du graphe porte une vitesse (OSM `maxspeed`, sinon la table d'osmnx) : aucune table de
# correspondance à inventer entre les deux mondes.
CLASSES_VITESSE = [("<=30", 0, 30), ("31-50", 31, 50), ("51-70", 51, 70),
                   ("71-90", 71, 90), (">90", 91, 999)]


def classe_de_vitesse(vitesse) -> str | None:
    """Classe d'une vitesse autorisée, ou `None` si elle n'est pas exploitable.

    Tolère les formes qu'OSM emploie réellement : liste de valeurs sur une arête fusionnée,
    chaîne « 50 » ou « 50 km/h », entier, absence.
    """
    if isinstance(vitesse, list):
        vitesse = vitesse[0] if vitesse else None
    if isinstance(vitesse, str):
        chiffres = "".join(ch for ch in vitesse if ch.isdigit())
        vitesse = chiffres or None
    if vitesse is None:
        return None
    try:
        v = int(float(vitesse))
    except (TypeError, ValueError):
        return None
    if v <= 0 or v > 200:
        return None
    for nom, bas, haut in CLASSES_VITESSE:
        if bas <= v <= haut:
            return nom
    return None


@dataclass(frozen=True)
class LoiBaac:
    """La loi d'accidentalité mesurée : ce qu'on tire, et avec quelles pondérations.

    Trois variables conditionnent le tirage, et une quatrième est déclarée non établie.
    Le fichier de configuration porte le détail de chaque choix, y compris le rejet motivé
    du facteur météo — il se lit avant de toucher à ces nombres.
    """

    taux_base_par_jour: float
    distribution_horaire: dict[int, float]
    facteur_jour_semaine: dict[str, float]
    distribution_classe_vitesse: dict[str, float]
    facteur_meteo: dict[str, float]
    facteur_meteo_etabli: bool
    millesimes: list

    @classmethod
    def charger(cls, chemin: pathlib.Path | None = None) -> LoiBaac:
        chemin = chemin or _LOI_PATH
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
        loi = cls(
            taux_base_par_jour=float(brut["taux_base_par_jour"]),
            distribution_horaire={int(h): float(v) for h, v in brut["distribution_horaire"].items()},
            facteur_jour_semaine={str(j): float(v) for j, v in brut["facteur_jour_semaine"].items()},
            distribution_classe_vitesse={
                str(c): float(v) for c, v in brut["distribution_classe_vitesse"].items()
            },
            facteur_meteo={str(m): float(v) for m, v in (brut.get("facteur_meteo") or {}).items()},
            facteur_meteo_etabli=bool(brut.get("facteur_meteo_etabli", False)),
            millesimes=list(brut.get("millesimes") or []),
        )
        loi.verifier()
        return loi

    def verifier(self) -> None:
        """Refuse une loi incohérente plutôt que de tirer avec elle.

        Une distribution qui ne somme pas à 1 ou un facteur de moyenne différente de 1
        déplacerait le taux moyen sans que rien ne le dise : le run entier serait faux et
        silencieux.
        """
        for nom, dist in (
            ("distribution_horaire", self.distribution_horaire),
            ("distribution_classe_vitesse", self.distribution_classe_vitesse),
        ):
            somme = sum(dist.values())
            if not 0.99 <= somme <= 1.01:
                raise ValueError(f"{nom} somme à {somme:.4f} au lieu de 1 ({_LOI_PATH})")
        moyenne = sum(self.facteur_jour_semaine.values()) / max(1, len(self.facteur_jour_semaine))
        if not 0.99 <= moyenne <= 1.01:
            raise ValueError(
                f"facteur_jour_semaine a pour moyenne {moyenne:.4f} au lieu de 1 : le taux de "
                f"base ne serait plus le taux moyen ({_LOI_PATH})"
            )
        if len(self.distribution_horaire) != 24:
            raise ValueError(f"distribution_horaire couvre {len(self.distribution_horaire)} h sur 24")


@dataclass(frozen=True)
class Accident:
    """Un accident posé : où, quand il commence, combien de temps il dure."""

    arete: CleArete
    debut_ts: int
    duree_s: int
    classe_vitesse: str = ""

    @property
    def fin_ts(self) -> int:
        return self.debut_ts + self.duree_s

    def actif_a(self, ts: int) -> bool:
        return self.debut_ts <= ts < self.fin_ts

    def __str__(self) -> str:
        debut = datetime.fromtimestamp(self.debut_ts, tz=timezone.utc)
        classe = f" [{self.classe_vitesse} km/h]" if self.classe_vitesse else ""
        return (
            f"arête {self.arete[0]}→{self.arete[1]}{classe} "
            f"à {debut:%Y-%m-%d %H:%M} pour {self.duree_s // 60} min"
        )


@dataclass
class CompteursJournee:
    """Ce qu'une journée simulée a produit. Publié même quand tout vaut zéro."""

    jour: int
    tires: int = 0
    refuses: int = 0
    # Déplacements dont l'itinéraire a traversé une arête accidentée. Publié même à zéro :
    # sans lui, « aucun effet mesuré » et « aucun trajet touché » sont indiscernables, et
    # c'est le motif récurrent du dépôt — l'absence de mesure déguisée en résultat.
    trajets_touches: int = 0


class RegistreAccidents:
    """L'état du monde : quels accidents existent, et quand.

    Un seul registre par run. Le tirage est déterministe à graine fixée : deux exécutions du
    même scénario posent les mêmes accidents aux mêmes endroits — sans quoi l'écart entre deux
    runs serait mis sur le compte des agents.
    """

    def __init__(self, config=None, loi: LoiBaac | None = None) -> None:
        self._config = config if config is not None else settings.accidents
        self._loi = loi if loi is not None else LoiBaac.charger()
        self._accidents: list[Accident] = []
        self._compteurs: list[CompteursJournee] = []
        self._jours_tires: set[int] = set()
        self._alea = random.Random(self._config.graine)
        # Arêtes indexées PAR CLASSE DE VITESSE : (clé, longueur cumulée dans la classe).
        # La classe se tire sur la loi BAAC, l'arête au prorata de sa longueur DANS la classe.
        self._aretes: dict[str, list[tuple[CleArete, float]]] = {}
        self._cles: set[CleArete] = set()
        # (lat, lon) des nœuds, pour résoudre un point en arête lors d'une pose manuelle.
        self._positions: dict[int, tuple[float, float]] | None = None

    # ── Préparation ──────────────────────────────────────────────────────────

    def charger_aretes(self, graphe) -> int:
        """Indexe les arêtes du graphe `drive` par CLASSE DE VITESSE, avec leur longueur.

        Le tirage se fait en deux temps, et l'ordre compte. La CLASSE se tire sur la
        distribution BAAC ; l'ARÊTE se tire ensuite au prorata de sa longueur À L'INTÉRIEUR
        de cette classe. Tirer directement au prorata de la longueur, comme le faisait la
        première tranche, plaçait 58 % des accidents en zone apaisée (≤ 30 km/h), qui porte
        58 % des kilomètres du graphe mais 8 % des accidents réels.
        """
        par_classe: dict[str, list[tuple[CleArete, float]]] = {}
        cumuls: dict[str, float] = {}
        sans_classe = 0
        for u, v, data in graphe.edges(data=True):
            longueur = float(data.get("length") or 0.0)
            if longueur <= 0:
                continue
            classe = classe_de_vitesse(data.get("maxspeed") or data.get("speed_kph"))
            if classe is None:
                sans_classe += 1
                continue
            cumul = cumuls.get(classe, 0.0) + longueur
            cumuls[classe] = cumul
            par_classe.setdefault(classe, []).append(((u, v), cumul))

        self._aretes = par_classe
        self._cles = {cle for aretes in par_classe.values() for cle, _ in aretes}
        # Positions des nœuds : seule la pose manuelle s'en sert, mais elles ne sont
        # disponibles qu'ici, au moment où le graphe est sous la main.
        try:
            self._positions = {
                n: (float(d["y"]), float(d["x"]))
                for n, d in graphe.nodes(data=True)
                if "x" in d and "y" in d
            }
        except (AttributeError, TypeError, KeyError, ValueError):
            self._positions = None

        if not par_classe:
            logger.error(
                "[ALARME] Aucune arête exploitable dans le graphe routier : le tirage "
                "d'accidents ne pourra rien poser. Le régime reste actif mais inerte."
            )
            return 0

        total_km = sum(cumuls.values()) / 1000.0
        detail = ", ".join(f"{c} {cumuls[c] / 1000:.0f} km" for c in sorted(cumuls))
        logger.info(
            f"[accidents] Réseau indexé par classe de vitesse : "
            f"{sum(len(a) for a in par_classe.values())} arêtes, {total_km:.0f} km — {detail}"
        )
        if sans_classe:
            logger.info(f"[accidents] {sans_classe} arête(s) sans vitesse exploitable, écartées")

        # Une classe que la loi fait tirer mais que le réseau ne porte pas donnerait des
        # accidents impossibles à poser. Le dire au chargement, pas au premier échec.
        manquantes = [
            c for c, part in self._loi.distribution_classe_vitesse.items()
            if part > 0 and c not in par_classe
        ]
        if manquantes:
            logger.error(
                f"[ALARME] Classes présentes dans la loi BAAC mais absentes du graphe : "
                f"{manquantes}. Les accidents qui leur seraient destinés seront redirigés "
                f"vers les classes disponibles — la géographie du tirage s'en trouve biaisée."
            )
        return sum(len(a) for a in par_classe.values())

    @property
    def pret(self) -> bool:
        return bool(self._aretes)

    @property
    def loi(self) -> LoiBaac:
        return self._loi

    # ── Tirage ───────────────────────────────────────────────────────────────

    def _tirer_classe(self) -> str | None:
        """Une classe de vitesse, tirée sur la distribution BAAC, restreinte au réseau présent.

        Restreindre plutôt que réessayer : si une classe manque au graphe, sa masse est
        redistribuée sur les autres au prorata, et l'écart a déjà été signalé au chargement.
        """
        disponibles = {c: p for c, p in self._loi.distribution_classe_vitesse.items()
                       if p > 0 and self._aretes.get(c)}
        if not disponibles:
            return None
        total = sum(disponibles.values())
        cible = self._alea.uniform(0.0, total)
        cumul = 0.0
        for classe, part in disponibles.items():
            cumul += part
            if cible <= cumul:
                return classe
        return next(iter(disponibles))

    def _tirer_arete(self, classe: str) -> CleArete:
        """Une arête de cette classe, la probabilité étant proportionnelle à sa longueur."""
        aretes = self._aretes[classe]
        cible = self._alea.uniform(0.0, aretes[-1][1])
        bas, haut = 0, len(aretes) - 1
        while bas < haut:
            milieu = (bas + haut) // 2
            if aretes[milieu][1] < cible:
                bas = milieu + 1
            else:
                haut = milieu
        return aretes[bas][0]

    def _tirer_heure(self) -> int:
        """L'heure du sinistre, sur la distribution horaire mesurée.

        C'est le conditionnement le plus marqué de la loi : 9,77 % des accidents à 17 h
        contre 1,45 % à 3 h. Le tirage uniforme de la première tranche les égalisait.
        """
        cible = self._alea.random()
        cumul = 0.0
        for heure in range(24):
            cumul += self._loi.distribution_horaire.get(heure, 0.0)
            if cible <= cumul:
                return heure
        return 23

    def _taux_du_jour(self, jour_semaine: int, meteo: str | None) -> float:
        """Taux journalier conditionné : base × jour de semaine × météo.

        Le facteur météo vaut 1 tant qu'il n'est pas établi — voir le fichier de
        coefficients, qui porte le calcul rejeté et la raison du rejet.
        """
        taux = self._loi.taux_base_par_jour
        if self._config.taux_journalier is not None:
            # Surcharge explicite de configuration : utile pour rendre le mécanisme
            # observable en développement, jamais pour une mesure.
            taux = float(self._config.taux_journalier)
        taux *= self._loi.facteur_jour_semaine.get(JOURS[jour_semaine], 1.0)
        if meteo and self._loi.facteur_meteo_etabli:
            taux *= self._loi.facteur_meteo.get(meteo, 1.0)
        return taux

    def _tirer_nombre(self, taux: float) -> int:
        """Nombre d'accidents pour une journée, loi de Poisson au taux conditionné.

        Poisson et non « taux arrondi » : à 1,56 accident par jour, un arrondi donnerait
        deux accidents tous les jours, c'est-à-dire un monde plus régulier que le vrai. La
        variance fait partie du phénomène.
        """
        # Tirage de Poisson par la méthode de Knuth — suffisant à ces taux, et il n'ajoute
        # aucune dépendance (random.Random n'expose pas de loi de Poisson).
        seuil = 2.718281828459045 ** (-taux)
        produit, n = self._alea.random(), 0
        while produit > seuil:
            produit *= self._alea.random()
            n += 1
        return n

    def tirer_journee(
        self, jour: int, debut_jour_ts: int, meteo: str | None = None
    ) -> list[Accident]:
        """Tire et pose les accidents d'une journée simulée. Idempotent par journée.

        Le conditionnement est celui de la loi BAAC mesurée : le NOMBRE dépend du jour de
        semaine (et de la météo quand ce facteur sera établi), l'HEURE suit la distribution
        horaire, la CLASSE D'AXE la distribution par vitesse autorisée, et l'ARÊTE se tire au
        prorata de sa longueur dans sa classe.
        """
        if jour in self._jours_tires:
            return []
        self._jours_tires.add(jour)

        jour_semaine = wall_clock(debut_jour_ts).weekday()
        compteurs = CompteursJournee(jour=jour)
        self._compteurs.append(compteurs)

        taux = self._taux_du_jour(jour_semaine, meteo)
        if taux <= 0 or taux > float(self._config.taux_journalier_max):
            logger.error(
                f"[ALARME] Taux d'accidents journalier hors bornes : {taux} "
                f"(attendu dans ]0 ; {self._config.taux_journalier_max}]). Aucun accident "
                f"tiré pour le jour {jour} — vérifiez la loi et `accidents.taux_journalier`."
            )
            return []
        if not self.pret:
            logger.error(
                f"[ALARME] Réseau non indexé : aucun accident tirable pour le jour {jour}. "
                "Le régime est actif mais ne pose rien."
            )
            return []

        nombre = self._tirer_nombre(taux)
        if nombre > MAX_ACCIDENTS_PAR_JOUR:
            logger.error(
                f"[ALARME] Tirage aberrant pour le jour {jour} : {nombre} accidents "
                f"(plafond {MAX_ACCIDENTS_PAR_JOUR}). Tirage ramené au plafond — "
                f"vérifiez la loi ({taux} accident/jour attendu)."
            )
            nombre = MAX_ACCIDENTS_PAR_JOUR

        poses: list[Accident] = []
        for _ in range(nombre):
            classe = self._tirer_classe()
            if classe is None:
                compteurs.refuses += 1
                continue
            heure = self._tirer_heure()
            accident = Accident(
                arete=self._tirer_arete(classe),
                debut_ts=debut_jour_ts + heure * 3600 + self._alea.randrange(3600),
                duree_s=60
                * self._alea.randint(
                    int(self._config.duree_min_minutes), int(self._config.duree_max_minutes)
                ),
                classe_vitesse=classe,
            )
            if not self._poser(accident):
                compteurs.refuses += 1
                continue
            poses.append(accident)
            compteurs.tires += 1

        # Le succès se journalise explicitement, et zéro est un résultat : sans cette ligne,
        # « aucun accident ce jour-là » ne se distingue pas de « le tirage ne tourne plus ».
        logger.info(
            f"[accidents] Jour {jour} ({JOURS[jour_semaine]}) — taux conditionné "
            f"{taux:.3f}/jour, accidents tirés={compteurs.tires}, refusés={compteurs.refuses}, "
            f"actifs au total={len(self._accidents)}, "
            f"trajets touchés la veille={self._compteurs[-2].trajets_touches if len(self._compteurs) > 1 else 0}"
        )
        for accident in poses:
            logger.info(f"[accidents]   posé : {accident}")
        return poses

    def _poser(self, accident: Accident) -> bool:
        """Valide puis enregistre un accident. Rend faux, en le disant, si la pose est refusée."""
        if accident.duree_s <= 0:
            logger.error(
                f"[ALARME] Accident refusé : durée non positive ({accident.duree_s} s) "
                f"sur l'arête {accident.arete}. Rien n'est entré dans l'état du monde."
            )
            return False
        if not self._arete_connue(accident.arete):
            logger.error(
                f"[ALARME] Accident refusé : arête {accident.arete} absente du graphe "
                "routier. Rien n'est entré dans l'état du monde."
            )
            return False
        self._accidents.append(accident)
        return True

    def _arete_connue(self, arete: CleArete) -> bool:
        return arete in self._cles

    # ── Lecture ──────────────────────────────────────────────────────────────

    def actifs_a(self, ts: int) -> list[Accident]:
        """Les accidents en cours à cet instant."""
        return [a for a in self._accidents if a.actif_a(ts)]

    def accident_sur(self, arete: CleArete, ts: int) -> Accident | None:
        """L'accident actif sur cette arête à cet instant, s'il y en a un."""
        for a in self._accidents:
            if a.arete == arete and a.actif_a(ts):
                return a
        return None

    def facteur_arete(self, arete: CleArete, ts: int) -> float:
        """Ce par quoi multiplier le temps de parcours de cette arête à cet instant.

        Rend 1,0 quand aucun accident n'y est actif — le cas de très loin le plus fréquent,
        et c'est pourquoi la recherche s'arrête au premier test.
        """
        if not self._accidents:
            return 1.0
        return (
            float(self._config.facteur_ralentissement)
            if self.accident_sur(arete, ts) is not None
            else 1.0
        )

    def poser_manuellement(
        self, lat: float, lon: float, debut_ts: int, duree_minutes: int
    ) -> Accident | None:
        """Pose un accident CHOISI, sur l'arête du graphe la plus proche d'un point.

        C'est le geste de l'expérimentateur, et c'est de LUI que viendront les figures : le
        tirage aléatoire, lui, ne peut rien montrer à ces cohortes (0,6 déplacement touché par
        journée simulée à 1 000 agents). Même mécanisme, même monde, autre déclenchement —
        l'accident posé entre dans le même registre et suit exactement le même chemin.

        Rend l'accident posé, ou `None` en le journalisant si la pose est refusée.
        """
        if not self.pret:
            logger.error(
                "[ALARME] Pose manuelle impossible : réseau non indexé. "
                f"Demande ({lat}, {lon}) à {debut_ts} ignorée."
            )
            return None
        if duree_minutes <= 0:
            logger.error(
                f"[ALARME] Pose manuelle refusée : durée {duree_minutes} min non positive."
            )
            return None

        arete, classe = self._arete_la_plus_proche(lat, lon)
        if arete is None:
            logger.error(
                f"[ALARME] Pose manuelle refusée : aucune arête trouvée près de ({lat}, {lon})."
            )
            return None

        accident = Accident(
            arete=arete,
            debut_ts=int(debut_ts),
            duree_s=int(duree_minutes) * 60,
            classe_vitesse=classe or "",
        )
        if not self._poser(accident):
            return None
        if self._compteurs:
            self._compteurs[-1].tires += 1
        logger.info(f"[accidents] POSÉ À LA MAIN : {accident}")
        return accident

    def _arete_la_plus_proche(self, lat: float, lon: float) -> tuple[CleArete | None, str | None]:
        """L'arête dont un extrémité est la plus proche du point, par distance euclidienne.

        Approximation assumée : on compare des degrés, pas des mètres, et on ne regarde que
        les nœuds. À l'échelle d'une agglomération et pour désigner « la rocade ici », c'est
        suffisant — et cela évite de dépendre d'osmnx dans ce module.
        """
        if self._positions is None:
            logger.error(
                "[ALARME] Positions des nœuds non indexées : la pose manuelle ne peut pas "
                "résoudre un point en arête. Le graphe a-t-il été chargé ?"
            )
            return None, None
        meilleure, distance2 = None, float("inf")
        for classe, aretes in self._aretes.items():
            for cle, _cumul in aretes:
                pos = self._positions.get(cle[0])
                if pos is None:
                    continue
                d2 = (pos[0] - lat) ** 2 + (pos[1] - lon) ** 2
                if d2 < distance2:
                    meilleure, distance2 = (cle, classe), d2
        return meilleure if meilleure else (None, None)

    def compter_trajet_touche(self) -> None:
        """Un déplacement de plus dont l'itinéraire a traversé une arête accidentée."""
        if self._compteurs:
            self._compteurs[-1].trajets_touches += 1

    def signature_active(self, ts: int) -> str:
        """Signature des accidents actifs à cet instant, pour les clés de cache.

        VOLONTAIREMENT GROSSIÈRE : elle décrit l'état du monde, pas ce que l'agent traverse.
        Deux agents dont aucun itinéraire ne croise l'accident auront quand même une clé
        distincte de celle d'un monde sans accident. C'est sur-invalider, jamais
        sous-invalider — l'erreur est du bon côté, et la bonne façon d'y remédier serait de
        connaître l'itinéraire au moment de bâtir la clé, ce qui n'est pas le cas ici.
        """
        actifs = self.actifs_a(ts)
        if not actifs:
            return ""
        return ",".join(
            sorted(f"{a.arete[0]}-{a.arete[1]}@{a.debut_ts}" for a in actifs)
        )

    def a_des_accidents_actifs(self, ts: int) -> bool:
        """Y a-t-il un accident en cours ? Décide de contourner les caches."""
        return any(a.actif_a(ts) for a in self._accidents)

    @property
    def accidents(self) -> list[Accident]:
        return list(self._accidents)

    @property
    def compteurs(self) -> list[CompteursJournee]:
        return list(self._compteurs)

    def resume(self) -> str:
        total = sum(c.tires for c in self._compteurs)
        return f"{total} accident(s) posé(s) sur {len(self._compteurs)} journée(s) simulée(s)"


# ── Registre du run ──────────────────────────────────────────────────────────

_registre: RegistreAccidents | None = None


def registre() -> RegistreAccidents | None:
    """Le registre du run en cours, ou `None` si le régime n'est pas actif."""
    return _registre


def initialiser() -> RegistreAccidents | None:
    """Ouvre le registre du run si l'interrupteur GAMA est à vrai. Idempotent.

    Journalise dans les DEUX cas : un run sans accidents doit le dire, sinon rien ne
    distingue « désactivé » de « la fonctionnalité est cassée ».
    """
    global _registre
    if not settings.accidents.enabled:
        logger.info("[accidents] Régime DÉSACTIVÉ — aucun accident ne sera tiré.")
        _registre = None
        return None
    if _registre is None:
        _registre = RegistreAccidents()
        logger.info(
            f"[accidents] Régime ACTIF — taux {settings.accidents.taux_journalier}/jour, "
            f"durée {settings.accidents.duree_min_minutes}-"
            f"{settings.accidents.duree_max_minutes} min, graine {settings.accidents.graine}. "
            "⚠ Loi PROVISOIRE : non conditionnée à l'heure, au jour, à la météo ni au type "
            "d'axe. Aucune durée d'itinéraire n'est modifiée par cette tranche."
        )
    return _registre


def reinitialiser() -> None:
    """Referme le registre. Appelé entre deux runs, et par les tests."""
    global _registre
    _registre = None


def jour_simule(ts: int, debut_run_ts: int) -> tuple[int, int]:
    """`(numéro de journée simulée, timestamp de son début)`, ancrés sur le début du run.

    Ancré sur le premier instant observé et non sur le calendrier mural, comme le reste du
    suivi temporel du contrôleur : c'est la même journée que celle des journaux `SIM_DAY`.
    """
    jour = (ts - debut_run_ts) // 86400
    return jour + 1, debut_run_ts + jour * 86400


def horizon_lisible(accident: Accident) -> str:
    """Fenêtre de l'accident en heure murale, pour les journaux lus par un humain."""
    debut = datetime.fromtimestamp(accident.debut_ts, tz=timezone.utc)
    return f"{debut:%H:%M}–{(debut + timedelta(seconds=accident.duree_s)):%H:%M}"
