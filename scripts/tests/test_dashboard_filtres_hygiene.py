"""Filtres d'hygiène du tableau de bord — spec `hygiene-prompts-et-plateforme-experiences.md`.

Trois retraits, un même principe : ne proposer que ce sur quoi on peut s'appuyer, et **compter
ce qu'on retire**. Un retrait muet ferait croire à une perte de données là où tout est intact.

Le test qui compte est celui de PARITÉ : le tableau de bord reproduit le critère de refus du
`PromptManager` sans importer le moteur (il lit le YAML). Cette duplication n'est tenable que
verrouillée — sans quoi le formulaire proposerait un prompt que le lancement refuserait.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "llm-agents"))

# `from scripts.dashboard import experiences`, jamais `import experiences` : le paquet
# `llm-agents/experiences` porte le même nom et l'emporterait selon l'ordre du sys.path.
# C'est cette collision même qui a rendu un import silencieusement inerte dans le module
# audité (cf. `_module_aptitude`).
from scripts.dashboard import experiences as D  # noqa: E402


# ── Prompts ──────────────────────────────────────────────────────────────────


def test_parite_avec_le_refus_de_la_passerelle():
    """Ce que le tableau de bord écarte est EXACTEMENT ce que le moteur refuse de servir."""
    from mobility_llm import build_prompt_manager
    from llm_gateway.prompts.engine import AvisNeutraliteManquant, VariantePromptInvalide

    pm = build_prompt_manager()
    refusees_moteur = set()
    for v in pm.variantes():
        try:
            pm.get_system_prompt("itinary_multi_agent", v)
        except (VariantePromptInvalide, AvisNeutraliteManquant):
            refusees_moteur.add(v)

    ecartees_ihm = set(D.variantes_prompt_ecartees())
    assert ecartees_ihm == refusees_moteur, (
        f"divergence — IHM seule : {ecartees_ihm - refusees_moteur} ; "
        f"moteur seul : {refusees_moteur - ecartees_ihm}"
    )


def test_les_variantes_proposees_sont_toutes_servables():
    from mobility_llm import build_prompt_manager

    pm = build_prompt_manager()
    proposees, _ = D.variantes_prompt()
    assert proposees, "le choix ne doit pas être vide"
    for v in proposees:
        assert pm.get_system_prompt("itinary_multi_agent", v), v


def test_la_variante_active_reste_proposee():
    """Écarter le prompt actif viderait le formulaire de son défaut."""
    proposees, active = D.variantes_prompt()
    assert active in proposees, active


def test_les_ecartees_sont_comptees_avec_un_motif():
    ecartees = D.variantes_prompt_ecartees()
    assert ecartees, "l'état courant du dépôt en compte trois"
    for nom, raison in ecartees.items():
        assert raison and raison.strip(), nom


def test_inclure_ecartees_les_rend():
    """Le retrait est un filtre d'affichage, jamais une amputation de la source."""
    sans, _ = D.variantes_prompt()
    avec, _ = D.variantes_prompt(inclure_ecartees=True)
    assert set(avec) - set(sans) == set(D.variantes_prompt_ecartees())


@pytest.mark.parametrize(
    "entree,attendu",
    [
        ({"content": "t"}, None),
        ({"content": "t", "_invalidation": {"statut": "invalide", "regle": "M1"}}, "invalidée"),
        ({"content": "t", "_invalidation": {"statut": "leve"}}, None),
        ({"content": "t", "_neutralite": {"verdict": "non_conforme"}}, "non conforme"),
        ({"content": "t", "_neutralite": {"verdict": "conforme_avec_reserve"}}, None),
        ({"content": "t", "_neutralite": {"verdict": "conforme", "sha256_texte": "faux"}}, "périmé"),
        ("pas un dict", "illisible"),
    ],
)
def test_critere_ecarte(entree, attendu):
    r = D.prompt_ecarte(entree)
    if attendu is None:
        assert r is None
    else:
        assert r and attendu in r


# ── Modèles ──────────────────────────────────────────────────────────────────


def test_les_modeles_a_quota_derisoire_sont_ecartes():
    """Un modèle à 20 requêtes/jour ne peut pas porter une expérience de 2 285 sollicitations."""
    inaptes = D.modeles_inaptes()
    assert inaptes, "le module d'aptitude doit être chargé — un dict vide signale un import muet"
    assert any("gemini-3.8-flash" == m for m in inaptes), sorted(inaptes)
    for m, raison in inaptes.items():
        assert raison and raison.strip(), m


def test_le_module_d_aptitude_se_charge_malgre_la_collision_de_noms():
    """Ce module s'appelle aussi `experiences` : l'import doit passer par le chemin du fichier."""
    assert D._module_aptitude() is not None


def test_les_modeles_utilisables_restent_proposables():
    inaptes = D.modeles_inaptes()
    locaux, distants = D.modeles_par_portee()
    assert [m for m in distants if m not in inaptes], "il doit rester des modèles distants"
    assert [m for m in locaux if m not in inaptes], "aucun modèle local ne doit être écarté"


# ── Expériences ──────────────────────────────────────────────────────────────


def test_les_experiences_invalidees_ou_archivees_sortent_du_tableau():
    toutes = D.lister()
    visibles = [l for l in toutes if not D.masquee(l)]
    assert visibles, "le tableau ne doit pas être vide"
    assert all(l.get("statut") == "actif" for l in visibles)
    assert len(visibles) < len(toutes), "l'état courant du dépôt en masque"


def test_chaque_experience_retiree_porte_son_motif():
    """Sans motif, une disparition se lit comme une perte de données."""
    retirees = [l for l in D.lister() if D.masquee(l)]
    assert retirees
    for l in retirees:
        assert l.get("statut") in ("archivee", "invalide"), l["experience"]
        assert l.get("statut_motif"), l["experience"]


# ── Profondeur de réflexion ──────────────────────────────────────────────────


@pytest.mark.parametrize("valeur,index", [(None, 0), (0, 1), (-1, 2), (1024, 3), (256, 3)])
def test_index_du_choix_de_reflexion(valeur, index):
    assert D._index_reflexion(valeur) == index


def test_valeur_de_reflexion_sans_widget():
    """Les trois premiers choix ne consultent aucun widget : None / 0 / -1."""
    assert D._valeur_reflexion(D.CHOIX_REFLEXION[0], None, None, None) is None
    assert D._valeur_reflexion(D.CHOIX_REFLEXION[1], None, None, None) == 0
    assert D._valeur_reflexion(D.CHOIX_REFLEXION[2], None, None, None) == -1


def test_valeur_de_reflexion_budget_fixe():
    class _Col:
        def number_input(self, *a, **kw):
            self.defaut = a[3]
            return a[3]

    col = _Col()
    assert D._valeur_reflexion(D.CHOIX_REFLEXION[3], 2048, col, lambda s: s) == 2048
    assert col.defaut == 2048, "la valeur enregistrée doit préremplir le champ"
    col2 = _Col()
    D._valeur_reflexion(D.CHOIX_REFLEXION[3], None, col2, lambda s: s)
    assert col2.defaut == 1024, "sans valeur enregistrée, un défaut raisonnable"


def test_aller_retour_none_ne_cree_pas_de_cle():
    """`None` doit laisser `parametres` SANS la clé : sinon deux empreintes pour un réglage."""
    src = (RACINE / "scripts" / "dashboard" / "experiences.py").read_text(encoding="utf-8")
    assert 'if v.get("reflexion") is not None:' in src
    assert 'params["thinking_budget"] = int(v["reflexion"])' in src


# ── « maximum » de réflexion, adossé au plafond déclaré ──────────────────────


def test_maximum_indisponible_sans_plafond_declare():
    """Aucun `thinking_budget_max` dans providers.yaml aujourd'hui : pas de « maximum » offert."""
    choix, plafond = D.choix_reflexion_pour("gemini-3.5-flash-lite")
    assert plafond is None
    assert choix == D.CHOIX_REFLEXION
    assert not any(c.startswith(D.CHOIX_REFLEXION_MAX) for c in choix)


def test_maximum_propose_quand_le_plafond_est_declare(monkeypatch):
    monkeypatch.setattr(D, "plafond_reflexion", lambda m: 24576)
    choix, plafond = D.choix_reflexion_pour("un-modele")
    assert plafond == 24576
    assert choix[-1] == f"{D.CHOIX_REFLEXION_MAX} (24576 jetons)"


def test_maximum_resout_vers_un_nombre_concret():
    """Pas de mot magique dans l'empreinte : « maximum » devient le plafond déclaré."""
    v = D._valeur_reflexion(f"{D.CHOIX_REFLEXION_MAX} (24576 jetons)", None, None, None, 24576)
    assert v == 24576


def test_maximum_sans_plafond_ne_fabrique_rien():
    """Sans plafond, « maximum » ne doit pas inventer une valeur : on ne demande rien."""
    assert D._valeur_reflexion(f"{D.CHOIX_REFLEXION_MAX} (x)", None, None, None, None) is None


def test_une_valeur_egale_au_plafond_se_relit_comme_maximum():
    assert D._index_reflexion(24576, 24576) == 4
    assert D._index_reflexion(1024, 24576) == 3
    assert D._index_reflexion(None, 24576) == 0


def test_le_champ_libre_est_borne_par_le_plafond():
    class _Col:
        def number_input(self, *a, **kw):
            self.borne_haute, self.defaut = a[2], a[3]
            return a[3]

    col = _Col()
    D._valeur_reflexion(D.CHOIX_REFLEXION[3], None, col, lambda s: s, 4096)
    assert col.borne_haute == 4096, "le champ ne doit pas permettre de dépasser le plafond"
    assert col.defaut == 1024


def test_plafond_absent_sur_une_seule_instance_annule_le_maximum(monkeypatch):
    """On ne déduit pas un plafond d'un sous-ensemble d'instances."""
    monkeypatch.setattr(D, "modeles", lambda: {"m": ["a", "b"]})
    monkeypatch.setattr(D, "_yaml", lambda p: {"providers": {
        "a": {"thinking_budget_max": 8192}, "b": {}}})
    assert D.plafond_reflexion("m") is None


def test_plafond_retient_le_plus_petit(monkeypatch):
    """Demander plus ferait refuser l'appel sur l'instance la plus contrainte."""
    monkeypatch.setattr(D, "modeles", lambda: {"m": ["a", "b"]})
    monkeypatch.setattr(D, "_yaml", lambda p: {"providers": {
        "a": {"thinking_budget_max": 8192}, "b": {"thinking_budget_max": 4096}}})
    assert D.plafond_reflexion("m") == 4096


# ── Niveau de réflexion (réglage courant de l'API) ───────────────────────────


def test_niveaux_declares_par_modele():
    """Relevés dans la doc du fournisseur : `minimal` n'existe pas sur 3.7 ni 3.8."""
    assert D.niveaux_reflexion("gemini-3.8-flash") == ["low", "medium", "high"]
    assert D.niveaux_reflexion("gemini-3.6-flash") == ["minimal", "low", "medium", "high"]


def test_aucun_niveau_pour_un_modele_non_documente():
    assert D.niveaux_reflexion("mistral-small-latest") == []
    assert D.niveaux_reflexion("gemini-3.1-flash-lite") == []   # instances sans thinking_levels
    # Un modèle ABSENT de providers.yaml rend `[]` lui aussi : sans ce second cas, le
    # renommage du 2026-09-10 aurait rendu l'assertion ci-dessus vraie par ignorance.
    assert D.niveaux_reflexion("modele-jamais-declare") == []


def test_niveaux_sont_l_intersection_des_instances(monkeypatch):
    """Un niveau accepté par une clé et pas l'autre ferait échouer selon le tirage."""
    monkeypatch.setattr(D, "modeles", lambda: {"m": ["a", "b"]})
    monkeypatch.setattr(D, "_yaml", lambda p: {"providers": {
        "a": {"thinking_levels": ["minimal", "low", "high"]},
        "b": {"thinking_levels": ["low", "medium", "high"]}}})
    assert D.niveaux_reflexion("m") == ["low", "high"]


def test_une_instance_sans_declaration_annule_les_niveaux(monkeypatch):
    monkeypatch.setattr(D, "modeles", lambda: {"m": ["a", "b"]})
    monkeypatch.setattr(D, "_yaml", lambda p: {"providers": {
        "a": {"thinking_levels": ["low", "high"]}, "b": {}}})
    assert D.niveaux_reflexion("m") == []


def test_le_maximum_est_un_nom_pas_un_nombre():
    """C'est la réponse à « comment dire au max » : `high`, sans plafond à relever."""
    assert "high" in D.niveaux_reflexion("gemini-3.8-flash")
    assert "maximum" in D.LIBELLES_NIVEAU["high"]


def test_niveau_et_budget_ne_partent_jamais_ensemble():
    """L'API rend 400 : le formulaire n'écrit que l'un des deux."""
    src = (RACINE / "scripts" / "dashboard" / "experiences.py").read_text(encoding="utf-8")
    assert 'if v.get("niveau_reflexion"):' in src
    assert 'elif v.get("reflexion") is not None:' in src
