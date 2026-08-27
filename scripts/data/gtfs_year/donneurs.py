"""
Choix de la source de chaque journée de l'année.

Deux décisions, dans cet ordre :

1. **Autorité.** Une date couverte par plusieurs exports ne prend son offre que
   dans UN seul. Prendre l'union sur-servirait : le 04/05/2026, deux exports
   donnent respectivement 12 538 et 12 484 trips pour seulement 11 282 en
   commun ; leur union en fabriquerait 13 740. C'est exactement le défaut du
   feed actuellement en service, qui sert 13 250 trips le 08/04 là où ses deux
   sources en donnent 12 652 et 12 660.

2. **Donneur.** Une date sans couverture reçoit la copie verbatim d'une journée
   réelle de même signature — le même jour de semaine dans la même classe de
   période scolaire — en préférant la plus proche dans le temps. Aucun horaire
   n'est synthétisé : ce qui est servi a été publié par l'opérateur, seulement
   pas ce jour-là.

Les dates que la source déclare explicitement sans service (le 1er mai, omis par
les deux exports qui l'englobent) ne sont pas des trous : les extrapoler
inventerait de l'offre un jour férié où le réseau ne roule pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .calendar_fr import Periode, Signature, signature, to_date
from .offre import IndexExport

REEL = "reel"
EXTRAPOLE = "extrapole"
SANS_SERVICE = "sans_service"

HAUTE = "haute"
MOYENNE = "moyenne"
BASSE = "basse"


@dataclass
class Provenance:
    """D'où vient l'offre d'une journée du feed produit."""

    date: str
    signature: str
    mode: str
    confiance: str
    export: str = ""
    date_source: str = ""
    ecart_jours: int = 0
    ecart_saison: int = 0
    motif: str = ""
    nb_trips: int = 0
    nb_lignes: int = 0

    def en_dict(self) -> dict:
        return {
            "date": self.date,
            "signature": self.signature,
            "mode": self.mode,
            "confiance": self.confiance,
            "export": self.export,
            "date_source": self.date_source,
            "ecart_jours": self.ecart_jours,
            "ecart_saison": self.ecart_saison,
            "motif": self.motif,
            "nb_trips": self.nb_trips,
            "nb_lignes": self.nb_lignes,
        }


def autorite(
    index_par_export: dict[str, IndexExport],
    dates_fiables: dict[str, list[str]],
    journal=print,
) -> dict[str, str]:
    """date → étiquette de l'export qui fait autorité ce jour-là.

    En cas de recouvrement, l'export le plus récemment publié gagne : c'est
    celui qui intègre les dernières décisions d'exploitation.
    """
    rang = {
        etiquette: (index.export.date_min, etiquette)
        for etiquette, index in index_par_export.items()
    }
    choix: dict[str, str] = {}
    recouvrements = 0
    for etiquette, dates in dates_fiables.items():
        for date in dates:
            actuel = choix.get(date)
            if actuel is None:
                choix[date] = etiquette
            else:
                recouvrements += 1
                if rang[etiquette] > rang[actuel]:
                    choix[date] = etiquette
    journal(
        f"    autorité : {len(choix)} date(s) réelle(s), "
        f"{recouvrements} recouvrement(s) arbitré(s) en faveur de l'export le plus récent"
    )
    return choix


def _signatures_reelles(
    dates_reelles: list[str],
    periodes: list[Periode],
    feries: dict[str, str],
    decalages: dict[str, int],
) -> dict[str, list[str]]:
    """signature → dates réelles disponibles, triées."""
    par_signature: dict[str, list[str]] = {}
    for date in dates_reelles:
        sig = str(signature(date, periodes, feries, decalages))
        par_signature.setdefault(sig, []).append(date)
    for dates in par_signature.values():
        dates.sort()
    return par_signature


def ecart_saisonnier(date_a: str, date_b: str) -> int:
    """Distance entre deux dates au sens des saisons, en jours.

    C'est la bonne notion de proximité pour choisir un donneur : ce qui compte
    n'est pas le nombre de jours calendaires écoulés mais la ressemblance de la
    période de l'année. Sans cela, un 5 janvier chercherait son donneur à
    259 jours (le 21 septembre) alors que le 16 mars, à 70 jours de saison, lui
    ressemble davantage — et une année entièrement copiée sur la précédente
    n'aurait que des donneurs « lointains ».
    """
    doy_a = to_date(date_a).timetuple().tm_yday
    doy_b = to_date(date_b).timetuple().tm_yday
    ecart = abs(doy_a - doy_b)
    return min(ecart, 365 - ecart)


def _candidats(sig: Signature, config_extrap: dict) -> list[tuple[str, bool]]:
    """Signatures acceptables pour une cible, de la meilleure à la pire.

    Le booléen dit s'il s'agit de la signature exacte. Un férié cherche d'abord
    un autre férié : le 14/07 sert 5 674 trips contre 4 683 à 5 054 pour les
    dimanches de juillet, et le 08/05 4 782 contre 4 644 — traiter un férié
    comme un dimanche se trompe d'environ 10 %.
    """
    types_jour = [sig.type_jour]
    if sig.type_jour == "ferie":
        types_jour = list(config_extrap.get("repli_ferie", ["ferie", "dim"]))

    periodes = [sig.periode] + list(config_extrap.get("repli_periodes", {}).get(sig.periode, []))

    sorties: list[tuple[str, bool]] = []
    for i_periode, periode in enumerate(periodes):
        for i_jour, type_jour in enumerate(types_jour):
            sorties.append((f"{type_jour}/{periode}", i_periode == 0 and i_jour == 0))
    return sorties


def plan_annee(
    annee: int,
    dates_annee: list[str],
    source_par_date: dict[str, str],
    index_par_export: dict[str, IndexExport],
    periodes: list[Periode],
    feries: dict[str, str],
    decalages: dict[str, int],
    config_extrap: dict,
    dates_sans_service: set[str],
    journal=print,
) -> dict[str, Provenance]:
    """Décide, pour chaque jour de l'année, d'où vient son offre."""
    dates_reelles = sorted(source_par_date)
    par_signature = _signatures_reelles(dates_reelles, periodes, feries, decalages)
    ecart_moyenne_max = int(config_extrap["confiance"]["moyenne_si_ecart_jours_max"])

    plan: dict[str, Provenance] = {}
    sans_donneur: list[str] = []

    for date in dates_annee:
        sig = signature(date, periodes, feries, decalages)
        sig_str = str(sig)

        if date in dates_sans_service:
            plan[date] = Provenance(
                date=date,
                signature=sig_str,
                mode=SANS_SERVICE,
                confiance=HAUTE,
                motif="déclaré sans service par la source",
            )
            continue

        if date in source_par_date:
            etiquette = source_par_date[date]
            index = index_par_export[etiquette]
            plan[date] = Provenance(
                date=date,
                signature=sig_str,
                mode=REEL,
                confiance=HAUTE,
                export=etiquette,
                date_source=date,
                nb_trips=index.nb_trips(date),
                nb_lignes=index.lignes_par_date.get(date, 0),
            )
            continue

        meilleur: tuple[int, str, str, bool] | None = None
        for sig_candidate, exacte in _candidats(sig, config_extrap):
            for candidate in par_signature.get(sig_candidate, ()):
                ecart = ecart_saisonnier(date, candidate)
                cle = (ecart, candidate)
                if meilleur is None or cle < (meilleur[0], meilleur[1]):
                    meilleur = (ecart, candidate, sig_candidate, exacte)
            if meilleur is not None:
                break  # un repli moins bon ne peut pas battre un meilleur rang

        if meilleur is None:
            sans_donneur.append(date)
            plan[date] = Provenance(
                date=date,
                signature=sig_str,
                mode=SANS_SERVICE,
                confiance=BASSE,
                motif="aucun donneur de signature compatible",
            )
            continue

        ecart, date_source, sig_source, exacte = meilleur
        if exacte and ecart <= ecart_moyenne_max:
            confiance = MOYENNE
        else:
            confiance = BASSE
        etiquette = source_par_date[date_source]
        index = index_par_export[etiquette]
        plan[date] = Provenance(
            date=date,
            signature=sig_str,
            mode=EXTRAPOLE,
            confiance=confiance,
            export=etiquette,
            date_source=date_source,
            ecart_jours=abs((to_date(date_source) - to_date(date)).days),
            ecart_saison=ecart,
            motif="signature exacte" if exacte else f"repli sur {sig_source}",
            nb_trips=index.nb_trips(date_source),
            nb_lignes=index.lignes_par_date.get(date_source, 0),
        )

    if sans_donneur:
        journal(
            f"[ALARME] {len(sans_donneur)} date(s) sans donneur compatible : "
            f"{', '.join(sans_donneur[:8])}{'…' if len(sans_donneur) > 8 else ''}"
        )

    reels = sum(1 for p in plan.values() if p.mode == REEL)
    extrapoles = sum(1 for p in plan.values() if p.mode == EXTRAPOLE)
    vides = sum(1 for p in plan.values() if p.mode == SANS_SERVICE)
    basses = sum(1 for p in plan.values() if p.confiance == BASSE)
    journal(
        f"    plan {annee} : {reels} jour(s) réel(s), {extrapoles_txt(extrapoles)}, "
        f"{vides} sans service — dont {basses} en confiance basse"
    )
    return plan


def extrapoles_txt(n: int) -> str:  # pragma: no cover - confort de lecture
    return f"{n} extrapolé(s)"
