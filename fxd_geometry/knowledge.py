"""Local, attributable correction records without source-CAD payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .concepts import CompleteFixtureConcept, FixtureCorrection


class KnowledgeError(ValueError):
    """Raised when a knowledge record is incomplete or unsafe to store."""


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeError(f"{label} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class ProposedFeature:
    """Safe feature metadata; deliberately excludes bounds and source refs."""

    identity: str
    kind: str
    rule: str
    parameters: tuple[tuple[str, str], ...] = ()
    units: str = "mm"
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, label in ((self.identity, "feature identity"),
                             (self.kind, "feature kind"), (self.rule, "feature rule"),
                             (self.units, "feature units")):
            _text(value, label)
        if any(not isinstance(key, str) or not key.strip() for key, _ in self.parameters):
            raise KnowledgeError("feature parameter keys must be non-empty")

    @classmethod
    def from_fixture_feature(cls, feature: object) -> "ProposedFeature":
        """Capture traceability metadata while dropping geometry and source refs."""
        return cls(feature.identity, feature.kind, feature.rule,
                   tuple(sorted((key, str(value)) for key, value in feature.parameters.items())),
                   feature.units, feature.assumptions, feature.warnings)

    def to_training_dict(self) -> dict[str, object]:
        """Return reusable feature semantics without project-local identity."""
        return {
            "kind": self.kind,
            "rule": self.rule,
            "parameters": self.parameters,
            "units": self.units,
            "warnings_present": bool(self.warnings),
            "assumptions_present": bool(self.assumptions),
        }


@dataclass(frozen=True)
class CorrectionRecord:
    record_id: str
    author: str
    recorded_at: str
    source_digest: str
    concept_identity: str
    proposed_features: tuple[ProposedFeature, ...]
    correction: FixtureCorrection
    decision: str = "proposed"
    rejection_reason: str | None = None
    accepted_outcome: str | None = None
    knowledge_kind: str = "lesson"
    scope: str = "single_project"
    confidence: float = 0.0
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, label in ((self.record_id, "record_id"), (self.author, "author"),
                             (self.recorded_at, "recorded_at"),
                             (self.source_digest, "source_digest"),
                             (self.concept_identity, "concept_identity"),
                             (self.knowledge_kind, "knowledge_kind"), (self.scope, "scope")):
            _text(value, label)
        if len(self.source_digest) != 64 or any(c not in "0123456789abcdef" for c in self.source_digest.lower()):
            raise KnowledgeError("source_digest must be a SHA-256 hexadecimal digest")
        if self.decision not in {"proposed", "accepted", "rejected"}:
            raise KnowledgeError("decision must be proposed, accepted, or rejected")
        if self.decision == "rejected" and not self.rejection_reason:
            raise KnowledgeError("rejected records require rejection_reason")
        if self.decision == "accepted" and not self.accepted_outcome:
            raise KnowledgeError("accepted records require accepted_outcome")
        if not 0.0 <= self.confidence <= 1.0:
            raise KnowledgeError("confidence must be between 0 and 1")
        if self.knowledge_kind not in {"lesson", "preference", "rule_candidate"}:
            raise KnowledgeError("knowledge_kind must be lesson, preference, or rule_candidate")
        if self.scope == "universal" and self.knowledge_kind != "rule_candidate":
            raise KnowledgeError("only a rule_candidate may claim universal scope")

    @classmethod
    def from_concept(cls, record_id: str, author: str, recorded_at: str,
                     concept: CompleteFixtureConcept, correction: FixtureCorrection,
                     *, decision: str = "proposed", rejection_reason: str | None = None,
                     accepted_outcome: str | None = None, knowledge_kind: str = "lesson",
                     scope: str = "single_project", confidence: float = 0.0,
                     evidence: Iterable[str] = ()) -> "CorrectionRecord":
        return cls(record_id, author, recorded_at, concept.fixture.source_sha256,
                   concept.identity,
                   tuple(ProposedFeature.from_fixture_feature(item) for item in concept.fixture.features),
                   correction, decision, rejection_reason, accepted_outcome,
                   knowledge_kind, scope, confidence, tuple(evidence))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_training_dict(self) -> dict[str, object]:
        """Return reusable engineering knowledge without audit or project identity.

        The full local record keeps attribution and evidence for engineering audit.
        The training view intentionally excludes author, timestamps, record ids,
        source/concept ids, feature ids, and free-form evidence because those may
        identify a person, customer, shop, or project.
        """
        return {
            "proposed_features": [item.to_training_dict() for item in self.proposed_features],
            "correction": asdict(self.correction),
            "decision": self.decision,
            "rejection_reason": self.rejection_reason,
            "accepted_outcome": self.accepted_outcome,
            "knowledge_kind": self.knowledge_kind,
            "scope": self.scope,
            "confidence": self.confidence,
            "privacy": "audit_and_source_identity_excluded",
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CorrectionRecord":
        features = tuple(ProposedFeature(
            item["identity"], item["kind"], item["rule"], tuple(tuple(pair) for pair in item.get("parameters", ())),
            item.get("units", "mm"), tuple(item.get("assumptions", ())), tuple(item.get("warnings", ())))
                        for item in data["proposed_features"])
        correction = FixtureCorrection(**data["correction"])
        return cls(data["record_id"], data["author"], data["recorded_at"],
                   data["source_digest"], data["concept_identity"], features,
                   correction, data.get("decision", "proposed"),
                   data.get("rejection_reason"), data.get("accepted_outcome"),
                   data.get("knowledge_kind", "lesson"), data.get("scope", "single_project"),
                   data.get("confidence", 0.0), tuple(data.get("evidence", ())))


@dataclass(frozen=True)
class KnowledgeStore:
    records: tuple[CorrectionRecord, ...] = ()

    def add(self, record: CorrectionRecord) -> "KnowledgeStore":
        if any(item.record_id == record.record_id for item in self.records):
            raise KnowledgeError(f"duplicate record_id {record.record_id!r}")
        return KnowledgeStore(self.records + (record,))

    def save(self, path: str | Path) -> None:
        payload = {"schema_version": "fxd-knowledge-v1",
                   "records": [item.to_dict() for item in self.records]}
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def save_training_view(self, path: str | Path) -> None:
        payload = {"schema_version": "fxd-training-knowledge-v1",
                   "records": [item.to_training_dict() for item in self.records]}
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeStore":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != "fxd-knowledge-v1":
            raise KnowledgeError("unsupported knowledge schema")
        store = cls()
        for item in payload.get("records", ()):
            store = store.add(CorrectionRecord.from_dict(item))
        return store


def private_knowledge_path(root: str | Path = ".fxd") -> Path:
    """Return the ignored local store location; never creates or populates it."""
    return Path(root) / "knowledge" / "corrections.json"


def digest_text(value: str) -> str:
    """Hash a non-geometry note when a caller needs a stable evidence id."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
