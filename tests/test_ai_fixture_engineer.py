from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fxd_geometry import (
    AdjustmentState, CancellationToken, ClecoStrategy, ConstructionMethod,
    FixtureBuildRequirements, FixtureLifecycle, FixtureProposal,
    FixtureProposalError, FixturePurpose, GeometryReference,
    HttpJsonAiProvider,
    InteractiveWorkflow, MissingIntentError, OcpKernel, ProcessSetup,
    ProposalCancelled, ProposalSource, ProviderState, RecommendationDecision,
    RecommendationType, StaticAiProvider, Vec3, ai_response_from_proposal,
    apply_recommended_intent, build_ai_request, generate_fixture_proposal,
    generate_fixture_build_plan, load_step_for_workbench, minimal_intent_questions,
    orientation_from_faces,
    reference_plane_orientation, ReferencePlane,
)
from fxd_geometry.operations import project_export_block_reason
from fxd_geometry.project import FxdProject, ProjectFormatError


class _TimeoutProvider:
    identity = "timeout-test"
    engine_identifier = "timeout-model"
    available = True

    def generate(self, request, *, timeout_seconds, cancellation):
        raise TimeoutError("bounded provider timeout")


class AiFixtureEngineerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.kernel = OcpKernel()
        cls.source = Path(cls.directory.name) / "m31-source.step"
        cls.source.write_bytes(cls.kernel.export_step(
            cls.kernel.make_box((0, 0, 0), (120, 80, 24))
        ))
        cls.original = cls.source.read_bytes()
        cls.document = load_step_for_workbench(cls.source)
        component = cls.document.assembly.components[0]
        body = "body:" + sha256(component.reference.encode()).hexdigest()[:20]

        def reference(normal):
            face = next(item for item in component.faces if all(
                abs(actual - expected) < 1.0e-7
                for actual, expected in zip(item.normal, normal)
            ))
            return GeometryReference(component.reference, body, face.reference)

        cls.bottom = reference((0.0, 0.0, -1.0))
        cls.front = reference((0.0, -1.0, 0.0))
        cls.orientation = orientation_from_faces(
            cls.document, cls.bottom, cls.front, flip_bottom=True, accepted=True,
        )
        cls.incomplete_workflow = InteractiveWorkflow(
            cls.document.source_sha256,
            ProcessSetup(
                "M31 guided proposal", manufacturing_orientation=cls.orientation,
                manufacturing_build_direction=Vec3(0, 0, 1),
            ),
        )
        cls.workflow = apply_recommended_intent(cls.incomplete_workflow)
        cls.fallback = generate_fixture_proposal(cls.document, cls.workflow)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_minimal_interview_asks_only_missing_essential_questions(self):
        questions = minimal_intent_questions(self.incomplete_workflow)
        self.assertEqual(
            {item.field for item in questions},
            {"fixture_type", "manufacturing_process", "operation_mode",
             "production_quantity", "fixture_lifecycle",
             "manufacturing_loading_direction", "manufacturing_unloading_direction"},
        )
        self.assertTrue(all(item.why_it_matters and item.recommended_answer is not None
                            for item in questions))
        with self.assertRaises(MissingIntentError):
            generate_fixture_proposal(self.document, self.incomplete_workflow)
        self.assertEqual(minimal_intent_questions(self.workflow), ())

    def test_offline_fallback_is_accurately_labeled_and_complete(self):
        proposal = self.fallback.proposal
        self.assertEqual(self.fallback.provider_state, ProviderState.UNAVAILABLE)
        self.assertEqual(proposal.provenance.source, ProposalSource.DETERMINISTIC_FALLBACK)
        self.assertIn("AI assistance unavailable", self.fallback.message)
        required = {
            RecommendationType.DATUM, RecommendationType.LOCATOR,
            RecommendationType.SUPPORT, RecommendationType.CLAMP,
            RecommendationType.BASE_STRUCTURE, RecommendationType.LOAD_UNLOAD,
        }
        self.assertTrue(required <= {item.recommendation_type
                                     for item in proposal.recommendations})
        self.assertTrue(all(item.engineering_reason and item.source_evidence
                            and item.deterministic_checks
                            for item in proposal.recommendations))

    def test_structured_context_contains_no_step_bytes_or_provider_secret(self):
        request = build_ai_request(self.fallback.project)
        encoded = json.dumps(request.to_dict(), sort_keys=True)
        self.assertNotIn("source_step_base64", encoded)
        self.assertNotIn("source_bytes", encoded)
        self.assertNotIn("FXD_AI_API_KEY", encoded)
        self.assertNotIn(self.original[:24].decode("ascii", errors="ignore"), encoded)
        self.assertEqual(request.source_sha256, sha256(self.original).hexdigest())

    def test_valid_mock_ai_response_is_versioned_and_provider_neutral(self):
        response = ai_response_from_proposal(self.fallback.proposal)
        outcome = generate_fixture_proposal(
            self.document, self.workflow,
            provider=StaticAiProvider(response, identity="mock-ai", engine_identifier="mock-v1"),
        )
        self.assertEqual(outcome.provider_state, ProviderState.SUCCESS)
        self.assertEqual(outcome.proposal.provenance.source, ProposalSource.AI)
        self.assertEqual(outcome.proposal.provenance.provider_identity, "mock-ai")
        self.assertEqual(outcome.proposal.provenance.engine_identifier, "mock-v1")

    def test_malformed_unknown_and_mismatched_ai_outputs_are_quarantined(self):
        cases = []
        malformed = ai_response_from_proposal(self.fallback.proposal)
        malformed["unexpected"] = True
        cases.append(malformed)
        wrong_source = ai_response_from_proposal(self.fallback.proposal)
        wrong_source["source_sha256"] = "f" * 64
        cases.append(wrong_source)
        wrong_orientation = ai_response_from_proposal(self.fallback.proposal)
        wrong_orientation["manufacturing_orientation_identity"] = "orientation-unknown"
        cases.append(wrong_orientation)
        unknown_identity = ai_response_from_proposal(self.fallback.proposal)
        unknown_identity["recommendations"][0]["source_evidence"][0]["identity"] = "face:unknown"
        cases.append(unknown_identity)
        malformed_recommendations = ai_response_from_proposal(self.fallback.proposal)
        malformed_recommendations["recommendations"] = None
        cases.append(malformed_recommendations)
        unknown_type = ai_response_from_proposal(self.fallback.proposal)
        unknown_type["recommendations"][0]["recommendation_type"] = "imaginary_fixture_rule"
        cases.append(unknown_type)
        provider_decision = ai_response_from_proposal(self.fallback.proposal)
        provider_decision["recommendations"][0]["decision"] = "accepted"
        cases.append(provider_decision)
        provider_note = ai_response_from_proposal(self.fallback.proposal)
        provider_note["recommendations"][0]["engineer_note"] = "provider-authored review"
        cases.append(provider_note)
        nested_recommendation = ai_response_from_proposal(self.fallback.proposal)
        nested_recommendation["recommendations"][0]["unsupported_claim"] = "approved"
        cases.append(nested_recommendation)
        nested_evidence = ai_response_from_proposal(self.fallback.proposal)
        nested_evidence["recommendations"][0]["source_evidence"][0]["extra"] = True
        cases.append(nested_evidence)
        nested_parameter = ai_response_from_proposal(self.fallback.proposal)
        editable = next(item for item in nested_parameter["recommendations"]
                        if item["editable_parameters"])
        editable["editable_parameters"][0]["unsupported_units_claim"] = True
        cases.append(nested_parameter)
        malformed_assumptions = ai_response_from_proposal(self.fallback.proposal)
        malformed_assumptions["recommendations"][0]["assumptions"] = "needs review"
        cases.append(malformed_assumptions)
        malformed_checks = ai_response_from_proposal(self.fallback.proposal)
        malformed_checks["recommendations"][0]["deterministic_checks"] = "validation"
        cases.append(malformed_checks)
        malformed_top_level = ai_response_from_proposal(self.fallback.proposal)
        malformed_top_level["assumptions"] = "review required"
        cases.append(malformed_top_level)
        for response in cases:
            with self.subTest(response=list(response)):
                outcome = generate_fixture_proposal(
                    self.document, self.workflow, provider=StaticAiProvider(response),
                )
                self.assertEqual(outcome.provider_state, ProviderState.FAILED)
                self.assertEqual(outcome.proposal.provenance.source,
                                 ProposalSource.DETERMINISTIC_FALLBACK)
                self.assertIn("quarantined", outcome.message)

    def test_invalid_ai_output_fails_closed_when_fallback_is_disabled(self):
        response = ai_response_from_proposal(self.fallback.proposal)
        response["source_sha256"] = "f" * 64
        with self.assertRaises(FixtureProposalError):
            generate_fixture_proposal(
                self.document, self.workflow, provider=StaticAiProvider(response),
                allow_fallback=False,
            )

    def test_timeout_and_cancellation_have_explicit_states(self):
        outcome = generate_fixture_proposal(
            self.document, self.workflow, provider=_TimeoutProvider(),
        )
        self.assertEqual(outcome.provider_state, ProviderState.FAILED)
        self.assertIn("timeout", outcome.message)
        cancellation = CancellationToken.create()
        cancellation.cancel()
        with self.assertRaises(ProposalCancelled):
            generate_fixture_proposal(
                self.document, self.workflow, cancellation=cancellation,
            )

    def test_provider_configuration_is_environment_only(self):
        with patch.dict("os.environ", {
            "FXD_AI_ENDPOINT": "https://provider.invalid/v1/proposals",
            "FXD_AI_API_KEY": "test-secret-not-persisted",
            "FXD_AI_MODEL": "fixture-model-v1",
            "FXD_AI_PROVIDER": "configured-test-provider",
        }, clear=False):
            provider = HttpJsonAiProvider.from_environment()
        self.assertTrue(provider.available)
        self.assertEqual(provider.identity, "configured-test-provider")
        self.assertEqual(provider.engine_identifier, "fixture-model-v1")
        self.assertNotIn(
            "test-secret-not-persisted",
            json.dumps(build_ai_request(self.fallback.project).to_dict(), sort_keys=True),
        )

    def test_deterministic_validation_wins_and_guided_issues_are_actionable(self):
        proposal = self.fallback.proposal
        self.assertGreater(proposal.blocker_count, 0)
        self.assertEqual(proposal.validation_status, "invalid")
        self.assertTrue(all(
            issue.rule_id and issue.what_is_wrong and issue.why_it_matters
            and issue.workflow_section and issue.fix_target
            for issue in proposal.guided_issues
        ))
        self.assertTrue(any(item.validation_status.value == "blocked"
                            for item in proposal.recommendations))
        project = self.fallback.project
        for recommendation in tuple(
                item for item in project.fixture_proposal.recommendations
                if item.recommendation_type == RecommendationType.CLAMP):
            project = project.decide_proposal_recommendation(
                recommendation.recommendation_id, RecommendationDecision.SUPPRESSED,
                "exercise missing-category correction routing",
            )
        missing = next(
            item for item in project.fixture_proposal.guided_issues
            if item.rule_id == "proposal_recommendation_missing"
            and item.affected_identity == RecommendationType.CLAMP.value
        )
        self.assertEqual(missing.workflow_section, "Proposal")
        self.assertEqual(missing.fix_target, "proposal_recommendations")

    def test_recommendation_decision_and_edit_are_audited_and_clear_downstream_state(self):
        requirements = FixtureBuildRequirements(
            self.fallback.project.product.source_sha256,
            FixturePurpose.TACK_LOCATION, ConstructionMethod.TACK_LOCATION,
            FixtureLifecycle.STORE_AND_REUSE, "JOB-A", "A", 10, "monthly", "MIG",
            ("laser cutting", "fixture welding"), True, None, True,
            AdjustmentState.LOCKED, ("review-only test plan",), (),
            ClecoStrategy.SEPARATE_FIXTURE_HOLES,
        )
        plan = generate_fixture_build_plan(
            self.fallback.project.product, self.fallback.project.active, requirements,
        )
        project = self.fallback.project.with_fixture_build(plan)
        project = project.with_drawing_intent({"drawing": "stale"})
        project = project.with_optimization_intent({"cost": "stale"})
        recommendation = next(
            item for item in project.fixture_proposal.recommendations
            if item.editable_parameters
        )
        decided = project.decide_proposal_recommendation(
            recommendation.recommendation_id, RecommendationDecision.REJECTED, "not usable",
        )
        changed = next(item for item in decided.fixture_proposal.recommendations
                       if item.recommendation_id == recommendation.recommendation_id)
        self.assertEqual(changed.decision, RecommendationDecision.REJECTED)
        self.assertTrue(decided.fixture_proposal.audit_history)
        self.assertIsNone(decided.drawing_intent)
        self.assertIsNone(decided.optimization_intent)
        self.assertIsNone(decided.fixture_build)
        editable = next(item for item in self.fallback.project.fixture_proposal.recommendations
                        if item.editable_parameters)
        parameter = editable.editable_parameters[0]
        edited = self.fallback.project.edit_proposal_recommendation(
            editable.recommendation_id, {parameter.name: parameter.value}, "confirmed value",
        )
        self.assertNotEqual(
            edited.fixture_proposal.proposal_identity,
            self.fallback.project.fixture_proposal.proposal_identity,
        )
        self.assertEqual(edited.fixture_proposal.proposal_decision, "pending")

    def test_regeneration_history_preserves_prior_proposal_identity(self):
        regenerated = generate_fixture_proposal(
            self.document, self.workflow, prior_proposal=self.fallback.proposal,
        )
        event = regenerated.proposal.audit_history[-1]
        self.assertEqual(event.action, "regenerate")
        self.assertEqual(event.prior_proposal_identity, self.fallback.proposal.proposal_identity)

    def test_proposal_persists_with_decisions_and_source_bytes_unchanged(self):
        recommendation = self.fallback.proposal.recommendations[0]
        project = self.fallback.project.decide_proposal_recommendation(
            recommendation.recommendation_id, RecommendationDecision.ACCEPTED,
            "reviewed against model",
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "m31.fxd.json"
            project.save(target)
            restored = FxdProject.load(target)
        self.assertEqual(restored.fixture_proposal.to_dict(), project.fixture_proposal.to_dict())
        self.assertEqual(restored.product.source_bytes, self.original)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_orientation_change_marks_visible_proposal_stale_and_blocks_approval_export(self):
        requirements = FixtureBuildRequirements(
            self.fallback.project.product.source_sha256,
            FixturePurpose.TACK_LOCATION, ConstructionMethod.TACK_LOCATION,
            FixtureLifecycle.STORE_AND_REUSE, "JOB-A", "A", 10, "monthly", "MIG",
            ("laser cutting", "fixture welding"), True, None, True,
            AdjustmentState.LOCKED, ("review-only test plan",), (),
            ClecoStrategy.SEPARATE_FIXTURE_HOLES,
        )
        plan = generate_fixture_build_plan(
            self.fallback.project.product, self.fallback.project.active, requirements,
        )
        project = self.fallback.project.with_fixture_build(plan)
        project = project.with_drawing_intent({"drawing": "stale"})
        project = project.with_optimization_intent({"cost": "stale"})
        changed_orientation = reference_plane_orientation(
            self.document.source_sha256, ReferencePlane.RIGHT, accepted=True,
        )
        changed_workflow = replace(
            project.workflow,
            setup=replace(
                project.workflow.setup,
                manufacturing_orientation=changed_orientation,
            ),
        )
        stale = project.with_workflow(changed_workflow)
        self.assertIsNotNone(stale.fixture_proposal)
        self.assertEqual(
            stale.fixture_proposal.stale_reason(
                stale.product.source_sha256, changed_orientation.identity,
            ),
            "manufacturing orientation changed",
        )
        self.assertIsNone(stale.drawing_intent)
        self.assertIsNone(stale.optimization_intent)
        self.assertIsNone(stale.fixture_build)
        self.assertIn("stale fixture proposal", project_export_block_reason(stale))
        with self.assertRaisesRegex(ProjectFormatError, "stale fixture proposal"):
            stale.decide("approve_for_review")

    def test_source_sha_mismatch_cannot_be_attached_or_loaded(self):
        payload = self.fallback.proposal.to_dict()
        payload["source_sha256"] = "f" * 64
        payload["proposal_identity"] = ""
        mismatched = FixtureProposal.from_dict(payload)
        with self.assertRaisesRegex(ProjectFormatError, "immutable source"):
            self.fallback.project.with_fixture_proposal(mismatched)


if __name__ == "__main__":
    unittest.main()
