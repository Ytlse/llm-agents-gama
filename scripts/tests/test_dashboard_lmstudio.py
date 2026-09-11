"""Le modèle local vu du tableau de bord (LM Studio) — onglet « 🧪 Expériences ».

Le fil de ces tests : le 2026-09-08, une expérience lancée sur Muse Glimmer a tourné sept minutes
sans une décision. Le modèle n'était pas chargé dans LM Studio, puis il l'était avec 4 096 jetons
de contexte, trop court pour un lot de deux agents. Rien ne le disait. Désormais le formulaire
sépare « modèle de langage (distant) » et « modèle de langage (local, LM Studio) », un bloc dit
si le modèle local est prêt, un bouton le charge, et « Lancer » attend qu'il le soit.

Tout se teste sur des réponses JSON figées de `GET /api/v1/models` : aucun LM Studio requis.
"""

import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.dashboard import experiences, lmstudio  # noqa: E402

LMS = "http://host.docker.internal:1234/v1"
PROVIDERS = {"providers": {
    "google_g35_key1": {"adapter": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta",
                        "default_model": "gemini-3.5-flash-lite", "rpm_limit": 15, "rpd_limit": 500},
    "groq_qwen38_key1": {"adapter": "groq", "base_url": "https://api.groq.com/openai/v1",
                         "default_model": "qwen/qwen3.8-27b", "rpm_limit": 30},
    "lmstudio_muse_key1": {"adapter": "openai_compatible", "base_url": LMS, "default_model": "meta/muse-glimmer",
                           "rpm_limit": 30, "concurrency_limit": 1, "weight": 0.0},
    "lmstudio_qwen38_key1": {"adapter": "openai_compatible", "base_url": LMS, "default_model": "qwen3.8-27b-local",
                             "rpm_limit": 30, "concurrency_limit": 1, "weight": 0.0},
    "lmstudio_mistral_key1": {"adapter": "openai_compatible", "base_url": LMS, "default_model": "mistralai/mistral-small-3.2",
                              "rpm_limit": 30, "concurrency_limit": 2, "weight": 0.0},
}}


def _payload(*, muse_ctx=4096, qwen_alias_ctx=None, qwen_cle_ctx=None, extra=()):
    """Une réponse `GET /api/v1/models` : Muse chargé (ou non) avec tel contexte, Qwen sous alias et/ou sous sa clé."""
    def inst(ident, ctx):
        return {"id": ident, "config": {"context_length": ctx, "parallel": 4}}
    models = [
        {"type": "vlm", "key": "meta/muse-glimmer", "params_string": "28B", "format": "gguf",
         "quantization": {"name": "Q4_K_M"}, "max_context_length": 131072,
         "loaded_instances": [inst("meta/muse-glimmer", muse_ctx)] if muse_ctx else []},
        {"type": "vlm", "key": "qwen/qwen3.8-27b", "params_string": "27B", "format": "safetensors",
         "quantization": {"name": "4bit"}, "max_context_length": 262144,
         "loaded_instances": ([inst("qwen3.8-27b-local", qwen_alias_ctx)] if qwen_alias_ctx else [])
                             + ([inst("qwen/qwen3.8-27b", qwen_cle_ctx)] if qwen_cle_ctx else [])},
        {"type": "llm", "key": "mistralai/mistral-small-3.2", "params_string": "24B", "format": "safetensors",
         "quantization": {"name": "4bit"}, "max_context_length": 131072, "loaded_instances": []},
        {"type": "embedding", "key": "text-embedding-nomic-embed-text-v1.5", "loaded_instances": []},
        *extra,
    ]
    return {"models": models}


# ── R1 : qui est local, qui est distant — lu dans providers.yaml, par l'URL ────────────────

def test_R1_une_instance_est_locale_par_son_url_vers_lm_studio():
    assert lmstudio.est_instance_lmstudio({"base_url": LMS})
    assert lmstudio.est_instance_lmstudio({"base_url": "http://localhost:1234/v1"})
    assert not lmstudio.est_instance_lmstudio({"base_url": "https://api.groq.com/openai/v1"})
    assert not lmstudio.est_instance_lmstudio({"base_url": "http://host.docker.internal:11434/v1"})  # Ollama : autre port
    assert not lmstudio.est_instance_lmstudio("pas un dict")


def test_R1_les_modeles_se_rangent_par_bord_et_un_meme_nom_peut_etre_des_deux():
    locaux, distants = lmstudio.modeles_locaux(PROVIDERS), lmstudio.modeles_distants(PROVIDERS)
    assert locaux == {"meta/muse-glimmer": ["lmstudio_muse_key1"], "mistralai/mistral-small-3.2": ["lmstudio_mistral_key1"],
                      "qwen3.8-27b-local": ["lmstudio_qwen38_key1"]}
    assert distants == {"gemini-3.5-flash-lite": ["google_g35_key1"], "qwen/qwen3.8-27b": ["groq_qwen38_key1"]}
    # L'alias sépare bien le Qwen local du Qwen Groq : aucun modèle des deux côtés.
    assert not set(locaux) & set(distants)


def test_R1_l_url_vue_des_conteneurs_devient_localhost_sur_l_hote():
    assert lmstudio.url_hote(LMS) == "http://localhost:1234"
    assert lmstudio.url_hote("http://localhost:1234/v1") == "http://localhost:1234"


# ── R2 : lire LM Studio ─────────────────────────────────────────────────────────────────────

def test_R2_la_reponse_de_lm_studio_se_reduit_aux_charges_et_a_leur_contexte():
    etat = lmstudio.analyser(_payload(muse_ctx=4096, qwen_alias_ctx=16384))
    assert etat["charges"] == {"meta/muse-glimmer": {"cle": "meta/muse-glimmer", "ctx": 4096},
                               "qwen3.8-27b-local": {"cle": "qwen/qwen3.8-27b", "ctx": 16384}}
    assert etat["modeles"]["meta/muse-glimmer"]["params"] == "28B"
    assert etat["modeles"]["meta/muse-glimmer"]["quant"] == "Q4_K_M"
    assert lmstudio.analyser({}) == {"modeles": {}, "charges": {}}


def test_R2_lm_studio_injoignable_rend_none_sans_lever():
    assert lmstudio.etat_lmstudio("http://127.0.0.1:1", timeout=0.2) is None


# ── R3 : l'alias `-local` retrouve sa clé ───────────────────────────────────────────────────

def test_R3_la_source_est_la_cle_l_alias_charge_ou_l_alias_local_sans_ambiguite():
    etat = lmstudio.analyser(_payload())
    assert lmstudio.resoudre_source("meta/muse-glimmer", etat) == "meta/muse-glimmer"
    assert lmstudio.resoudre_source("qwen3.8-27b-local", etat) == "qwen/qwen3.8-27b"         # convention -local
    charge = lmstudio.analyser(_payload(qwen_alias_ctx=16384))
    assert lmstudio.resoudre_source("qwen3.8-27b-local", charge) == "qwen/qwen3.8-27b"       # alias déjà chargé
    assert lmstudio.resoudre_source("inconnu-local", etat) is None
    assert lmstudio.resoudre_source("meta/muse-glimmer", None) is None
    # Deux clés au même dernier segment : l'alias n'a plus de sens, on ne devine pas.
    ambigu = lmstudio.analyser(_payload(extra=[{"type": "llm", "key": "autre/qwen3.8-27b", "loaded_instances": []}]))
    assert lmstudio.resoudre_source("qwen3.8-27b-local", ambigu) is None


# ── R4 : le diagnostic dit ce qui manque, en une phrase actionnable ─────────────────────────

def test_R4_prete_quand_chargee_avec_assez_de_contexte():
    d = lmstudio.diagnostic("meta/muse-glimmer", lmstudio.analyser(_payload(muse_ctx=16384)))
    assert d.pret and d.motif is None and d.contexte == 16384 and not d.recharger
    assert d.etat_court.startswith("🟢")


def test_R4_les_quatre_motifs_de_refus():
    injoignable = lmstudio.diagnostic("meta/muse-glimmer", None)
    assert not injoignable.pret and injoignable.motif == lmstudio.MOTIF_INJOIGNABLE and "⚫" in injoignable.etat_court
    non_charge = lmstudio.diagnostic("meta/muse-glimmer", lmstudio.analyser(_payload(muse_ctx=None)))
    assert not non_charge.pret and "n'est pas chargé" in non_charge.motif and not non_charge.recharger
    assert non_charge.source == "meta/muse-glimmer" and "⚪" in non_charge.etat_court
    court = lmstudio.diagnostic("meta/muse-glimmer", lmstudio.analyser(_payload(muse_ctx=4096)))
    assert not court.pret and court.recharger and "4 096" in court.motif and "8 192" in court.motif and "🔴" in court.etat_court
    inconnu = lmstudio.diagnostic("nimporte-local", lmstudio.analyser(_payload()))
    assert not inconnu.pret and "aucun modèle téléchargé" in inconnu.motif and inconnu.source is None


def test_R4_charge_sous_sa_cle_mais_pas_sous_l_alias_attendu_demande_un_rechargement():
    d = lmstudio.diagnostic("qwen3.8-27b-local", lmstudio.analyser(_payload(qwen_cle_ctx=16384)))
    assert not d.pret and d.recharger and "pas sous l'identifiant « qwen3.8-27b-local »" in d.motif
    assert d.source == "qwen/qwen3.8-27b"


def test_R4_les_autres_modeles_en_memoire_sont_nommes():
    d = lmstudio.diagnostic("mistralai/mistral-small-3.2", lmstudio.analyser(_payload(muse_ctx=4096)))
    assert d.autres_charges == ["meta/muse-glimmer"]


# ── R5 : les variables de `make lmstudio-charger` ───────────────────────────────────────────

def test_R5_l_alias_passe_par_identifiant_et_le_rechargement_par_recharger():
    assert lmstudio.variables_chargement("meta/muse-glimmer", "meta/muse-glimmer") == \
        {"MODELE": "meta/muse-glimmer", "IDENTIFIANT": "", "CTX": "16384", "RECHARGER": ""}
    assert lmstudio.variables_chargement("qwen3.8-27b-local", "qwen/qwen3.8-27b", recharger=True) == \
        {"MODELE": "qwen/qwen3.8-27b", "IDENTIFIANT": "qwen3.8-27b-local", "CTX": "16384", "RECHARGER": "1"}


# ── R6 : le formulaire scinde « passerelle », le fichier ne le sait pas ──────────────────────

def test_R6_les_deux_choix_modele_de_langage_s_ecrivent_passerelle():
    assert experiences.type_plateforme("passerelle_local") == "passerelle"
    assert experiences.type_plateforme("passerelle_distant") == "passerelle"
    assert experiences.type_plateforme("aleatoire") == "aleatoire"
    for choix in experiences.CHOIX_DECIDEUR:
        assert experiences.type_plateforme(choix) in experiences.TYPES_DECIDEUR
    assert set(experiences.LIBELLES_DECIDEUR) == set(experiences.CHOIX_DECIDEUR)
    assert experiences.LIBELLES_DECIDEUR["passerelle_distant"] == "modèle de langage (distant)"
    assert experiences.LIBELLES_DECIDEUR["passerelle_local"].startswith("modèle de langage (local")


def test_R6_un_fichier_relu_se_range_du_cote_qui_sert_son_modele():
    locaux = lmstudio.modeles_locaux(PROVIDERS)
    assert experiences.choix_decideur("passerelle", "meta/muse-glimmer", locaux) == "passerelle_local"
    assert experiences.choix_decideur("passerelle", "gemini-3.5-flash-lite", locaux) == "passerelle_distant"
    assert experiences.choix_decideur("passerelle", None, locaux) == "passerelle_distant"
    assert experiences.choix_decideur("rejeu", None, locaux) == "rejeu"


def test_R6_construire_experience_ecrit_passerelle_pour_un_modele_local(monkeypatch):
    v = {**experiences.defauts(), "decideur_type": "passerelle_local", "modele": "meta/muse-glimmer"}
    exp = experiences.construire_experience(v)
    assert exp["decideur"]["type"] == "passerelle" and exp["decideur"]["modele"] == "meta/muse-glimmer"
    v = {**experiences.defauts(), "decideur_type": "passerelle_distant", "modele": "gemini-3.5-flash-lite"}
    assert experiences.construire_experience(v)["decideur"]["type"] == "passerelle"


def test_R6_un_brouillon_d_avant_la_scission_est_relu_sans_casser(monkeypatch, tmp_path):
    fichier = tmp_path / "providers.yaml"
    fichier.write_text(yaml.safe_dump(PROVIDERS), encoding="utf-8")
    monkeypatch.setattr(experiences, "PROVIDERS_YAML", fichier)
    base = experiences._valider_base({"decideur_type": "passerelle", "modele": "meta/muse-glimmer"})
    assert base["decideur_type"] == "passerelle_local"
    base = experiences._valider_base({"decideur_type": "passerelle", "modele": "gemini-3.5-flash-lite"})
    assert base["decideur_type"] == "passerelle_distant"
    base = experiences._valider_base({"decideur_type": "n_existe_pas"})
    assert base["decideur_type"] == experiences.defauts()["decideur_type"]


# ── R7 : un modèle local absent ne grise que « Lancer » ─────────────────────────────────────

def test_R7_le_motif_du_modele_local_ne_grise_que_lancer():
    exp = {"nom": "exp_x", "jeu": {"nom": "j"}, "decideur": {"type": "passerelle", "modele": "meta/muse-glimmer"}}
    motifs = experiences.motifs_indisponibilite(exp, jeu_clos=True, controleur_ok=True, registre=True,
                                                modele_local="modèle local : non chargé")
    assert motifs["lancer"] == ["modèle local : non chargé"]
    assert motifs["estimer"] == [] and motifs["enregistrer"] == [] and motifs["construire"] == []
    sans = experiences.motifs_indisponibilite(exp, jeu_clos=True, controleur_ok=True, registre=True)
    assert sans["lancer"] == []


def test_R7_le_modele_local_d_une_experience_est_celui_que_lm_studio_sert(monkeypatch, tmp_path):
    fichier = tmp_path / "providers.yaml"
    fichier.write_text(yaml.safe_dump(PROVIDERS), encoding="utf-8")
    monkeypatch.setattr(experiences, "PROVIDERS_YAML", fichier)
    assert experiences.modele_local_de({"decideur": {"type": "passerelle", "modele": "meta/muse-glimmer"}}) == "meta/muse-glimmer"
    assert experiences.modele_local_de({"decideur": {"type": "passerelle", "modele": "gemini-3.5-flash-lite"}}) is None
    assert experiences.modele_local_de({"decideur": {"type": "aleatoire"}}) is None


# ── R8 : le parallélisme conseillé d'un modèle local, c'est ses appels simultanés ───────────

def test_R8_le_conseil_local_compte_les_appels_simultanes_pas_les_requetes_par_minute(monkeypatch, tmp_path):
    fichier = tmp_path / "providers.yaml"
    fichier.write_text(yaml.safe_dump(PROVIDERS), encoding="utf-8")
    monkeypatch.setattr(experiences, "PROVIDERS_YAML", fichier)
    conseil = experiences.parallelisme_conseille("meta/muse-glimmer", None)
    assert conseil == {"valeur": 1, "rpm": None, "instances": ["lmstudio_muse_key1"], "mesure": False, "local": True}
    assert experiences.parallelisme_conseille("mistralai/mistral-small-3.2", None)["valeur"] == 2
    distant = experiences.parallelisme_conseille("gemini-3.5-flash-lite", None)
    assert distant is not None and not distant.get("local") and distant["rpm"] == 15
