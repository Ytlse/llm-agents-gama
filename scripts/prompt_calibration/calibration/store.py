"""Store SQLite — phase 1.2 du ticket 004 (la fondation).

L'historique d'une campagne est un **DAG content-addressed** :
- un prompt = un **nœud**, identifié par le hash de son texte (comme un commit git) ;
- une mutation = une **arête** (``node_from → node_to``) ;
- un merge (phase 6) = un nœud à **deux parents** ;
- chaque éval conserve ses **décisions brutes** → toute métrique (loss v2, phase 3)
  est recalculable rétroactivement sans réappel LLM.

Un seul fichier ``calibration.db`` (stdlib ``sqlite3``, journal WAL pour lecture
concurrente pendant les runs — le dashboard Streamlit lit pendant que la boucle
écrit). Justification du choix SQLite vs CSV : ticket 004 §1.

Reprise (critère d'acceptation phase 1) : ``resume_state`` recharge le meilleur
nœud et l'état exact de la boucle ; l'init n'est rejouée que si le store ne
contient aucun nœud pour le prompt seed de la branche.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .blocks import blocks_to_prompt
from .models import EvalResult, Scores

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
  hash        TEXT PRIMARY KEY,
  prompt_text TEXT NOT NULL,
  blocks_json TEXT NOT NULL,
  parent      TEXT REFERENCES nodes(hash),
  parent2     TEXT REFERENCES nodes(hash),
  branch      TEXT NOT NULL,
  iteration   INTEGER,
  created_at   TEXT,
  mutation_prompt_text TEXT
);

CREATE TABLE IF NOT EXISTS mutations (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  branch       TEXT,
  iteration    INTEGER,
  node_from    TEXT REFERENCES nodes(hash),
  node_to      TEXT,
  operator     TEXT,
  target_block TEXT,
  new_content  TEXT,
  rationale    TEXT,
  verdict      TEXT,
  reject_cause TEXT,
  created_at   TEXT,
  mutation_prompt_text TEXT
);

CREATE TABLE IF NOT EXISTS evals (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  node_hash   TEXT REFERENCES nodes(hash),
  dataset     TEXT,
  params_key  TEXT,
  decisions   TEXT NOT NULL,
  scores_json TEXT NOT NULL,
  eval_model  TEXT,
  eval_temp   REAL,
  created_at  TEXT,
  UNIQUE(node_hash, dataset, params_key)
);

CREATE TABLE IF NOT EXISTS ablations (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  node_hash   TEXT REFERENCES nodes(hash),
  block_name  TEXT,
  method      TEXT,
  value       REAL,
  scores_json TEXT,
  diag        TEXT,
  created_at  TEXT
);

CREATE TABLE IF NOT EXISTS tabu (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  embedding              BLOB,
  mutation_id            INTEGER REFERENCES mutations(id),
  expires_after_accepted INTEGER,
  created_at             TEXT
);

-- Statistiques de bandit UCB par (branche, opérateur) — phase 4.3 (DE).
CREATE TABLE IF NOT EXISTS bandit (
  branch     TEXT,
  operator   TEXT,
  pulls      INTEGER NOT NULL DEFAULT 0,
  reward_sum REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (branch, operator)
);

-- Bibliothèque d'arguments comportementaux — phase 6.4 (DL).
-- Chaque bloc inséré/réécrit accepté avec gain significatif y entre, taggé.
CREATE TABLE IF NOT EXISTS snippets (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  node_origin TEXT REFERENCES nodes(hash),
  branch      TEXT,
  operator    TEXT,
  block_name  TEXT,
  content     TEXT NOT NULL,
  tag_mode    TEXT,
  tag_strata  TEXT,
  gain        REAL,
  created_at  TEXT
);

-- État de la boucle par branche (reprise exacte du recuit simulé).
CREATE TABLE IF NOT EXISTS run_state (
  branch     TEXT PRIMARY KEY,
  state_json TEXT NOT NULL,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_evals_node ON evals(node_hash);
CREATE INDEX IF NOT EXISTS idx_mut_branch ON mutations(branch, iteration);
CREATE INDEX IF NOT EXISTS idx_nodes_branch ON nodes(branch);
CREATE INDEX IF NOT EXISTS idx_abl_node ON ablations(node_hash);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunStore:
    """Accès au store SQLite. Sûr pour un writer + plusieurs lecteurs (WAL)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        """Applies simple schema migrations for columns added after initial creation."""
        # Check for mutation_prompt_text in mutations
        cursor = self.conn.execute("PRAGMA table_info(mutations)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'mutation_prompt_text' not in columns:
            self.conn.execute("ALTER TABLE mutations ADD COLUMN mutation_prompt_text TEXT")

        # Check for mutation_prompt_text in nodes
        cursor = self.conn.execute("PRAGMA table_info(nodes)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'mutation_prompt_text' not in columns:
            self.conn.execute("ALTER TABLE nodes ADD COLUMN mutation_prompt_text TEXT")

        # Phase 4 : colonnes ``second_block`` / ``anchor`` sur mutations (opérateurs
        # riches — reorder/merge), ``created_at`` sur tabu.
        cursor = self.conn.execute("PRAGMA table_info(mutations)")
        columns = [row['name'] for row in cursor.fetchall()]
        for col in ('second_block', 'anchor'):
            if col not in columns:
                self.conn.execute(f"ALTER TABLE mutations ADD COLUMN {col} TEXT")
        cursor = self.conn.execute("PRAGMA table_info(tabu)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'created_at' not in columns:
            self.conn.execute("ALTER TABLE tabu ADD COLUMN created_at TEXT")

    def __enter__(self) -> "RunStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── Nœuds ────────────────────────────────────────────────────────────────

    def get_or_create_node(self, blocks: list[dict], *, branch: str,
                           parent: Optional[str] = None,
                           parent2: Optional[str] = None,
                           iteration: Optional[int] = None) -> str:
        """Insère (ou retrouve) le nœud d'un jeu de blocs et renvoie son hash.

        Le hash est content-addressed (texte du prompt reconstruit) : réévaluer
        le même prompt retombe sur le même nœud — pas de doublon.
        """
        prompt_text = blocks_to_prompt(blocks)
        import hashlib
        node_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]
        row = self.conn.execute("SELECT hash FROM nodes WHERE hash=?",
                                (node_hash,)).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO nodes(hash, prompt_text, blocks_json, parent, parent2, "
                "branch, iteration, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (node_hash, prompt_text, json.dumps(blocks, ensure_ascii=False),
                 parent, parent2, branch, iteration, _now()))
            self.conn.commit()
        return node_hash

    def node(self, node_hash: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM nodes WHERE hash=?",
                                 (node_hash,)).fetchone()

    def node_blocks(self, node_hash: str) -> Optional[list[dict]]:
        row = self.node(node_hash)
        return json.loads(row["blocks_json"]) if row else None

    def has_node(self, node_hash: str) -> bool:
        return self.node(node_hash) is not None

    def lineage(self, node_hash: str) -> list[sqlite3.Row]:
        """Chaîne de lignage seed → nœud (via le parent principal)."""
        chain: list[sqlite3.Row] = []
        cur = self.node(node_hash)
        while cur is not None:
            chain.append(cur)
            cur = self.node(cur["parent"]) if cur["parent"] else None
        return list(reversed(chain))

    # ── Évals (avec cache adressé par contenu) ───────────────────────────────

    def cached_eval(self, node_hash: str, dataset: str,
                    params_key: str) -> Optional[EvalResult]:
        """Renvoie l'éval déjà calculée pour (nœud × dataset × params), ou None.

        C'est le cœur de la reprise sans réappel LLM : une éval identique (même
        prompt, même jeu, mêmes paramètres) n'est jamais recalculée.
        """
        row = self.conn.execute(
            "SELECT * FROM evals WHERE node_hash=? AND dataset=? AND params_key=?",
            (node_hash, dataset, params_key)).fetchone()
        if row is None:
            return None
        return EvalResult(
            node_hash=node_hash, dataset=dataset,
            decisions=[tuple(d) for d in json.loads(row["decisions"])],
            scores=Scores.model_validate(json.loads(row["scores_json"])),
            eval_model=row["eval_model"] or "", eval_temp=row["eval_temp"] or 0.0)

    def record_eval(self, result: EvalResult, params_key: str) -> None:
        """Enregistre une éval (décisions brutes + scores). Idempotent sur la clé."""
        self.conn.execute(
            "INSERT OR REPLACE INTO evals(node_hash, dataset, params_key, decisions, "
            "scores_json, eval_model, eval_temp, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (result.node_hash, result.dataset, params_key, result.decisions_json(),
             result.scores.to_json(), result.eval_model, result.eval_temp, _now()))
        self.conn.commit()

    # ── Mutations ────────────────────────────────────────────────────────────

    def record_mutation(self, *, branch: str, iteration: int,
                        node_from: Optional[str], node_to: Optional[str],
                        operator: str, target_block: str, new_content: str,
                        rationale: str, verdict: str, reject_cause: str = "",
                        mutation_prompt_text: str = "",
                        second_block: str = "", anchor: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO mutations(branch, iteration, node_from, node_to, operator, "
            "target_block, new_content, rationale, verdict, reject_cause, created_at, "
            "mutation_prompt_text, second_block, anchor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (branch, iteration, node_from, node_to, operator, target_block, new_content,
             rationale, verdict, reject_cause, _now(), mutation_prompt_text,
             second_block, anchor))
        self.conn.commit()
        return cur.lastrowid

    def mutations(self, branch: Optional[str] = None) -> list[sqlite3.Row]:
        if branch is None:
            return self.conn.execute(
                "SELECT * FROM mutations ORDER BY id").fetchall()
        return self.conn.execute(
            "SELECT * FROM mutations WHERE branch=? ORDER BY id", (branch,)).fetchall()

    def mutation_row_at(self, branch: str, iteration: int) -> Optional[sqlite3.Row]:
        """Ligne de mutation déjà enregistrée à cette itération (une par itération)."""
        return self.conn.execute(
            "SELECT * FROM mutations WHERE branch=? AND iteration=? ORDER BY id DESC LIMIT 1",
            (branch, iteration)).fetchone()

    def update_mutation(self, mutation_id: int, *, verdict: str,
                        node_to: Optional[str], reject_cause: str = "") -> None:
        """Fixe le verdict d'une mutation proposée (accepted/rejected/vetoed/…)."""
        self.conn.execute(
            "UPDATE mutations SET verdict=?, node_to=?, reject_cause=? WHERE id=?",
            (verdict, node_to, reject_cause, mutation_id))
        self.conn.commit()

    def replayable_mutation(self, branch: str, iteration: int) -> Optional[dict]:
        """Mutation déjà jouée à cette itération (rejeu déterministe à la reprise)."""
        row = self.conn.execute(
            "SELECT operator, target_block, new_content, rationale, second_block, anchor "
            "FROM mutations WHERE branch=? AND iteration=? ORDER BY id DESC LIMIT 1",
            (branch, iteration)).fetchone()
        if row is None:
            return None
        return {"target_block": row["target_block"], "action": row["operator"],
                "new_content": row["new_content"], "rationale": row["rationale"],
                "second_block": row["second_block"] or "", "anchor": row["anchor"] or ""}

    # ── Ablations ────────────────────────────────────────────────────────────

    def record_ablation(self, node_hash: str, block_name: str, method: str,
                        value: float, scores_json: str = "", diag: str = "") -> None:
        self.conn.execute(
            "INSERT INTO ablations(node_hash, block_name, method, value, scores_json, "
            "diag, created_at) VALUES (?,?,?,?,?,?,?)",
            (node_hash, block_name, method, value, scores_json, diag, _now()))
        self.conn.commit()

    def ablations(self, node_hash: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM ablations WHERE node_hash=? ORDER BY value DESC",
            (node_hash,)).fetchall()

    # ── Tabu (phase 4.1, D3) ─────────────────────────────────────────────────

    def record_tabu(self, embedding: bytes, mutation_id: Optional[int],
                    expires_after_accepted: int) -> None:
        """Ajoute l'embedding d'une mutation rejetée, avec sa tenure d'expiration."""
        self.conn.execute(
            "INSERT INTO tabu(embedding, mutation_id, expires_after_accepted, created_at) "
            "VALUES (?,?,?,?)",
            (embedding, mutation_id, expires_after_accepted, _now()))
        self.conn.commit()

    def active_tabu(self, accepted_count: int) -> list[tuple[bytes, int]]:
        """Entrées tabu non expirées (``expires_after_accepted > accepted_count``)."""
        rows = self.conn.execute(
            "SELECT embedding, expires_after_accepted FROM tabu "
            "WHERE expires_after_accepted > ?", (accepted_count,)).fetchall()
        return [(r["embedding"], r["expires_after_accepted"]) for r in rows
                if r["embedding"] is not None]

    # ── Bandit UCB (phase 4.3, DE) ───────────────────────────────────────────

    def bandit_stats(self, branch: str) -> dict[str, tuple[int, float]]:
        """Statistiques ``{operator: (pulls, reward_sum)}`` de la branche."""
        rows = self.conn.execute(
            "SELECT operator, pulls, reward_sum FROM bandit WHERE branch=?",
            (branch,)).fetchall()
        return {r["operator"]: (r["pulls"], r["reward_sum"]) for r in rows}

    def bandit_update(self, branch: str, operator: str, reward: float) -> None:
        """Incrémente (pulls, reward_sum) du bras — upsert atomique."""
        self.conn.execute(
            "INSERT INTO bandit(branch, operator, pulls, reward_sum) VALUES (?,?,1,?) "
            "ON CONFLICT(branch, operator) DO UPDATE SET "
            "pulls = pulls + 1, reward_sum = reward_sum + excluded.reward_sum",
            (branch, operator, reward))
        self.conn.commit()

    # ── Bibliothèque de snippets (phase 6.4, DL) ─────────────────────────────

    def record_snippet(self, *, node_origin: str, branch: str, operator: str,
                       block_name: str, content: str, tag_mode: str = "",
                       tag_strata: str = "", gain: float = 0.0) -> int:
        """Capitalise un bloc accepté avec gain significatif dans la bibliothèque."""
        cur = self.conn.execute(
            "INSERT INTO snippets(node_origin, branch, operator, block_name, content, "
            "tag_mode, tag_strata, gain, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (node_origin, branch, operator, block_name, content, tag_mode,
             tag_strata, gain, _now()))
        self.conn.commit()
        return cur.lastrowid

    def top_snippets(self, limit: int = 3, tag_mode: Optional[str] = None,
                     ) -> list[sqlite3.Row]:
        """Meilleurs snippets par gain observé, filtrables par mode ciblé.

        Si ``tag_mode`` est fourni, on privilégie les snippets qui ont aidé ce mode
        (le levier du moment) ; sinon les plus rentables toutes cibles confondues.
        """
        if tag_mode:
            return self.conn.execute(
                "SELECT * FROM snippets WHERE tag_mode=? ORDER BY gain DESC LIMIT ?",
                (tag_mode, limit)).fetchall()
        return self.conn.execute(
            "SELECT * FROM snippets ORDER BY gain DESC LIMIT ?", (limit,)).fetchall()

    # ── Archive de Pareto (phase 6.1, DC) ────────────────────────────────────

    def pareto_candidates(self, dataset: str = "train") -> list[dict]:
        """Nœuds évalués avec leurs losses par dimension (matière du front Pareto).

        Un dict par nœud ``{hash, branch, iteration, composite, global, age, …}``
        reconstruit depuis ``evals.scores_json`` (jointure la plus récente par nœud
        sur ``dataset``). Le calcul du front non dominé est **pur** (``pareto.py``) :
        le store ne fait que fournir les points, jamais maintenir une archive qui
        pourrait dériver (§1 : « le front = un SELECT »).
        """
        rows = self.conn.execute(
            "SELECT n.hash AS hash, n.branch AS branch, n.iteration AS iteration, "
            "  e.scores_json AS scores_json "
            "FROM nodes n JOIN evals e ON e.node_hash=n.hash "
            "WHERE e.dataset=? GROUP BY n.hash", (dataset,)).fetchall()
        out = []
        for r in rows:
            scores = json.loads(r["scores_json"])
            item = {"hash": r["hash"], "branch": r["branch"],
                    "iteration": r["iteration"]}
            item.update(scores)
            out.append(item)
        return out

    # ── Meilleur nœud / requêtes du dashboard ────────────────────────────────

    def best(self, branch: str, dataset: str = "train") -> Optional[sqlite3.Row]:
        """Nœud de plus faible composite (jeu ``dataset``) sur la branche.

        Jointure nœuds × évals : renvoie le hash, l'itération et le composite du
        meilleur prompt évalué — le « chiffre » de la campagne.
        """
        return self.conn.execute(
            "SELECT n.hash AS hash, n.iteration AS iteration, "
            "  json_extract(e.scores_json,'$.composite') AS composite "
            "FROM nodes n JOIN evals e ON e.node_hash=n.hash "
            "WHERE n.branch=? AND e.dataset=? "
            "ORDER BY composite ASC LIMIT 1", (branch, dataset)).fetchone()

    def best_overall(self, dataset: str = "train") -> Optional[sqlite3.Row]:
        """Meilleur nœud (plus faible composite) **toutes branches confondues**.

        Le « chiffre » d'une campagne multi-îlots (phase 6) : le meilleur prompt
        produit par n'importe quelle branche. Utilisé par la finalisation (phase 7)
        pour choisir le prompt à évaluer sur le jeu ``test`` et publier.
        """
        return self.conn.execute(
            "SELECT n.hash AS hash, n.branch AS branch, n.iteration AS iteration, "
            "  json_extract(e.scores_json,'$.composite') AS composite "
            "FROM nodes n JOIN evals e ON e.node_hash=n.hash "
            "WHERE e.dataset=? ORDER BY composite ASC LIMIT 1", (dataset,)).fetchone()

    def scores_by_dataset(self, node_hash: str) -> dict[str, Scores]:
        """Scores stockés d'un nœud, par jeu (``train``/``val``/``test``/``screen``)."""
        rows = self.conn.execute(
            "SELECT dataset, scores_json FROM evals WHERE node_hash=?",
            (node_hash,)).fetchall()
        return {r["dataset"]: Scores.model_validate(json.loads(r["scores_json"]))
                for r in rows}

    def eval_span(self) -> tuple[Optional[str], Optional[str]]:
        """Premier et dernier horodatage d'éval (durée approximative de campagne)."""
        row = self.conn.execute(
            "SELECT MIN(created_at) AS a, MAX(created_at) AS b FROM evals").fetchone()
        return (row["a"], row["b"]) if row else (None, None)

    def node_count(self, branch: Optional[str] = None) -> int:
        if branch is None:
            return self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM nodes WHERE branch=?",
                                 (branch,)).fetchone()[0]

    # ── État de la boucle (reprise) ──────────────────────────────────────────

    def save_run_state(self, branch: str, state: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO run_state(branch, state_json, updated_at) "
            "VALUES (?,?,?)", (branch, json.dumps(state, ensure_ascii=False), _now()))
        self.conn.commit()

    def resume_state(self, branch: str) -> Optional[dict]:
        """État sérialisé de la boucle pour cette branche (None si run neuf)."""
        row = self.conn.execute(
            "SELECT state_json FROM run_state WHERE branch=?", (branch,)).fetchone()
        return json.loads(row["state_json"]) if row else None
