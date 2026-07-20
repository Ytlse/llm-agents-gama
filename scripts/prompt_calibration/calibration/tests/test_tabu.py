"""Archive tabu dure — phase 4.1 du ticket 004 (D3).

On teste l'embedding local (quasi-doublons proches, textes différents éloignés),
le seuil de rejet, et surtout la **tenure** : une entrée expire après N
acceptations et redevient éligible.
"""

from calibration.store import RunStore
from calibration.tabu import TabuArchive, cosine, hash_embedding, mutation_signature


def test_embedding_near_duplicates_are_close():
    a = hash_embedding("modify intro renforcer le vélo par beau temps")
    b = hash_embedding("modify intro renforcer le velo par beau temps !!")
    c = hash_embedding("supprimer le bloc sur la voiture en centre-ville")
    assert cosine(a, b) > cosine(a, c)
    assert cosine(a, b) > 0.8


def test_signature_combines_operator_target_content():
    sig = mutation_signature({"action": "modify", "target_block": "intro_s1",
                              "new_content": "texte", "second_block": ""})
    assert "intro_s1" in sig and "texte" in sig and "modify" in sig


def test_tabu_rejects_near_duplicate_of_recorded(tmp_path):
    store = RunStore(tmp_path / "t.db")
    archive = TabuArchive(store, threshold=0.9, tenure=10)
    mut = {"action": "modify", "target_block": "intro_s1",
           "new_content": "Renforcer le vélo quand il fait beau."}
    assert archive.is_tabu(mut, accepted_count=0)[0] is False   # rien encore
    archive.add(mut, mutation_id=None, accepted_count=0)
    near = {"action": "modify", "target_block": "intro_s1",
            "new_content": "Renforcer le vélo quand il fait beau !"}
    assert archive.is_tabu(near, accepted_count=0)[0] is True
    far = {"action": "delete", "target_block": "bullet_9", "new_content": ""}
    assert archive.is_tabu(far, accepted_count=0)[0] is False
    store.close()


def test_tabu_tenure_expires_after_n_accepted(tmp_path):
    store = RunStore(tmp_path / "t.db")
    archive = TabuArchive(store, threshold=0.9, tenure=10)
    mut = {"action": "modify", "target_block": "intro_s1",
           "new_content": "Encourager la marche pour les courts trajets."}
    archive.add(mut, mutation_id=None, accepted_count=3)  # expire à 3+10 = 13
    # Toujours actif à 12 acceptations…
    assert archive.is_tabu(mut, accepted_count=12)[0] is True
    # …expiré à 13 (tenure écoulée → re-éligible).
    assert archive.is_tabu(mut, accepted_count=13)[0] is False
    store.close()
