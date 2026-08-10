"""Explicit M33.1 live-AI versus deterministic/offline execution boundary."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping

from .ai_fixture_engineer import (
    AiFixtureProvider, CancellationToken, FixtureProposal, FixtureProposalError,
    MissingIntentError, OpenAiResponsesProvider, ProposalCancelled,
    ProposalContractRejection, ProposalGenerationOutcome, ProviderState,
    UnavailableAiProvider, generate_fixture_proposal, prepare_proposal_project,
)
from .interactive_workflow import InteractiveWorkflow
from .product_reconstruction import ProductReconstruction, reconstruct_product
from .project import FxdProject
from .workbench import WorkbenchDocument


AI_EXECUTION_SCHEMA = "fxd-ai-design-execution-v1"


class AiExecutionError(ValueError):
    """Raised when execution provenance is unsafe, malformed, or inconsistent."""


class ExecutionMode(str, Enum):
    AI_DESIGN_LIVE = "ai_design_live"
    DETERMINISTIC_OFFLINE = "deterministic_offline"


class RequestStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    OFFLINE = "offline_no_live_request"
    SUCCEEDED = "live_request_succeeded"
    FAILED = "live_request_failed"
    CANCELLED = "live_request_cancelled"


class FailureCategory(str, Enum):
    NONE = "none"
    MISSING_CONFIGURATION = "missing_configuration"
    RECONSTRUCTION_BLOCKED = "reconstruction_blocked"
    INTENT_BLOCKED = "intent_blocked"
    TIMEOUT = "timeout"
    PROVIDER_FAILURE = "provider_failure"
    CONTRACT_QUARANTINE = "contract_quarantine"
    MALFORMED_OUTPUT = "malformed_output"
    CANCELLATION = "cancellation"


@dataclass(frozen=True)
class AiExecutionProvenance:
    schema_version: str
    execution_identity: str
    mode: ExecutionMode
    source_sha256: str
    reconstruction_identity: str | None
    provider_identity: str | None
    model_identity: str | None
    request_attempted: bool
    request_count: int
    request_status: RequestStatus
    generated_at_utc: str | None
    prompt_contract_version: str | None
    response_contract_version: str | None
    result_identity: str | None
    failure_category: FailureCategory
    fallback_used: bool
    automatic_retries: int
    timeout_seconds: float
    usage_status: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None

    def __post_init__(self) -> None:
        if self.schema_version != AI_EXECUTION_SCHEMA:
            raise AiExecutionError("unsupported AI execution provenance schema")
        if len(self.source_sha256) != 64:
            raise AiExecutionError("AI execution source SHA-256 is malformed")
        if self.execution_identity and self.execution_identity != self.expected_identity():
            raise AiExecutionError("AI execution identity does not match provenance")
        if self.fallback_used:
            raise AiExecutionError("M33.1 execution provenance may never record fallback use")
        if self.automatic_retries != 0:
            raise AiExecutionError("M33.1 automatic provider retries must remain zero")
        if not 0.1 <= self.timeout_seconds <= 60.0:
            raise AiExecutionError("M33.1 request timeout must be within 0.1 to 60 seconds")
        if self.request_count not in {0, 1}:
            raise AiExecutionError("M33.1 execution may record at most one request")
        if self.request_attempted != (self.request_count == 1):
            raise AiExecutionError("request attempted state does not match request count")
        if self.mode == ExecutionMode.DETERMINISTIC_OFFLINE:
            if self.request_count or self.provider_identity or self.model_identity:
                raise AiExecutionError("offline mode cannot record a live provider request")
            if self.request_status not in {RequestStatus.NOT_ATTEMPTED, RequestStatus.OFFLINE}:
                raise AiExecutionError("offline mode has an invalid request status")
            if self.result_identity is not None:
                raise AiExecutionError("offline mode cannot claim an AI result identity")
        else:
            if self.provider_identity != "openai":
                raise AiExecutionError("live AI Design requires the explicit OpenAI provider")
            if self.request_status == RequestStatus.SUCCEEDED:
                if not self.model_identity or self.request_count != 1 or not self.result_identity:
                    raise AiExecutionError("successful live execution lacks model, request, or result evidence")
                if self.failure_category != FailureCategory.NONE:
                    raise AiExecutionError("successful live execution cannot contain a failure category")
            if self.request_status in {RequestStatus.FAILED, RequestStatus.CANCELLED}:
                if self.failure_category == FailureCategory.NONE:
                    raise AiExecutionError("failed live execution lacks a safe failure category")
        for value in (self.input_tokens, self.output_tokens, self.total_tokens):
            if value is not None and value < 0:
                raise AiExecutionError("token usage cannot be negative")
        if self.cost_usd is not None and self.cost_usd < 0:
            raise AiExecutionError("cost evidence cannot be negative")

    def _identity_payload(self) -> dict[str, object]:
        payload = self.to_dict()
        payload["execution_identity"] = ""
        return payload

    def expected_identity(self) -> str:
        encoded = json.dumps(
            self._identity_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=True,
        )
        return "ai-execution-" + sha256(encoded.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "execution_identity": self.execution_identity,
            "mode": self.mode.value,
            "source_sha256": self.source_sha256,
            "reconstruction_identity": self.reconstruction_identity,
            "provider_identity": self.provider_identity,
            "model_identity": self.model_identity,
            "request_attempted": self.request_attempted,
            "request_count": self.request_count,
            "request_status": self.request_status.value,
            "generated_at_utc": self.generated_at_utc,
            "prompt_contract_version": self.prompt_contract_version,
            "response_contract_version": self.response_contract_version,
            "result_identity": self.result_identity,
            "failure_category": self.failure_category.value,
            "fallback_used": self.fallback_used,
            "automatic_retries": self.automatic_retries,
            "timeout_seconds": self.timeout_seconds,
            "usage_status": self.usage_status,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "AiExecutionProvenance":
        try:
            result = cls(
                str(data["schema_version"]), str(data["execution_identity"]),
                ExecutionMode(str(data["mode"])), str(data["source_sha256"]),
                str(data["reconstruction_identity"])
                if data.get("reconstruction_identity") is not None else None,
                str(data["provider_identity"])
                if data.get("provider_identity") is not None else None,
                str(data["model_identity"])
                if data.get("model_identity") is not None else None,
                bool(data["request_attempted"]), int(data["request_count"]),
                RequestStatus(str(data["request_status"])),
                str(data["generated_at_utc"])
                if data.get("generated_at_utc") is not None else None,
                str(data["prompt_contract_version"])
                if data.get("prompt_contract_version") is not None else None,
                str(data["response_contract_version"])
                if data.get("response_contract_version") is not None else None,
                str(data["result_identity"])
                if data.get("result_identity") is not None else None,
                FailureCategory(str(data["failure_category"])),
                bool(data["fallback_used"]), int(data["automatic_retries"]),
                float(data["timeout_seconds"]), str(data["usage_status"]),
                int(data["input_tokens"]) if data.get("input_tokens") is not None else None,
                int(data["output_tokens"]) if data.get("output_tokens") is not None else None,
                int(data["total_tokens"]) if data.get("total_tokens") is not None else None,
                float(data["cost_usd"]) if data.get("cost_usd") is not None else None,
            )
            if not result.execution_identity:
                raise AiExecutionError("AI execution identity is missing")
            return result
        except AiExecutionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise AiExecutionError(f"invalid AI execution provenance: {exc}") from exc


@dataclass(frozen=True)
class DesignExecutionOutcome:
    project: FxdProject
    proposal: FixtureProposal | None
    provider_state: ProviderState
    message: str
    provenance: AiExecutionProvenance


def _record(**values: object) -> AiExecutionProvenance:
    provisional = AiExecutionProvenance(
        AI_EXECUTION_SCHEMA, "",
        values["mode"], values["source_sha256"],
        values.get("reconstruction_identity"), values.get("provider_identity"),
        values.get("model_identity"), bool(values.get("request_attempted", False)),
        int(values.get("request_count", 0)), values["request_status"],
        values.get("generated_at_utc"), values.get("prompt_contract_version"),
        values.get("response_contract_version"), values.get("result_identity"),
        values.get("failure_category", FailureCategory.NONE), False, 0,
        float(values.get("timeout_seconds", 45.0)),
        str(values.get("usage_status", "unavailable")),
        values.get("input_tokens"), values.get("output_tokens"),
        values.get("total_tokens"), values.get("cost_usd"),
    )
    return AiExecutionProvenance(
        provisional.schema_version, provisional.expected_identity(), provisional.mode,
        provisional.source_sha256, provisional.reconstruction_identity,
        provisional.provider_identity, provisional.model_identity,
        provisional.request_attempted, provisional.request_count,
        provisional.request_status, provisional.generated_at_utc,
        provisional.prompt_contract_version, provisional.response_contract_version,
        provisional.result_identity, provisional.failure_category,
        provisional.fallback_used, provisional.automatic_retries,
        provisional.timeout_seconds, provisional.usage_status,
        provisional.input_tokens, provisional.output_tokens,
        provisional.total_tokens, provisional.cost_usd,
    )


def selected_mode_provenance(
    mode: ExecutionMode, source_sha256: str,
    reconstruction_identity: str | None = None,
) -> AiExecutionProvenance:
    return _record(
        mode=mode,
        source_sha256=source_sha256,
        reconstruction_identity=reconstruction_identity,
        provider_identity="openai" if mode == ExecutionMode.AI_DESIGN_LIVE else None,
        model_identity=None,
        request_status=RequestStatus.NOT_ATTEMPTED,
        failure_category=FailureCategory.NONE,
        timeout_seconds=45.0,
    )


def _failure_category(exc: Exception) -> FailureCategory:
    if isinstance(exc, ProposalCancelled):
        return FailureCategory.CANCELLATION
    if isinstance(exc, TimeoutError):
        return FailureCategory.TIMEOUT
    if isinstance(exc, ProposalContractRejection):
        return FailureCategory.CONTRACT_QUARANTINE
    if isinstance(exc, MissingIntentError):
        return FailureCategory.INTENT_BLOCKED
    message = str(exc).lower()
    if any(token in message for token in (
        "malformed", "no structured output", "no json proposal", "not contain a json",
        "json proposal was not an object",
    )):
        return FailureCategory.MALFORMED_OUTPUT
    return FailureCategory.PROVIDER_FAILURE


def _safe_failure_message(category: FailureCategory) -> str:
    return {
        FailureCategory.MISSING_CONFIGURATION:
            "Live AI Design requires an explicit OpenAI API key and model.",
        FailureCategory.RECONSTRUCTION_BLOCKED:
            "Native product reconstruction contains material ambiguity; no live request was made.",
        FailureCategory.INTENT_BLOCKED:
            "Essential manufacturing intent is incomplete; no live request was made.",
        FailureCategory.TIMEOUT:
            "The live OpenAI request timed out; no fallback was used.",
        FailureCategory.PROVIDER_FAILURE:
            "The live OpenAI request failed; no fallback was used.",
        FailureCategory.CONTRACT_QUARANTINE:
            "OpenAI output failed the typed contract and was quarantined; no fallback was used.",
        FailureCategory.MALFORMED_OUTPUT:
            "OpenAI output was malformed and was rejected; no fallback was used.",
        FailureCategory.CANCELLATION:
            "The live OpenAI request was cancelled; no fallback was used.",
        FailureCategory.NONE: "",
    }[category]


def _usage(provider: AiFixtureProvider) -> dict[str, int]:
    raw = getattr(provider, "last_usage", None)
    if not isinstance(raw, dict):
        return {}
    return {
        key: int(raw[key]) for key in ("input_tokens", "output_tokens", "total_tokens")
        if isinstance(raw.get(key), int) and raw[key] >= 0
    }


def execute_design_mode(
    document: WorkbenchDocument,
    workflow: InteractiveWorkflow,
    mode: ExecutionMode,
    *,
    provider: AiFixtureProvider | None = None,
    timeout_seconds: float = 45.0,
    cancellation: CancellationToken | None = None,
    prior_proposal: FixtureProposal | None = None,
    current_project: FxdProject | None = None,
) -> DesignExecutionOutcome:
    """Execute one explicit mode; live failures persist without fallback output."""
    if not isinstance(mode, ExecutionMode):
        raise AiExecutionError("execution mode must be explicitly selected")
    timeout = min(max(float(timeout_seconds), 0.1), 60.0)
    try:
        project = prepare_proposal_project(
            document, workflow, current_project=current_project,
        )
    except MissingIntentError:
        raise
    reconstruction = reconstruct_product(document, project.product, project.workflow)
    project = project.with_product_reconstruction(reconstruction)

    if mode == ExecutionMode.DETERMINISTIC_OFFLINE:
        baseline: ProposalGenerationOutcome = generate_fixture_proposal(
            document, workflow, provider=UnavailableAiProvider(), allow_fallback=True,
            timeout_seconds=timeout, cancellation=cancellation,
            prior_proposal=prior_proposal, current_project=project,
        )
        baseline_project = baseline.project.with_product_reconstruction(reconstruction)
        provenance = _record(
            mode=mode, source_sha256=document.source_sha256,
            reconstruction_identity=reconstruction.reconstruction_identity,
            provider_identity=None, model_identity=None, request_attempted=False,
            request_count=0, request_status=RequestStatus.OFFLINE,
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            prompt_contract_version=None, response_contract_version=None,
            result_identity=None, failure_category=FailureCategory.NONE,
            timeout_seconds=timeout, usage_status="unavailable",
        )
        baseline_project = baseline_project.with_ai_execution(provenance)
        return DesignExecutionOutcome(
            baseline_project, baseline.proposal, ProviderState.UNAVAILABLE,
            "Deterministic/offline mode completed; no live AI request occurred.", provenance,
        )

    active_provider = provider or OpenAiResponsesProvider.from_environment()
    model = getattr(active_provider, "engine_identifier", None)
    if (getattr(active_provider, "identity", None) != "openai"
            or not getattr(active_provider, "available", False)
            or not isinstance(model, str) or not model.strip()):
        provenance = _record(
            mode=mode, source_sha256=document.source_sha256,
            reconstruction_identity=reconstruction.reconstruction_identity,
            provider_identity="openai", model_identity=None,
            request_attempted=False, request_count=0,
            request_status=RequestStatus.FAILED,
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            failure_category=FailureCategory.MISSING_CONFIGURATION,
            timeout_seconds=timeout, usage_status="unavailable",
        )
        failed_project = project.with_ai_execution(provenance, clear_proposal=True)
        return DesignExecutionOutcome(
            failed_project, None, ProviderState.FAILED,
            _safe_failure_message(provenance.failure_category), provenance,
        )
    if reconstruction.blocked:
        provenance = _record(
            mode=mode, source_sha256=document.source_sha256,
            reconstruction_identity=reconstruction.reconstruction_identity,
            provider_identity="openai", model_identity=model.strip(),
            request_attempted=False, request_count=0,
            request_status=RequestStatus.FAILED,
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            failure_category=FailureCategory.RECONSTRUCTION_BLOCKED,
            timeout_seconds=timeout, usage_status="unavailable",
        )
        failed_project = project.with_ai_execution(provenance, clear_proposal=True)
        return DesignExecutionOutcome(
            failed_project, None, ProviderState.FAILED,
            _safe_failure_message(provenance.failure_category), provenance,
        )

    before_requests = int(getattr(active_provider, "request_count", 0))
    token = cancellation or CancellationToken.create()
    try:
        outcome = generate_fixture_proposal(
            document, workflow, provider=active_provider, allow_fallback=False,
            timeout_seconds=timeout, cancellation=token,
            prior_proposal=prior_proposal, current_project=project,
        )
        after_requests = int(getattr(active_provider, "request_count", before_requests + 1))
        request_count = after_requests - before_requests
        if request_count != 1:
            raise AiExecutionError("live provider did not record exactly one request")
        usage = _usage(active_provider)
        proposal = outcome.proposal
        provenance = _record(
            mode=mode, source_sha256=document.source_sha256,
            reconstruction_identity=reconstruction.reconstruction_identity,
            provider_identity="openai", model_identity=model.strip(),
            request_attempted=True, request_count=1,
            request_status=RequestStatus.SUCCEEDED,
            generated_at_utc=proposal.provenance.generated_at_utc,
            prompt_contract_version=proposal.provenance.prompt_contract_version,
            response_contract_version=proposal.provenance.response_contract_version,
            result_identity=proposal.proposal_identity,
            failure_category=FailureCategory.NONE, timeout_seconds=timeout,
            usage_status="reported" if usage else "unavailable",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=usage.get("total_tokens"), cost_usd=None,
        )
        completed = outcome.project.with_product_reconstruction(reconstruction)
        completed = completed.with_ai_execution(provenance)
        return DesignExecutionOutcome(
            completed, proposal, ProviderState.SUCCESS,
            "Live OpenAI request succeeded; no fallback was used.", provenance,
        )
    except Exception as exc:
        category = _failure_category(exc)
        after_requests = int(getattr(active_provider, "request_count", before_requests))
        request_count = max(0, min(1, after_requests - before_requests))
        status = RequestStatus.CANCELLED if category == FailureCategory.CANCELLATION else RequestStatus.FAILED
        provenance = _record(
            mode=mode, source_sha256=document.source_sha256,
            reconstruction_identity=reconstruction.reconstruction_identity,
            provider_identity="openai", model_identity=model.strip(),
            request_attempted=request_count == 1, request_count=request_count,
            request_status=status,
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            failure_category=category, timeout_seconds=timeout,
            usage_status="unavailable",
        )
        failed_project = project.with_ai_execution(provenance, clear_proposal=True)
        return DesignExecutionOutcome(
            failed_project, None,
            ProviderState.CANCELLED if status == RequestStatus.CANCELLED else ProviderState.FAILED,
            _safe_failure_message(category), provenance,
        )
