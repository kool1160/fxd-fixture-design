"""Versioned, public fixture precedent and deterministic local retrieval.

This library is deliberately separate from :mod:`fxd_geometry.knowledge`,
which stores private, project-scoped correction records below ``.fxd``.  The
records loaded here contain only public-source metadata, original paraphrases,
and abstract human-review evidence suitable for this public repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable


FIXTURE_KNOWLEDGE_SCHEMA = "fxd-fixture-knowledge-v1"
FIXTURE_KNOWLEDGE_SOURCE_SCHEMA = "fxd-fixture-knowledge-sources-v1"
FIXTURE_KNOWLEDGE_RECORD_TYPES = frozenset({
    "engineering_principle",
    "fixture_pattern",
    "component_application",
    "human_acceptance",
    "human_rejection",
})


class FixtureKnowledgeError(ValueError):
    """Raised when public precedent is malformed, ambiguous, or untraceable."""


def _strings(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise FixtureKnowledgeError(f"{field} must be a list of nonempty strings")
    return tuple(value)


@dataclass(frozen=True)
class FixtureKnowledgeSource:
    identity: str
    publisher: str
    title: str
    url: str | None
    source_type: str
    reuse_classification: str
    licensing_note: str
    accessed: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FixtureKnowledgeSource":
        required = ("identity", "publisher", "title", "source_type",
                    "reuse_classification", "licensing_note", "accessed")
        if any(not isinstance(data.get(key), str) or not str(data[key]).strip() for key in required):
            raise FixtureKnowledgeError("knowledge sources require stable identity and complete provenance")
        url = data.get("url")
        if url is not None and (not isinstance(url, str) or not url.startswith("https://")):
            raise FixtureKnowledgeError(f"source {data['identity']} has a malformed public URL")
        return cls(*(str(data[key]) for key in required[:3]), url,
                   *(str(data[key]) for key in required[3:]))

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "publisher": self.publisher,
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "reuse_classification": self.reuse_classification,
            "licensing_note": self.licensing_note,
            "accessed": self.accessed,
        }


@dataclass(frozen=True)
class FixtureKnowledgeRecord:
    identity: str
    schema_version: str
    record_type: str
    title: str
    summary: str
    fixture_families: tuple[str, ...]
    assembly_forms: tuple[str, ...]
    material_forms: tuple[str, ...]
    processes: tuple[str, ...]
    production_volumes: tuple[str, ...]
    handling_modes: tuple[str, ...]
    build_orientations: tuple[str, ...]
    construction_methods: tuple[str, ...]
    component_families: tuple[str, ...]
    datum_hierarchy: tuple[str, ...]
    constrained_dofs: tuple[str, ...]
    floating_dofs: tuple[str, ...]
    support_strategy: tuple[str, ...]
    locator_strategy: tuple[str, ...]
    stop_strategy: tuple[str, ...]
    foolproof_strategy: tuple[str, ...]
    clamp_strategy: tuple[str, ...]
    reaction_strategy: tuple[str, ...]
    base_strategy: tuple[str, ...]
    station_repetition: tuple[str, ...]
    weld_access: tuple[str, ...]
    load_unload: tuple[str, ...]
    distortion_heat_spatter: tuple[str, ...]
    cleaning_maintenance: tuple[str, ...]
    changeover: tuple[str, ...]
    failure_modes: tuple[str, ...]
    selection_criteria: tuple[str, ...]
    assumptions: tuple[str, ...]
    confidence: str
    source_ids: tuple[str, ...]
    related_record_ids: tuple[str, ...]
    human_disposition: str
    downstream_dependencies: tuple[str, ...]
    station_count_range: tuple[int, int] | None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FixtureKnowledgeRecord":
        scalar_fields = ("identity", "schema_version", "record_type", "title", "summary",
                         "confidence", "human_disposition")
        if any(not isinstance(data.get(key), str) or not str(data[key]).strip() for key in scalar_fields):
            raise FixtureKnowledgeError("knowledge records require complete scalar identity and disposition")
        if data["schema_version"] != FIXTURE_KNOWLEDGE_SCHEMA:
            raise FixtureKnowledgeError(f"record {data['identity']} has unsupported schema_version")
        if data["record_type"] not in FIXTURE_KNOWLEDGE_RECORD_TYPES:
            raise FixtureKnowledgeError(f"record {data['identity']} has unsupported record_type")
        tuple_fields = (
            "fixture_families", "assembly_forms", "material_forms", "processes",
            "production_volumes", "handling_modes", "build_orientations",
            "construction_methods", "component_families", "datum_hierarchy",
            "constrained_dofs", "floating_dofs", "support_strategy", "locator_strategy",
            "stop_strategy", "foolproof_strategy", "clamp_strategy", "reaction_strategy",
            "base_strategy", "station_repetition", "weld_access", "load_unload",
            "distortion_heat_spatter", "cleaning_maintenance", "changeover",
            "failure_modes", "selection_criteria", "assumptions", "source_ids",
            "related_record_ids", "downstream_dependencies",
        )
        values = [_strings(data.get(field, []), field) for field in tuple_fields]
        if not values[28]:
            raise FixtureKnowledgeError(f"record {data['identity']} has no source provenance")
        count_range = data.get("station_count_range")
        parsed_range = None
        if count_range is not None:
            if (not isinstance(count_range, list) or len(count_range) != 2
                    or any(not isinstance(item, int) or item < 1 for item in count_range)
                    or count_range[0] > count_range[1]):
                raise FixtureKnowledgeError(f"record {data['identity']} has invalid station_count_range")
            parsed_range = (count_range[0], count_range[1])
        return cls(
            *(str(data[key]) for key in scalar_fields[:5]),
            *values[:28],
            str(data["confidence"]),
            values[28],
            values[29],
            str(data["human_disposition"]),
            values[30],
            parsed_range,
        )

    def to_dict(self) -> dict[str, object]:
        result = {
            "identity": self.identity,
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "title": self.title,
            "summary": self.summary,
        }
        for field in (
            "fixture_families", "assembly_forms", "material_forms", "processes",
            "production_volumes", "handling_modes", "build_orientations",
            "construction_methods", "component_families", "datum_hierarchy",
            "constrained_dofs", "floating_dofs", "support_strategy", "locator_strategy",
            "stop_strategy", "foolproof_strategy", "clamp_strategy", "reaction_strategy",
            "base_strategy", "station_repetition", "weld_access", "load_unload",
            "distortion_heat_spatter", "cleaning_maintenance", "changeover",
            "failure_modes", "selection_criteria", "assumptions",
        ):
            result[field] = list(getattr(self, field))
        result.update({
            "confidence": self.confidence,
            "source_ids": list(self.source_ids),
            "related_record_ids": list(self.related_record_ids),
            "human_disposition": self.human_disposition,
            "downstream_dependencies": list(self.downstream_dependencies),
            "station_count_range": list(self.station_count_range) if self.station_count_range else None,
        })
        return result


@dataclass(frozen=True)
class FixtureKnowledgeLibrary:
    schema_version: str
    records: tuple[FixtureKnowledgeRecord, ...]
    sources: tuple[FixtureKnowledgeSource, ...]

    def __post_init__(self) -> None:
        if self.schema_version != FIXTURE_KNOWLEDGE_SCHEMA:
            raise FixtureKnowledgeError("unsupported fixture knowledge library schema")
        record_ids = [item.identity for item in self.records]
        source_ids = [item.identity for item in self.sources]
        if len(record_ids) != len(set(record_ids)) or record_ids != sorted(record_ids):
            raise FixtureKnowledgeError("knowledge record identities must be unique and stably ordered")
        if len(source_ids) != len(set(source_ids)) or source_ids != sorted(source_ids):
            raise FixtureKnowledgeError("knowledge source identities must be unique and stably ordered")
        known_records, known_sources = set(record_ids), set(source_ids)
        for record in self.records:
            missing_sources = set(record.source_ids) - known_sources
            missing_records = set(record.related_record_ids) - known_records
            if missing_sources:
                raise FixtureKnowledgeError(
                    f"record {record.identity} references unknown sources {sorted(missing_sources)}"
                )
            if missing_records:
                raise FixtureKnowledgeError(
                    f"record {record.identity} references unknown records {sorted(missing_records)}"
                )

    def to_json(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "records": [item.to_dict() for item in self.records],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    @property
    def evidence_digest(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "records": [item.to_dict() for item in self.records],
            "sources": [item.to_dict() for item in self.sources],
        }
        return sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PrecedentQuery:
    fixture_family: str
    assembly_form: str
    material_form: str
    process: str
    production_volume: str
    handling_mode: str
    build_orientation: str
    construction_method: str
    station_count: int | None = None
    datum_opportunities: tuple[str, ...] = ()
    support_opportunities: tuple[str, ...] = ()
    locator_opportunities: tuple[str, ...] = ()
    clamp_direction: str = ""
    load_unload_intent: tuple[str, ...] = ()
    weld_access: tuple[str, ...] = ()
    changeover_needs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrecedentMatch:
    record_identity: str
    record_type: str
    score: int
    score_components: tuple[str, ...]
    matching_fields: tuple[str, ...]
    conflicts: tuple[str, ...]
    assumptions: tuple[str, ...]
    failure_modes: tuple[str, ...]
    source_ids: tuple[str, ...]
    applicable: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "record_identity": self.record_identity,
            "record_type": self.record_type,
            "score": self.score,
            "score_components": list(self.score_components),
            "matching_fields": list(self.matching_fields),
            "conflicts": list(self.conflicts),
            "assumptions": list(self.assumptions),
            "failure_modes": list(self.failure_modes),
            "source_ids": list(self.source_ids),
            "applicable": self.applicable,
        }


@dataclass(frozen=True)
class PrecedentRetrievalResult:
    library_evidence_digest: str
    query: PrecedentQuery
    selected: tuple[PrecedentMatch, ...]
    rejected_constraints: tuple[PrecedentMatch, ...]
    non_applicable: tuple[PrecedentMatch, ...]
    unresolved_questions: tuple[str, ...]

    @property
    def selected_record_identities(self) -> tuple[str, ...]:
        return tuple(item.record_identity for item in self.selected)

    def compact_context(self) -> dict[str, object]:
        return {
            "library_schema_version": FIXTURE_KNOWLEDGE_SCHEMA,
            "library_evidence_digest": self.library_evidence_digest,
            "selected": [item.to_dict() for item in self.selected],
            "human_rejection_constraints": [
                item.to_dict() for item in self.rejected_constraints
            ],
            "non_applicable_record_ids": [
                item.record_identity for item in self.non_applicable
            ],
            "unresolved_questions": list(self.unresolved_questions),
        }


_MATCH_FIELDS = (
    ("fixture_family", "fixture_families", 12),
    ("assembly_form", "assembly_forms", 5),
    ("material_form", "material_forms", 5),
    ("process", "processes", 8),
    ("production_volume", "production_volumes", 3),
    ("handling_mode", "handling_modes", 5),
    ("build_orientation", "build_orientations", 3),
    ("construction_method", "construction_methods", 5),
)


def _normalized(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _match_record(record: FixtureKnowledgeRecord, query: PrecedentQuery) -> PrecedentMatch:
    score, components, matches, conflicts = 0, [], [], []
    for query_field, record_field, weight in _MATCH_FIELDS:
        query_value = _normalized(str(getattr(query, query_field)))
        candidates = tuple(_normalized(item) for item in getattr(record, record_field))
        if not candidates or "*" in candidates:
            continue
        if query_value and any(query_value == item or query_value in item or item in query_value
                               for item in candidates):
            score += weight
            components.append(f"{query_field}=+{weight}")
            matches.append(query_field)
        elif query_value:
            score -= weight
            components.append(f"{query_field}=-{weight}")
            conflicts.append(query_field)
    if query.station_count is not None and record.station_count_range is not None:
        low, high = record.station_count_range
        if low <= query.station_count <= high:
            score += 6
            components.append("station_count=+6")
            matches.append("station_count")
        else:
            score -= 6
            components.append("station_count=-6")
            conflicts.append("station_count")
    if record.human_disposition == "rejected":
        components.append("human_rejection=constraint_only")
    applicable = score > 0 and "fixture_family" not in conflicts
    return PrecedentMatch(
        record.identity, record.record_type, score, tuple(components),
        tuple(matches), tuple(conflicts), record.assumptions,
        record.failure_modes, record.source_ids, applicable,
    )


def retrieve_precedent(library: FixtureKnowledgeLibrary, query: PrecedentQuery,
                       *, limit: int = 6) -> PrecedentRetrievalResult:
    """Rank public precedent deterministically with stable identity tie-breaking."""
    if limit < 1:
        raise FixtureKnowledgeError("precedent result limit must be positive")
    matches = tuple(_match_record(record, query) for record in library.records)
    selected_pool = tuple(item for item in matches if item.applicable
                          and item.record_type != "human_rejection")
    selected = tuple(sorted(
        selected_pool, key=lambda item: (-item.score, item.record_identity),
    )[:limit])
    rejected = tuple(sorted(
        (item for item in matches
         if item.record_type == "human_rejection" and item.applicable),
        key=lambda item: (-item.score, item.record_identity),
    ))
    non_applicable = tuple(sorted(
        (item for item in matches if not item.applicable),
        key=lambda item: item.record_identity,
    ))
    unresolved = []
    for value, question in (
        (query.datum_opportunities, "Confirm primary, secondary, and tertiary datum features."),
        (query.weld_access, "Confirm tack and full-weld corridors."),
        (query.load_unload_intent, "Confirm loading, clamp, release, and unloading sequence."),
        (query.clamp_direction, "Confirm clamp working direction and reaction supports."),
    ):
        if not value:
            unresolved.append(question)
    return PrecedentRetrievalResult(
        library.evidence_digest, query, selected, rejected, non_applicable,
        tuple(unresolved),
    )


def _default_data_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "fixture_knowledge" / name


def load_fixture_knowledge(
    records_path: str | Path | None = None,
    sources_path: str | Path | None = None,
) -> FixtureKnowledgeLibrary:
    records_path = Path(records_path) if records_path else _default_data_path("fixture_knowledge_v1.json")
    sources_path = Path(sources_path) if sources_path else _default_data_path("fixture_knowledge_sources_v1.json")
    records_payload = json.loads(records_path.read_text(encoding="utf-8"))
    sources_payload = json.loads(sources_path.read_text(encoding="utf-8"))
    if records_payload.get("schema_version") != FIXTURE_KNOWLEDGE_SCHEMA:
        raise FixtureKnowledgeError("unsupported fixture knowledge file schema")
    if sources_payload.get("schema_version") != FIXTURE_KNOWLEDGE_SOURCE_SCHEMA:
        raise FixtureKnowledgeError("unsupported fixture knowledge source schema")
    records = tuple(FixtureKnowledgeRecord.from_dict(item)
                    for item in records_payload.get("records", ()))
    sources = tuple(FixtureKnowledgeSource.from_dict(item)
                    for item in sources_payload.get("sources", ()))
    return FixtureKnowledgeLibrary(FIXTURE_KNOWLEDGE_SCHEMA, records, sources)


def knowledge_record_counts(records: Iterable[FixtureKnowledgeRecord]) -> dict[str, int]:
    counts = {kind: 0 for kind in sorted(FIXTURE_KNOWLEDGE_RECORD_TYPES)}
    for record in records:
        counts[record.record_type] += 1
    return counts
