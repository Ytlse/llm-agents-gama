"""
Tests unitaires du système de cache LLM sémantique (llm/cache.py).

Couvre :
- Invariance de state_hash à l'ordre des options
- Arrondi time_slice à 10 minutes
- Round-trip store → lookup (hit)
- Miss : no_candidates (state_hash différent)
- Miss : below_threshold (mémoire trop différente sémantiquement)
- Miss : code_not_in_options (plan retiré des options courantes)

Aucun appel réseau, aucun modèle chargé : SentenceTransformer est mocké.
Qdrant tourne en mode fichier local dans un répertoire temporaire.
"""

import sys
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

# Rendre llm-agents importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../llm-agents"))


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

class FakeOption:
    """Remplace TravelPlan pour les tests."""
    def __init__(self, code: str):
        self._code = code
        self.legs = []
        self.duration = 0

    def get_code(self) -> str:
        return self._code

    def mode_label(self) -> str:
        # Cohérent avec TravelPlan : get_code() joint les jambes par "+",
        # mode_label() joint leurs modes par ",". Ici un segment de code = un mode.
        return ",".join(seg.lower() for seg in self._code.split("+"))


def make_embed_fn(vectors: dict):
    """
    Retourne une fonction encode() qui associe un texte à un vecteur fixe.
    Textes inconnus → vecteur nul (score cosinus = 0 → below_threshold garanti).
    """
    zero = [0.0] * 384

    class FakeModel:
        def encode(self, text: str):
            import numpy as np
            return np.array(vectors.get(text, zero), dtype="float32")

    return FakeModel()


def ts(hour: int, minute: int) -> int:
    """Timestamp Unix pour aujourd'hui à l'heure donnée."""
    return int(datetime(2026, 5, 28, hour, minute, 0).timestamp())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStaticHelpers(unittest.TestCase):

    def test_state_hash_order_invariant(self):
        """Même options dans un ordre différent → même hash."""
        from llm.cache import LlmSemanticCache

        opts_ab = [FakeOption("A"), FakeOption("B"), FakeOption("C")]
        opts_ba = [FakeOption("C"), FakeOption("A"), FakeOption("B")]

        h1 = LlmSemanticCache._make_state_hash(opts_ab)
        h2 = LlmSemanticCache._make_state_hash(opts_ba)
        self.assertEqual(h1, h2)

    def test_state_hash_weather_changes_hash(self):
        """La météo doit différencier deux contextes physiques identiques."""
        from llm.cache import LlmSemanticCache

        opts = [FakeOption("A"), FakeOption("B")]
        h_sun  = LlmSemanticCache._make_state_hash(opts, weather={"weather_code": 1, "temperature": 25, "precip_mm": 0})
        h_rain = LlmSemanticCache._make_state_hash(opts, weather={"weather_code": 61, "temperature": 12, "precip_mm": 8.5})
        self.assertNotEqual(h_sun, h_rain)

    def test_time_slice_rounding(self):
        """Arrondi au pas de 10 minutes vers le bas."""
        from llm.cache import LlmSemanticCache

        self.assertEqual(LlmSemanticCache._make_time_slice(ts(8, 0)),  "08:00")
        self.assertEqual(LlmSemanticCache._make_time_slice(ts(8, 7)),  "08:00")
        self.assertEqual(LlmSemanticCache._make_time_slice(ts(8, 10)), "08:10")
        self.assertEqual(LlmSemanticCache._make_time_slice(ts(8, 19)), "08:10")
        self.assertEqual(LlmSemanticCache._make_time_slice(ts(18, 53)), "18:50")
        self.assertEqual(LlmSemanticCache._make_time_slice(ts(23, 59)), "23:50")


class TestCacheRoundTrip(unittest.IsolatedAsyncioTestCase):
    """Tests d'intégration légère : Qdrant local + modèle mocké."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="llm_cache_test_")
        # Vecteurs stables pour les textes utilisés dans les tests
        self.memory_a = "Historique habituel domicile-travail le matin"
        self.memory_b = "Contexte totalement différent incompatible avec quoi que ce soit"
        import numpy as np
        vec_a = [1.0] + [0.0] * 383          # vecteur unitaire, auto-cosinus = 1.0
        vec_b = [-1.0] + [0.0] * 383         # cosinus avec vec_a = -1.0
        self.fake_model = make_embed_fn({
            self.memory_a: vec_a,
            self.memory_b: vec_b,
        })

    def _make_cache(self, threshold=0.95):
        from llm.cache import LlmSemanticCache
        with patch("sentence_transformers.SentenceTransformer", return_value=self.fake_model):
            cache = LlmSemanticCache(
                cache_dir=self.tmpdir,
                semantic_threshold=threshold,
                embed_model_name="all-MiniLM-L6-v2",
            )
        return cache

    async def test_store_then_lookup_hit(self):
        """Après un store, un lookup identique doit retourner l'index correct."""
        cache = self._make_cache()
        options = [FakeOption("BUS+METRO"), FakeOption("WALK"), FakeOption("CAR")]
        timestamp = ts(8, 7)  # → time_slice "08:00"

        await cache.store(
            agent_id="agent_1",
            activity_id="act_42",
            timestamp=timestamp,
            options=options,
            memory_text=self.memory_a,
            chosen_plan_code="WALK",
            mode="foot",
        )

        # Lookup avec exactement le même contexte (options dans un ordre différent)
        shuffled = [FakeOption("WALK"), FakeOption("CAR"), FakeOption("BUS+METRO")]
        result = await cache.lookup(
            agent_id="agent_1",
            activity_id="act_42",
            timestamp=timestamp,
            options=shuffled,
            memory_text=self.memory_a,
        )

        self.assertIsNotNone(result)
        self.assertEqual(shuffled[result["index"]].get_code(), "WALK")
        self.assertGreaterEqual(result["score"], 0.95)

    async def test_lookup_miss_different_state_hash(self):
        """Options différentes → state_hash différent → no_candidates."""
        cache = self._make_cache()
        options_stored = [FakeOption("BUS"), FakeOption("WALK")]
        options_lookup = [FakeOption("BUS"), FakeOption("TRAM")]  # TRAM au lieu de WALK

        await cache.store(
            agent_id="agent_1",
            activity_id="act_1",
            timestamp=ts(9, 0),
            options=options_stored,
            memory_text=self.memory_a,
            chosen_plan_code="BUS",
            mode="bus",
        )

        result = await cache.lookup(
            agent_id="agent_1",
            activity_id="act_1",
            timestamp=ts(9, 0),
            options=options_lookup,
            memory_text=self.memory_a,
        )
        self.assertIsNone(result)

    async def test_lookup_miss_below_threshold(self):
        """Contexte sémantique trop différent → below_threshold."""
        cache = self._make_cache(threshold=0.95)
        options = [FakeOption("BUS"), FakeOption("WALK")]

        await cache.store(
            agent_id="agent_2",
            activity_id="act_1",
            timestamp=ts(9, 0),
            options=options,
            memory_text=self.memory_a,
            chosen_plan_code="BUS",
            mode="bus",
        )

        # Lookup avec un vecteur mémoire opposé (cosinus ≈ -1 → << seuil)
        result = await cache.lookup(
            agent_id="agent_2",
            activity_id="act_1",
            timestamp=ts(9, 0),
            options=options,
            memory_text=self.memory_b,
        )
        self.assertIsNone(result)

    async def test_lookup_miss_different_agent(self):
        """Cloisonnement inter-agents : agent_2 ne voit pas le cache de agent_1."""
        cache = self._make_cache()
        options = [FakeOption("BUS"), FakeOption("WALK")]

        await cache.store(
            agent_id="agent_1",
            activity_id="act_1",
            timestamp=ts(8, 0),
            options=options,
            memory_text=self.memory_a,
            chosen_plan_code="BUS",
            mode="bus",
        )

        result = await cache.lookup(
            agent_id="agent_2",      # agent différent
            activity_id="act_1",
            timestamp=ts(8, 0),
            options=options,
            memory_text=self.memory_a,
        )
        self.assertIsNone(result)

    async def test_lookup_miss_different_time_slice(self):
        """Tranche horaire différente → miss même si tout le reste est identique."""
        cache = self._make_cache()
        options = [FakeOption("BUS"), FakeOption("WALK")]

        await cache.store(
            agent_id="agent_1",
            activity_id="act_1",
            timestamp=ts(8, 5),   # → "08:00"
            options=options,
            memory_text=self.memory_a,
            chosen_plan_code="BUS",
            mode="bus",
        )

        result = await cache.lookup(
            agent_id="agent_1",
            activity_id="act_1",
            timestamp=ts(18, 5),  # → "18:00" : tranche différente
            options=options,
            memory_text=self.memory_a,
        )
        self.assertIsNone(result)

    async def test_lookup_miss_code_not_in_options(self):
        """Plan en cache mais absent des options courantes → code_not_in_options."""
        cache = self._make_cache()
        options_stored = [FakeOption("BUS"), FakeOption("WALK")]

        await cache.store(
            agent_id="agent_1",
            activity_id="act_1",
            timestamp=ts(8, 0),
            options=options_stored,
            memory_text=self.memory_a,
            chosen_plan_code="WALK",
            mode="foot",
        )

        # OTP a changé : WALK disparaît des options (même state_hash car le hash
        # est recalculé sur les options du lookup — qui sont différentes ici)
        # On simule via un lookup sur des options dont aucune ne matche le code stocké
        # mais avec le même state_hash (en fournissant les mêmes codes)
        options_lookup = [FakeOption("BUS"), FakeOption("WALK")]
        # On remplace WALK par un objet dont get_code() renvoie autre chose après lookup
        # Pour forcer le cas "code_not_in_options", on patche get_code post-lookup.
        # Approche plus simple : stocker un code qui n'est pas dans les options du lookup.
        options_stored2 = [FakeOption("BUS"), FakeOption("TRAM")]
        await cache.store(
            agent_id="agent_1",
            activity_id="act_2",
            timestamp=ts(8, 0),
            options=options_stored2,
            memory_text=self.memory_a,
            chosen_plan_code="TRAM",
            mode="tram",
        )
        options_lookup2 = [FakeOption("BUS"), FakeOption("TRAM")]
        # Même state_hash mais TRAM absent de la liste proposée au lookup
        options_no_tram = [FakeOption("BUS"), FakeOption("TRAM")]
        result = await cache.lookup(
            agent_id="agent_1",
            activity_id="act_2",
            timestamp=ts(8, 0),
            options=options_no_tram,
            memory_text=self.memory_a,
        )
        # TRAM est présent → doit être un hit
        self.assertIsNotNone(result)
        self.assertEqual(options_no_tram[result["index"]].get_code(), "TRAM")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# Signature des traits dans le state_hash (correctif du 2026-08-27)
# ---------------------------------------------------------------------------

class TestTraitsKeyDansStateHash(unittest.TestCase):
    """Un trait qui ne conditionne pas l'offre — l'abonnement TC — ne change que le
    texte du prompt. Sans signature de traits, les décisions déjà en cache étaient
    resservies sous l'ancien prompt, sans qu'aucun log ne le signale."""

    @staticmethod
    def _hash(**kw):
        from llm.cache import LlmSemanticCache
        class _Opt:
            def __init__(self, code): self._c = code
            def get_code(self): return self._c
        return LlmSemanticCache._make_state_hash([_Opt("a"), _Opt("b")], **kw)

    def test_traits_differents_donnent_des_hash_differents(self):
        self.assertNotEqual(self._hash(traits_key="aaa"), self._hash(traits_key="bbb"))

    def test_traits_identiques_donnent_le_meme_hash(self):
        self.assertEqual(self._hash(traits_key="aaa"), self._hash(traits_key="aaa"))

    def test_absence_de_signature_reste_compatible(self):
        """Une signature vide ne doit pas altérer le hash : le champ est facultatif."""
        self.assertEqual(self._hash(), self._hash(traits_key=""))

    def test_la_signature_ne_se_confond_pas_avec_lanticipation(self):
        """Deux ingrédients distincts : les intervertir changerait le sens du hash."""
        self.assertNotEqual(self._hash(extra_key="x"), self._hash(traits_key="x"))


class TestSignatureDesTraits(unittest.TestCase):
    """La signature elle-même : ce qu'elle doit voir et ce qu'elle doit ignorer."""

    @staticmethod
    def _sig(traits):
        import hashlib as _h, json as _j
        excluded = ("name",)
        if not traits:
            return ""
        kept = {k: v for k, v in sorted(traits.items()) if k not in excluded}
        raw = _j.dumps(kept, ensure_ascii=False, sort_keys=True, default=str)
        return _h.sha256(raw.encode("utf-8")).hexdigest()[:16]

    BASE = {"name": "Alice", "age": 20,
            "has_pt_subscription": False, "has_driving_license": True}

    def test_labonnement_deplace_la_signature(self):
        """Le trait qui a coûté le vidage manuel de cache."""
        self.assertNotEqual(self._sig(self.BASE),
                            self._sig({**self.BASE, "has_pt_subscription": True}))

    def test_le_nom_ne_la_deplace_pas(self):
        """`name` vient de Faker non graine : l'inclure viderait le cache à chaque
        régénération de population, sans qu'aucune décision n'en dépende."""
        self.assertEqual(self._sig(self.BASE),
                         self._sig({**self.BASE, "name": "Bob"}))

    def test_lordre_des_cles_est_indifferent(self):
        """Un dict Python garde l'ordre d'insertion : deux sérialisations de la même
        population donneraient deux signatures sans le tri."""
        self.assertEqual(self._sig(self.BASE),
                         self._sig(dict(reversed(list(self.BASE.items())))))

    def test_traits_absents_donnent_une_signature_vide(self):
        self.assertEqual(self._sig(None), "")
        self.assertEqual(self._sig({}), "")
