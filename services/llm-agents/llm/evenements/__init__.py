"""Un seul canal d'événement, pour le vécu et le lu — ticket 100.

CE QUE CE PAQUET REMPLACE, ET POURQUOI
--------------------------------------
Un choc subi sur un trajet et un article lu le matin entraient par deux chemins de code
distincts : `llm/chocs.py`, livré au ticket 079, et `llm/informations.py`, planifié au lot 4 du
ticket 059 comme **sa copie** — mêmes gardes de contenu, même exposition, mêmes compteurs, même
jour du run, même trace, même alarme. Tout leur aval était pourtant déjà commun : gravité, force,
durée de service, consolidation, croyance, contradiction, foyer.

Ce paquet pose le canal unique, à deux prises d'injection :

- `arrivee` — après la décision, avec un fait mesuré. L'agent a choisi en voyant l'offre
  nominale, puis il encaisse. C'est le choc du ticket 079.
- `reveil` — avant la première décision, sans rien de mesuré. L'agent sait avant de choisir.
  C'est l'article du ticket 059. Livré au lot 2.

CE QUE CE PAQUET NE FAIT PAS, ET C'EST LE POINT
------------------------------------------------
Il ne coupe aucune ligne, ne dégrade aucune fréquence, ne touche ni OTP, ni GTFS, ni OSMnx. Le
monde reste nominal ; ce qui change, c'est ce que l'agent en sait et ce qu'il en garde. Un
événement qui dégraderait aussi l'offre mêlerait inextricablement l'adaptation à la contrainte et
l'inertie de la mémoire, et aucune des deux ne serait mesurable.

LA RÈGLE QUI NE SE NÉGOCIE PAS
------------------------------
Le retard **injecté** et le retard **mesuré** ne se confondent jamais. Deux variables, deux
colonnes, deux champs dans la trace. Sans cette séparation, aucune relecture ne pourrait plus
distinguer ce que la simulation a produit de ce qu'on lui a fait dire.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from llm.evenements.declaration import (  # noqa: F401 — façade du paquet
    CADENCES,
    CADENCE_PAR_DEFAUT,
    CANAUX,
    JUGEMENTS,
    JUGEMENTS_LIVRES,
    MOMENTS,
    Calendrier,
    TexteCite,
    Evenement,
    EvenementApplique,
    EffetPhysique,
    Exposition,
    JourDEvenement,
    RefusDEvenement,
    charger,
)
from llm.evenements.exposition import REGLES_EXPOSITION  # noqa: F401
from llm.evenements.injection import (  # noqa: F401
    PREFIXE_FOYER,
    a_l_arrivee,
    au_reveil,
    entree_de_lecture,
    joindre,
    ligne_de_foyer,
    ligne_de_lecture,
)
from llm.evenements.jugement import (  # noqa: F401
    Jugement,
    JugementRefuse,
    juger,
)
from llm.evenements.registre import CompteursJournee, RegistreEvenements  # noqa: F401
from llm.evenements.relais import Message, RelaisFoyer, RelaisRefuse  # noqa: F401
from settings import settings

# ── Registre du processus ───────────────────────────────────────────────────────────────────
_registre: RegistreEvenements | None = None
_initialise = False


def registre() -> RegistreEvenements | None:
    return _registre


def incident_reseau_a_une_source() -> bool:
    """Vrai dès qu'un événement chargé porte la composante `incident_reseau`.

    C'est ce que `llm/gravite.py` consulte pour cesser de la déclarer inactive. Sans événement,
    elle reste déclarée inactive : une composante sans source doit continuer de le dire, sans
    quoi zéro se confondrait avec « trajet parfait ».
    """
    if _registre is None:
        return False
    return any(j.incident_reseau for j in _registre.evenement.jours.values())


def cache_coupe(timestamp: int) -> bool:
    """Le cache de décisions doit-il être contourné à cet instant ? (ticket 100, Q5)

    Faux quand aucun événement n'est déclaré — un run nominal garde son cache entier.
    """
    if _registre is None:
        return False
    try:
        return _registre.cache_coupe(int(timestamp))
    except Exception:  # noqa: BLE001 — une garde ne fait jamais tomber une décision
        return False


def noter_decision(timestamp: int, depuis_cache: bool) -> None:
    """Compte une décision, et dit si le cache l'a servie. Sans événement, ne fait rien."""
    if _registre is None:
        return
    _registre.noter_decision(int(timestamp), depuis_cache)


async def lignes_du_jour(person_id: str, timestamp: int, *, compter: bool = True) -> list[str]:
    """Les lignes garanties au prompt de cet agent pour un trajet à `timestamp` — ticket 111.

    Liste vide sans événement, hors des jours de service, ou pour un agent non exposé. Ne lève
    JAMAIS vers l'appelant : une ligne qui ne se calcule pas ne doit pas faire perdre la
    décision — mais elle ne disparaît pas en silence, une [ALARME] le dit.
    """
    if _registre is None:
        return []
    try:
        return await _registre.lignes_du_jour(str(person_id), int(timestamp), compter=compter)
    except Exception as err:  # noqa: BLE001
        logger.error(
            f"[ALARME] [evenements] lignes de service non calculées pour {person_id} à "
            f"{timestamp} ({type(err).__name__}: {err}) — la décision part SANS la ligne "
            f"garantie par le ticket 111."
        )
        return []


def noter_instant(timestamp: int) -> None:
    """L'instant simulé du /sync courant. Sans événement, ne fait rien."""
    if _registre is not None:
        _registre.noter_instant(int(timestamp))


def noter_rendu(person_id: str, timestamp: int, lignes, historique) -> None:
    """Vérifie qu'une décision porte bien ses lignes de service. Sans événement, ne fait rien."""
    if _registre is not None and lignes:
        _registre.noter_rendu(str(person_id), int(timestamp), lignes, historique)


def noter_contournement_cache() -> None:
    if _registre is not None:
        _registre.noter_contournement_cache()


def noter_reflexion_presse(
    person_id: str,
    timestamp: int,
    lignes: list[str],
    *,
    etape: str,
    prise_en_compte: bool | None = None,
    reflection: str = "",
) -> None:
    """Trace l'article présenté à une réflexion et l'accusé de lecture structuré du modèle."""
    if _registre is not None and lignes:
        _registre.tracer_reflexion_presse(
            str(person_id),
            int(timestamp),
            lignes,
            etape=etape,
            prise_en_compte=prise_en_compte,
            reflection=reflection,
        )


def _declaration_demandee() -> str | None:
    """Le fichier à charger, `None` si aucun.

    Deux clés de configuration pendant une version : `evenements` (ticket 100) et `chocs`
    (ticket 079). La seconde est lue avec un avertissement, jamais en silence — une campagne
    lancée sous l'ancienne clé doit continuer de tourner, mais celui qui relit le journal doit
    savoir laquelle a servi.
    """
    bloc_100 = getattr(settings, "evenements", None)
    if bloc_100 is not None and getattr(bloc_100, "enabled", False):
        chemin = getattr(bloc_100, "fichier", None)
        if chemin:
            return str(chemin)
        logger.error(
            "[ALARME] [evenements] `evenements.enabled` est vrai mais `evenements.fichier` est "
            "vide : AUCUN événement ne sera joué, et le run se comportera comme un run nominal. "
            "Déclarez le fichier, ou coupez le drapeau."
        )
        return None

    bloc_079 = getattr(settings, "chocs", None)
    if bloc_079 is not None and getattr(bloc_079, "enabled", False):
        chemin = getattr(bloc_079, "fichier", None)
        if chemin:
            logger.warning(
                "[evenements] déclaration lue sous la clé `chocs:` du ticket 079. Elle reste "
                "servie ; la clé `evenements:` la remplace (ticket 100, lot 6)."
            )
            return str(chemin)
    return None


def initialiser(workdir: Path | None = None) -> RegistreEvenements | None:
    """Charge l'événement déclaré, s'il y en a un. Sans fichier, RIEN ne change.

    Le refus est FRANC : une déclaration invalide arrête le chargement au lieu de laisser courir
    un run de soixante jours qui ne fera rien et dont personne ne saura pourquoi.
    """
    global _registre, _initialise
    if _initialise:
        return _registre
    _initialise = True
    chemin = _declaration_demandee()
    if not chemin:
        logger.info(
            "[evenements] aucun événement déclaré — le run se comporte comme sans ce mécanisme."
        )
        return None
    evenement = charger(chemin)
    # ⚠ La lecture et l'ARMEMENT sont deux choses. `charger()` vérifie une déclaration —
    # empreintes, exposition, calendrier — et doit pouvoir le faire pour un fichier qui décrit
    # un protocole pas encore jouable ; sans quoi on ne pourrait même pas tester que les cinq
    # articles du corpus concordent avec leur manifeste. Armer un RUN, c'est autre chose :
    # là, ce qui n'est pas livré doit arrêter le démarrage, pas échouer au milieu.
    if evenement.canal == "lu" and evenement.jugement == "aucun":
        # Refus à l'ARMEMENT, et non à la lecture. Un article sans jugement entre à gravité
        # 0,00 et vit 2,8 jours : il aura disparu du prompt le surlendemain, et son silence
        # passerait pour une absence d'effet. La déclaration reste lisible — c'est ce qui
        # permet de vérifier les empreintes d'un corpus — mais elle n'arme pas un run.
        raise RefusDEvenement(
            f"événement « {evenement.evenement_id} » : un `canal: lu` sans jugement ne peut "
            f"pas armer un run. L'article entrerait en mémoire à gravité 0,00, donc pour "
            f"2,8 jours, et aucune mesure longitudinale ne serait possible. Déclarez "
            f"`jugement: a_l_injection`."
        )
    journal = None
    if workdir is not None:
        journal = Path(workdir) / "evenements.jsonl"
        try:
            Path(workdir).mkdir(parents=True, exist_ok=True)
            declaration = Path(workdir) / "evenement.yaml"
            declaration.write_bytes(Path(chemin).read_bytes())
            # Compatibilité 079 : les dépouilleurs et les rapports déjà écrits cherchent
            # `choc.yaml` et `chocs.jsonl` dans le répertoire du run. Deux liens, pas deux
            # copies — et ils partent au lot 6 avec le reste des alias.
            for alias, cible in (("choc.yaml", declaration), ("chocs.jsonl", journal)):
                lien = Path(workdir) / alias
                if not lien.exists():
                    try:
                        lien.symlink_to(cible.name)
                    except OSError:
                        # Systèmes de fichiers sans lien symbolique : la copie vaut mieux que
                        # rien pour la déclaration ; le journal, lui, se recopierait à chaque
                        # ligne — il reste sous son nom neuf, et le dépouilleur le trouvera.
                        if alias.endswith(".yaml"):
                            lien.write_bytes(cible.read_bytes())
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[evenements] déclaration non archivée dans le run ({err})")
    _registre = RegistreEvenements(evenement, journal=journal)
    jours = ", ".join(
        f"j{j.jour}:+{j.retard_min}min"
        for j in sorted(evenement.jours.values(), key=lambda x: x.jour)
    )
    logger.info(
        f"[evenements] « {evenement.libelle} » ({evenement.evenement_id}) chargé — canal "
        f"{evenement.canal}, moment {evenement.moment}, jugement {evenement.jugement}, "
        f"exposition {evenement.exposition.regle}"
        + (f" {sorted(evenement.exposition.modes)}" if evenement.exposition.modes else "")
        + f", jours {evenement.premier_jour}→{evenement.dernier_jour} [{jours}], "
        f"empreinte {evenement.empreinte[:12]}, format {evenement.format_source}, "
        f"source : {evenement.source or 'non déclarée'}"
    )
    if getattr(settings.cache, "enabled", False):
        # Décision de l'auteur du 2026-09-22 : le cache est coupé LE JOUR de l'événement, et
        # ce jour-là seulement. Automatique, donc sans dépendre d'un `CACHE=0` qu'on penserait
        # à poser — le run du 19 septembre a montré ce que coûte une garde qui repose sur la
        # mémoire de l'opérateur.
        jours = ", ".join(f"j{j}" for j in sorted(evenement.jours))
        logger.info(
            f"[evenements] cache de décisions ACTIF, coupé automatiquement les jours "
            f"d'événement ({jours}). Le reste du run le garde."
        )
        logger.warning(
            "[evenements] ⚠ la coupure porte sur le JOUR de l'événement, pas sur la fenêtre "
            "d'APRÈS, qui est celle qu'on mesure. La clé exacte du cache ne porte ni la date "
            "ni la mémoire : une décision prise avant l'événement reste servable après. Ce "
            "qui l'en empêche est la branche sémantique (0,95 de similarité de mémoire), et "
            "personne ne l'a mesuré sur cette fenêtre. Les compteurs journaliers "
            "« décision(s) servie(s) DEPUIS LE CACHE » disent, jour par jour, sur combien de "
            "décisions la réserve porte. `make run CACHE=0` la lève entièrement."
        )
    return _registre


def reinitialiser() -> None:
    """Oublie l'événement. Réservé aux tests et à la fin d'un run."""
    global _registre, _initialise
    if _registre is not None:
        _registre.journaliser_compteurs()
    _registre = None
    _initialise = False
