"""LM Studio vu du tableau de bord : le modèle local est-il chargé, avec assez de contexte ?

Le tableau de bord tourne sur la machine hôte, là où LM Studio sert ses modèles (port 1234) ;
la passerelle, elle, les joint depuis les conteneurs par `host.docker.internal`. Ce module lit
`GET /api/v1/models` de LM Studio — quels modèles sont téléchargés, lesquels sont chargés, avec
quel contexte — et en tire un diagnostic à afficher, ainsi que les variables de
`make lmstudio-charger`.

Pourquoi : le 2026-09-08, une expérience lancée sur Muse Glimmer a tourné sept minutes sans une
décision. Le modèle n'était pas chargé ; LM Studio l'a chargé à la volée, plus lentement que les
120 s de l'adaptateur, et une fois chargé son contexte par défaut (4 096 jetons) ne tenait pas un
lot de deux agents. Rien dans l'interface ne le disait.

Alias local : quand l'identifiant d'un modèle LM Studio est aussi celui d'un fournisseur distant
(`qwen/qwen3.8-27b` chez Groq), l'instance locale porte un alias suffixé `-local`, chargé par
`lms load <clé> --identifier <alias>`. La clé source se retrouve en retirant le suffixe et en
cherchant la clé dont le dernier segment correspond (`qwen3.8-27b-local` → `qwen/qwen3.8-27b`).

Tout est pur sauf `etat_lmstudio` (un GET local, 1,5 s de délai) : le reste se teste sur des
réponses JSON figées.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

PORT_LMSTUDIO = 1234
URL_HOTE_DEFAUT = f"http://localhost:{PORT_LMSTUDIO}"
CTX_MIN = 8192          # deux agents par requête ≈ 4 400 jetons de prompt, plus la réponse
CTX_CHARGEMENT = 16384  # ce que `make lmstudio-charger` demande
SUFFIXE_ALIAS = "-local"
_HOTES_VERS_LOCALHOST = ("host.docker.internal", "gateway.docker.internal")
_HOTES_LOCAUX = _HOTES_VERS_LOCALHOST + ("localhost", "127.0.0.1")

MOTIF_INJOIGNABLE = (f"LM Studio est injoignable sur localhost:{PORT_LMSTUDIO} — ouvrez LM Studio et démarrez son "
                     "serveur (onglet Developer → Start Server, ou `lms server start`)")


def _n(x: Optional[int]) -> str:
    """16384 → « 16 384 », pour les libellés."""
    return "?" if x is None else f"{int(x):,}".replace(",", " ")


# ── providers.yaml : qui est servi par LM Studio ────────────────────────────

def _providers(d) -> dict:
    if not isinstance(d, dict):
        return {}
    interne = d.get("providers")
    return interne if isinstance(interne, dict) else d


def est_instance_lmstudio(cfg) -> bool:
    """Une instance dont le `base_url` vise le port de LM Studio sur l'hôte (vu des conteneurs ou de l'hôte)."""
    if not isinstance(cfg, dict):
        return False
    u = urlsplit(str(cfg.get("base_url") or ""))
    if u.hostname not in _HOTES_LOCAUX:
        return False
    return (u.port or (443 if u.scheme == "https" else 80)) == PORT_LMSTUDIO


def url_hote(base_url: str) -> str:
    """L'URL de LM Studio depuis l'hôte : `host.docker.internal` (vu des conteneurs) devient `localhost`."""
    u = urlsplit(str(base_url or ""))
    hote = "localhost" if u.hostname in _HOTES_VERS_LOCALHOST else (u.hostname or "localhost")
    return urlunsplit((u.scheme or "http", f"{hote}:{u.port or PORT_LMSTUDIO}", "", "", ""))


def instances_lmstudio(providers) -> dict[str, dict]:
    return {nom: cfg for nom, cfg in _providers(providers).items() if est_instance_lmstudio(cfg)}


def modeles_locaux(providers) -> dict[str, list[str]]:
    """modèle (`default_model`) → instances LM Studio qui le servent."""
    out: dict[str, list[str]] = {}
    for nom, cfg in instances_lmstudio(providers).items():
        if cfg.get("default_model"):
            out.setdefault(str(cfg["default_model"]), []).append(nom)
    return dict(sorted(out.items()))


def modeles_distants(providers) -> dict[str, list[str]]:
    """modèle → instances d'un fournisseur distant (tout ce qui n'est pas LM Studio)."""
    out: dict[str, list[str]] = {}
    for nom, cfg in _providers(providers).items():
        if isinstance(cfg, dict) and cfg.get("default_model") and not est_instance_lmstudio(cfg):
            out.setdefault(str(cfg["default_model"]), []).append(nom)
    return dict(sorted(out.items()))


# ── LM Studio : ce qui est téléchargé, ce qui est chargé ────────────────────

def analyser(payload) -> dict:
    """La réponse de `GET /api/v1/models`, réduite à ce qui compte.

    {"modeles": {clé: {"type", "params", "format", "quant", "ctx_max", "charges": [{"id", "ctx"}]}},
     "charges": {identifiant chargé: {"cle": clé source, "ctx": contexte chargé}}}
    Un modèle chargé sous un alias apparaît dans `charges` sous cet alias, avec sa clé source.
    """
    modeles: dict[str, dict] = {}
    charges: dict[str, dict] = {}
    for m in (payload or {}).get("models") or []:
        if not isinstance(m, dict) or not m.get("key"):
            continue
        cle = str(m["key"])
        instances = []
        for i in m.get("loaded_instances") or []:
            ident = str((i or {}).get("id") or cle)
            ctx = ((i or {}).get("config") or {}).get("context_length")
            ctx = int(ctx) if isinstance(ctx, (int, float)) else None
            instances.append({"id": ident, "ctx": ctx})
            charges[ident] = {"cle": cle, "ctx": ctx}
        q = m.get("quantization")
        modeles[cle] = {"type": m.get("type"), "params": m.get("params_string"), "format": m.get("format"),
                        "quant": q.get("name") if isinstance(q, dict) else q,
                        "ctx_max": m.get("max_context_length"), "charges": instances}
    return {"modeles": modeles, "charges": charges}


def etat_lmstudio(url: str = URL_HOTE_DEFAUT, timeout: float = 1.5) -> Optional[dict]:
    """L'état de LM Studio (cf. `analyser`), ou None s'il est injoignable — serveur arrêté, application fermée."""
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/v1/models", timeout=timeout) as r:  # noqa: S310 — URL locale
            return analyser(json.loads(r.read().decode("utf-8")))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def resoudre_source(identifiant: str, etat: Optional[dict]) -> Optional[str]:
    """La clé LM Studio derrière un `default_model` : la clé elle-même, l'alias déjà chargé, ou l'alias `-local`."""
    if not etat or not identifiant:
        return None
    if identifiant in etat["modeles"]:
        return identifiant
    charge = etat["charges"].get(identifiant)
    if charge:
        return charge["cle"]
    if identifiant.endswith(SUFFIXE_ALIAS):
        base = identifiant[: -len(SUFFIXE_ALIAS)]
        candidats = [c for c in etat["modeles"] if c == base or c.rsplit("/", 1)[-1] == base]
        if len(candidats) == 1:
            return candidats[0]
    return None


@dataclass
class Diagnostic:
    identifiant: str
    pret: bool
    motif: Optional[str] = None
    source: Optional[str] = None        # clé LM Studio à charger (`lms load`)
    contexte: Optional[int] = None      # contexte de l'instance chargée sous `identifiant`, si elle existe
    recharger: bool = False             # quelque chose d'inutilisable est chargé (contexte court, mauvais identifiant)
    autres_charges: list[str] = field(default_factory=list)  # les autres modèles en mémoire
    params: Optional[str] = None
    format: Optional[str] = None
    quant: Optional[str] = None

    @property
    def etat_court(self) -> str:
        if self.pret:
            return f"🟢 chargé, contexte {_n(self.contexte)}"
        if self.motif == MOTIF_INJOIGNABLE:
            return "⚫ LM Studio injoignable"
        if self.source is None:
            return "❓ inconnu de LM Studio"
        if self.contexte is not None:
            return f"🔴 chargé, contexte {_n(self.contexte)} < {_n(CTX_MIN)}"
        return "⚪ non chargé"


def diagnostic(identifiant: str, etat: Optional[dict], ctx_min: int = CTX_MIN) -> Diagnostic:
    """Prêt, ou pourquoi pas : injoignable, inconnu, non chargé, chargé sous un autre nom, contexte trop court."""
    if etat is None:
        return Diagnostic(identifiant, False, motif=MOTIF_INJOIGNABLE)
    autres = sorted(i for i in etat["charges"] if i != identifiant)
    source = resoudre_source(identifiant, etat)
    if source is None:
        return Diagnostic(identifiant, False, autres_charges=autres,
                          motif=f"« {identifiant} » ne correspond à aucun modèle téléchargé dans LM Studio, ni comme "
                                f"clé (`lms ls`), ni comme alias `{SUFFIXE_ALIAS}` d'une clé")
    info = etat["modeles"].get(source) or {}
    d = Diagnostic(identifiant, False, source=source, autres_charges=autres,
                   params=info.get("params"), format=info.get("format"), quant=info.get("quant"))
    charge = etat["charges"].get(identifiant)
    if charge is None:
        if identifiant != source and any(c["id"] == source for c in info.get("charges", [])):
            d.recharger = True
            d.motif = (f"« {source} » est chargé, mais pas sous l'identifiant « {identifiant} » qu'attend la "
                       f"passerelle — il faut le décharger puis le charger avec cet alias")
        else:
            d.motif = f"le modèle « {identifiant} » n'est pas chargé dans LM Studio"
        return d
    d.contexte = charge["ctx"]
    if d.contexte is not None and d.contexte < ctx_min:
        d.recharger = True
        d.motif = (f"« {identifiant} » est chargé avec {_n(d.contexte)} jetons de contexte, il en faut au moins "
                   f"{_n(ctx_min)} (deux agents par requête) — il faut le décharger puis le recharger")
        return d
    d.pret = True
    return d


def variables_chargement(identifiant: str, source: str, ctx: int = CTX_CHARGEMENT, recharger: bool = False) -> dict[str, str]:
    """Les variables de `make lmstudio-charger` : la clé à charger, l'alias s'il diffère, le contexte, et
    RECHARGER=1 pour décharger d'abord ce qui est en mémoire sous ce nom."""
    return {"MODELE": source, "IDENTIFIANT": "" if identifiant == source else identifiant,
            "CTX": str(ctx), "RECHARGER": "1" if recharger else ""}


__all__ = ["CTX_CHARGEMENT", "CTX_MIN", "Diagnostic", "MOTIF_INJOIGNABLE", "SUFFIXE_ALIAS", "analyser", "diagnostic",
           "est_instance_lmstudio", "etat_lmstudio", "instances_lmstudio", "modeles_distants", "modeles_locaux",
           "resoudre_source", "url_hote", "variables_chargement"]
