from __future__ import annotations

import json
from app.database import connect_database
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


GRAPH_ENGINE_VERSION = "assurance-graph-1.0.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    label: str
    properties: Dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    relationship: str
    properties: Dict[str, Any]
    created_at: str


class AssuranceGraph:
    """
    Persistent relationship graph for the AI assurance system.

    v1 deliberately uses SQLite rather than a dedicated graph database.
    The graph semantics are independent of the storage backend so a
    dedicated graph backend can be introduced later without changing the
    external assurance model.
    """

    def __init__(self, db_path: str = "data/assurance.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return connect_database(str(self.db_path))

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    properties_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_edges (
                    edge_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    properties_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(source_id, target_id, relationship)
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_graph_nodes_type
                ON graph_nodes(node_type)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_graph_edges_source
                ON graph_edges(source_id)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_graph_edges_target
                ON graph_edges(target_id)
                """
            )

    def upsert_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> GraphNode:
        now = _utc_now()
        properties = dict(properties or {})

        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT created_at
                FROM graph_nodes
                WHERE node_id = ?
                """,
                (node_id,),
            ).fetchone()

            created_at = (
                str(existing["created_at"])
                if existing
                else now
            )

            connection.execute(
                """
                INSERT INTO graph_nodes (
                    node_id,
                    node_type,
                    label,
                    properties_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    node_type = excluded.node_type,
                    label = excluded.label,
                    properties_json = excluded.properties_json
                """,
                (
                    node_id,
                    node_type,
                    label,
                    _canonical_json(properties),
                    created_at,
                ),
            )

        return GraphNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            properties=properties,
            created_at=created_at,
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        properties: Optional[Dict[str, Any]] = None,
        edge_id: Optional[str] = None,
    ) -> GraphEdge:
        properties = dict(properties or {})
        now = _utc_now()

        with self._connect() as connection:
            source = connection.execute(
                "SELECT node_id FROM graph_nodes WHERE node_id = ?",
                (source_id,),
            ).fetchone()

            target = connection.execute(
                "SELECT node_id FROM graph_nodes WHERE node_id = ?",
                (target_id,),
            ).fetchone()

            if source is None:
                raise ValueError(f"Source node does not exist: {source_id}")

            if target is None:
                raise ValueError(f"Target node does not exist: {target_id}")

            existing = connection.execute(
                """
                SELECT edge_id, created_at
                FROM graph_edges
                WHERE source_id = ?
                  AND target_id = ?
                  AND relationship = ?
                """,
                (source_id, target_id, relationship),
            ).fetchone()

            if existing:
                resolved_edge_id = str(existing["edge_id"])
                created_at = str(existing["created_at"])

                connection.execute(
                    """
                    UPDATE graph_edges
                    SET properties_json = ?
                    WHERE edge_id = ?
                    """,
                    (
                        _canonical_json(properties),
                        resolved_edge_id,
                    ),
                )
            else:
                resolved_edge_id = edge_id or f"edge_{uuid.uuid4().hex}"
                created_at = now

                connection.execute(
                    """
                    INSERT INTO graph_edges (
                        edge_id,
                        source_id,
                        target_id,
                        relationship,
                        properties_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resolved_edge_id,
                        source_id,
                        target_id,
                        relationship,
                        _canonical_json(properties),
                        created_at,
                    ),
                )

        return GraphEdge(
            edge_id=resolved_edge_id,
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
            properties=properties,
            created_at=created_at,
        )

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM graph_nodes
                WHERE node_id = ?
                """,
                (node_id,),
            ).fetchone()

        if row is None:
            return None

        return self._node_from_row(row)

    def list_nodes(
        self,
        node_type: Optional[str] = None,
    ) -> List[GraphNode]:
        with self._connect() as connection:
            if node_type:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM graph_nodes
                    WHERE node_type = ?
                    ORDER BY created_at
                    """,
                    (node_type,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM graph_nodes
                    ORDER BY created_at
                    """
                ).fetchall()

        return [self._node_from_row(row) for row in rows]

    def list_edges(
        self,
        node_id: Optional[str] = None,
        relationship: Optional[str] = None,
    ) -> List[GraphEdge]:
        query = """
            SELECT *
            FROM graph_edges
            WHERE 1 = 1
        """
        parameters: List[Any] = []

        if node_id:
            query += """
                AND (
                    source_id = ?
                    OR target_id = ?
                )
            """
            parameters.extend([node_id, node_id])

        if relationship:
            query += " AND relationship = ?"
            parameters.append(relationship)

        query += " ORDER BY created_at"

        with self._connect() as connection:
            rows = connection.execute(
                query,
                tuple(parameters),
            ).fetchall()

        return [self._edge_from_row(row) for row in rows]

    def neighbors(self, node_id: str) -> Dict[str, Any]:
        node = self.get_node(node_id)

        if node is None:
            raise ValueError(f"Node does not exist: {node_id}")

        edges = self.list_edges(node_id=node_id)

        connected_ids = set()

        for edge in edges:
            if edge.source_id == node_id:
                connected_ids.add(edge.target_id)
            else:
                connected_ids.add(edge.source_id)

        nodes = []

        for connected_id in connected_ids:
            connected = self.get_node(connected_id)
            if connected:
                nodes.append(connected)

        return {
            "node": asdict(node),
            "edges": [asdict(edge) for edge in edges],
            "neighbors": [asdict(item) for item in nodes],
        }

    def graph_for_system(self, system_id: str) -> Dict[str, Any]:
        system_node_id = f"system:{system_id}"

        if self.get_node(system_node_id) is None:
            raise ValueError(f"System graph node does not exist: {system_id}")

        visited = {system_node_id}
        frontier = [system_node_id]

        while frontier:
            current = frontier.pop()

            for edge in self.list_edges(node_id=current):
                next_id = (
                    edge.target_id
                    if edge.source_id == current
                    else edge.source_id
                )

                if next_id not in visited:
                    visited.add(next_id)
                    frontier.append(next_id)

        nodes = []

        for node_id in visited:
            node = self.get_node(node_id)
            if node:
                nodes.append(node)

        edges = []

        for edge in self.list_edges():
            if edge.source_id in visited and edge.target_id in visited:
                edges.append(edge)

        return {
            "system_id": system_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": [asdict(node) for node in nodes],
            "edges": [asdict(edge) for edge in edges],
            "engine_version": GRAPH_ENGINE_VERSION,
        }

    def sync_assurance(
        self,
        system: Any,
        assurance: Any,
        evaluations: Optional[List[Any]] = None,
        evidence: Optional[List[Any]] = None,
        policy: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Materialize the assurance relationship graph.

        This method is intentionally idempotent. Re-running it for the same
        assurance does not create duplicate nodes or relationships.
        """

        system_id = f"system:{system.system_id}"
        version_id = (
            f"system-version:"
            f"{system.system_id}:"
            f"{system.version}"
        )
        assurance_id = f"assurance:{assurance.assurance_id}"

        self.upsert_node(
            node_id=system_id,
            node_type="system",
            label=system.name,
            properties={
                "system_id": system.system_id,
                "system_type": system.system_type,
                "version": system.version,
                "environment": system.environment,
                "model": system.model,
                "framework": system.framework,
                "owner": system.owner,
                "metadata": system.metadata,
            },
        )

        self.upsert_node(
            node_id=version_id,
            node_type="system_version",
            label=f"{system.name} {system.version}",
            properties={
                "system_id": system.system_id,
                "version": system.version,
                "environment": system.environment,
            },
        )

        self.add_edge(
            system_id,
            version_id,
            "HAS_VERSION",
        )

        self.upsert_node(
            node_id=assurance_id,
            node_type="assurance",
            label=assurance.assurance_id,
            properties={
                "assurance_id": assurance.assurance_id,
                "system_id": assurance.system_id,
                "system_version": assurance.system_version,
                "environment": assurance.environment,
                "verdict": (
                    assurance.verdict.value
                    if hasattr(assurance.verdict, "value")
                    else str(assurance.verdict)
                ),
                "metrics": assurance.metrics,
                "policy_id": assurance.policy_id,
                "reasons": assurance.reasons,
                "created_at": assurance.created_at,
                "engine_version": assurance.engine_version,
            },
        )

        self.add_edge(
            version_id,
            assurance_id,
            "HAS_ASSURANCE",
        )

        passport_id = f"passport-for:{assurance.assurance_id}"

        self.upsert_node(
            node_id=passport_id,
            node_type="passport",
            label=f"Passport for {assurance.assurance_id}",
            properties={
                "assurance_id": assurance.assurance_id,
                "system_id": assurance.system_id,
                "system_version": assurance.system_version,
            },
        )

        self.add_edge(
            assurance_id,
            passport_id,
            "HAS_PASSPORT",
        )

        for evaluation in evaluations or []:
            evaluation_node_id = (
                f"evaluation:{evaluation.evaluation_id}"
            )

            self.upsert_node(
                node_id=evaluation_node_id,
                node_type="evaluation",
                label=evaluation.evaluation_id,
                properties={
                    "evaluation_id": evaluation.evaluation_id,
                    "evaluation_type": evaluation.evaluation_type,
                    "system_id": evaluation.system_id,
                    "system_version": evaluation.system_version,
                    "metrics": evaluation.metrics,
                    "passed": evaluation.passed,
                    "details": evaluation.details,
                    "created_at": evaluation.created_at,
                },
            )

            self.add_edge(
                assurance_id,
                evaluation_node_id,
                "BASED_ON_EVALUATION",
            )

            for evidence_id in evaluation.evidence_ids:
                evidence_node_id = f"evidence:{evidence_id}"

                matching = next(
                    (
                        item
                        for item in evidence or []
                        if item.evidence_id == evidence_id
                    ),
                    None,
                )

                properties = {
                    "evidence_id": evidence_id,
                }

                if matching is not None:
                    properties.update(
                        {
                            "evidence_type": matching.evidence_type,
                            "source": matching.source,
                            "content_hash": matching.content_hash,
                            "system_id": matching.system_id,
                            "system_version": matching.system_version,
                            "created_at": matching.created_at,
                        }
                    )

                self.upsert_node(
                    node_id=evidence_node_id,
                    node_type="evidence",
                    label=evidence_id,
                    properties=properties,
                )

                self.add_edge(
                    evaluation_node_id,
                    evidence_node_id,
                    "SUPPORTED_BY",
                )

        if policy is not None:
            policy_node_id = f"policy:{policy.policy_id}"

            self.upsert_node(
                node_id=policy_node_id,
                node_type="policy",
                label=policy.name,
                properties={
                    "policy_id": policy.policy_id,
                    "name": policy.name,
                    "version": policy.version,
                    "rules": [
                        {
                            "metric": rule.metric,
                            "operator": rule.operator,
                            "threshold": rule.threshold,
                            "severity": rule.severity,
                            "description": rule.description,
                        }
                        for rule in policy.rules
                    ],
                    "metadata": policy.metadata,
                },
            )

            self.add_edge(
                assurance_id,
                policy_node_id,
                "GOVERNED_BY",
            )

        return self.graph_for_system(system.system_id)

    @staticmethod
    def _node_from_row(row: Any) -> GraphNode:
        return GraphNode(
            node_id=str(row["node_id"]),
            node_type=str(row["node_type"]),
            label=str(row["label"]),
            properties=json.loads(row["properties_json"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _edge_from_row(row: Any) -> GraphEdge:
        return GraphEdge(
            edge_id=str(row["edge_id"]),
            source_id=str(row["source_id"]),
            target_id=str(row["target_id"]),
            relationship=str(row["relationship"]),
            properties=json.loads(row["properties_json"]),
            created_at=str(row["created_at"]),
        )
