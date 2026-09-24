from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class ProvenanceService:
    """
    Query layer over the Assurance Core and Assurance Graph.

    Responsibilities:
    - Determine the latest assurance status for a system.
    - Return the provenance chain behind an assurance.
    - Compare assurance results between system versions.

    This service does not create or mutate assurance data.
    """

    def __init__(
        self,
        registry,
        assurance_store,
        evidence_store,
        graph,
    ):
        self.registry = registry
        self.assurance_store = assurance_store
        self.evidence_store = evidence_store
        self.graph = graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _jsonable(value: Any) -> Any:
        """Convert common Python objects into JSON-safe values."""
        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(key): ProvenanceService._jsonable(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                ProvenanceService._jsonable(item)
                for item in value
            ]

        return value

    @staticmethod
    def _record_to_dict(record: Any) -> Dict[str, Any]:
        """Convert a Pydantic/dataclass/object record into a dictionary."""
        if record is None:
            return {}

        if hasattr(record, "model_dump"):
            try:
                return record.model_dump(mode="json")
            except TypeError:
                return record.model_dump()

        if hasattr(record, "dict"):
            return record.dict()

        if hasattr(record, "__dict__"):
            return ProvenanceService._jsonable(record.__dict__)

        return {}

    @staticmethod
    def _created_at(record: Any) -> str:
        value = getattr(record, "created_at", None)

        if isinstance(value, datetime):
            return value.isoformat()

        if value is None:
            return ""

        return str(value)

    @staticmethod
    def _latest(records: List[Any]) -> Optional[Any]:
        if not records:
            return None

        return max(records, key=ProvenanceService._created_at)

    @staticmethod
    def _node_map(graph_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return {
            node["node_id"]: node
            for node in graph_data.get("nodes", [])
            if "node_id" in node
        }

    @staticmethod
    def _edge_list(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return graph_data.get("edges", [])

    # ------------------------------------------------------------------
    # 1. System status
    # ------------------------------------------------------------------

    def get_system_status(self, system_id: str) -> Dict[str, Any]:
        """
        Return the latest assurance status for a system.

        This is the primary machine-to-machine trust query:

            "Is this AI system currently assured?"
        """

        system = self.registry.get(system_id)

        if system is None:
            raise KeyError(f"System not found: {system_id}")

        assurances = self.assurance_store.list_for_system(system_id)
        latest = self._latest(assurances)

        graph_data = self.graph.graph_for_system(system_id)

        if latest is None:
            return {
                "system_id": system_id,
                "status": "UNKNOWN",
                "system": self._record_to_dict(system),
                "current_assurance": None,
                "graph": graph_data,
            }

        assurance = self._record_to_dict(latest)

        return {
            "system_id": system_id,
            "status": assurance.get("verdict", "UNKNOWN"),
            "system_version": assurance.get("system_version"),
            "environment": assurance.get("environment"),
            "assurance_id": assurance.get("assurance_id"),
            "metrics": assurance.get("metrics", {}),
            "policy_id": assurance.get("policy_id"),
            "reasons": assurance.get("reasons", []),
            "created_at": assurance.get("created_at"),
            "engine_version": assurance.get("engine_version"),
            "system": self._record_to_dict(system),
            "current_assurance": assurance,
            "assurance_history": [
                self._record_to_dict(item)
                for item in sorted(
                    assurances,
                    key=self._created_at,
                    reverse=True,
                )
            ],
            "graph": graph_data,
        }

    # ------------------------------------------------------------------
    # 2. Assurance provenance
    # ------------------------------------------------------------------

    def get_assurance_provenance(
        self,
        assurance_id: str,
    ) -> Dict[str, Any]:
        """
        Return the evidence lineage behind a specific assurance.

        Expected chain:

            System
              -> System Version
              -> Assurance
                 -> Passport
                 -> Evaluation
                    -> Evidence
                 -> Policy
        """

        assurance = self.assurance_store.get(assurance_id)

        if assurance is None:
            raise KeyError(f"Assurance not found: {assurance_id}")

        assurance_dict = self._record_to_dict(assurance)

        system_id = assurance_dict.get("system_id")

        if not system_id:
            raise ValueError(
                f"Assurance {assurance_id} does not contain system_id"
            )

        graph_data = self.graph.graph_for_system(system_id)
        nodes = self._node_map(graph_data)
        edges = self._edge_list(graph_data)

        assurance_node_id = f"assurance:{assurance_id}"

        relevant_node_ids = {assurance_node_id}
        relevant_edge_ids = set()

        # --------------------------------------------------------------
        # Find direct assurance relationships.
        # --------------------------------------------------------------

        for edge in edges:
            source = edge.get("source_id")
            target = edge.get("target_id")
            relationship = edge.get("relationship")

            if source == assurance_node_id:
                relevant_edge_ids.add(edge.get("edge_id"))
                relevant_node_ids.add(target)

            # Link system-version -> assurance.
            if (
                target == assurance_node_id
                and relationship == "HAS_ASSURANCE"
            ):
                relevant_edge_ids.add(edge.get("edge_id"))
                relevant_node_ids.add(source)

        # --------------------------------------------------------------
        # Find system-version -> system.
        # --------------------------------------------------------------

        version_nodes = [
            node_id
            for node_id in relevant_node_ids
            if node_id and node_id.startswith("system-version:")
        ]

        for edge in edges:
            source = edge.get("source_id")
            target = edge.get("target_id")

            if target in version_nodes:
                if edge.get("relationship") == "HAS_VERSION":
                    relevant_edge_ids.add(edge.get("edge_id"))
                    relevant_node_ids.add(source)

        # --------------------------------------------------------------
        # Evaluation -> Evidence.
        # --------------------------------------------------------------

        evaluation_nodes = [
            node_id
            for node_id in relevant_node_ids
            if node_id and node_id.startswith("evaluation:")
        ]

        for edge in edges:
            source = edge.get("source_id")
            target = edge.get("target_id")

            if source in evaluation_nodes:
                if edge.get("relationship") == "SUPPORTED_BY":
                    relevant_edge_ids.add(edge.get("edge_id"))
                    relevant_node_ids.add(target)

        # --------------------------------------------------------------
        # Build categorized provenance.
        # --------------------------------------------------------------

        selected_nodes = [
            nodes[node_id]
            for node_id in relevant_node_ids
            if node_id in nodes
        ]

        selected_edges = [
            edge
            for edge in edges
            if edge.get("edge_id") in relevant_edge_ids
        ]

        by_type: Dict[str, List[Dict[str, Any]]] = {}

        for node in selected_nodes:
            node_type = node.get("node_type", "unknown")
            by_type.setdefault(node_type, []).append(node)

        return {
            "assurance_id": assurance_id,
            "system_id": system_id,
            "system_version": assurance_dict.get("system_version"),
            "verdict": assurance_dict.get("verdict"),
            "assurance": assurance_dict,
            "provenance": {
                "system": by_type.get("system", []),
                "system_versions": by_type.get("system_version", []),
                "assurance": by_type.get("assurance", []),
                "passports": by_type.get("passport", []),
                "evaluations": by_type.get("evaluation", []),
                "evidence": by_type.get("evidence", []),
                "policies": by_type.get("policy", []),
            },
            "edges": selected_edges,
            "graph_engine_version": graph_data.get("engine_version"),
        }

    # ------------------------------------------------------------------
    # 3. Version comparison
    # ------------------------------------------------------------------

    def compare_versions(
        self,
        system_id: str,
        from_version: str,
        to_version: str,
    ) -> Dict[str, Any]:
        """
        Compare the latest assurance for two versions of a system.
        """

        system = self.registry.get(system_id)

        if system is None:
            raise KeyError(f"System not found: {system_id}")

        assurances = self.assurance_store.list_for_system(system_id)

        from_records = [
            item
            for item in assurances
            if getattr(item, "system_version", None) == from_version
        ]

        to_records = [
            item
            for item in assurances
            if getattr(item, "system_version", None) == to_version
        ]

        from_assurance = self._latest(from_records)
        to_assurance = self._latest(to_records)

        if from_assurance is None:
            raise KeyError(
                f"No assurance found for {system_id} version {from_version}"
            )

        if to_assurance is None:
            raise KeyError(
                f"No assurance found for {system_id} version {to_version}"
            )

        old = self._record_to_dict(from_assurance)
        new = self._record_to_dict(to_assurance)

        old_metrics = old.get("metrics", {})
        new_metrics = new.get("metrics", {})

        metric_changes: Dict[str, Dict[str, Any]] = {}

        for metric in sorted(
            set(old_metrics.keys()) | set(new_metrics.keys())
        ):
            old_value = old_metrics.get(metric)
            new_value = new_metrics.get(metric)

            if old_value != new_value:
                metric_changes[metric] = {
                    "from": old_value,
                    "to": new_value,
                }

        changes = {
            "verdict": {
                "from": old.get("verdict"),
                "to": new.get("verdict"),
            },
            "policy_id": {
                "from": old.get("policy_id"),
                "to": new.get("policy_id"),
            },
            "environment": {
                "from": old.get("environment"),
                "to": new.get("environment"),
            },
            "engine_version": {
                "from": old.get("engine_version"),
                "to": new.get("engine_version"),
            },
            "metrics": metric_changes,
            "evaluation_ids": {
                "from": old.get("evaluation_ids", []),
                "to": new.get("evaluation_ids", []),
            },
            "evidence_ids": {
                "from": old.get("evidence_ids", []),
                "to": new.get("evidence_ids", []),
            },
        }

        # Remove unchanged scalar fields.
        scalar_changes = {
            key: value
            for key, value in changes.items()
            if key in {
                "verdict",
                "policy_id",
                "environment",
                "engine_version",
            }
            and value["from"] != value["to"]
        }

        changes["changed_fields"] = list(
            scalar_changes.keys()
        )

        if metric_changes:
            changes["changed_fields"].append("metrics")

        if old.get("evaluation_ids", []) != new.get("evaluation_ids", []):
            changes["changed_fields"].append("evaluation_ids")

        if old.get("evidence_ids", []) != new.get("evidence_ids", []):
            changes["changed_fields"].append("evidence_ids")

        return {
            "system_id": system_id,
            "from_version": from_version,
            "to_version": to_version,
            "from_assurance": old,
            "to_assurance": new,
            "changes": changes,
        }