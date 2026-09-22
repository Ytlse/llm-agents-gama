"""Aptitude d'un modèle à porter une expérience — refus a priori (spec hygiène §6, P3).

`estimer()` chiffrait déjà le coût prévisionnel ; il ne refusait rien. Cinq exécutions se sont
arrêtées en cours de route faute de quota ou de modèle joignable, et ont dû être archivées sans
avoir rien mesuré. Ce module transforme le chiffrage en verdict.

Deux niveaux, et la distinction est délibérée :

- **refus** — l'exécution ne PEUT PAS aboutir : un seul agent dépasserait le plafond par
  requête du fournisseur (chaque appel serait tronqué), ou les réglages de réflexion
  partiraient en 400. Aucun réglage de patience n'y changerait rien.
- **avertissement** — elle aboutira, mais lentement : le plafond de jetons par minute borne le
  débit sous le `rpm_limit` déclaré. On dit la durée impliquée et on laisse décider.

Deux unités, à ne jamais confondre : une **sollicitation** est un déplacement à décider, une
**requête** est un appel fournisseur, et la passerelle fusionne plusieurs agents par appel. Les
quotas se comptent en requêtes ; c'est `experiences/lots.py` qui fournit le diviseur et
`estimer()` qui l'applique. Sans mesure, ce diviseur vaut 1 et l'on retombe sur l'hypothèse
d'avant le 2026-09-22 : la prudence ne peut pas baisser.

Ce que ce module NE sait pas : les limites que `providers.yaml` ne déclare pas. L'OTPM
(jetons de SORTIE par minute) des passerelles Groq en est le cas connu — 1 000 mesurés le
2026-09-08, invisibles hors du corps des 429, absents du fichier. Un fournisseur peut donc
passer ce contrôle et brider quand même : c'est ce que P4 (sonde de santé) doit corriger.
"""

from __future__ import annotations

import math
from typing import Any

# Marge de sécurité sur le quota journalier : une exécution qui consommerait exactement le
# quota au jeton près échoue sur la première erreur réessayée.
MARGE_QUOTA = 1.05

# Un quota journalier inférieur à la charge n'est PAS une impossibilité : une exécution se
# reprend au déplacement près (S9) et peut donc s'étaler sur plusieurs fenêtres de quota.
# C'est mesuré : des runs sur `gemini-3.5-flash-lite` ont abouti alors que le `rpd_limit`
# déclaré (2 × 500) est inférieur à leurs 2 048 sollicitations — soit la limite réelle est
# plus haute, soit la comptabilité RPD du fichier est fausse (cf. P4, sonde de santé).
# On ne refuse donc que l'absurde : au-delà de ce facteur, aucun étalement raisonnable ne
# rattrape l'écart (20 requêtes/jour pour 2 285 sollicitations = 114 jours).
FACTEUR_QUOTA_ABSURDE = 10

# Au-delà, on avertit sur la durée : une exécution de plus de 6 h traverse une fenêtre de
# renouvellement de quota et se met en attente au milieu.
SEUIL_DUREE_AVERTISSEMENT_S = 6 * 3600


def _int_ou_none(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _somme(providers: dict[str, dict], instances: list[str], cle: str) -> int | None:
    """Somme d'une limite sur les instances qui la déclarent. None si aucune ne la déclare."""
    vals = [
        _int_ou_none((providers.get(i) or {}).get(cle))
        for i in instances
    ]
    connus = [v for v in vals if v is not None]
    return sum(connus) if connus else None


def verifier(
    *,
    modele: str | None,
    sollicitations: int,
    jetons_entree: int | None,
    jetons_sortie: int | None,
    max_tokens_demande: int | None,
    providers: dict[str, dict],
    instances: list[str],
    reflexion_demandee: int | None = None,
    niveau_demande: str | None = None,
    requetes: int | None = None,
    regroupement: dict | None = None,
) -> tuple[list[str], list[str]]:
    """(refus, avertissements) pour un modèle donné face à une charge donnée.

    `jetons_entree` / `jetons_sortie` : par sollicitation, c'est-à-dire par AGENT. `None` quand
    aucune mesure n'existe — on ne refuse alors PAS sur les jetons : refuser sur une valeur
    inconnue reviendrait à bloquer tout modèle jamais mesuré, donc tout modèle nouveau.

    `sollicitations` compte des DÉPLACEMENTS ; `requetes` compte des APPELS FOURNISSEUR, qui en
    regroupent plusieurs (micro-batching de la passerelle). Un quota `rpd_limit` se compare aux
    seconds, jamais aux premiers : la passerelle en groupe huit par requête, et les confondre
    faisait crier au quota court des bras qui tenaient largement (ticket 073 § 4). `requetes=None` retombe sur
    `sollicitations`, c'est-à-dire sur l'hypothèse la plus prudente — aucun regroupement.
    """
    refus: list[str] = []
    avert: list[str] = []
    if not instances:
        return refus, avert  # l'absence d'instance est déjà refusée en amont

    par_agent = (jetons_entree or 0) + (jetons_sortie or 0)
    appels = int(requetes) if requetes else int(sollicitations)
    facteur = (regroupement or {}).get("prudent") or (
        sollicitations / appels if appels else 1
    )
    dit_regroupement = (
        f" (regroupement retenu {float(facteur):.2f} agent(s)/requête ; "
        f"{(regroupement or {}).get('source', 'aucune mesure : une requête par déplacement')})"
    )
    # Ce que le bras coûtera vraisemblablement, à côté de ce qu'on retient pour décider. Sans
    # exécution archivée exploitable, le chiffre prudent vaut le nombre de déplacements — dire
    # l'attendu à côté évite de lire un avertissement de quota sans savoir qu'il est bâti sur
    # l'hypothèse la plus défavorable, et que le plafond dérivé promet huit fois moins.
    attendu = (regroupement or {}).get("attendu")
    dit_attendu = ""
    if attendu and float(attendu) > float(facteur):
        appels_attendus = max(1, math.ceil(sollicitations / float(attendu)))
        dit_attendu = (
            f" — attendu plutôt ~{appels_attendus} requêtes à {float(attendu):.2f} "
            f"agent(s)/requête, mais aucune mesure ne le garantit encore"
        )
    requis = int(appels * MARGE_QUOTA)

    # 1. Quota journalier. Uniquement un avertissement : une exécution se reprend et peut
    # s'étaler sur plusieurs fenêtres de quota. Les limites déclaratives de providers.yaml
    # ou les estimations brutes de déplacements ne doivent jamais bloquer un lancement légitime.
    rpd = _somme(providers, instances, "rpd_limit")
    if rpd is not None and rpd > 0 and rpd < requis:
        jours = appels / rpd
        avert.append(
            f"quota journalier plus court que la charge pour {modele!r} : {rpd} "
            f"requêtes/jour déclarées contre ~{appels} requêtes pour {sollicitations} "
            f"déplacements{dit_regroupement} (~{jours:.1f} jours) → l'exécution s'étalera sur "
            f"plusieurs fenêtres, avec reprise. Les limites de providers.yaml sont déclaratives "
            f"et connues comme parfois fausses : ce n'est pas un refus{dit_attendu}"
        )

    # 2. Plafond par requête — chaque appel serait tronqué.
    #
    # Comparé à UN agent, pas au lot : un lot trop gros n'est pas un refus, la passerelle le
    # réduit d'elle-même (`max_tokens_per_request` borne `batch_max_agents`, cf.
    # `llm_gateway.core.batching.compute_batch_max_agents`). C'est l'agent seul qui ne tient pas
    # dans une requête qui est structurel, et qu'aucun réglage de patience ne rattrape.
    if par_agent:
        for i in instances:
            plafond = _int_ou_none((providers.get(i) or {}).get("max_tokens_per_request"))
            if plafond is not None and plafond < par_agent:
                refus.append(
                    f"{i} plafonne à {plafond} jetons par requête, or UNE sollicitation en "
                    f"demande ~{par_agent} (entrée {jetons_entree} + sortie {jetons_sortie}) "
                    f"→ chaque appel serait tronqué, même sans regroupement ; relevez "
                    f"max_tokens_per_request ou changez d'instance"
                )
    if max_tokens_demande:
        for i in instances:
            sortie_max = _int_ou_none((providers.get(i) or {}).get("max_output_tokens"))
            if sortie_max is not None and sortie_max < max_tokens_demande:
                refus.append(
                    f"{i} plafonne la sortie à {sortie_max} jetons, or l'expérience demande "
                    f"max_tokens={max_tokens_demande} → abaissez max_tokens ou changez d'instance"
                )

    # 2 bis-a. Les deux réglages de réflexion ensemble : l'API rend 400.
    if niveau_demande and reflexion_demandee is not None:
        refus.append(
            f"thinking_level={niveau_demande!r} et thinking_budget={reflexion_demandee} "
            "demandés ensemble : l'API les refuse conjointement (400) → n'en garder qu'un, "
            "`thinking_level` étant le réglage courant"
        )

    # 2 bis-b. Niveau de réflexion non accepté par le modèle — 400 à chaque appel.
    if niveau_demande:
        for i in instances:
            connus = (providers.get(i) or {}).get("thinking_levels")
            if connus and niveau_demande not in connus:
                refus.append(
                    f"niveau de réflexion {niveau_demande!r} non accepté par {i} "
                    f"(déclarés : {', '.join(connus)}) → chaque appel partirait en 400"
                )
        if not any((providers.get(i) or {}).get("thinking_levels") for i in instances):
            avert.append(
                f"niveau de réflexion {niveau_demande!r} demandé, mais aucun "
                f"`thinking_levels` n'est déclaré pour {modele!r} : impossible de vérifier "
                f"que le modèle l'accepte"
            )

    # 2 bis. Profondeur de réflexion au-delà du plafond déclaré — refus, parce que le
    # fournisseur raboterait sans le dire et l'empreinte porterait un budget non appliqué.
    if reflexion_demandee is not None and reflexion_demandee > 0:
        for i in instances:
            plafond = _int_ou_none((providers.get(i) or {}).get("thinking_budget_max"))
            if plafond is not None and reflexion_demandee > plafond:
                refus.append(
                    f"profondeur de réflexion {reflexion_demandee} au-delà du plafond déclaré "
                    f"{plafond} de {i} → le fournisseur la raboterait sans le signaler et "
                    f"l'empreinte porterait un budget non appliqué ; abaissez thinking_budget "
                    f"ou corrigez thinking_budget_max"
                )
        if not any((providers.get(i) or {}).get("thinking_budget_max") for i in instances):
            avert.append(
                f"profondeur de réflexion {reflexion_demandee} demandée, mais aucun "
                f"`thinking_budget_max` n'est déclaré pour {modele!r} : impossible de vérifier "
                f"qu'elle sera appliquée telle quelle"
            )

    # 3. Débit — l'exécution aboutit, mais le plafond de jetons par minute borne le rythme.
    rpm = _somme(providers, instances, "rpm_limit")
    tpm = _somme(providers, instances, "tpm_limit")
    if rpm and par_agent:
        rpm_effectif = rpm
        # Les jetons d'UNE requête sont ceux de tous les agents qu'elle porte. Le bornage par
        # le TPM est donc insensible au regroupement (n·jetons_agent ÷ tpm des deux côtés) ;
        # celui par le RPM, lui, est divisé d'autant. C'est la raison d'être de la distinction.
        jetons_par_appel = max(1, int(par_agent * float(facteur)))
        if tpm:
            rpm_par_tpm = tpm / jetons_par_appel
            if rpm_par_tpm < rpm:
                rpm_effectif = rpm_par_tpm
                avert.append(
                    f"débit bridé par les jetons : tpm cumulé {tpm} ÷ ~{jetons_par_appel} jetons "
                    f"par requête ({par_agent} par agent × {float(facteur):.2f}) = "
                    f"{rpm_par_tpm:.1f} requêtes/min effectives, contre rpm_limit {rpm} déclaré"
                )
        duree = appels / rpm_effectif * 60
        if duree > SEUIL_DUREE_AVERTISSEMENT_S:
            avert.append(
                f"durée estimée ~{duree / 3600:.1f} h à {rpm_effectif:.1f} requêtes/min : "
                f"l'exécution traversera une fenêtre de renouvellement de quota et se mettra "
                f"en attente en cours de route"
            )
    return refus, avert


def verifier_depuis_estimation(
    exp, est: dict, providers: dict[str, dict], instances: list[str]
) -> tuple[list[str], list[str]]:
    """Adaptateur : lit la sortie de `experience.estimer()` plutôt que ses entrées."""
    deplacements = (
        (est.get("deplacements") or {}).get("valeur")
        or (est.get("sollicitations") or {}).get("valeur")
        or 0
    )
    j = est.get("jetons") or {}
    par = j.get("par_sollicitation") or {}
    # `prudente` est le chiffre qui décide (cf. `lots.facteurs`) : sans mesure il vaut le nombre
    # de déplacements, donc le verdict ne peut pas devenir plus permissif qu'avant la correction.
    appels = (est.get("requetes") or {}).get("prudente")
    return verifier(
        modele=exp.decideur.modele,
        sollicitations=int(deplacements),
        requetes=int(appels) if appels else None,
        regroupement=est.get("regroupement"),
        jetons_entree=_int_ou_none(par.get("entree")),
        jetons_sortie=_int_ou_none(par.get("sortie")),
        max_tokens_demande=_int_ou_none((exp.decideur.parametres or {}).get("max_tokens")),
        providers=providers,
        instances=instances,
        reflexion_demandee=_int_ou_none((exp.decideur.parametres or {}).get("thinking_budget")),
        niveau_demande=(exp.decideur.parametres or {}).get("thinking_level"),
    )


__all__ = ["FACTEUR_QUOTA_ABSURDE",
           "MARGE_QUOTA", "SEUIL_DUREE_AVERTISSEMENT_S", "verifier", "verifier_depuis_estimation"]
