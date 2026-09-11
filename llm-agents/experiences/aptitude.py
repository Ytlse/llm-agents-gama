"""Aptitude d'un modèle à porter une expérience — refus a priori (spec hygiène §6, P3).

`estimer()` chiffrait déjà le coût prévisionnel ; il ne refusait rien. Cinq exécutions se sont
arrêtées en cours de route faute de quota ou de modèle joignable, et ont dû être archivées sans
avoir rien mesuré. Ce module transforme le chiffrage en verdict.

Deux niveaux, et la distinction est délibérée :

- **refus** — l'exécution ne PEUT PAS aboutir : le quota journalier cumulé est inférieur au
  nombre de sollicitations, ou chaque requête dépasserait le plafond par requête du
  fournisseur (elle serait tronquée). Aucun réglage de patience n'y changerait rien.
- **avertissement** — elle aboutira, mais lentement : le plafond de jetons par minute borne le
  débit sous le `rpm_limit` déclaré. On dit la durée impliquée et on laisse décider.

Ce que ce module NE sait pas : les limites que `providers.yaml` ne déclare pas. L'OTPM
(jetons de SORTIE par minute) des passerelles Groq en est le cas connu — 1 000 mesurés le
2026-09-08, invisibles hors du corps des 429, absents du fichier. Un fournisseur peut donc
passer ce contrôle et brider quand même : c'est ce que P4 (sonde de santé) doit corriger.
"""

from __future__ import annotations

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
) -> tuple[list[str], list[str]]:
    """(refus, avertissements) pour un modèle donné face à une charge donnée.

    `jetons_entree` / `jetons_sortie` : par sollicitation. `None` quand aucune mesure n'existe
    — on ne refuse alors PAS sur les jetons : refuser sur une valeur inconnue reviendrait à
    bloquer tout modèle jamais mesuré, donc tout modèle nouveau.
    """
    refus: list[str] = []
    avert: list[str] = []
    if not instances:
        return refus, avert  # l'absence d'instance est déjà refusée en amont

    par_requete = (jetons_entree or 0) + (jetons_sortie or 0)
    requis = int(sollicitations * MARGE_QUOTA)

    # 1. Quota journalier. Refus seulement si l'écart est absurde ; sinon avertissement,
    # parce qu'une exécution se reprend et peut s'étaler sur plusieurs fenêtres de quota.
    rpd = _somme(providers, instances, "rpd_limit")
    if rpd is not None and rpd > 0 and rpd < requis:
        jours = sollicitations / rpd
        if rpd * FACTEUR_QUOTA_ABSURDE < requis:
            refus.append(
                f"quota journalier hors d'atteinte pour {modele!r} : {rpd} requêtes/jour "
                f"cumulées sur {len(instances)} instance(s) contre {sollicitations} "
                f"sollicitations attendues, soit ~{jours:.0f} jours de quota → choisissez un "
                f"modèle mieux doté, réduisez le jeu, ou passez par un canal sans quota"
            )
        else:
            avert.append(
                f"quota journalier plus court que la charge pour {modele!r} : {rpd} "
                f"requêtes/jour déclarées contre {sollicitations} sollicitations "
                f"(~{jours:.1f} jours) → l'exécution s'étalera sur plusieurs fenêtres, avec "
                f"reprise. Les limites de providers.yaml sont déclaratives et connues comme "
                f"parfois fausses : ce n'est pas un refus"
            )

    # 2. Plafond par requête — chaque appel serait tronqué.
    if par_requete:
        for i in instances:
            plafond = _int_ou_none((providers.get(i) or {}).get("max_tokens_per_request"))
            if plafond is not None and plafond < par_requete:
                refus.append(
                    f"{i} plafonne à {plafond} jetons par requête, or une sollicitation en "
                    f"demande ~{par_requete} (entrée {jetons_entree} + sortie {jetons_sortie}) "
                    f"→ chaque appel serait tronqué ; relevez max_tokens_per_request ou changez d'instance"
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
    if rpm and par_requete:
        rpm_effectif = rpm
        if tpm:
            rpm_par_tpm = tpm / par_requete
            if rpm_par_tpm < rpm:
                rpm_effectif = rpm_par_tpm
                avert.append(
                    f"débit bridé par les jetons : tpm cumulé {tpm} ÷ ~{par_requete} jetons par "
                    f"sollicitation = {rpm_par_tpm:.1f} requêtes/min effectives, contre "
                    f"rpm_limit {rpm} déclaré"
                )
        duree = sollicitations / rpm_effectif * 60
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
    sollicitations = ((est.get("sollicitations") or {}).get("valeur")) or 0
    j = est.get("jetons") or {}
    par = j.get("par_sollicitation") or {}
    return verifier(
        modele=exp.decideur.modele,
        sollicitations=int(sollicitations),
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
