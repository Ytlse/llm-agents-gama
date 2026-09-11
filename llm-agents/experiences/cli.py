"""CLI de la plateforme d'expériences (ticket 035) — `python -m experiences <commande>`.

    preparer-jeu    --population P --nom N [--jour AAAA-MM-JJ] [--concurrence 8] [--seuil 0.05]
    consulter-jeu   --nom N [--personne ID]
    verifier-jeu    --nom N
    verifier-jours  --nom N --jour AAAA-MM-JJ [--methode gtfs|moteurs] [--declarer]   l'offre TC de ce jour ? (lu dans le GTFS, ou mesuré)
    definir         EXPERIENCE.yaml [--accepter-nom]   valide, vérifie le nom calculé, range dans data/experiences/<nom>/
    dupliquer       --de NOM [--vers NOM] [--decideur-type T] [--decideur-modele M]   sans --vers, le nom est calculé
    estimer         --experience NOM
    lancer          --experience NOM [--reprendre] [--accepter-perime] [--attendre-fenetre]
    pause | arreter --experience NOM           (fichier PAUSE / STOP dans la dernière exécution)
    file                                       expériences en attente d'une clé (FIFO)
    actives         [--est-vide]               expériences tenant une clé (code 0 si aucune)
    defiler         --experience NOM           retire une expérience de la file (R2e)
    reconcilier                                libère les clés des exécutions terminées/fantômes (DANS le conteneur)
    ordonnancer     [--intervalle S]           boucle hôte : réconcilie et promeut la file
    registre        [--trier CHAMP] [--decroissant] [--filtrer champ=valeur …]
    comparer        EXEC_A EXEC_B
    synthese        EXEC
    erreurs         [EXEC | --experience NOM]  rapproche decisions.jsonl du jeu (manquants, trous, tentatives)

Dans le conteneur : `docker compose exec controller python -m experiences …` (les cibles `make`
de la racine encapsulent ces appels).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from experiences import experience as E
from experiences import jeu as J
from experiences import nommage as NOM
from experiences.archive import ETAT_EN_COURS, ETAT_TERMINEE, Execution
from experiences.population import charger_population, info_population
from experiences.runner import FICHIER_PAUSE, FICHIER_STOP, executer
from loguru import logger


def motif_non_reprenable(execution) -> str | None:
    """Pourquoi cette exécution ne peut pas être reprise — None si elle peut l'être.

    Est reprenable toute exécution dont l'archive n'est pas clôturée : en pause, épuisée
    (le runner la marque SANS sceller, cf. R4), interrompue (processus mort), ou en cours
    sans runner. Jusqu'au 2026-09-08 la CLI refusait tout état de `ETATS_FINAUX`, épuisée
    comprise — alors que son propre message, la spec et le bouton « Reprendre » du tableau de
    bord la donnaient reprenable : une exécution sur Muse Glimmer, déclarée épuisée à tort
    (instance occupée lue comme hors service), ne pouvait plus repartir que par « Rejouer ».
    """
    etat = (execution.etat() or {}).get("etat")
    if execution.cloturee or etat == ETAT_TERMINEE:
        return (
            f"la dernière exécution {execution.nom} est clôturée ({etat}) : immuable (E19), "
            "« Rejouer » en crée une nouvelle"
        )
    return None


def _derniere_execution(exp: E.Experience) -> Path | None:
    d = exp.dossier() / "executions"
    if not d.is_dir():
        return None
    execs = sorted(p for p in d.iterdir() if (p / "execution.yaml").is_file())
    return execs[-1] if execs else None


def _charger_experience_par_nom(nom: str) -> E.Experience:
    chemin = Path(nom)
    if chemin.suffix in (".yaml", ".yml") and chemin.is_file():
        return E.charger_experience(chemin)
    return E.charger_experience(E.dossier_experiences() / nom / "experience.yaml")


# ── jeu ──────────────────────────────────────────────────────────────────────


def _trip_helper_reel():
    """Le trip helper de la simulation (OTP + OSMnx, caches inclus) — services requis."""
    from urban_mobility_agents.factory.factory import init_static_data

    return init_static_data().trip_helper


def cmd_preparer_jeu(a: argparse.Namespace) -> int:
    personnes, info = charger_population(a.population)
    dossier = Path(a.dossier) if a.dossier else E.dossier_jeux() / a.nom
    prep = J.JeuEnPreparation.ouvrir(dossier, a.nom, info, a.jour)
    trip_helper = _trip_helper_reel()
    compteurs = asyncio.run(
        J.preparer(
            prep,
            personnes,
            trip_helper,
            concurrence=a.concurrence,
            seuil_sans_proposition=a.seuil,
        )
    )
    if compteurs.get("erreurs"):
        prep.fermer()
        logger.error(
            f"[jeu] {compteurs['erreurs']} erreurs moteur : le jeu n'est PAS clos — relancez pour reprendre (J11)"
        )
        return 2
    prep.clore(J.deplacements_attendus(personnes, a.jour), len(personnes))
    print(J.Jeu.charger(dossier).resume())
    return 0


def cmd_consulter_jeu(a: argparse.Namespace) -> int:
    jeu = J.Jeu.charger(
        Path(a.dossier) if a.dossier else E.dossier_jeux() / a.nom,
        verifier=not a.sans_verification,
    )
    print(jeu.resume())
    if a.personne:
        lignes = jeu.consulter(a.personne)
        if not lignes:
            print(f"aucun déplacement enregistré pour {a.personne!r}")
            return 1
        for l in lignes:
            h = f"{l.depart_24h // 3600:02d}:{(l.depart_24h % 3600) // 60:02d}"
            print(
                f"\n{h} → {l.purpose} (activité {l.activity_id}) — {len(l.propositions)} proposition(s)"
                + (f" — {l.motif_absence}" if l.motif_absence else "")
            )
            for i, p in enumerate(l.vers_propositions()):
                print(
                    f"   {i:2d}. {p.mode:<28} {((p.plan.duration or 0) // 60):4d} min  [{p.source}]"
                )
    return 0


def cmd_verifier_jeu(a: argparse.Namespace) -> int:
    jeu = J.Jeu.charger(Path(a.dossier) if a.dossier else E.dossier_jeux() / a.nom)
    print(jeu.resume())
    differentes, non_verif = J.perime(jeu)
    if differentes:
        print("PÉRIMÉ — dépendances changées : " + ", ".join(differentes))
    if non_verif:
        print("non vérifiables : " + ", ".join(non_verif))
    if not differentes:
        print(
            "dépendances : inchangées"
            if not non_verif
            else "dépendances vérifiables : inchangées"
        )
    return 1 if differentes else 0


def cmd_verifier_jours(a: argparse.Namespace) -> int:
    """L'offre TC d'un autre jour est-elle celle du jeu ?

    `gtfs` (défaut, aucun service requis) : chaque course proposée existe-t-elle ce jour dans les
    feeds ? Validité déclarée PAR DÉPLACEMENT. `moteurs` : OTP interrogé sur un échantillon,
    équivalence du jour entier déclarée seulement si 100 % identique.
    """
    jeu = J.Jeu.charger(Path(a.dossier) if a.dossier else E.dossier_jeux() / a.nom)
    if a.methode == "gtfs":
        from experiences.offre_jour import verifier_offre_jour_gtfs

        res = verifier_offre_jour_gtfs(
            jeu,
            a.jour,
            Path(a.gtfs) if a.gtfs else None,
            fenetre_s=int(a.fenetre_h * 3600),
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in res.items()
                    if k not in ("invalides_detail", "invalides_cles")
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        for d in res["invalides_detail"][:5]:
            print(
                f"  ≠ {d['cle']} (départ {d['depart_24h'] // 3600:02d}:{(d['depart_24h'] % 3600) // 60:02d}) : "
                f"{d['evenements_dans_la_fenetre']} passage(s) différents dans sa fenêtre"
            )
        if a.declarer:
            jeu.declarer_verification_jour(a.jour, res)
            print(
                f"déclaré dans {jeu.dossier / J.FICHIER_EQUIVALENCES} : {res['valides']} déplacements servis du jeu le {a.jour}, "
                f"{res['invalides']} recalculés (TC)"
            )
        return 0 if res["equivalent"] else 1
    trip_helper = _trip_helper_reel()
    mesure = asyncio.run(
        J.comparer_offre_jour(
            jeu, trip_helper, a.jour, echantillon=a.echantillon, graine=a.graine
        )
    )
    print(
        json.dumps(
            {k: v for k, v in mesure.items() if k != "differences"},
            ensure_ascii=False,
            indent=1,
        )
    )
    for d in mesure["differences"][:5]:
        print(
            f"  ≠ {d['cle']} : {len(d['avant'])} TC enregistrées vs {len(d['apres'])} le {a.jour}"
        )
    if mesure["equivalent"]:
        print(
            f"offre TC du {a.jour} IDENTIQUE à celle du {jeu.jour_simule} sur {mesure['compares']} déplacements"
        )
        if a.declarer:
            jeu.declarer_jour_equivalent(
                a.jour, {k: v for k, v in mesure.items() if k != "differences"}
            )
            print(f"déclaré dans {jeu.dossier / J.FICHIER_EQUIVALENCES}")
        return 0
    print(
        f"offre TC du {a.jour} DIFFÉRENTE : {mesure['differents']} déplacement(s) sur {mesure['compares']} — "
        f"aucune équivalence déclarée ; la simulation recalculera les TC ce jour-là, le mode sans simulateur refuse cette date"
    )
    return 1


# ── expérience ───────────────────────────────────────────────────────────────


def cmd_definir(a: argparse.Namespace) -> int:
    exp = E.charger_experience(a.fichier)
    # N13 — le nom se calcule depuis les paramètres. Une définition écrite à la main peut
    # nommer autre chose que ce qu'elle fait : c'est exactement ce que le nommage calculé
    # supprime, et un dossier mal nommé se paie ensuite en confusion d'archives.
    attendu = NOM.verifier_nom(E.experience_vers_dict(exp))
    if attendu and not a.accepter_nom:
        print(
            f"nom refusé : {exp.nom!r} ne dit pas ses paramètres — attendu {attendu!r}\n"
            f"→ renommez le `nom` du fichier, ou relancez avec --accepter-nom "
            f"(spec nommage-canonique-experiences, N13)",
            file=sys.stderr,
        )
        return 2
    chemin = E.sauver_experience(exp)
    print(f"expérience {exp.nom!r} validée et rangée : {chemin}")
    if attendu:
        print(f"⚠ nom hors convention (attendu {attendu!r}), accepté explicitement")
    return 0


def cmd_dupliquer(a: argparse.Namespace) -> int:
    exp = _charger_experience_par_nom(a.de)
    changements = {}
    if a.decideur_type or a.decideur_modele:
        dec = exp.decideur.model_dump()
        if a.decideur_type:
            dec["type"] = a.decideur_type
        if a.decideur_modele:
            dec["modele"] = a.decideur_modele
        changements["decideur"] = dec
    nouvelle = E.dupliquer(exp, a.vers or None, **changements)
    if not a.vers:
        # Nom calculé (N1) : l'indice de collision se résout sur le disque (N10). Une copie
        # qui ne change AUCUN paramètre nommé retombe sur une expérience existante — la
        # dupliquer l'écraserait au lieu d'ouvrir une variante.
        attribution = NOM.attribuer_nom(
            E.experience_vers_dict(nouvelle), E.dossier_experiences()
        )
        if attribution.reutilise:
            print(
                f"rien à dupliquer : ces paramètres sont déjà ceux de "
                f"{attribution.reutilise!r} — changez un paramètre, ou relancez cette "
                f"expérience pour lui ajouter une exécution",
                file=sys.stderr,
            )
            return 2
        nouvelle.nom = attribution.nom
        if attribution.indice > 1:
            print(
                f"⚠ {attribution.base!r} est déjà pris par une autre définition : "
                f"indice ajouté (N10)"
            )
    print(
        f"expérience {nouvelle.nom!r} créée depuis {exp.nom!r} : "
        f"{E.sauver_experience(nouvelle)}"
    )
    return 0


def _jeu_de_cles_experience(exp: E.Experience, moniteur) -> set[str]:
    """Identités de clé API que l'expérience peut solliciter (R4/R8/R9). Vide hors passerelle."""
    if exp.decideur.type != "passerelle":
        return set()
    from experiences.cles import jeu_de_cles

    providers = getattr(moniteur, "providers", {}) or {}
    admises = None
    if moniteur is not None:
        admises = (
            moniteur.instances_disponibles()
            if moniteur.joignable
            else moniteur.instances
        )
    return jeu_de_cles(
        exp.decideur.modele or "",
        providers,
        instances_admises=admises,
        portee=exp.decideur.portee,
    )


def _annuler_execution_creee(
    exp: E.Experience, execution, dossier_exp: Path, *, creee: bool
) -> None:
    """Supprime une exécution fraîchement créée mais jamais démarrée (partie en file). Une reprise
    (exécution préexistante) n'est jamais détruite."""
    if not creee:
        return
    import shutil

    shutil.rmtree(execution.dossier, ignore_errors=True)
    exp.executions_connues = [n for n in exp.executions_connues if n != execution.nom]
    E.sauver_experience(exp, dossier_exp)


def _preparer_lancement(exp: E.Experience, *, accepter_perime: bool):
    jeu = J.Jeu.charger(exp.jeu.chemin())
    info = info_population(exp.population.chemin)
    from experiences.ressources import (
        MoniteurRessources,
        charger_providers,
        instances_pour_modele,
    )

    moniteur = None
    instances = None
    if exp.decideur.type == "passerelle":
        providers = charger_providers()
        instances = instances_pour_modele(
            exp.decideur.modele or "", providers, exp.decideur.portee
        )
        moniteur = MoniteurRessources(instances, providers)
        moniteur.rafraichir()
        instances = (
            moniteur.instances_disponibles() if moniteur.joignable else instances
        )
    refus, avert = E.refuser_si_impossible(
        exp, jeu, info, instances_disponibles=instances, perime_accepte=accepter_perime
    )
    for w in avert:
        logger.warning(f"[experience] {w}")
    return jeu, info, moniteur, refus


def _aptitude(exp, est: dict) -> tuple[list[str], list[str]]:
    """(refus, avertissements) d'aptitude du modèle à la charge. Best-effort : un diagnostic
    indisponible ne doit jamais empêcher un lancement légitime."""
    if exp.decideur.type != "passerelle":
        return [], []
    try:
        from experiences import aptitude as APT
        from experiences.ressources import charger_providers, instances_pour_modele

        providers = charger_providers()
        instances = instances_pour_modele(
            exp.decideur.modele or "", providers, exp.decideur.portee
        )
        return APT.verifier_depuis_estimation(exp, est, providers, instances)
    except Exception as e:  # noqa: BLE001
        return [], [f"aptitude non vérifiée ({type(e).__name__}: {e})"]


def cmd_estimer(a: argparse.Namespace) -> int:
    exp = _charger_experience_par_nom(a.experience)
    jeu, _info, moniteur, refus = _preparer_lancement(exp, accepter_perime=True)
    est = E.estimer(exp, jeu, moniteur=moniteur)
    print(json.dumps(est, ensure_ascii=False, indent=1, default=str))

    # P3 — le chiffrage devient un verdict : ce qui ne peut pas aboutir est refusé
    # d'avance plutôt que découvert au bout de trois heures.
    refus_apt, avert_apt = _aptitude(exp, est)
    if avert_apt:
        print("\nAVERTISSEMENTS :\n- " + "\n- ".join(avert_apt))
    refus = list(refus) + refus_apt
    if refus:
        print("\nREFUS au lancement :\n- " + "\n- ".join(refus))
        return 1
    return 0


def cmd_lancer(a: argparse.Namespace) -> int:
    exp = _charger_experience_par_nom(a.experience)
    jeu, info, moniteur, refus = _preparer_lancement(
        exp, accepter_perime=a.accepter_perime
    )
    # P3 — l'aptitude du modèle à la charge est vérifiée AVANT de créer l'exécution : une
    # expérience qui ne peut pas aboutir ne doit pas laisser un dossier à archiver derrière elle.
    refus_apt, avert_apt = _aptitude(exp, E.estimer(exp, jeu, moniteur=moniteur))
    for m in avert_apt:
        print(f"AVERTISSEMENT : {m}")
    refus = list(refus) + (
        [] if a.ignorer_aptitude else refus_apt
    )
    if a.ignorer_aptitude and refus_apt:
        for m in refus_apt:
            print(f"AVERTISSEMENT (aptitude ignorée) : {m}")
    if refus:
        print("REFUSÉ — aucune exécution créée :\n- " + "\n- ".join(refus))
        return 1
    if exp.mode != E.MODE_SANS_SIMULATEUR:
        print(
            "mode simulateur : lancer par `make run JEU=<nom>` (spec 04) — la plateforme ne pilote pas GAMA ici"
        )
        return 1

    from settings import settings

    # Le décideur et le gabarit sont ceux de l'expérience : réglages imposés au processus.
    settings.agent.long_term_memory_enabled = bool(exp.memoire)
    settings.cache.enabled = False  # chaque décision non archivée est demandée (RG-2)
    settings.agent.mode_draw_seed = exp.graine_tirage
    settings.agent.option_order_seed = exp.graine_ordre
    settings.agent.weather_per_agent_dates = exp.calendrier.politique != "commune"
    settings.agent.weather_draw_seed = exp.calendrier.graine
    if exp.decideur.type in ("passerelle", "antigravity"):
        settings.agent.llm_params = {
            **settings.agent.llm_params,
            **exp.decideur.parametres,
        }
        if exp.gabarit.variante:
            # Le gabarit est celui de l'expérience, pas celui actif sur la passerelle : la
            # requête le désigne (`parameters.prompt_variant`, résolu par le PromptManager).
            settings.agent.llm_params["prompt_variant"] = exp.gabarit.variante
        elif exp.decideur.type == "antigravity":
            from experiences.experience import empreinte_gabarit

            emp = empreinte_gabarit(exp.gabarit.categorie, None)
            logger.warning(
                f"[antigravity] gabarit.variante non figée : utilisation du prompt actif (sha256: {emp['sha256']})"
            )

    personnes, info = charger_population(exp.population.chemin)
    dossier_exp = exp.dossier()
    # Lancer ne réécrit PAS la définition : elle est chargée par nom, telle qu'elle est sur
    # disque, et un run ne doit pas la muter. La seule écriture est l'ajout de la nouvelle
    # exécution à l'index (plus bas), et uniquement quand une exécution est réellement créée.
    derniere = _derniere_execution(exp) if a.reprendre else None
    if a.reprendre:
        motif = (
            "aucune exécution pour cette expérience"
            if derniere is None
            else motif_non_reprenable(Execution.ouvrir(derniere))
        )
        if motif:
            print(
                f"rien à reprendre : {motif} — se reprend toute exécution non clôturée : "
                "en pause, épuisée, interrompue ou en cours sans runner"
            )
            return 1
    if derniere is not None:
        execution = Execution.ouvrir(derniere)
    else:
        execution = Execution.creer(
            dossier_exp,
            E.experience_vers_dict(exp),
            E.empreintes(exp, jeu, info),
            regime_demande={
                "parallelisme": exp.regroupement.parallelisme,
                "unite_sollicitation": "deplacement",
            },
            sources_alea={
                "graine_ordre": exp.graine_ordre,
                "graine_tirage": exp.graine_tirage,
                "graine_calendrier": exp.calendrier.graine,
                "echantillonnage_decideur": exp.decideur.type in ("passerelle", "antigravity"),
            },
            reglages_herites={
                "agenda_anticipation_enabled": settings.agent.agenda_anticipation_enabled,
                "max_trip_candidates": settings.gtfs.max_trip_candidates,
            },
        )
        # executions_connues DOIT refléter le disque : le dict de définition écrit par le
        # tableau de bord ne porte pas ce champ, si bien que chaque run le réinitialisait à sa
        # seule exécution et effaçait les précédentes de l'index. On fait l'union avec les
        # dossiers présents, sans toucher au reste de la définition.
        dossier_execs = dossier_exp / "executions"
        sur_disque = (
            {p.name for p in dossier_execs.iterdir() if p.is_dir()}
            if dossier_execs.is_dir()
            else set()
        )
        exp.executions_connues = sorted(
            set(exp.executions_connues) | sur_disque | {execution.nom}
        )
        E.sauver_experience(exp, dossier_exp)
    settings.app.llm_exchanges_file = str(execution.dossier / "llm_exchanges.jsonl")

    # Admission par clé (spec parallelisation_experiences) : parallèle si les clés de l'expérience
    # sont libres, sinon mise en file — l'ordonnanceur la démarrera quand une clé se libérera.
    from experiences import reservations as R

    creee = derniere is None
    cles = _jeu_de_cles_experience(exp, moniteur)
    if exp.decideur.type == "passerelle" and not getattr(moniteur, "providers", None):
        # R12 fail-safe : jeux de clés inétablissables (configuration fournisseurs illisible) →
        # ne pas démarrer plutôt que risquer deux runs sur la même clé.
        _annuler_execution_creee(exp, execution, dossier_exp, creee=creee)
        print(
            "REFUSÉ — configuration des fournisseurs illisible : clés inétablissables (fail-safe R12)"
        )
        return 1
    issue = R.admettre(
        cles,
        execution.dossier,
        exp.nom,
        args={
            "accepter_perime": a.accepter_perime,
            "attendre_fenetre": a.attendre_fenetre,
            "reprendre": a.reprendre,
        },
    )
    if issue == "file":
        _annuler_execution_creee(exp, execution, dossier_exp, creee=creee)
        print(
            f"EN FILE — {exp.nom} attend qu'une clé se libère ({sorted(cles)}). "
            "L'ordonnanceur la démarrera automatiquement (FIFO)."
        )
        return 4

    from experiences.decideurs import construire_decideur

    agent = None
    if exp.decideur.type in ("passerelle", "antigravity"):
        from urban_mobility_agents.agents.llm_agent import LlmAgent

        agent = LlmAgent()
    dossier_echanges = (
        execution.dossier / "echanges" if exp.decideur.type == "antigravity" else None
    )
    decideur = construire_decideur(
        exp.decideur,
        agent=agent,
        moniteur=moniteur,
        instances=(moniteur.instances if moniteur else None),
        dossier_echanges=dossier_echanges,
        attente_max_s=exp.attente_max_s,
        execution=execution,
    )
    # Traçabilité (R3) : tout le journal de l'exécution ([execution]/[ALARME]) est aussi archivé dans
    # le dossier ; lancé via `docker compose exec`, il n'allait sinon que sur le terminal lanceur.
    sink = logger.add(
        str(execution.dossier / "execution.log"),
        level="INFO",
        enqueue=True,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} {level} {message}",
    )
    try:
        compteurs = asyncio.run(
            executer(
                exp,
                jeu,
                personnes,
                execution,
                decideur,
                moniteur=moniteur,
                attendre_fenetre=a.attendre_fenetre,
            )
        )
    finally:
        # La clé se libère au statut terminal (R7) : `liberer` retire les réservations de cette
        # exécution, y compris si `executer` a levé (le statut est alors non terminal, mais le
        # processus s'arrête — pas de fantôme). Un kill dur est rattrapé par `reconcilier`.
        R.liberer(execution.dossier)
        logger.remove(sink)
    print(
        json.dumps(
            {k: v for k, v in compteurs.items() if k != "quota"},
            ensure_ascii=False,
            indent=1,
            default=str,
        )
    )
    print(f"exécution : {execution.dossier}")
    return 0 if compteurs.get("etat") == "terminee" else 3


def _signal_fichier(a: argparse.Namespace, nom_fichier: str) -> int:
    exp = _charger_experience_par_nom(a.experience)
    derniere = _derniere_execution(exp)
    if derniere is None:
        print("aucune exécution")
        return 1
    if Execution.ouvrir(derniere).etat().get("etat") != ETAT_EN_COURS:
        print(f"la dernière exécution ({derniere.name}) n'est pas en cours")
        return 1
    (derniere / nom_fichier).touch()
    from experiences.runner import DELAI_GRACE_PAUSE_S

    print(
        f"{nom_fichier} demandé pour {derniere.name} — effectif dans {DELAI_GRACE_PAUSE_S:.0f} s "
        f"au plus (les sollicitations encore en vol sont abandonnées, leurs déplacements "
        f"redemandés à la reprise)"
    )
    return 0


def cmd_registre(a: argparse.Namespace) -> int:
    from experiences.registre import formater_table, lister, trier_filtrer

    filtres = dict(f.split("=", 1) for f in (a.filtrer or []) if "=" in f)
    lignes = trier_filtrer(
        lister(inclure_masquees=a.inclure_masquees),
        trier=a.trier,
        decroissant=a.decroissant,
        filtres=filtres,
    )
    if a.json:
        print(json.dumps(lignes, ensure_ascii=False, indent=1, default=str))
    else:
        print(formater_table(lignes))
    return 0


def cmd_statuer(a: argparse.Namespace) -> int:
    """Pose le statut d'une expérience (§3.2, §5). N'efface et ne déplace rien."""
    from experiences import statut as S
    from experiences.experience import dossier_experiences

    dossier = Path(a.experience)
    if not (dossier / "experience.yaml").is_file():
        dossier = dossier_experiences() / a.experience
    corps = S.ecrire(
        dossier,
        a.statut,
        motif=a.motif,
        reference=a.reference,
        visible_par_defaut=a.visible,
    )
    print(
        f"{dossier.name} : {corps['statut']}"
        + (f" — {corps['motif']}" if corps["motif"] else "")
    )
    print(f"  données conservées, aucun fichier déplacé ({dossier})")
    if corps["statut"] != S.ACTIF:
        print("  masquée du registre par défaut ; `--inclure-masquees` la réaffiche")
    return 0


def cmd_statuts(a: argparse.Namespace) -> int:
    """Statut de toutes les expériences, masquées comprises."""
    from experiences import statut as S
    from experiences.experience import dossier_experiences

    tous = S.statuts_par_experience(dossier_experiences())
    if a.json:
        print(json.dumps(tous, ensure_ascii=False, indent=1, default=str))
        return 0
    largeur = max((len(n) for n in tous), default=10)
    for nom, st in sorted(tous.items(), key=lambda kv: (kv[1]["statut"], kv[0])):
        motif = f" — {st['motif']}" if st.get("motif") else ""
        print(f"{nom:<{largeur}}  {st['statut']:<9}{motif}")
    compte: dict[str, int] = {}
    for st in tous.values():
        compte[st["statut"]] = compte.get(st["statut"], 0) + 1
    print("\n" + " · ".join(f"{k} : {v}" for k, v in sorted(compte.items())))
    return 0


def cmd_comparer(a: argparse.Namespace) -> int:
    from experiences.registre import comparer, formater_comparaison

    c = comparer(a.a, a.b, inclure_invalides=a.inclure_invalides)
    print(
        json.dumps(c, ensure_ascii=False, indent=1, default=str)
        if a.json
        else formater_comparaison(c)
    )
    return 0 if c["comparable"] else 1


def cmd_synthese(a: argparse.Namespace) -> int:
    from experiences.registre import ecrire_synthese

    print(ecrire_synthese(a.execution))
    return 0


def cmd_score(a: argparse.Namespace) -> int:
    """Score une exécution (ou toutes) sous une formule, et écrit la page de synthèse.

    `--toutes` recalcule tout l'historique hors-ligne (rejeu depuis les scores bruts
    quand c'est possible) ; sinon score la seule exécution `--execution`.
    """
    from experiences import formule as F
    from experiences import rendu_scores, score

    registre = F.charger()
    formule = registre.reference
    if a.formule:
        formule = registre.par_nom(a.formule)
        if formule is None:
            print(f"ERREUR : formule inconnue : {a.formule!r}", file=sys.stderr)
            return 2

    if a.toutes:
        bilan = score.rescorer_tout(formule, registre)
        # Régénère les pages des exécutions qui ont désormais un scores.json.
        racine = score.REPO_ROOT / "data" / "experiences"
        for dossier in score._executions(racine):
            rendu_scores.ecrire(dossier, registre)
        print(json.dumps(bilan, ensure_ascii=False))
        return 0

    if not a.execution:
        print("ERREUR : préciser une exécution ou --toutes", file=sys.stderr)
        return 2
    chemin = score.score_execution(a.execution, formule, registre)
    if chemin is None:
        print("exécution non scorée (partielle, ou moteur de loss absent)")
        return 1
    page = rendu_scores.ecrire(a.execution, registre)
    print(page or chemin)
    return 0


def cmd_erreurs(a: argparse.Namespace) -> int:
    """Rapproche decisions.jsonl du jeu : tentatives par type, déplacements manquants, journées à trous."""
    from experiences.erreurs import diagnostiquer, formater

    if a.execution:
        dossier = Path(a.execution)
    else:
        exp = _charger_experience_par_nom(a.experience)
        derniere = _derniere_execution(exp)
        if derniere is None:
            print("aucune exécution")
            return 1
        dossier = derniere
    diag = diagnostiquer(dossier)
    print(
        json.dumps(diag, ensure_ascii=False, indent=1, default=str)
        if a.json
        else formater(diag)
    )
    return 0 if diag["nb_manquants"] == 0 else 1


def cmd_reconcilier(a: argparse.Namespace) -> int:
    """Libère les clés des exécutions terminées et des fantômes (pid mort). À lancer DANS le conteneur."""
    from experiences import reservations as R

    liberees = R.reconcilier()
    print(json.dumps({"cles_liberees": liberees}, ensure_ascii=False))
    return 0


def cmd_actives(a: argparse.Namespace) -> int:
    """Expériences qui tiennent au moins une clé. `--est-vide` : code 0 si aucune (services arrêtables)."""
    from experiences import reservations as R

    R.reconcilier()  # dans le conteneur : purge d'abord les fantômes
    actives = R.actives()
    if a.est_vide:
        return 0 if not actives else 1
    print(json.dumps(actives, ensure_ascii=False, indent=1))
    return 0


def cmd_file(a: argparse.Namespace) -> int:
    """Expériences en attente de clé, ordre FIFO."""
    from experiences import reservations as R

    print(json.dumps(R.lister_file(), ensure_ascii=False, indent=1))
    return 0


def cmd_defiler(a: argparse.Namespace) -> int:
    """Retire une expérience de la file avant sa promotion (R2e)."""
    from experiences import reservations as R

    retiree = R.retirer_file(a.experience)
    print(
        f"{a.experience} : {'retirée de la file' if retiree else 'absente de la file'}"
    )
    return 0 if retiree else 1


def cmd_ordonnancer(a: argparse.Namespace) -> int:
    """Boucle d'ordonnancement (hôte) : réconcilie et promeut la file (R2b). Ctrl-C pour arrêter."""
    from experiences.ordonnanceur import boucle

    return boucle(intervalle_s=a.intervalle)


def construire_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="experiences",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="commande", required=True)

    s = sub.add_parser("preparer-jeu")
    s.set_defaults(fn=cmd_preparer_jeu)
    s.add_argument("--population", required=True)
    s.add_argument("--nom", required=True)
    s.add_argument("--dossier")
    s.add_argument("--jour", default="2026-03-16")
    s.add_argument("--concurrence", type=int, default=8)
    s.add_argument(
        "--seuil",
        type=float,
        default=0.05,
        help="part de déplacements sans proposition qui lève l'ALARME",
    )

    s = sub.add_parser("consulter-jeu")
    s.set_defaults(fn=cmd_consulter_jeu)
    s.add_argument("--nom", required=True)
    s.add_argument("--dossier")
    s.add_argument("--personne")
    s.add_argument("--sans-verification", action="store_true")

    s = sub.add_parser("verifier-jeu")
    s.set_defaults(fn=cmd_verifier_jeu)
    s.add_argument("--nom", required=True)
    s.add_argument("--dossier")

    s = sub.add_parser(
        "verifier-jours",
        help="l'offre TC d'un autre jour est-elle celle du jeu ? (services requis)",
    )
    s.set_defaults(fn=cmd_verifier_jours)
    s.add_argument("--nom", required=True)
    s.add_argument("--dossier")
    s.add_argument("--jour", required=True)
    s.add_argument("--methode", choices=("gtfs", "moteurs"), default="gtfs")
    s.add_argument("--gtfs", help="dossier GTFS (défaut : réglage gtfs.gtfs_file)")
    s.add_argument(
        "--fenetre-h",
        type=float,
        default=4.0,
        help="fenêtre temporelle (h) après le départ programmé dans laquelle un passage différent invalide le déplacement",
    )
    s.add_argument("--echantillon", type=int, default=100)
    s.add_argument("--graine", type=int, default=42)
    s.add_argument(
        "--declarer",
        action="store_true",
        help="écrit EQUIVALENCES.yaml (gtfs : validité par déplacement ; moteurs : si 100 %% identique)",
    )

    s = sub.add_parser("definir")
    s.set_defaults(fn=cmd_definir)
    s.add_argument("fichier")
    s.add_argument(
        "--accepter-nom",
        action="store_true",
        help="accepte un `nom` qui n'est pas le nom canonique des paramètres (N13)",
    )

    s = sub.add_parser("dupliquer")
    s.set_defaults(fn=cmd_dupliquer)
    s.add_argument("--de", required=True)
    s.add_argument(
        "--vers",
        help="nom de la copie ; par défaut, calculé depuis ses paramètres (N1)",
    )
    s.add_argument("--decideur-type")
    s.add_argument("--decideur-modele")

    s = sub.add_parser("estimer")
    s.set_defaults(fn=cmd_estimer)
    s.add_argument("--experience", required=True)

    # Attendre la fenêtre est le comportement PAR DÉFAUT depuis le 2026-09-08 : la
    # réouverture est connue (heure annoncée par le fournisseur, ou minuit dans son fuseau),
    # donc l'exécution se termine seule au lieu de mourir sur un quota du jour.
    _AIDE_FENETRE = (
        "accepté et sans effet : attendre la fenêtre de reprise est désormais le défaut "
        "(conservé pour ne pas casser les scripts existants)"
    )
    _AIDE_SANS_FENETRE = (
        "à l'épuisement du quota, NE PAS attendre la fenêtre de reprise : passer `epuisee` "
        "tout de suite (ancien comportement par défaut)"
    )
    s = sub.add_parser("lancer")
    s.add_argument(
        "--ignorer-aptitude",
        action="store_true",
        dest="ignorer_aptitude",
        help="lance malgré un refus d'aptitude (quota, plafonds) — l'avertissement reste affiché",
    )
    s.set_defaults(fn=cmd_lancer)
    s.add_argument("--experience", required=True)
    s.add_argument("--reprendre", action="store_true")
    s.add_argument("--accepter-perime", action="store_true")
    s.add_argument("--attendre-fenetre", action="store_true", help=_AIDE_FENETRE)
    s.add_argument(
        "--ne-pas-attendre-fenetre",
        dest="attendre_fenetre",
        action="store_false",
        default=True,
        help=_AIDE_SANS_FENETRE,
    )

    s = sub.add_parser("reprendre")
    s.add_argument(
        "--ignorer-aptitude",
        action="store_true",
        dest="ignorer_aptitude",
        help="lance malgré un refus d'aptitude (quota, plafonds) — l'avertissement reste affiché",
    )
    s.set_defaults(
        fn=lambda a: cmd_lancer(argparse.Namespace(**{**vars(a), "reprendre": True}))
    )
    s.add_argument("--experience", required=True)
    s.add_argument("--accepter-perime", action="store_true")
    s.add_argument("--attendre-fenetre", action="store_true", help=_AIDE_FENETRE)
    s.add_argument(
        "--ne-pas-attendre-fenetre",
        dest="attendre_fenetre",
        action="store_false",
        default=True,
        help=_AIDE_SANS_FENETRE,
    )

    s = sub.add_parser("pause")
    s.set_defaults(fn=lambda a: _signal_fichier(a, FICHIER_PAUSE))
    s.add_argument("--experience", required=True)
    s = sub.add_parser("arreter")
    s.set_defaults(fn=lambda a: _signal_fichier(a, FICHIER_STOP))
    s.add_argument("--experience", required=True)

    s = sub.add_parser(
        "reconcilier",
        help="libère les clés des exécutions terminées/fantômes (DANS le conteneur)",
    )
    s.set_defaults(fn=cmd_reconcilier)

    s = sub.add_parser(
        "actives", help="expériences tenant une clé ; --est-vide : code 0 si aucune"
    )
    s.set_defaults(fn=cmd_actives)
    s.add_argument("--est-vide", action="store_true")

    s = sub.add_parser("file", help="expériences en attente de clé (FIFO)")
    s.set_defaults(fn=cmd_file)

    s = sub.add_parser("defiler", help="retire une expérience de la file (R2e)")
    s.set_defaults(fn=cmd_defiler)
    s.add_argument("--experience", required=True)

    s = sub.add_parser(
        "ordonnancer", help="boucle hôte : réconcilie et promeut la file d'attente"
    )
    s.set_defaults(fn=cmd_ordonnancer)
    s.add_argument("--intervalle", type=float, default=5.0)

    s = sub.add_parser("registre")
    s.set_defaults(fn=cmd_registre)
    s.add_argument("--trier")
    s.add_argument("--decroissant", action="store_true")
    s.add_argument("--filtrer", action="append")
    s.add_argument("--json", action="store_true")
    s.add_argument(
        "--inclure-masquees",
        action="store_true",
        dest="inclure_masquees",
        help="réaffiche les expériences archivées ou invalidées (masquées par défaut)",
    )

    s = sub.add_parser(
        "statuer",
        help="pose le statut d'une expérience (actif|archivee|invalide) sans rien supprimer",
    )
    s.set_defaults(fn=cmd_statuer)
    s.add_argument("experience", help="nom ou chemin du dossier d'expérience")
    s.add_argument("statut", choices=("actif", "archivee", "invalide"))
    s.add_argument("--motif", help="obligatoire pour archivee et invalide")
    s.add_argument("--reference", help="spec ou ticket qui justifie le statut")
    s.add_argument(
        "--visible",
        action="store_true",
        default=None,
        help="garder la ligne visible au registre malgré le statut",
    )

    s = sub.add_parser("statuts", help="statut de toutes les expériences, masquées comprises")
    s.set_defaults(fn=cmd_statuts)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("comparer")
    s.set_defaults(fn=cmd_comparer)
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--json", action="store_true")
    s.add_argument(
        "--inclure-invalides",
        action="store_true",
        dest="inclure_invalides",
        help="compare malgré une expérience invalidée ou archivée (le statut est rappelé)",
    )
    s = sub.add_parser("synthese")
    s.set_defaults(fn=cmd_synthese)
    s.add_argument("execution")

    s = sub.add_parser(
        "score",
        help="score une exécution (composite + détail par strate) et écrit sa page ; "
        "--toutes recalcule tout l'historique hors-ligne",
    )
    s.set_defaults(fn=cmd_score)
    s.add_argument("execution", nargs="?", help="dossier d'exécution à scorer")
    s.add_argument(
        "--toutes",
        action="store_true",
        help="recalcule toutes les exécutions terminées (rejeu hors-ligne)",
    )
    s.add_argument(
        "--formule", help="nom de formule du registre (défaut : la référence)"
    )

    s = sub.add_parser(
        "erreurs",
        help="rapproche decisions.jsonl du jeu (manquants, journées à trous, tentatives)",
    )
    s.set_defaults(fn=cmd_erreurs)
    s.add_argument(
        "execution",
        nargs="?",
        help="dossier d'exécution ; à défaut --experience prend la dernière",
    )
    s.add_argument(
        "--experience", help="expérience dont on diagnostique la dernière exécution"
    )
    s.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    a = construire_parser().parse_args(argv)
    try:
        return int(a.fn(a))
    except (
        E.ExperienceInvalide,
        J.JeuInvalide,
        J.JeuClos,
        FileNotFoundError,
        ValueError,
    ) as e:  # StatutInvalide et VariantePromptInvalide dérivent de ValueError
        print(f"ERREUR : {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
