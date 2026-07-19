"""Provider-neutral AI fixture proposals governed by deterministic validation.

The module sends compact structured summaries, never STEP bytes. AI output is
strictly parsed into a versioned contract and remains subordinate to the
existing placement, concept, validation, revision, and export gates.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from threading import Event
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .aabb import Vec3
from .annotations import GeometryReference
from .interactive_workflow import (
    AnnotationRole,
    InteractiveWorkflow,
    ProcessSetup,
    analyze_engineering_workflow,
    face_annotation,
)
from .manufacturing_orientation import ManufacturingOrientationError
from .placement import PlacementRole
from .project import FxdProject, ProjectFormatError
from .workbench import WorkbenchDocument


PROPOSAL_SCHEMA = "fxd-fixture-proposal-v1"
PROPOSAL_REQUEST_SCHEMA = "fxd-fixture-proposal-request-v1"
PROMPT_CONTRACT_VERSION = "fxd-fixture-engineer-prompt-v1"
OPENAI_PROMPT_CONTRACT_VERSION = "fxd-fixture-engineer-openai-responses-prompt-v1"
OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MAX_CONTEXT_BYTES = 512_000
OPENAI_MAX_RESPONSE_BYTES = 1_000_000
OPENAI_MAX_TIMEOUT_SECONDS = 60.0
OPENAI_MAX_OUTPUT_TOKENS = 4_096


class FixtureProposalError(ValueError):
    """Raised when proposal evidence is malformed, stale, or unsupported."""


class ProviderUnavailable(FixtureProposalError):
    """Raised when no configured AI provider can run."""


class ProposalCancelled(FixtureProposalError):
    """Raised when proposal generation is cancelled safely."""


class MissingIntentError(FixtureProposalError):
    def __init__(self, questions: tuple["IntentQuestion", ...]) -> None:
        self.questions = questions
        super().__init__("essential manufacturing intent requires engineer confirmation")


class ProposalSource(str, Enum):
    AI = "ai"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class ProviderState(str, Enum):
    SUCCESS = "ai_proposal_generated"
    UNAVAILABLE = "ai_unavailable"
    FAILED = "proposal_generation_failed"
    FALLBACK = "deterministic_fallback_used"
    CANCELLED = "proposal_generation_cancelled"


class RecommendationType(str, Enum):
    ORIENTATION = "orientation"
    DATUM = "datum"
    LOCATOR = "locator"
    SUPPORT = "support"
    CLAMP = "clamp"
    BASE_STRUCTURE = "base_structure"
    WELD_ACCESS = "weld_or_tack_access"
    LOAD_UNLOAD = "load_and_unload"
    OPERATOR_AUTOMATION_ACCESS = "operator_or_automation_access"
    STANDARD_COMPONENT = "standard_component"
    MANUFACTURING_LIFECYCLE = "manufacturing_and_lifecycle"
    UNRESOLVED_QUESTION = "unresolved_question"
    ALTERNATIVE = "alternative"


class RecommendationDecision(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPPRESSED = "suppressed"
    EDITED = "edited"


class RecommendationValidation(str, Enum):
    PASSED = "passed"
    PROVISIONAL = "provisional"
    BLOCKED = "blocked"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class CancellationToken:
    """Cooperative cancellation used before and after provider I/O."""

    _event: Event

    @classmethod
    def create(cls) -> "CancellationToken":
        return cls(Event())

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ProposalCancelled("proposal generation was cancelled")


@dataclass(frozen=True)
class IntentQuestion:
    field: str
    prompt: str
    why_it_matters: str
    recommended_answer: object
    units: str | None = None

    def __post_init__(self) -> None:
        if not self.field or not self.prompt or not self.why_it_matters:
            raise FixtureProposalError("intent questions require field, prompt, and reason")


@dataclass(frozen=True)
class ProposalEvidence:
    identity: str
    kind: str
    summary: str

    def __post_init__(self) -> None:
        if not self.identity or not self.kind or not self.summary:
            raise FixtureProposalError("proposal evidence requires identity, kind, and summary")


@dataclass(frozen=True)
class EditableParameter:
    name: str
    value: object
    units: str | None = None
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise FixtureProposalError("editable proposal parameters require a name")
        try:
            json.dumps(self.value)
        except (TypeError, ValueError) as exc:
            raise FixtureProposalError("editable parameter values must be JSON serializable") from exc


@dataclass(frozen=True)
class ProposalRecommendation:
    recommendation_id: str
    recommendation_type: RecommendationType
    title: str
    engineering_reason: str
    source_evidence: tuple[ProposalEvidence, ...]
    assumptions: tuple[str, ...]
    confidence: float
    deterministic_checks: tuple[str, ...]
    validation_status: RecommendationValidation
    unresolved_risks: tuple[str, ...]
    editable_parameters: tuple[EditableParameter, ...]
    downstream_dependencies: tuple[str, ...]
    geometry_reference: GeometryReference | None = None
    fixture_feature_identity: str | None = None
    decision: RecommendationDecision = RecommendationDecision.PROPOSED
    engineer_note: str = ""

    def __post_init__(self) -> None:
        if not self.recommendation_id or not self.title or not self.engineering_reason:
            raise FixtureProposalError("recommendations require ID, title, and engineering reason")
        if not isinstance(self.recommendation_type, RecommendationType):
            raise FixtureProposalError("unsupported recommendation type")
        if not self.source_evidence:
            raise FixtureProposalError("every recommendation requires source evidence")
        if not 0.0 <= self.confidence <= 1.0:
            raise FixtureProposalError("recommendation confidence must be between zero and one")
        if not self.deterministic_checks:
            raise FixtureProposalError("every recommendation must name deterministic checks")

    def to_dict(self) -> dict[str, object]:
        return {
            "recommendation_id": self.recommendation_id,
            "recommendation_type": self.recommendation_type.value,
            "title": self.title,
            "engineering_reason": self.engineering_reason,
            "source_evidence": [
                {"identity": item.identity, "kind": item.kind, "summary": item.summary}
                for item in self.source_evidence
            ],
            "assumptions": list(self.assumptions),
            "confidence": self.confidence,
            "deterministic_checks": list(self.deterministic_checks),
            "validation_status": self.validation_status.value,
            "unresolved_risks": list(self.unresolved_risks),
            "editable_parameters": [
                {"name": item.name,
                 "value": json.loads(json.dumps(item.value)), "units": item.units,
                 "choices": list(item.choices)} for item in self.editable_parameters
            ],
            "downstream_dependencies": list(self.downstream_dependencies),
            "geometry_reference": (
                dict(self.geometry_reference.__dict__) if self.geometry_reference else None
            ),
            "fixture_feature_identity": self.fixture_feature_identity,
            "decision": self.decision.value,
            "engineer_note": self.engineer_note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ProposalRecommendation":
        reference = data.get("geometry_reference")
        return cls(
            str(data["recommendation_id"]),
            RecommendationType(data["recommendation_type"]),
            str(data["title"]), str(data["engineering_reason"]),
            tuple(ProposalEvidence(**item) for item in data["source_evidence"]),
            tuple(str(item) for item in data.get("assumptions", ())),
            float(data["confidence"]),
            tuple(str(item) for item in data["deterministic_checks"]),
            RecommendationValidation(data.get("validation_status", "not_evaluated")),
            tuple(str(item) for item in data.get("unresolved_risks", ())),
            tuple(EditableParameter(
                str(item["name"]), item.get("value"), item.get("units"),
                tuple(str(value) for value in item.get("choices", ())),
            ) for item in data.get("editable_parameters", ())),
            tuple(str(item) for item in data.get("downstream_dependencies", ())),
            GeometryReference(**reference) if isinstance(reference, dict) else None,
            data.get("fixture_feature_identity"),
            RecommendationDecision(data.get("decision", "proposed")),
            str(data.get("engineer_note", "")),
        )


@dataclass(frozen=True)
class GuidedValidationIssue:
    issue_id: str
    severity: str
    title: str
    what_is_wrong: str
    why_it_matters: str
    rule_id: str
    affected_identity: str | None
    workflow_section: str
    fix_target: str
    technical_details: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in {"error", "warning", "info"}:
            raise FixtureProposalError("guided issue severity is unsupported")
        if not all((self.issue_id, self.title, self.what_is_wrong, self.why_it_matters,
                    self.rule_id, self.workflow_section, self.fix_target)):
            raise FixtureProposalError("guided issues require correction-routing evidence")


@dataclass(frozen=True)
class ProposalProvenance:
    source: ProposalSource
    provider_identity: str
    engine_identifier: str
    prompt_contract_version: str
    response_contract_version: str
    generated_at_utc: str
    provider_state: ProviderState
    provider_message: str = ""


@dataclass(frozen=True)
class ProposalAuditEvent:
    action: str
    target: str
    note: str
    timestamp_utc: str
    prior_proposal_identity: str


@dataclass(frozen=True)
class FixtureProposal:
    schema_version: str
    proposal_identity: str
    source_sha256: str
    manufacturing_orientation_identity: str
    engineering_context_identity: str
    concept_name: str
    fixture_purpose: str
    base_strategy: str
    lifecycle: str
    complexity_class: str
    assumptions: tuple[str, ...]
    recommendations: tuple[ProposalRecommendation, ...]
    alternative_summary: str | None
    provenance: ProposalProvenance
    guided_issues: tuple[GuidedValidationIssue, ...] = ()
    audit_history: tuple[ProposalAuditEvent, ...] = ()
    proposal_decision: str = "pending"

    def __post_init__(self) -> None:
        if self.schema_version != PROPOSAL_SCHEMA:
            raise FixtureProposalError("unsupported fixture proposal schema")
        if len(self.source_sha256) != 64:
            raise FixtureProposalError("proposal source SHA-256 is malformed")
        if not self.manufacturing_orientation_identity:
            raise FixtureProposalError("proposal requires manufacturing orientation identity")
        if not self.engineering_context_identity:
            raise FixtureProposalError("proposal requires engineering context identity")
        if len({item.recommendation_id for item in self.recommendations}) != len(self.recommendations):
            raise FixtureProposalError("proposal recommendation IDs must be unique")
        if not self.recommendations:
            raise FixtureProposalError("fixture proposal requires recommendations")
        expected = proposal_identity(self)
        if self.proposal_identity and self.proposal_identity != expected:
            raise FixtureProposalError("proposal identity does not match proposal evidence")

    @property
    def blocker_count(self) -> int:
        return sum(item.severity == "error" for item in self.guided_issues)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.guided_issues)

    @property
    def validation_status(self) -> str:
        return "invalid" if self.blocker_count else (
            "provisional" if self.warning_count else "valid"
        )

    def stale_reason(self, source_sha256: str, orientation_identity: str | None,
                     engineering_context_identity: str | None) -> str | None:
        if source_sha256 != self.source_sha256:
            return "source SHA-256 changed"
        if orientation_identity != self.manufacturing_orientation_identity:
            return "manufacturing orientation changed"
        if engineering_context_identity != self.engineering_context_identity:
            return "manufacturing intent or engineering context changed"
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "proposal_identity": self.proposal_identity,
            "source_sha256": self.source_sha256,
            "manufacturing_orientation_identity": self.manufacturing_orientation_identity,
            "engineering_context_identity": self.engineering_context_identity,
            "concept_name": self.concept_name,
            "fixture_purpose": self.fixture_purpose,
            "base_strategy": self.base_strategy,
            "lifecycle": self.lifecycle,
            "complexity_class": self.complexity_class,
            "assumptions": list(self.assumptions),
            "recommendations": [item.to_dict() for item in self.recommendations],
            "alternative_summary": self.alternative_summary,
            "provenance": {
                "provider_identity": self.provenance.provider_identity,
                "engine_identifier": self.provenance.engine_identifier,
                "prompt_contract_version": self.provenance.prompt_contract_version,
                "response_contract_version": self.provenance.response_contract_version,
                "generated_at_utc": self.provenance.generated_at_utc,
                "provider_message": self.provenance.provider_message,
                "source": self.provenance.source.value,
                "provider_state": self.provenance.provider_state.value,
            },
            "guided_issues": [{
                "issue_id": item.issue_id, "severity": item.severity,
                "title": item.title, "what_is_wrong": item.what_is_wrong,
                "why_it_matters": item.why_it_matters, "rule_id": item.rule_id,
                "affected_identity": item.affected_identity,
                "workflow_section": item.workflow_section, "fix_target": item.fix_target,
                "technical_details": list(item.technical_details),
            } for item in self.guided_issues],
            "audit_history": [{
                "action": item.action, "target": item.target, "note": item.note,
                "timestamp_utc": item.timestamp_utc,
                "prior_proposal_identity": item.prior_proposal_identity,
            } for item in self.audit_history],
            "proposal_decision": self.proposal_decision,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FixtureProposal":
        raw_provenance = dict(data["provenance"])
        raw_provenance["source"] = ProposalSource(raw_provenance["source"])
        raw_provenance["provider_state"] = ProviderState(raw_provenance["provider_state"])
        return cls(
            str(data["schema_version"]), str(data["proposal_identity"]),
            str(data["source_sha256"]), str(data["manufacturing_orientation_identity"]),
            str(data["engineering_context_identity"]),
            str(data["concept_name"]), str(data["fixture_purpose"]),
            str(data["base_strategy"]), str(data["lifecycle"]),
            str(data["complexity_class"]),
            tuple(str(item) for item in data.get("assumptions", ())),
            tuple(ProposalRecommendation.from_dict(item)
                  for item in data.get("recommendations", ())),
            data.get("alternative_summary"), ProposalProvenance(**raw_provenance),
            tuple(GuidedValidationIssue(
                str(item["issue_id"]), str(item["severity"]), str(item["title"]),
                str(item["what_is_wrong"]), str(item["why_it_matters"]),
                str(item["rule_id"]), item.get("affected_identity"),
                str(item["workflow_section"]), str(item["fix_target"]),
                tuple(str(value) for value in item.get("technical_details", ())),
            ) for item in data.get("guided_issues", ())),
            tuple(ProposalAuditEvent(**item) for item in data.get("audit_history", ())),
            str(data.get("proposal_decision", "pending")),
        )


def _identity_payload(proposal: FixtureProposal) -> dict[str, object]:
    return {
        "schema": proposal.schema_version,
        "source": proposal.source_sha256,
        "orientation": proposal.manufacturing_orientation_identity,
        "engineering_context": proposal.engineering_context_identity,
        "name": proposal.concept_name,
        "purpose": proposal.fixture_purpose,
        "base": proposal.base_strategy,
        "lifecycle": proposal.lifecycle,
        "complexity": proposal.complexity_class,
        "assumptions": proposal.assumptions,
        "recommendations": [item.to_dict() for item in proposal.recommendations],
        "alternative": proposal.alternative_summary,
        "provenance_source": proposal.provenance.source.value,
        "audit": [item.__dict__ for item in proposal.audit_history],
        "decision": proposal.proposal_decision,
    }


def proposal_identity(proposal: FixtureProposal) -> str:
    encoded = json.dumps(_identity_payload(proposal), sort_keys=True, separators=(",", ":"))
    return "proposal-" + sha256(encoded.encode()).hexdigest()[:20]


def _finalize(proposal: FixtureProposal) -> FixtureProposal:
    return replace(proposal, proposal_identity=proposal_identity(proposal))


@dataclass(frozen=True)
class AiProposalRequest:
    schema_version: str
    prompt_contract_version: str
    source_sha256: str
    manufacturing_orientation_identity: str
    engineering_context_identity: str
    context: dict[str, object]
    known_identities: frozenset[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "prompt_contract_version": self.prompt_contract_version,
            "source_sha256": self.source_sha256,
            "manufacturing_orientation_identity": self.manufacturing_orientation_identity,
            "engineering_context_identity": self.engineering_context_identity,
            "context": self.context,
        }


class AiFixtureProvider(Protocol):
    identity: str
    engine_identifier: str

    @property
    def available(self) -> bool: ...

    def generate(self, request: AiProposalRequest, *, timeout_seconds: float,
                 cancellation: CancellationToken) -> dict[str, object]: ...


class UnavailableAiProvider:
    identity = "unavailable"
    engine_identifier = "none"
    available = False

    def generate(self, request: AiProposalRequest, *, timeout_seconds: float,
                 cancellation: CancellationToken) -> dict[str, object]:
        raise ProviderUnavailable("AI provider is not configured")


class StaticAiProvider:
    """Deterministic fixture provider for tests; never used as a runtime AI claim."""

    def __init__(self, response: dict[str, object], *, identity: str = "test-provider",
                 engine_identifier: str = "fixture-model") -> None:
        self.response = response
        self.identity = identity
        self.engine_identifier = engine_identifier
        self.available = True

    def generate(self, request: AiProposalRequest, *, timeout_seconds: float,
                 cancellation: CancellationToken) -> dict[str, object]:
        cancellation.raise_if_cancelled()
        return json.loads(json.dumps(self.response))


def _strict_object(properties: dict[str, object]) -> dict[str, object]:
    """Return the strict object form required by OpenAI Structured Outputs."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _openai_proposal_response_schema() -> dict[str, object]:
    """Schema bridge for the existing proposal parser; no new proposal model."""
    text = {"type": "string"}
    nullable_text = {"type": ["string", "null"]}
    text_list = {"type": "array", "items": text}
    evidence = _strict_object({"identity": text, "kind": text, "summary": text})
    editable_parameter = _strict_object({
        "name": text,
        "value": {"type": ["string", "number", "boolean", "null"]},
        "units": nullable_text,
        "choices": text_list,
    })
    geometry_reference = _strict_object({
        "component_identity": text,
        "body_identity": nullable_text,
        "face_identity": nullable_text,
        "edge_identity": nullable_text,
    })
    recommendation = _strict_object({
        "recommendation_id": text,
        "recommendation_type": {
            "type": "string", "enum": [item.value for item in RecommendationType],
        },
        "title": text,
        "engineering_reason": text,
        "source_evidence": {"type": "array", "items": evidence},
        "assumptions": text_list,
        "confidence": {"type": "number"},
        "deterministic_checks": text_list,
        "validation_status": text,
        "unresolved_risks": text_list,
        "editable_parameters": {"type": "array", "items": editable_parameter},
        "downstream_dependencies": text_list,
        "geometry_reference": {
            "type": ["object", "null"],
            "properties": geometry_reference["properties"],
            "required": geometry_reference["required"],
            "additionalProperties": False,
        },
        "fixture_feature_identity": nullable_text,
        "decision": {"type": "string", "enum": [RecommendationDecision.PROPOSED.value]},
        "engineer_note": {"type": "string", "enum": [""]},
    })
    return _strict_object({
        "schema_version": {"type": "string", "enum": [PROPOSAL_SCHEMA]},
        "source_sha256": text,
        "manufacturing_orientation_identity": text,
        "engineering_context_identity": text,
        "concept_name": text,
        "fixture_purpose": text,
        "base_strategy": text,
        "lifecycle": text,
        "complexity_class": text,
        "assumptions": text_list,
        "recommendations": {"type": "array", "items": recommendation},
        "alternative_summary": nullable_text,
    })


class OpenAiResponsesProvider:
    """OpenAI Responses adapter that returns the existing typed proposal payload.

    It deliberately sends compact FXD context only. Geometry, source bytes,
    credentials, and project files never cross this provider boundary.
    """

    identity = "openai"
    prompt_contract_version = OPENAI_PROMPT_CONTRACT_VERSION

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.engine_identifier = model

    @property
    def available(self) -> bool:
        return bool(self._api_key and self.engine_identifier)

    @classmethod
    def from_environment(cls) -> AiFixtureProvider:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        model = (os.environ.get("FXD_OPENAI_MODEL", "").strip()
                 or os.environ.get("FXD_AI_MODEL", "").strip())
        if not api_key or not model:
            return UnavailableAiProvider()
        return cls(api_key, model)

    @staticmethod
    def _failure_for_status(status: int) -> FixtureProposalError:
        if status in {401, 403}:
            return FixtureProposalError("OpenAI authentication is unavailable")
        if status in {400, 422}:
            return FixtureProposalError("OpenAI structured-output request was rejected")
        if status == 404:
            return FixtureProposalError("OpenAI model or endpoint is unavailable")
        if status == 429:
            return FixtureProposalError("OpenAI request limit prevented proposal generation")
        return FixtureProposalError("OpenAI Responses request failed")

    @staticmethod
    def _extract_output(raw: object) -> dict[str, object]:
        if not isinstance(raw, dict):
            raise FixtureProposalError("OpenAI response was malformed")
        if raw.get("status") == "incomplete":
            raise FixtureProposalError("OpenAI response was incomplete")
        output = raw.get("output")
        if not isinstance(output, list):
            raise FixtureProposalError("OpenAI response contained no structured output")
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    raise FixtureProposalError("OpenAI response was refused")
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    try:
                        proposal = json.loads(part["text"])
                    except json.JSONDecodeError as exc:
                        raise FixtureProposalError(
                            "OpenAI response did not contain a JSON proposal"
                        ) from exc
                    if isinstance(proposal, dict):
                        return proposal
                    raise FixtureProposalError("OpenAI JSON proposal was not an object")
        raise FixtureProposalError("OpenAI response contained no JSON proposal")

    def generate(self, request: AiProposalRequest, *, timeout_seconds: float,
                 cancellation: CancellationToken) -> dict[str, object]:
        cancellation.raise_if_cancelled()
        request_text = json.dumps(
            request.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        )
        if len(request_text.encode("utf-8")) > OPENAI_MAX_CONTEXT_BYTES:
            raise FixtureProposalError("OpenAI proposal context exceeds the configured safe limit")
        payload = {
            "model": self.engine_identifier,
            "input": [
                {"role": "system", "content": (
                    "Return one FXD fixture proposal object. AI is assistive only; "
                    "FXD deterministic validation remains authoritative. Use only "
                    "provided identities and evidence, state uncertainty in the "
                    "typed fields, and never claim approval, certification, or safety."
                )},
                {"role": "user", "content": request_text},
            ],
            "text": {"format": {
                "type": "json_schema",
                "name": "fxd_fixture_proposal_v1",
                "schema": _openai_proposal_response_schema(),
                "strict": True,
            }},
            "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
            "store": False,
        }
        http_request = Request(
            OPENAI_RESPONSES_ENDPOINT,
            data=json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
            method="POST",
            headers={"Authorization": "Bearer " + self._api_key,
                     "Content-Type": "application/json"},
        )
        bounded_timeout = min(max(float(timeout_seconds), 0.1), OPENAI_MAX_TIMEOUT_SECONDS)
        try:
            with urlopen(http_request, timeout=bounded_timeout) as response:
                response_bytes = response.read()
        except TimeoutError as exc:
            raise TimeoutError("OpenAI fixture proposal timed out") from exc
        except HTTPError as exc:
            raise self._failure_for_status(exc.code) from exc
        except (URLError, OSError) as exc:
            raise FixtureProposalError("OpenAI Responses request was unavailable") from exc
        if len(response_bytes) > OPENAI_MAX_RESPONSE_BYTES:
            raise FixtureProposalError("OpenAI response exceeded the configured safe limit")
        try:
            raw = json.loads(response_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FixtureProposalError("OpenAI response was malformed") from exc
        cancellation.raise_if_cancelled()
        return self._extract_output(raw)


def _sanitized_provider_failure_reason(provider: AiFixtureProvider, exc: Exception) -> str:
    """Keep provider diagnostics useful without retaining response or prompt content."""
    if isinstance(exc, TimeoutError):
        return (
            "OpenAI provider request timed out."
            if provider.identity == "openai" else "AI provider request timed out."
        )
    if provider.identity != "openai":
        return "AI provider failed safely."
    message = str(exc)
    known_reasons = {
        "OpenAI authentication is unavailable",
        "OpenAI structured-output request was rejected",
        "OpenAI model or endpoint is unavailable",
        "OpenAI request limit prevented proposal generation",
        "OpenAI Responses request failed",
        "OpenAI Responses request was unavailable",
        "OpenAI proposal context exceeds the configured safe limit",
        "OpenAI response exceeded the configured safe limit",
        "OpenAI response was malformed",
        "OpenAI response was incomplete",
        "OpenAI response was refused",
        "OpenAI response did not contain a JSON proposal",
        "OpenAI JSON proposal was not an object",
        "OpenAI response contained no structured output",
        "OpenAI response contained no JSON proposal",
    }
    if message in known_reasons:
        return message + "."
    if message.startswith("AI "):
        return "FXD typed proposal contract rejected provider output."
    return "OpenAI provider failed safely."


class HttpJsonAiProvider:
    """Provider-neutral JSON-over-HTTP adapter configured only through environment."""

    def __init__(self, endpoint: str, api_key: str, model: str,
                 *, identity: str = "http-json") -> None:
        self.endpoint = endpoint
        self._api_key = api_key
        self.engine_identifier = model
        self.identity = identity

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self._api_key and self.engine_identifier)

    @classmethod
    def from_environment(cls) -> AiFixtureProvider:
        provider_name = os.environ.get("FXD_AI_PROVIDER", "").strip().lower()
        openai_configured = bool(
            os.environ.get("OPENAI_API_KEY", "").strip()
            or os.environ.get("FXD_OPENAI_MODEL", "").strip()
        )
        if provider_name in {"openai", "openai-responses"} or (
                not provider_name and openai_configured):
            return OpenAiResponsesProvider.from_environment()
        endpoint = os.environ.get("FXD_AI_ENDPOINT", "").strip()
        api_key = os.environ.get("FXD_AI_API_KEY", "").strip()
        model = os.environ.get("FXD_AI_MODEL", "").strip()
        provider = provider_name or "http-json"
        if not all((endpoint, api_key, model)):
            return UnavailableAiProvider()
        return cls(endpoint, api_key, model, identity=provider)

    def generate(self, request: AiProposalRequest, *, timeout_seconds: float,
                 cancellation: CancellationToken) -> dict[str, object]:
        cancellation.raise_if_cancelled()
        system = (
            "Return one JSON fixture proposal matching fxd-fixture-proposal-v1. "
            "Use only supplied identities. AI proposes; deterministic validation wins. "
            "Do not claim approval and do not expose hidden reasoning."
        )
        payload = {
            "model": self.engine_identifier,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(request.to_dict(), sort_keys=True)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        http_request = Request(
            self.endpoint, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + self._api_key,
                     "Content-Type": "application/json"},
        )
        try:
            with urlopen(http_request, timeout=timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise TimeoutError("AI fixture proposal timed out") from exc
        except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
            raise FixtureProposalError(f"AI fixture provider failed: {exc}") from exc
        cancellation.raise_if_cancelled()
        if not isinstance(raw, dict):
            raise FixtureProposalError("AI provider returned a non-object response")
        if isinstance(raw.get("proposal"), dict):
            return raw["proposal"]
        try:
            content = raw["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            if isinstance(raw, dict):
                return raw
            raise FixtureProposalError("AI provider returned no structured proposal")


@dataclass(frozen=True)
class ProposalGenerationOutcome:
    project: FxdProject
    proposal: FixtureProposal
    provider_state: ProviderState
    message: str


def minimal_intent_questions(workflow: InteractiveWorkflow) -> tuple[IntentQuestion, ...]:
    setup = workflow.setup
    values = (
        ("fixture_type", setup.fixture_type, "What fixture purpose is required?",
         "Purpose changes locating, access, validation, and lifecycle requirements.",
         "Full weld fixture", None),
        ("manufacturing_process", setup.manufacturing_process,
         "What process will the fixture support?",
         "Process choice changes weld or assembly access and restraint assumptions.",
         "MIG welding", None),
        ("operation_mode", setup.operation_mode, "How will the fixture be handled?",
         "Manual, cobot, and robotic handling need different access evidence.",
         "Manual", None),
        ("production_quantity", setup.production_quantity, "What production quantity is expected?",
         "Volume affects disposable, fabricated, adjustable, and permanent strategies.",
         10, "parts"),
        ("fixture_lifecycle", setup.fixture_lifecycle, "How long should the fixture remain usable?",
         "Lifecycle affects job revision, adjustment, wear, and recut requirements.",
         "Store and reuse", None),
        ("manufacturing_loading_direction", setup.manufacturing_loading_direction,
         "From which manufacturing direction is the assembly loaded?",
         "Locators and clamps must not block the assembly entry path.",
         {"x": 1.0, "y": 0.0, "z": 0.0}, None),
        ("manufacturing_unloading_direction", setup.manufacturing_unloading_direction,
         "In which manufacturing direction is the assembly removed?",
         "The completed assembly must not be trapped by fixture geometry.",
         {"x": -1.0, "y": 0.0, "z": 0.0}, None),
    )
    return tuple(IntentQuestion(field, prompt, why, answer, units)
                 for field, current, prompt, why, answer, units in values if current is None)


def apply_recommended_intent(workflow: InteractiveWorkflow) -> InteractiveWorkflow:
    """Apply visible recommendations only after the caller records confirmation."""
    setup = workflow.setup
    values: dict[str, object] = {}
    for question in minimal_intent_questions(workflow):
        value = question.recommended_answer
        if question.field in {"manufacturing_loading_direction", "manufacturing_unloading_direction"}:
            value = Vec3(**value)
        values[question.field] = value
    if "production_quantity" in values and setup.volume_category is None:
        values["volume_category"] = "Low"
    return replace(workflow, setup=replace(setup, **values), active_stage="Manufacturing Intent")


def _infer_minimum_annotations(document: WorkbenchDocument,
                               workflow: InteractiveWorkflow) -> InteractiveWorkflow:
    orientation = workflow.setup.manufacturing_orientation
    if orientation is None or orientation.selected_reference is None:
        return workflow
    existing_roles = {item.role for item in workflow.geometry_annotations}
    candidates: list[tuple[GeometryReference, AnnotationRole]] = []
    if AnnotationRole.PRIMARY_DATUM not in existing_roles:
        candidates.append((orientation.selected_reference, AnnotationRole.PRIMARY_DATUM))
    if (orientation.front_reference is not None
            and AnnotationRole.SECONDARY_DATUM not in existing_roles):
        candidates.append((orientation.front_reference, AnnotationRole.SECONDARY_DATUM))
    known = {reference.face_identity for reference, _ in candidates}
    datum_normals: list[Vec3] = []
    for reference, _ in candidates:
        face = next(
            (face for component in document.assembly.components for face in component.faces
             if face.reference == reference.face_identity), None,
        )
        if face is not None:
            datum_normals.append(Vec3(*face.normal))

    def independent(face: object) -> bool:
        normal = Vec3(*face.normal)
        return all(abs(
            normal.x * other.x + normal.y * other.y + normal.z * other.z
        ) < 0.95 for other in datum_normals)

    faces = sorted(
        (face for component in document.assembly.components for face in component.faces
         if face.is_planar and face.reference not in known and independent(face)),
        key=lambda face: (-face.area_mm2, face.reference),
    )
    if faces and AnnotationRole.TERTIARY_DATUM not in existing_roles:
        face = faces[0]
        component = next(item for item in document.assembly.components
                         if face in item.faces)
        body_identity = "body:" + sha256(component.reference.encode()).hexdigest()[:20]
        candidates.append((GeometryReference(component.reference, body_identity, face.reference),
                           AnnotationRole.TERTIARY_DATUM))
    result = workflow
    for reference, role in candidates:
        annotation = face_annotation(
            document, reference, role,
            notes="Deterministic datum candidate proposed by FXD; engineer confirmation required.",
        )
        result = result.with_annotation(annotation)
    return result


def _known_identities(project: FxdProject) -> frozenset[str]:
    values = {project.product.source_sha256, project.active_concept}
    values.update(item.identity for item in project.concepts)
    for component in project.product.components:
        values.add(component.identity)
        for body in component.bodies:
            values.add(body.identity)
            values.update(face.identity for face in body.faces)
            values.update(edge.identity for edge in body.edges)
    values.update(item.identity for item in project.active.fixture.features)
    if project.workflow:
        values.update(item.identity for item in project.workflow.geometry_annotations)
        values.update(
            item.identity for item in project.workflow.customer_tooling if item.verified
        )
    if project.placement:
        values.update(item.identity for item in project.placement.placements)
    orientation = project.workflow.setup.manufacturing_orientation if project.workflow else None
    if orientation:
        values.add(orientation.identity)
    return frozenset(values)


def build_ai_request(project: FxdProject) -> AiProposalRequest:
    workflow = project.workflow
    if workflow is None or not workflow.has_accepted_manufacturing_orientation():
        raise FixtureProposalError("AI proposal requires an accepted current manufacturing orientation")
    orientation = workflow.setup.manufacturing_orientation
    assert orientation is not None
    context = {
        "source": {"name": project.product.source_name,
                   "sha256": project.product.source_sha256, "units": project.product.units},
        "manufacturing_orientation": {
            "identity": orientation.identity,
            "manufacturing_x_source": orientation.manufacturing_x_source.__dict__,
            "manufacturing_y_source": orientation.manufacturing_y_source.__dict__,
            "manufacturing_z_source": orientation.manufacturing_z_source.__dict__,
        },
        "components": [{
            "identity": component.identity, "name": component.name,
            "faces": [face.identity for body in component.bodies for face in body.faces],
            "bounds_mm": [body.bounds.as_dict() for body in component.bodies],
        } for component in project.product.components],
        "intent": workflow.setup.to_dict() | {"manufacturing_orientation": orientation.identity},
        "annotations": [{"identity": item.identity, "role": item.role.value,
                         "reference": item.reference.__dict__, "area_mm2": item.surface_area_mm2,
                         "normal": item.normal.__dict__}
                        for item in workflow.geometry_annotations],
        "customer_tooling": [{
            "identity": item.identity,
            "kind": item.kind,
            "manufacturer": item.manufacturer,
            "part_number": item.part_number,
            "revision": item.revision,
            "source_sha256": item.source_sha256,
            "mounting_direction": (
                item.mounting_direction.__dict__ if item.mounting_direction else None
            ),
            "working_direction": (
                item.working_direction.__dict__ if item.working_direction else None
            ),
            "stroke_mm": item.stroke_mm,
            "reach_mm": item.reach_mm,
            "force_n": item.force_n,
            "verified": item.verified,
        } for item in sorted(workflow.customer_tooling, key=lambda value: value.identity)
          if item.verified],
        "placements": [item.to_dict() for item in project.placement.placements]
        if project.placement else [],
        "fixture_candidates": [{"identity": item.identity, "kind": item.kind,
                                "references": [value.__dict__ for value in item.source_references],
                                "rule": item.rule, "parameters": item.parameters}
                               for item in project.active.fixture.features],
        "deterministic_findings": [
            item.__dict__ for item in project.validation_for(project.active).findings
        ],
        "alternatives": [{"identity": item.identity, "objective": item.objective,
                          "validation": project.validation_for(item).status}
                         for item in project.concepts],
    }
    encoded = json.dumps(context, sort_keys=True)
    if "source_step_base64" in encoded or "source_bytes" in encoded:
        raise FixtureProposalError("raw source geometry must not enter AI context")
    context_identity = "context-" + sha256(encoded.encode()).hexdigest()
    return AiProposalRequest(
        PROPOSAL_REQUEST_SCHEMA, PROMPT_CONTRACT_VERSION,
        project.product.source_sha256, orientation.identity, context_identity, context,
        _known_identities(project),
    )


def proposal_engineering_context_identity(project: FxdProject) -> str:
    """Return the governed upstream context identity used to author a proposal."""
    return build_ai_request(project).engineering_context_identity


def _evidence(identity: str, kind: str, summary: str) -> tuple[ProposalEvidence, ...]:
    return (ProposalEvidence(identity, kind, summary),)


def _recommendation(
    recommendation_id: str, kind: RecommendationType, title: str, reason: str,
    evidence_identity: str, evidence_kind: str, evidence_summary: str,
    *, reference: GeometryReference | None = None, feature: str | None = None,
    assumptions: tuple[str, ...] = (), risks: tuple[str, ...] = (),
    parameters: tuple[EditableParameter, ...] = (), confidence: float = 0.75,
) -> ProposalRecommendation:
    return ProposalRecommendation(
        recommendation_id, kind, title, reason,
        _evidence(evidence_identity, evidence_kind, evidence_summary), assumptions,
        confidence, ("existing deterministic validation pipeline",),
        RecommendationValidation.NOT_EVALUATED, risks, parameters,
        ("analysis", "fixture geometry", "approval", "export"), reference, feature,
    )


def deterministic_baseline_proposal(
    project: FxdProject, *, provider_state: ProviderState = ProviderState.FALLBACK,
    provider_message: str = "AI assistance unavailable",
) -> FixtureProposal:
    workflow = project.workflow
    if workflow is None or not workflow.has_accepted_manufacturing_orientation():
        raise FixtureProposalError("deterministic proposal requires accepted orientation")
    setup = workflow.setup
    orientation = setup.manufacturing_orientation
    assert orientation is not None
    recommendations: list[ProposalRecommendation] = []
    bottom = orientation.selected_reference
    if bottom is not None:
        recommendations.append(_recommendation(
            "orientation-build", RecommendationType.ORIENTATION,
            "Use the accepted manufacturing orientation",
            "The engineer-confirmed fixture-down and operator-front faces define the only current manufacturing frame.",
            orientation.identity, "manufacturing_orientation", "Accepted source-SHA-linked frame",
            reference=bottom, confidence=1.0,
        ))
    if project.placement:
        role_types = {
            PlacementRole.PRIMARY_DATUM: RecommendationType.DATUM,
            PlacementRole.SECONDARY_DATUM: RecommendationType.DATUM,
            PlacementRole.TERTIARY_DATUM: RecommendationType.DATUM,
            PlacementRole.ROUND_PIN: RecommendationType.LOCATOR,
            PlacementRole.DIAMOND_PIN: RecommendationType.LOCATOR,
            PlacementRole.REST: RecommendationType.SUPPORT,
            PlacementRole.SUPPORT: RecommendationType.SUPPORT,
            PlacementRole.STOP: RecommendationType.LOCATOR,
            PlacementRole.CLAMP: RecommendationType.CLAMP,
        }
        for placement in project.placement.placements:
            kind = role_types[placement.role]
            recommendations.append(_recommendation(
                "placement-" + placement.identity, kind,
                placement.role.value.replace("_", " ").title(),
                "The deterministic placement engine selected this candidate from confirmed face evidence, constraint direction, accessibility, and standard-tooling rules.",
                placement.reference.face_identity or placement.identity,
                "ocp_face", "Exact OCP face used by deterministic placement",
                reference=placement.reference, assumptions=placement.assumptions,
                risks=placement.warnings,
                parameters=(EditableParameter("position_mm", placement.position_mm.__dict__, "mm"),
                            EditableParameter("role", placement.role.value)),
                confidence=placement.confidence,
            ))
    feature_kinds = {item.kind: item for item in project.active.fixture.features}
    for feature_kind, recommendation_type, title in (
        ("baseplate", RecommendationType.BASE_STRUCTURE, "Fabricated plate base"),
        ("support_pad", RecommendationType.SUPPORT, "Support pad"),
        ("round_pin", RecommendationType.LOCATOR, "Round locator pin"),
        ("relieved_locator", RecommendationType.LOCATOR, "Relieved locator"),
        ("clamp_mount", RecommendationType.CLAMP, "Standard clamp region"),
    ):
        feature = feature_kinds.get(feature_kind)
        if feature is None:
            continue
        recommendations.append(_recommendation(
            "feature-" + feature.identity, recommendation_type, title,
            "The existing deterministic concept generator included this editable feature and its manufacturing intent.",
            feature.identity, "fixture_feature", f"Generated by rule {feature.rule}",
            feature=feature.identity, assumptions=feature.assumptions,
            parameters=tuple(EditableParameter(str(key), value, "mm" if isinstance(value, (int, float)) else None)
                             for key, value in sorted(feature.parameters.items())),
        ))
    recommendations.extend((
        _recommendation(
            "load-unload", RecommendationType.LOAD_UNLOAD, "Load and unload along confirmed manufacturing axes",
            "Entry and removal directions are stored in manufacturing coordinates and converted only at the deterministic engine boundary.",
            orientation.identity, "manufacturing_orientation", "Accepted manufacturing coordinate system",
            assumptions=("Clearance envelopes require engineer review.",),
            risks=("Trapped-part and final welded-shape clearance remain validation items.",),
            parameters=(EditableParameter("loading_direction", setup.manufacturing_loading_direction.__dict__),
                        EditableParameter("unloading_direction", setup.manufacturing_unloading_direction.__dict__)),
        ),
        _recommendation(
            "weld-access", RecommendationType.WELD_ACCESS, "Preserve tack and weld access",
            "Fixture features must remain outside supplied weld, torch, hand, and spatter-sensitive evidence.",
            project.active_concept, "fixture_concept", "Current deterministic access findings",
            assumptions=(setup.operator_access or "Operator access not fully specified.",),
            risks=("Qualified weld-process review remains required.",),
        ),
        _recommendation(
            "operator-access", RecommendationType.OPERATOR_AUTOMATION_ACCESS,
            f"{setup.operation_mode} handling assumption",
            "Handling mode determines operator, cobot, or robot approach and maintenance envelopes.",
            project.active_concept, "fixture_concept", "Current handling intent",
            assumptions=(setup.automation_assumptions or "Automation assumptions not supplied.",),
            parameters=(EditableParameter("operation_mode", setup.operation_mode,
                                          choices=("Manual", "Cobot", "Robotic")),),
        ),
        _recommendation(
            "standard-tooling", RecommendationType.STANDARD_COMPONENT,
            "Prefer vendor-neutral standard tooling",
            "Standard clamps, pins, and support rests reduce avoidable custom machining and remain replaceable.",
            project.active_concept, "fixture_concept", "Generic tooling library contract",
            risks=("Exact commercial part selection requires customer verification.",),
        ),
        _recommendation(
            "lifecycle", RecommendationType.MANUFACTURING_LIFECYCLE,
            f"{setup.fixture_type} for {setup.fixture_lifecycle}",
            "Purpose, production quantity, construction method, and lifecycle govern fixture complexity and revision evidence.",
            project.active_concept, "fixture_concept", "Engineer-confirmed process intent",
            parameters=(EditableParameter("fixture_type", setup.fixture_type),
                        EditableParameter("fixture_lifecycle", setup.fixture_lifecycle),
                        EditableParameter("production_quantity", setup.production_quantity, "parts")),
        ),
        _recommendation(
            "unresolved-questions", RecommendationType.UNRESOLVED_QUESTION,
            "Resolve provisional engineering assumptions",
            "The proposal preserves unproven weld access, unloading clearance, clamp reaction, and manufacturing evidence as explicit review work.",
            project.active_concept, "fixture_concept", "Current deterministic warning evidence",
            assumptions=tuple(item.message for item in project.active_validation.findings
                              if item.severity == "warning"),
            risks=("Warnings remain visible until supported by deterministic or engineer-recorded evidence.",),
        ),
    ))
    alternative = None
    if len(project.concepts) > 1:
        alternative = (
            f"Alternative {project.concepts[1].identity}: {project.concepts[1].objective}; "
            f"deterministic status {project.validation_for(project.concepts[1]).status}."
        )
        recommendations.append(_recommendation(
            "alternative-1", RecommendationType.ALTERNATIVE, "Review a materially different objective",
            "The deterministic concept engine produced another eligible fixture strategy for comparison.",
            project.concepts[1].identity, "fixture_concept", alternative,
        ))
    provenance = ProposalProvenance(
        ProposalSource.DETERMINISTIC_FALLBACK, "deterministic-baseline",
        "existing FXD placement/concept engines", PROMPT_CONTRACT_VERSION,
        PROPOSAL_SCHEMA, datetime.now(timezone.utc).isoformat(), provider_state,
        provider_message,
    )
    proposal = FixtureProposal(
        PROPOSAL_SCHEMA, "", project.product.source_sha256, orientation.identity,
        proposal_engineering_context_identity(project),
        "Deterministic baseline fixture proposal", setup.fixture_type or "Unknown",
        setup.preferred_base_strategy or "Auto-select", setup.fixture_lifecycle or "Unknown",
        "review required", (
            "Recommendations are deterministic candidates, not production approval.",
            "Engineer confirmation is required for every inferred datum and access assumption.",
        ), tuple(recommendations), alternative, provenance,
    )
    return _finalize(proposal)


def ai_response_from_proposal(proposal: FixtureProposal) -> dict[str, object]:
    """Return the strict provider response surface, useful for deterministic tests."""
    return {
        "schema_version": PROPOSAL_SCHEMA,
        "source_sha256": proposal.source_sha256,
        "manufacturing_orientation_identity": proposal.manufacturing_orientation_identity,
        "engineering_context_identity": proposal.engineering_context_identity,
        "concept_name": proposal.concept_name,
        "fixture_purpose": proposal.fixture_purpose,
        "base_strategy": proposal.base_strategy,
        "lifecycle": proposal.lifecycle,
        "complexity_class": proposal.complexity_class,
        "assumptions": list(proposal.assumptions),
        "recommendations": [item.to_dict() for item in proposal.recommendations],
        "alternative_summary": proposal.alternative_summary,
    }


def proposal_from_ai_response(data: dict[str, object], request: AiProposalRequest,
                              provider: AiFixtureProvider) -> FixtureProposal:
    required = {
        "schema_version", "source_sha256", "manufacturing_orientation_identity",
        "engineering_context_identity",
        "concept_name", "fixture_purpose", "base_strategy", "lifecycle",
        "complexity_class", "assumptions", "recommendations", "alternative_summary",
    }
    if not isinstance(data, dict) or set(data) != required:
        raise FixtureProposalError("AI response does not match the strict proposal schema")
    if data["schema_version"] != PROPOSAL_SCHEMA:
        raise FixtureProposalError("AI proposal response is unversioned or unsupported")
    if data["source_sha256"] != request.source_sha256:
        raise FixtureProposalError("AI proposal source SHA-256 mismatch")
    if data["manufacturing_orientation_identity"] != request.manufacturing_orientation_identity:
        raise FixtureProposalError("AI proposal manufacturing orientation mismatch")
    if data["engineering_context_identity"] != request.engineering_context_identity:
        raise FixtureProposalError("AI proposal engineering context mismatch")
    top_string_fields = (
        "concept_name", "fixture_purpose", "base_strategy", "lifecycle",
        "complexity_class",
    )
    if any(not isinstance(data[field], str) or not data[field].strip()
           for field in top_string_fields):
        raise FixtureProposalError("AI proposal contains malformed text fields")
    if (not isinstance(data["assumptions"], list)
            or any(not isinstance(value, str) for value in data["assumptions"])):
        raise FixtureProposalError("AI proposal assumptions must be a list of strings")
    if (data["alternative_summary"] is not None
            and not isinstance(data["alternative_summary"], str)):
        raise FixtureProposalError("AI proposal alternative summary is malformed")
    recommendation_fields = {
        "recommendation_id", "recommendation_type", "title", "engineering_reason",
        "source_evidence", "assumptions", "confidence", "deterministic_checks",
        "validation_status", "unresolved_risks", "editable_parameters",
        "downstream_dependencies", "geometry_reference", "fixture_feature_identity",
        "decision", "engineer_note",
    }
    evidence_fields = {"identity", "kind", "summary"}
    parameter_fields = {"name", "value", "units", "choices"}
    reference_fields = {
        "component_identity", "body_identity", "face_identity", "edge_identity",
    }
    try:
        raw_recommendations = data["recommendations"]
        if not isinstance(raw_recommendations, list):
            raise FixtureProposalError("AI recommendations must be a list")
        for item in raw_recommendations:
            if not isinstance(item, dict) or set(item) != recommendation_fields:
                raise FixtureProposalError(
                    "AI recommendation does not match the strict nested schema"
                )
            string_fields = (
                "recommendation_id", "recommendation_type", "title",
                "engineering_reason", "validation_status", "decision", "engineer_note",
            )
            if any(not isinstance(item[field], str) for field in string_fields):
                raise FixtureProposalError("AI recommendation contains malformed text fields")
            if (not item["recommendation_id"].strip() or not item["title"].strip()
                    or not item["engineering_reason"].strip()):
                raise FixtureProposalError("AI recommendation contains empty required text")
            if (isinstance(item["confidence"], bool)
                    or not isinstance(item["confidence"], (int, float))):
                raise FixtureProposalError("AI recommendation confidence must be numeric")
            for field in (
                    "assumptions", "deterministic_checks", "unresolved_risks",
                    "downstream_dependencies"):
                if (not isinstance(item[field], list)
                        or any(not isinstance(value, str) for value in item[field])):
                    raise FixtureProposalError(
                        f"AI recommendation {field} must be a list of strings"
                    )
            if (item["fixture_feature_identity"] is not None
                    and not isinstance(item["fixture_feature_identity"], str)):
                raise FixtureProposalError("AI fixture feature identity is malformed")
            if (not isinstance(item["source_evidence"], list)
                    or any(not isinstance(value, dict) or set(value) != evidence_fields
                           for value in item["source_evidence"])):
                raise FixtureProposalError("AI evidence does not match the strict nested schema")
            if any(any(not isinstance(value[field], str) or not value[field].strip()
                       for field in evidence_fields)
                   for value in item["source_evidence"]):
                raise FixtureProposalError("AI evidence fields must be non-empty strings")
            if (not isinstance(item["editable_parameters"], list)
                    or any(not isinstance(value, dict) or set(value) != parameter_fields
                           for value in item["editable_parameters"])):
                raise FixtureProposalError(
                    "AI editable parameters do not match the strict nested schema"
                )
            for parameter in item["editable_parameters"]:
                if not isinstance(parameter["name"], str) or not parameter["name"].strip():
                    raise FixtureProposalError("AI editable parameter name is malformed")
                if (parameter["units"] is not None
                        and not isinstance(parameter["units"], str)):
                    raise FixtureProposalError("AI editable parameter units are malformed")
                if (not isinstance(parameter["choices"], list)
                        or any(not isinstance(value, str) for value in parameter["choices"])):
                    raise FixtureProposalError("AI editable parameter choices are malformed")
            reference = item["geometry_reference"]
            if reference is not None and (
                    not isinstance(reference, dict) or set(reference) != reference_fields):
                raise FixtureProposalError(
                    "AI geometry reference does not match the strict nested schema"
                )
            if reference is not None:
                if (not isinstance(reference["component_identity"], str)
                        or not reference["component_identity"].strip()
                        or any(reference[field] is not None
                               and not isinstance(reference[field], str)
                               for field in ("body_identity", "face_identity", "edge_identity"))):
                    raise FixtureProposalError("AI geometry reference identities are malformed")
        recommendations = tuple(ProposalRecommendation.from_dict(item)
                                for item in raw_recommendations)
    except FixtureProposalError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise FixtureProposalError(f"AI recommendations are malformed: {exc}") from exc
    for recommendation in recommendations:
        if (recommendation.decision != RecommendationDecision.PROPOSED
                or recommendation.engineer_note):
            raise FixtureProposalError(
                "AI proposal may not author engineer recommendation decisions"
            )
        for evidence in recommendation.source_evidence:
            if evidence.identity not in request.known_identities:
                raise FixtureProposalError(
                    f"AI proposal references unknown feature identity {evidence.identity!r}"
                )
        if recommendation.geometry_reference is not None:
            identities = {
                recommendation.geometry_reference.component_identity,
                recommendation.geometry_reference.body_identity,
                recommendation.geometry_reference.face_identity,
                recommendation.geometry_reference.edge_identity,
            } - {None}
            if not identities <= request.known_identities:
                raise FixtureProposalError("AI proposal contains malformed geometry reference")
        if (recommendation.fixture_feature_identity is not None
                and recommendation.fixture_feature_identity not in request.known_identities):
            raise FixtureProposalError("AI proposal references unknown fixture feature")
    provenance = ProposalProvenance(
        ProposalSource.AI, provider.identity, provider.engine_identifier,
        getattr(provider, "prompt_contract_version", PROMPT_CONTRACT_VERSION), PROPOSAL_SCHEMA,
        datetime.now(timezone.utc).isoformat(), ProviderState.SUCCESS,
        "AI proposal passed strict response-contract validation.",
    )
    try:
        proposal = FixtureProposal(
            PROPOSAL_SCHEMA, "", request.source_sha256,
            request.manufacturing_orientation_identity,
            request.engineering_context_identity, str(data["concept_name"]),
            str(data["fixture_purpose"]), str(data["base_strategy"]),
            str(data["lifecycle"]), str(data["complexity_class"]),
            tuple(str(item) for item in data["assumptions"]), recommendations,
            data.get("alternative_summary"), provenance,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FixtureProposalError(f"AI proposal values are malformed: {exc}") from exc
    return _finalize(proposal)


_SUBSYSTEM_ROUTE = {
    "locating": ("Proposal", "proposal_recommendations"),
    "placement": ("Proposal", "proposal_recommendations"),
    "clamp": ("Proposal", "proposal_recommendations"),
    "access": ("Proposal", "proposal_recommendations"),
    "weld": ("Proposal", "proposal_recommendations"),
    "structure": ("Proposal", "proposal_recommendations"),
    "manufacturing": ("Manufacturing Intent", "process_fixture_type"),
    "tolerance": ("Proposal", "proposal_recommendations"),
    "geometry": ("Validation", "engineering_findings"),
    "fabrication": ("Manufacturing Intent", "process_lifecycle"),
    "concept": ("Proposal", "proposal_recommendations"),
}


def _guided_issue(code: str, severity: str, title: str, message: str, why: str,
                  section: str, target: str, *, affected: str | None = None,
                  details: tuple[str, ...] = ()) -> GuidedValidationIssue:
    token = sha256(f"{code}|{severity}|{affected}|{message}".encode()).hexdigest()[:16]
    return GuidedValidationIssue(
        "proposal-issue-" + token, severity, title, message, why, code,
        affected, section, target, details,
    )


def validate_fixture_proposal(project: FxdProject,
                              proposal: FixtureProposal) -> FixtureProposal:
    workflow = project.workflow
    orientation = workflow.setup.manufacturing_orientation if workflow else None
    orientation_identity = orientation.identity if orientation else None
    context_identity = (
        proposal_engineering_context_identity(project)
        if workflow is not None and workflow.has_accepted_manufacturing_orientation()
        else None
    )
    issues: list[GuidedValidationIssue] = []
    stale = proposal.stale_reason(
        project.product.source_sha256, orientation_identity, context_identity,
    )
    if stale:
        context_changed = stale == "manufacturing intent or engineering context changed"
        issues.append(_guided_issue(
            "proposal_stale", "error", "Fixture proposal is stale", stale,
            "A proposal tied to different source, orientation, or engineering intent evidence cannot control approval or export.",
            "Manufacturing Intent" if context_changed else "Orientation",
            "process_fixture_type" if context_changed else "orientation_workflow",
            details=(f"proposal_source={proposal.source_sha256}",
                     f"current_source={project.product.source_sha256}",
                     f"proposal_orientation={proposal.manufacturing_orientation_identity}",
                     f"current_orientation={orientation_identity}",
                     f"proposal_context={proposal.engineering_context_identity}",
                     f"current_context={context_identity}"),
        ))
    required_types = {
        RecommendationType.DATUM, RecommendationType.LOCATOR,
        RecommendationType.SUPPORT, RecommendationType.CLAMP,
        RecommendationType.BASE_STRUCTURE, RecommendationType.LOAD_UNLOAD,
    }
    present = {item.recommendation_type for item in proposal.recommendations
               if item.decision not in {RecommendationDecision.REJECTED,
                                        RecommendationDecision.SUPPRESSED}}
    for missing in sorted(required_types - present, key=lambda item: item.value):
        issues.append(_guided_issue(
            "proposal_recommendation_missing", "error",
            f"{missing.value.replace('_', ' ').title()} recommendation is missing",
            "The proposal does not contain a required fixture-engineering recommendation.",
            "A complete proposal must address locating, support, clamping, structure, and removal.",
            "Proposal", "proposal_recommendations", affected=missing.value,
        ))
    setup = workflow.setup if workflow else None
    if setup is not None and setup.manufacturing_loading_direction is None:
        issues.append(_guided_issue(
            "loading_direction_required", "error", "Load direction is unresolved",
            "FXD cannot confirm that the assembly can enter the fixture without interfering with locators or clamps.",
            "Loading direction is required for deterministic access and trapped-part checks.",
            "Manufacturing Intent", "process_load",
        ))
    if setup is not None and setup.manufacturing_unloading_direction is None:
        issues.append(_guided_issue(
            "unloading_direction_required", "error", "Unload direction is unresolved",
            "FXD cannot confirm that the completed assembly can leave the fixture.",
            "An unresolved removal path can hide trapped-part risk.",
            "Manufacturing Intent", "process_unload",
        ))
    if (setup is not None and setup.fixture_lifecycle == "Disposable or job-run recut"
            and not setup.job_revision):
        issues.append(_guided_issue(
            "job_revision_required", "error", "Job revision is required",
            "Disposable or recut fixture evidence has no job revision.",
            "The shop must be able to identify which product revision the recut fixture supports.",
            "Manufacturing Intent", "process_job_revision",
        ))
    validation = project.active_validation
    for finding in validation.findings:
        section, target = _SUBSYSTEM_ROUTE.get(
            finding.subsystem, ("Validation", "engineering_findings")
        )
        issues.append(_guided_issue(
            finding.code, finding.severity,
            finding.code.replace("_", " ").title(), finding.message,
            "Deterministic engineering evidence must be resolved or reviewed before approval and export.",
            section, target,
            affected=next((value.split("=", 1)[-1] for value in finding.evidence
                           if "=" in value), None),
            details=tuple(finding.evidence) + tuple(finding.assumptions),
        ))
    subsystem_for_type = {
        RecommendationType.DATUM: {"locating", "placement", "tolerance"},
        RecommendationType.LOCATOR: {"locating", "placement", "tolerance"},
        RecommendationType.SUPPORT: {"placement", "structure"},
        RecommendationType.CLAMP: {"clamp", "placement", "access"},
        RecommendationType.BASE_STRUCTURE: {"structure", "geometry"},
        RecommendationType.WELD_ACCESS: {"weld", "access"},
        RecommendationType.LOAD_UNLOAD: {"access", "geometry"},
        RecommendationType.MANUFACTURING_LIFECYCLE: {"manufacturing", "fabrication"},
    }
    updated: list[ProposalRecommendation] = []
    for recommendation in proposal.recommendations:
        related = subsystem_for_type.get(recommendation.recommendation_type, set())
        findings = tuple(item for item in validation.findings if item.subsystem in related)
        status = RecommendationValidation.BLOCKED if any(
            item.severity == "error" for item in findings
        ) else (RecommendationValidation.PROVISIONAL if (
            findings or recommendation.unresolved_risks or recommendation.assumptions
        ) else RecommendationValidation.PASSED)
        risks = tuple(dict.fromkeys(
            recommendation.unresolved_risks + tuple(item.message for item in findings)
        ))
        updated.append(replace(recommendation, validation_status=status,
                               unresolved_risks=risks))
    candidate = replace(proposal, proposal_identity="", recommendations=tuple(updated),
                        guided_issues=tuple(issues))
    return _finalize(candidate)


def decide_recommendation(proposal: FixtureProposal, recommendation_id: str,
                          decision: RecommendationDecision, note: str = "") -> FixtureProposal:
    if decision == RecommendationDecision.PROPOSED:
        raise FixtureProposalError("engineer decision must change the recommendation state")
    if recommendation_id not in {item.recommendation_id for item in proposal.recommendations}:
        raise FixtureProposalError("unknown fixture proposal recommendation")
    recommendations = tuple(
        replace(item, decision=decision, engineer_note=note)
        if item.recommendation_id == recommendation_id else item
        for item in proposal.recommendations
    )
    event = ProposalAuditEvent(
        decision.value, recommendation_id, note,
        datetime.now(timezone.utc).isoformat(), proposal.proposal_identity,
    )
    candidate = replace(
        proposal, proposal_identity="", recommendations=recommendations,
        audit_history=proposal.audit_history + (event,), proposal_decision="pending",
    )
    return _finalize(candidate)


def edit_recommendation(proposal: FixtureProposal, recommendation_id: str,
                        values: dict[str, object], note: str) -> FixtureProposal:
    target = next((item for item in proposal.recommendations
                   if item.recommendation_id == recommendation_id), None)
    if target is None:
        raise FixtureProposalError("unknown fixture proposal recommendation")
    supported = {item.name for item in target.editable_parameters}
    if not values or set(values) - supported:
        raise FixtureProposalError("proposal edit contains unsupported parameters")
    parameters = tuple(replace(item, value=values.get(item.name, item.value))
                       for item in target.editable_parameters)
    changed = replace(target, editable_parameters=parameters,
                      decision=RecommendationDecision.EDITED, engineer_note=note,
                      validation_status=RecommendationValidation.NOT_EVALUATED)
    recommendations = tuple(changed if item.recommendation_id == recommendation_id else item
                            for item in proposal.recommendations)
    event = ProposalAuditEvent(
        "edit", recommendation_id, note, datetime.now(timezone.utc).isoformat(),
        proposal.proposal_identity,
    )
    return _finalize(replace(
        proposal, proposal_identity="", recommendations=recommendations,
        audit_history=proposal.audit_history + (event,), proposal_decision="pending",
    ))


def decide_proposal(proposal: FixtureProposal, decision: str, note: str = "") -> FixtureProposal:
    if decision not in {"accepted_for_engineering_review", "rejected"}:
        raise FixtureProposalError("proposal decision is unsupported")
    if decision == "accepted_for_engineering_review" and proposal.blocker_count:
        raise FixtureProposalError("proposal with deterministic blockers cannot be accepted")
    event = ProposalAuditEvent(
        decision, proposal.proposal_identity, note,
        datetime.now(timezone.utc).isoformat(), proposal.proposal_identity,
    )
    return _finalize(replace(
        proposal, proposal_identity="", proposal_decision=decision,
        audit_history=proposal.audit_history + (event,),
    ))


def _reanalyze_preserving_authored_state(
    document: WorkbenchDocument, workflow: InteractiveWorkflow,
    current_project: FxdProject,
) -> FxdProject:
    """Re-run deterministic engines, then replay reviewable authored project state."""
    prepared = _infer_minimum_annotations(document, workflow)
    project = analyze_engineering_workflow(document, prepared)
    target = current_project.active_concept
    if target not in {item.identity for item in project.concepts}:
        objective = current_project.active.objective
        target = next(
            (item.identity for item in project.concepts if item.objective == objective),
            "",
        )
    if not target:
        raise FixtureProposalError(
            "deterministic reanalysis cannot preserve the selected fixture concept"
        )
    project = project.with_concept(target)
    try:
        for edit in current_project.edit_log:
            if edit.operation in {"suppress", "unsuppress"}:
                project = project.suppress(edit.target, edit.reason)
            elif edit.operation == "correction":
                project = project.correct(edit.target, str(edit.value), edit.reason)
            elif edit.operation == "set_parameter":
                project = project.edit_parameter(edit.target, edit.value, edit.reason)
            elif edit.operation in {"move", "resize", "replace"}:
                project = project.edit_feature(
                    edit.target, edit.operation, edit.value, edit.reason,
                )
            else:
                raise FixtureProposalError(
                    f"unsupported authored project edit {edit.operation!r}"
                )
    except ProjectFormatError as exc:
        raise FixtureProposalError(
            f"deterministic reanalysis cannot preserve authored project edits: {exc}"
        ) from exc
    if project.suppressed_features != current_project.suppressed_features:
        raise FixtureProposalError(
            "deterministic reanalysis cannot reproduce authored suppression state"
        )
    revisions = {
        item.revision_id: item
        for item in current_project.revisions + project.revisions
    }
    return replace(
        project, hidden_layers=current_project.hidden_layers,
        decisions=current_project.decisions,
        revisions=tuple(revisions.values()), approved_revision=None,
    )


def generate_fixture_proposal(
    document: WorkbenchDocument, workflow: InteractiveWorkflow,
    *, provider: AiFixtureProvider | None = None, allow_fallback: bool = True,
    timeout_seconds: float = 45.0, cancellation: CancellationToken | None = None,
    prior_proposal: FixtureProposal | None = None,
    current_project: FxdProject | None = None,
) -> ProposalGenerationOutcome:
    if workflow.source_sha256 != document.source_sha256:
        raise FixtureProposalError("workflow and immutable STEP source do not match")
    orientation = workflow.setup.manufacturing_orientation
    if orientation is None:
        raise FixtureProposalError("accept manufacturing orientation before generating a proposal")
    try:
        orientation.require_accepted_for(document.source_sha256)
    except ManufacturingOrientationError as exc:
        raise FixtureProposalError(str(exc)) from exc
    questions = minimal_intent_questions(workflow)
    if questions:
        raise MissingIntentError(questions)
    token = cancellation or CancellationToken.create()
    token.raise_if_cancelled()
    if current_project is not None:
        if (current_project.product.source_sha256 != document.source_sha256
                or current_project.product.source_bytes != document.source_bytes):
            raise FixtureProposalError(
                "current project does not match the immutable STEP source"
            )
        project = _reanalyze_preserving_authored_state(
            document, workflow, current_project,
        )
        prepared = replace(
            project.workflow, concepts_generated=True, active_stage="Proposal",
        )
        project = project.with_workflow(prepared)
    else:
        prepared = _infer_minimum_annotations(document, workflow)
        project = analyze_engineering_workflow(document, prepared)
        prepared = replace(project.workflow, concepts_generated=True, active_stage="Proposal")
        project = project.with_workflow(prepared)
    request = build_ai_request(project)
    provider = provider or HttpJsonAiProvider.from_environment()
    proposal: FixtureProposal
    state: ProviderState
    message: str
    if provider.available:
        try:
            response = provider.generate(
                request, timeout_seconds=timeout_seconds, cancellation=token,
            )
            token.raise_if_cancelled()
            proposal = proposal_from_ai_response(response, request, provider)
            state = ProviderState.SUCCESS
            message = "AI proposal passed strict schema validation."
        except ProposalCancelled:
            raise
        except Exception as exc:
            if not allow_fallback:
                raise
            failure_reason = _sanitized_provider_failure_reason(provider, exc)
            proposal = deterministic_baseline_proposal(
                project, provider_state=ProviderState.FAILED,
                provider_message=f"AI proposal failed or was quarantined: {failure_reason}",
            )
            state = ProviderState.FAILED
            message = proposal.provenance.provider_message
    else:
        if not allow_fallback:
            raise ProviderUnavailable("AI provider is not configured")
        proposal = deterministic_baseline_proposal(project)
        state = ProviderState.UNAVAILABLE
        message = "Deterministic baseline proposal; AI assistance unavailable."
    proposal = validate_fixture_proposal(project, proposal)
    if prior_proposal is not None:
        event = ProposalAuditEvent(
            "regenerate", proposal.proposal_identity,
            "Proposal regenerated from current governed engineering context.",
            datetime.now(timezone.utc).isoformat(), prior_proposal.proposal_identity,
        )
        proposal = _finalize(replace(
            proposal, proposal_identity="",
            audit_history=prior_proposal.audit_history + (event,),
        ))
    project = project.with_fixture_proposal(proposal)
    return ProposalGenerationOutcome(project, proposal, state, message)
