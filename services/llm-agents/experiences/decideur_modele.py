"""Décideur « modèle statistique » (LightGBM, logit multinomial ou KLR) — spec R11..R15.

Un décideur de plus, au même contrat que la passerelle LLM
(`Decideur.choisir(person, ctx, presentees)`) : il ne score pas en parallèle, il
**décide**. On peut donc relancer une expérience (avec ou sans simulateur) en
échangeant seulement le décideur, et la version du modèle est scellée par SHA
dans l'empreinte de l'exécution (R12).

Rien de la prédiction n'est réécrit : `persona_features`, `renormalize`,
`load_policy` et `predict` sont importés de `scripts/synthesis/model_on_common_set.py`,
et l'encodage vient du script d'entraînement. C'est la seule façon de ne pas
introduire de décalage silencieux entre l'entraînement et la décision.

Cas **non imputables** (RG-2, R13) — persona sans traits, aucune offre de mode
prédictible, OD hors de la couche de zones : le décideur rend une **non-décision
explicite** (`non_imputable`), jamais un repli silencieux vers un mode.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from experiences.chemins import racine_depot
from experiences.decision import (
    ContexteDecision,
    Proposition,
    ReponseDecideur,
    graine_ordre,
)
from loguru import logger
from models import Person

REPO_ROOT = racine_depot()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.synthesis.model_on_common_set import (
    CANONICAL_TO_CAT,
    PREDICTABLE_CATS,
    STATUS_OK,
    load_policy,
    persona_features,
    predict,
)

# Chemins par défaut des artefacts (mêmes que scripts/synthesis/sources.yaml).
POLICY_DEFAUT = REPO_ROOT / "scripts" / "progedo_logit" / "mode_choice_policy.json"
SPEC_DEFAUT = REPO_ROOT / "scripts" / "progedo_logit" / "feature_spec.json"

# Format d'artefact → nom de famille, pour les libellés de trace.
#
# **Pourquoi une table et non une constante.** Deux familles de modèles passent par ce
# décideur depuis le ticket 042 — le booster supervisé et le logit multinomial de parité
# stricte — et elles empruntent le MÊME chemin de décision. Tant que le nom du décideur,
# l'empreinte et la réponse brute portaient « lightgbm » en dur, une exécution du logit
# s'annonçait LightGBM : le SHA de l'artefact restait juste (R12), mais toute comparaison
# lue dans les traces désignait le mauvais modèle. Un libellé faux est pire qu'un libellé
# absent, parce qu'il ne se remarque pas.
FAMILLES = {
    "lightgbm_mode_choice_policy": "lightgbm",
    "mnl_mode_choice_policy": "mnl",
    # Ticket 043 : la logistique à noyau rejoint la table sans autre changement — c'est
    # tout l'intérêt d'un libellé DÉRIVÉ du format plutôt qu'écrit en dur.
    "klr_mode_choice_policy": "klr",
    # PAS de `rf_mode_choice_policy` ici, et c'est délibéré (ticket 044, règle R7) : le témoin
    # random forest ne doit pas devenir un ARBITRE. Son lanceur dédié
    # (`scripts/progedo_logit/lancer_experience_rf.py`) inscrit sa famille dans cette table
    # POUR LA DURÉE DE SON PROCESSUS et remplace `load_policy` dans l'espace de noms du
    # décideur — l'exécution produite est une vraie exécution de la plateforme, sans que les
    # modules de score connaissent le témoin.
}


def _sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _resoudre(chemin: str | Path) -> Path:
    """Chemin d'artefact, absolu tel quel, relatif résolu depuis la racine du dépôt."""
    p = Path(chemin)
    return p if p.is_absolute() else REPO_ROOT / p


def _page_cat(mode: str) -> str:
    """Mode d'une proposition → catégorie de la page (via le mode canonique)."""
    from mobility_llm.mode_choice import canonical_mode

    return CANONICAL_TO_CAT.get(canonical_mode(mode), "other")


def _purpose_origin(person: Person, activity_id: str) -> str | None:
    """Motif de l'activité d'origine — la précédente dans la chaîne cyclique du persona.

    Même logique que `model_on_common_set.activity_index` : l'origine du premier
    déplacement est la dernière activité (chaîne cyclique). Aucune valeur inventée :
    activité introuvable → None (le contrat routera la variable en manquante)."""
    activities = getattr(person.identity, "activities", None) or []
    for i, act in enumerate(activities):
        if getattr(act, "id", None) == activity_id:
            origine = activities[i - 1]
            return getattr(origine, "purpose", None)
    return None


class DecideurModele:
    """Politique statistique LightGBM comme décideur. Déterministe, sans quota."""

    sans_quota = True

    def __init__(
        self,
        artefact: str | Path | None = None,
        spec: str | Path | None = None,
        zones: str | Path | None = None,
    ):
        # Un chemin relatif est résolu depuis la racine du dépôt, pas depuis le dossier
        # courant : l'`experience.yaml` doit désigner le même artefact sur l'hôte et dans le
        # conteneur, et `empreinte()` a besoin d'un chemin relatif À CETTE racine (R12).
        self.policy_path = _resoudre(artefact) if artefact else POLICY_DEFAUT
        self.spec_path = Path(spec) if spec else SPEC_DEFAUT
        # R14 — refus de démarrer si un artefact obligatoire manque : pas de décision
        # dégradée, l'exécution ne commence pas.
        for label, p in (
            ("policy", self.policy_path),
            ("feature_spec", self.spec_path),
        ):
            if not p.exists():
                raise FileNotFoundError(
                    f"Décideur modèle : {label} introuvable ({p}). "
                    "Entraînez la politique (make policy) avant de lancer une expérience modèle."
                )
        self._spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        self._booster, self._artefact = load_policy(self.policy_path, self._spec)
        self.sha256 = _sha256(self.policy_path)
        self._resolver = self._charger_resolver(zones)
        self.format = self._artefact.get("format")
        # Un format hors table est refusé plutôt que nommé « inconnu » : le nom du décideur
        # entre dans le nom canonique de l'expérience et dans ses traces.
        if self.format not in FAMILLES:
            raise ValueError(
                f"Décideur modèle : format d'artefact non reconnu ({self.format!r}). "
                f"Formats connus : {sorted(FAMILLES)}."
            )
        self.famille = FAMILLES[self.format]
        self.nom = f"modele:{self.famille}@{self.sha256[:12]}"
        logger.info(
            f"[decideur] Modèle {self.famille} chargé ({self.format}) — spec "
            f"v{self._spec.get('spec_version')}, artefact {self.sha256[:12]}, "
            f"résolveur de zones {'prêt' if self._resolver is not None else 'ABSENT'}"
        )

    def _charger_resolver(self, zones: str | Path | None):
        # R14 — la couche de zones est obligatoire : les 6 variables géographiques
        # (dont od_km, la première du modèle) en dépendent. Absente → refus.
        from mobility_core.zone_resolver import ZoneResolver

        return ZoneResolver.load(
            Path(zones) if zones else None, feature_spec=self.spec_path
        )

    def empreinte(self) -> dict:
        """Ce qui scelle la version du modèle dans l'empreinte de l'exécution (R12)."""
        return {
            "type": "modele",
            "modele": self.format,
            "famille": self.famille,
            "artefact": str(self.policy_path.relative_to(REPO_ROOT)),
            "sha256": self.sha256,
            "spec_version": self._spec.get("spec_version"),
        }

    def _construire_ligne(
        self, person: Person, ctx: ContexteDecision, offered_predictable: list[str]
    ) -> dict | None:
        """Une ligne de features pour la politique, ou None si l'OD est hors couche."""
        traits = getattr(person.identity, "traits_json", None) or {}
        origin = ctx.from_location
        dest = ctx.destination
        if origin is None or dest is None:
            return None
        geo = self._resolver.geo_features_many(
            [(float(origin.lat), float(origin.lon))],
            [(float(dest.lat), float(dest.lon))],
        )
        if not geo or geo[0] is None:
            return None  # OD hors de la couche de zones (R13)
        heure = datetime.fromtimestamp(int(ctx.departure_time), tz=timezone.utc).hour
        ligne = {
            "agent_id": person.person_id,
            "activity_id": ctx.activity_id,
            "offered_predictable": "|".join(offered_predictable),
            "status": STATUS_OK,
            "purpose": ctx.purpose,
            "purpose_origin": _purpose_origin(person, ctx.activity_id),
            "departure_hour": heure,
            **persona_features(traits),
            **geo[0].as_dict(),
        }
        return ligne

    async def choisir(
        self, person: Person, ctx: ContexteDecision, presentees: list[Proposition]
    ) -> ReponseDecideur:
        from experiences.decideurs import _distribution, _presente_local

        traits = getattr(person.identity, "traits_json", None) or {}
        if not traits:
            return self._non_imputable("persona_sans_traits", presentees)

        cats = [_page_cat(p.mode) for p in presentees]
        offered_predictable = sorted({c for c in cats if c in PREDICTABLE_CATS})
        if not offered_predictable:
            return self._non_imputable("offre_sans_mode_predictible", presentees)

        ligne = self._construire_ligne(person, ctx, offered_predictable)
        if ligne is None:
            return self._non_imputable("od_hors_couche_zones", presentees)

        predict([ligne], self._booster, self._spec)
        if ligne.get("status") != STATUS_OK:
            # Le modèle n'accorde aucune masse à ce qui est offert : pas de distribution.
            return self._non_imputable("modele_sans_masse_offerte", presentees)

        # Masse renormalisée par catégorie → poids par proposition présentée, en
        # répartissant la masse d'une catégorie également entre ses propositions.
        par_cat = {c: cats.count(c) for c in offered_predictable}
        poids = [
            (ligne.get(f"p_{c}", 0.0) / par_cat[c]) if c in offered_predictable else 0.0
            for c in cats
        ]
        total = sum(poids)
        if total <= 0:
            return self._non_imputable("poids_nuls", presentees)
        poids = [w / total for w in poids]

        idx = self._tirer(
            poids, graine_ordre(ctx.graine_tirage, person.person_id, ctx.activity_id)
        )
        brut = {f"p_{c}": ligne.get(f"p_{c}") for c in PREDICTABLE_CATS}
        brut.update({f"p_raw_{c}": ligne.get(f"p_raw_{c}") for c in PREDICTABLE_CATS})
        return ReponseDecideur(
            index=idx,
            fournisseur=self.nom,
            distribution=_distribution(poids, presentees),
            poids=poids,
            reponse_brute=json.dumps(
                {"modele": self.famille, **brut}, ensure_ascii=False
            ),
            raison="modèle statistique (masse renormalisée sur l'offre)",
            presente=_presente_local(presentees),
        )

    @staticmethod
    def _tirer(poids: list[float], graine: int) -> int:
        """Tire un index proportionnellement aux poids (déterministe, comme le LLM)."""
        r = random.Random(graine).random() * sum(poids)
        cumul = 0.0
        for i, w in enumerate(poids):
            cumul += w
            if r <= cumul:
                return i
        return len(poids) - 1

    def _non_imputable(
        self, raison: str, presentees: list[Proposition]
    ) -> ReponseDecideur:
        from experiences.decideurs import _presente_local

        logger.debug(f"[decideur] modèle non imputable ({raison}) — non-décision")
        return ReponseDecideur(
            index=None,
            fournisseur=self.nom,
            non_imputable=True,
            raison=f"modele_non_imputable:{raison}",
            presente=_presente_local(presentees),
        )


__all__ = ["DecideurModele"]
