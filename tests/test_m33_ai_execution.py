import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fxd_geometry import (
    AnnotationRole, CancellationToken, ExecutionMode, FailureCategory,
    FixtureProposalError, GeometryReference, InteractiveWorkflow, OcpKernel,
    ProcessSetup, ProviderState, RequestStatus, Vec3, ai_response_from_proposal,
    execute_design_mode, face_annotation, load_step_for_workbench,
    orientation_from_faces, product_from_workbench_document,
)
from fxd_geometry.project import FxdProject


class _LiveProvider:
    identity = "openai"
    engine_identifier = "explicit-test-model"
    prompt_contract_version = "test-prompt-v1"
    available = True

    def __init__(self, response=None, failure=None):
        self.response = response
        self.failure = failure
        self.request_count = 0
        self.last_usage = {
            "input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
        }

    def generate(self, request, *, timeout_seconds, cancellation):
        cancellation.raise_if_cancelled()
        self.request_count += 1
        if self.failure is not None:
            raise self.failure
        return self.response


class _MissingModelProvider:
    identity = "openai"
    engine_identifier = ""
    available = False
    request_count = 0


class _OverrunProvider(_LiveProvider):
    def generate(self, request, *, timeout_seconds, cancellation):
        cancellation.raise_if_cancelled()
        self.request_count += 2
        return self.response


class M33AiExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = OcpKernel()
        cls.source = cls.kernel.export_step(
            cls.kernel.make_box((0, 0, 0), (120, 80, 8))
        )

    def setUp(self):
        self.document = load_step_for_workbench(
            self.source, source_name="synthetic-live-proof.step",
        )
        product = product_from_workbench_document(self.document)
        component = product.components[0]
        kernel_component = self.document.assembly.components[0]
        bottom = kernel_component.faces[0]
        front = next(face for face in kernel_component.faces if abs(sum(
            left * right for left, right in zip(bottom.normal, face.normal)
        )) < 0.1)
        bottom_ref = GeometryReference(
            component.identity, component.bodies[0].identity, bottom.reference,
        )
        front_ref = GeometryReference(
            component.identity, component.bodies[0].identity, front.reference,
        )
        orientation = orientation_from_faces(
            self.document, bottom_ref, front_ref, accepted=True,
        )
        setup = ProcessSetup(
            "m33-live-proof", fixture_type="Full weld fixture",
            manufacturing_process="MIG welding", operation_mode="Manual",
            production_quantity=10, volume_category="Low",
            fixture_lifecycle="Store and reuse",
            manufacturing_orientation=orientation,
            manufacturing_build_direction=Vec3(0, 0, 1),
            manufacturing_loading_direction=Vec3(1, 0, 0),
            manufacturing_unloading_direction=Vec3(-1, 0, 0),
        )
        weld = face_annotation(
            self.document, front_ref, AnnotationRole.WELD_JOINT,
            notes="Synthetic confirmed weld intent.",
        )
        self.workflow = InteractiveWorkflow(
            self.document.source_sha256, setup, geometry_annotations=(weld,),
        )

    def test_offline_mode_never_calls_provider_or_claims_live_ai(self):
        provider = _LiveProvider(failure=AssertionError("must not be called"))
        outcome = execute_design_mode(
            self.document, self.workflow, ExecutionMode.DETERMINISTIC_OFFLINE,
            provider=provider,
        )
        self.assertEqual(provider.request_count, 0)
        self.assertIsNotNone(outcome.proposal)
        self.assertEqual(outcome.provider_state, ProviderState.UNAVAILABLE)
        self.assertEqual(outcome.provenance.request_status, RequestStatus.OFFLINE)
        self.assertFalse(outcome.provenance.request_attempted)
        self.assertFalse(outcome.provenance.fallback_used)
        self.assertEqual(outcome.project.ai_execution.mode, ExecutionMode.DETERMINISTIC_OFFLINE)

    def test_live_success_records_exactly_one_request_and_safe_usage(self):
        offline = execute_design_mode(
            self.document, self.workflow, ExecutionMode.DETERMINISTIC_OFFLINE,
        )
        provider = _LiveProvider(ai_response_from_proposal(offline.proposal))
        outcome = execute_design_mode(
            self.document, self.workflow, ExecutionMode.AI_DESIGN_LIVE,
            provider=provider, current_project=offline.project,
        )
        self.assertEqual(provider.request_count, 1)
        self.assertEqual(outcome.provider_state, ProviderState.SUCCESS)
        self.assertEqual(outcome.provenance.request_count, 1)
        self.assertTrue(outcome.provenance.request_attempted)
        self.assertEqual(outcome.provenance.model_identity, "explicit-test-model")
        self.assertEqual(outcome.provenance.total_tokens, 150)
        self.assertEqual(outcome.provenance.usage_status, "reported")
        self.assertFalse(outcome.provenance.fallback_used)
        self.assertNotEqual(outcome.proposal.provenance.source.value, "deterministic_fallback")

        with tempfile.TemporaryDirectory() as directory:
            restored = FxdProject.load(
                outcome.project.save(Path(directory) / "live.fxd.json")
            )
        self.assertEqual(restored.ai_execution.to_dict(), outcome.provenance.to_dict())
        self.assertEqual(
            restored.product_reconstruction.reconstruction_identity,
            outcome.provenance.reconstruction_identity,
        )

        reviewed = outcome.project.decide_fixture_proposal(
            "rejected", "retain the generation record through engineering review",
        )
        self.assertEqual(reviewed.ai_execution.to_dict(), outcome.provenance.to_dict())
        self.assertEqual(reviewed.fixture_proposal.proposal_decision, "rejected")

    def test_missing_key_or_model_fails_before_request_without_substitute(self):
        outcome = execute_design_mode(
            self.document, self.workflow, ExecutionMode.AI_DESIGN_LIVE,
            provider=_MissingModelProvider(),
        )
        self.assertEqual(outcome.provider_state, ProviderState.FAILED)
        self.assertEqual(outcome.provenance.failure_category,
                         FailureCategory.MISSING_CONFIGURATION)
        self.assertEqual(outcome.provenance.request_count, 0)
        self.assertIsNone(outcome.proposal)
        self.assertIsNone(outcome.project.fixture_proposal)
        self.assertFalse(outcome.provenance.fallback_used)

    def test_timeout_provider_failure_quarantine_and_malformed_output_fail_closed(self):
        offline = execute_design_mode(
            self.document, self.workflow, ExecutionMode.DETERMINISTIC_OFFLINE,
        )
        cases = (
            (TimeoutError("secret timeout detail"), FailureCategory.TIMEOUT),
            (FixtureProposalError("provider private detail"), FailureCategory.PROVIDER_FAILURE),
            (FixtureProposalError("OpenAI response was malformed"), FailureCategory.MALFORMED_OUTPUT),
        )
        for failure, category in cases:
            with self.subTest(category=category):
                provider = _LiveProvider(failure=failure)
                outcome = execute_design_mode(
                    self.document, self.workflow, ExecutionMode.AI_DESIGN_LIVE,
                    provider=provider, current_project=offline.project,
                )
                self.assertEqual(provider.request_count, 1)
                self.assertEqual(outcome.provenance.failure_category, category)
                self.assertEqual(outcome.provenance.request_count, 1)
                self.assertIsNone(outcome.proposal)
                self.assertIsNone(outcome.project.fixture_proposal)
                self.assertNotIn("private detail", outcome.message)
                self.assertFalse(outcome.provenance.fallback_used)

        malformed = ai_response_from_proposal(offline.proposal)
        malformed["schema_version"] = "unsupported"
        quarantined = execute_design_mode(
            self.document, self.workflow, ExecutionMode.AI_DESIGN_LIVE,
            provider=_LiveProvider(malformed), current_project=offline.project,
        )
        self.assertEqual(
            quarantined.provenance.failure_category,
            FailureCategory.CONTRACT_QUARANTINE,
        )
        self.assertIsNone(quarantined.proposal)

    def test_cancellation_is_persisted_and_makes_no_request_when_pre_cancelled(self):
        token = CancellationToken.create()
        token.cancel()
        provider = _LiveProvider(response={})
        outcome = execute_design_mode(
            self.document, self.workflow, ExecutionMode.AI_DESIGN_LIVE,
            provider=provider, cancellation=token,
        )
        self.assertEqual(provider.request_count, 0)
        self.assertEqual(outcome.provider_state, ProviderState.CANCELLED)
        self.assertEqual(outcome.provenance.failure_category, FailureCategory.CANCELLATION)
        self.assertEqual(outcome.provenance.request_status, RequestStatus.CANCELLED)
        self.assertIsNone(outcome.proposal)

    def test_provider_request_overrun_preserves_actual_count_and_fails_closed(self):
        offline = execute_design_mode(
            self.document, self.workflow, ExecutionMode.DETERMINISTIC_OFFLINE,
        )
        provider = _OverrunProvider(ai_response_from_proposal(offline.proposal))
        outcome = execute_design_mode(
            self.document, self.workflow, ExecutionMode.AI_DESIGN_LIVE,
            provider=provider, current_project=offline.project,
        )
        self.assertEqual(provider.request_count, 2)
        self.assertEqual(outcome.provider_state, ProviderState.FAILED)
        self.assertEqual(outcome.provenance.request_count, 2)
        self.assertTrue(outcome.provenance.request_attempted)
        self.assertEqual(
            outcome.provenance.failure_category,
            FailureCategory.REQUEST_BUDGET_VIOLATION,
        )
        self.assertIsNone(outcome.proposal)
        self.assertIsNone(outcome.project.fixture_proposal)
        self.assertFalse(outcome.provenance.fallback_used)

        with tempfile.TemporaryDirectory() as directory:
            restored = FxdProject.load(
                outcome.project.save(Path(directory) / "request-overrun.fxd.json")
            )
        self.assertEqual(restored.ai_execution.request_count, 2)
        self.assertEqual(
            restored.ai_execution.failure_category,
            FailureCategory.REQUEST_BUDGET_VIOLATION,
        )

    def test_environment_configuration_is_not_a_mode_selector(self):
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "configuration-only-secret",
            "FXD_OPENAI_MODEL": "explicit-env-model",
        }, clear=False):
            outcome = execute_design_mode(
                self.document, self.workflow, ExecutionMode.DETERMINISTIC_OFFLINE,
            )
        self.assertEqual(outcome.provenance.mode, ExecutionMode.DETERMINISTIC_OFFLINE)
        self.assertEqual(outcome.provenance.request_count, 0)
        self.assertIsNone(outcome.provenance.provider_identity)


if __name__ == "__main__":
    unittest.main()
