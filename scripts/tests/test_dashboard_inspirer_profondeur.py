"""Tests pour la copie des paramètres d'expérience et la conservation de la profondeur de réflexion.

Vérifie que :
1. Les 6 paramètres clés (jeu, prompt, décideur, modèle, température, profondeur)
   sont fidèlement extraits et validés lors d'une copie (« S'inspirer de », « Dupliquer »).
2. La profondeur de réflexion (budget numérique ou niveau déclaratif) est conservée
   à la lecture, dans la validation de base, dans l'empreinte de formulaire et à la construction
   de l'expérience (pour passerelle et antigravity).
3. Les paramètres secondaires (graines, mode, calendrier, parallélisme, tolérances)
   sont tous intégralement reportés.
"""

from pathlib import Path
import pytest
import yaml

from scripts.dashboard import experiences


@pytest.fixture
def base_exp():
    return {
        "nom": "exp_gemini38_test",
        "population": {"chemin": "data/population/population_1000_AAMAS_v5"},
        "jeu": {"nom": "population_1000_AAMAS_v5_20260316"},
        "gabarit": {"categorie": "itinary_multi_agent", "variante": "expert_gem_3.8_v3"},
        "decideur": {
            "type": "passerelle",
            "portee": "distant",
            "modele": "gemini-3.5-flash-lite",
            "parametres": {
                "temperature": 0.7,
                "thinking_level": "high",
                "top_p": 1.0,
                "max_tokens": 4096,
            },
        },
        "mode": "sans_simulateur",
        "calendrier": {
            "politique": "commune",
            "date": "2026-03-16",
            "graine": 123,
        },
        "horizon_jours": 1,
        "memoire": False,
        "graine_ordre": 456,
        "graine_tirage": 789,
        "regroupement": {"parallelisme": 16},
        "tolerances_horaires": {"walk": "insensible", "car": "heure"},
        "max_candidats": 8,
        "attente_max_s": 90,
        "derive_de": None,
    }


def test_defauts_reflexion_initiale():
    """defauts() doit initialiser les champs de réflexion à None sans casser le modèle."""
    d = experiences.defauts()
    assert "reflexion" in d
    assert "niveau_reflexion" in d
    assert d["reflexion"] is None
    assert d["niveau_reflexion"] is None
    assert d["modele"] != "", "un modèle distant utilisable doit être proposé par défaut"


def test_depuis_experience_copie_profondeur_niveau(base_exp):
    """depuis_experience() et _valider_base() doivent extraire thinking_level et tous les paramètres clés."""
    recopie = experiences.depuis_experience(base_exp)

    # 6 paramètres clés
    assert recopie["jeu"] == "population_1000_AAMAS_v5_20260316"
    assert recopie["variante"] == "expert_gem_3.8_v3"
    assert recopie["decideur_type"] == "passerelle_distant"
    assert recopie["modele"] == "gemini-3.5-flash-lite"
    assert recopie["temperature"] == 0.7
    assert recopie["niveau_reflexion"] == "high"
    assert recopie["reflexion"] is None

    # Paramètres secondaires
    assert recopie["politique"] == "commune"
    assert recopie["date"] == "2026-03-16"
    assert recopie["graine_calendrier"] == 123
    assert recopie["graine_ordre"] == 456
    assert recopie["graine_tirage"] == 789
    assert recopie["parallelisme"] == 16
    assert recopie["max_candidats"] == 8
    assert recopie["attente_max_s"] == 90
    assert recopie["tolerances"] == {"walk": "insensible", "car": "heure"}
    assert recopie["derive_de"] == "exp_gemini38_test"

    valide = experiences._valider_base(recopie)
    assert valide["niveau_reflexion"] == "high"
    assert valide["temperature"] == 0.7
    assert valide["modele"] == "gemini-3.5-flash-lite"


def test_depuis_experience_copie_profondeur_budget(base_exp):
    """depuis_experience() et _valider_base() doivent extraire thinking_budget."""
    base_exp["decideur"]["parametres"] = {
        "temperature": 0.3,
        "thinking_budget": 2048,
        "top_p": 1.0,
    }
    recopie = experiences.depuis_experience(base_exp)
    assert recopie["reflexion"] == 2048
    assert recopie["niveau_reflexion"] is None
    assert recopie["temperature"] == 0.3

    valide = experiences._valider_base(recopie)
    assert valide["reflexion"] == 2048
    assert valide["niveau_reflexion"] is None
    assert valide["temperature"] == 0.3


def test_depuis_experience_antigravity(base_exp):
    """Pour un décideur antigravity, le modèle, la température et la réflexion sont conservés."""
    base_exp["decideur"] = {
        "type": "antigravity",
        "modele": "gemini-3.8-flash",
        "parametres": {
            "temperature": 0.5,
            "thinking_level": "medium",
        },
    }
    recopie = experiences.depuis_experience(base_exp)
    assert recopie["decideur_type"] == "antigravity"
    assert recopie["modele"] == "gemini-3.8-flash"
    assert recopie["temperature"] == 0.5
    assert recopie["niveau_reflexion"] == "medium"

    valide = experiences._valider_base(recopie)
    assert valide["decideur_type"] == "antigravity"
    assert valide["modele"] == "gemini-3.8-flash"
    assert valide["temperature"] == 0.5
    assert valide["niveau_reflexion"] == "medium"


def test_construire_experience_reflexion():
    """construire_experience() doit écrire thinking_level ou thinking_budget pour passerelle et antigravity."""
    v_niveau = experiences.defauts()
    v_niveau.update({
        "decideur_type": "passerelle_distant",
        "modele": "gemini-3.8-flash",
        "temperature": 0.4,
        "niveau_reflexion": "high",
        "reflexion": None,
    })
    exp_niveau = experiences.construire_experience(v_niveau)
    params_niveau = exp_niveau["decideur"]["parametres"]
    assert params_niveau["thinking_level"] == "high"
    assert "thinking_budget" not in params_niveau
    assert params_niveau["temperature"] == 0.4

    # Antigravity avec budget
    v_budget = experiences.defauts()
    v_budget.update({
        "decideur_type": "antigravity",
        "modele": "gemini-3.8-flash",
        "temperature": 0.0,
        "niveau_reflexion": None,
        "reflexion": 4096,
    })
    exp_budget = experiences.construire_experience(v_budget)
    params_budget = exp_budget["decideur"]["parametres"]
    assert params_budget["thinking_budget"] == 4096
    assert "thinking_level" not in params_budget
    assert exp_budget["decideur"]["type"] == "antigravity"

    # Sans réflexion demandée : ni thinking_level ni thinking_budget ne doivent être présents
    v_sans = experiences.defauts()
    v_sans.update({
        "decideur_type": "passerelle_distant",
        "modele": "gemini-3.8-flash",
        "niveau_reflexion": None,
        "reflexion": None,
    })
    exp_sans = experiences.construire_experience(v_sans)
    assert "thinking_level" not in exp_sans["decideur"]["parametres"]
    assert "thinking_budget" not in exp_sans["decideur"]["parametres"]


def test_empreinte_formulaire_retient_reflexion():
    """L'empreinte du formulaire (brouillon) doit préserver les clés de réflexion."""
    v = experiences.defauts()
    v["niveau_reflexion"] = "low"
    v["reflexion"] = None
    v["temperature"] = 0.2

    texte = experiences._empreinte_formulaire(v)
    brut = yaml.safe_load(texte)
    assert brut["niveau_reflexion"] == "low"
    assert brut["temperature"] == 0.2
    assert "reflexion" in brut


def test_aller_retour_experience_reelle_disque():
    """Vérifie le cycle complet sur une expérience réelle du disque portant thinking_level."""
    chemin = Path("data/experiences/exp_gemini-35-fl_expgem38v2_jtir_pop-1000_AAMAS_v5_t0_nosim/experience.yaml")
    if not chemin.is_file():
        pytest.skip("expérience réelle absente du disque")
    exp_source = yaml.safe_load(chemin.read_text(encoding="utf-8"))

    formulaire = experiences.depuis_experience(exp_source)
    valide = experiences._valider_base(formulaire)

    assert valide["jeu"] == exp_source["jeu"]["nom"]
    assert valide["variante"] == exp_source["gabarit"]["variante"]
    assert valide["decideur_type"] == "passerelle_distant"
    assert valide["modele"] == exp_source["decideur"]["modele"]
    assert valide["temperature"] == exp_source["decideur"]["parametres"]["temperature"]
    assert valide["niveau_reflexion"] == exp_source["decideur"]["parametres"]["thinking_level"]

    reconstruite = experiences.construire_experience(valide)
    assert reconstruite["decideur"]["parametres"]["thinking_level"] == "high"
    assert reconstruite["decideur"]["modele"] == "gemini-3.5-flash-lite"
    assert reconstruite["decideur"]["parametres"]["temperature"] == 0.0

