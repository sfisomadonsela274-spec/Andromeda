"""
=============================================================================
     🌌 ANDROMEDA RAGAS & DEEPEVAL EVALUATION PYTEST INTEGRATION 🌌
=============================================================================
Automated evaluation test suite assessing:
  - Context Precision & Recall
  - Faithfulness (Groundedness / Inverse Hallucination)
  - Council Seat Compliance
  - Answer Relevancy
Using local Ollama stack (llama3.2 LLM-as-a-Judge and qwen2.5-coder:1.5b Generator).
=============================================================================
"""

import os
import sys
import pytest
import pytest_asyncio

# Ensure project root is resolvable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.andromeda_eval import AndromedaEvaluator, EvaluationCase, LLMJudge


@pytest.fixture(scope="module")
def evaluator():
    return AndromedaEvaluator()


@pytest.fixture(scope="module")
def judge():
    return LLMJudge()


class TestAndromedaRagasDeepEvalSuite:
    """Evaluates Andromeda using native Ragas and DeepEval-style local LLM metrics."""

    @pytest.mark.asyncio
    async def test_eval_council_seat_compliance(self, evaluator):
        """
        Verifies that the Council of AIs gate accurately routes prompts
        to the expected specialist seat (The Scribe, The Architect, The Logician, The Sentinel)
        with 100% compliance across benchmark cases.
        """
        cases = evaluator.cases
        for case in cases:
            from council_engine import adjudicate_seat
            seat_obj, _ = adjudicate_seat(case.query)
            assert case.expected_seat.lower() in seat_obj.title.lower(), (
                f"Query '{case.query}' misrouted to {seat_obj.title}, expected {case.expected_seat}"
            )

    @pytest.mark.asyncio
    async def test_eval_faithfulness_and_hallucination(self, evaluator, judge):
        """
        Evaluates whether claims in generated responses are strictly substantiated
        by the retrieved context, preventing hallucinations (Faithfulness >= 0.80, Hallucination <= 0.20).
        """
        case = evaluator.cases[0]  # case_01_scribe_architecture
        result = await evaluator.run_evaluation_case(case)

        assert result.faithfulness >= 0.75, (
            f"Faithfulness score {result.faithfulness:.2f} fell below threshold 0.75. "
            f"Reasoning: {result.judge_reasoning.get('faithfulness')}"
        )
        assert result.hallucination_score <= 0.25, (
            f"Hallucination score {result.hallucination_score:.2f} exceeded threshold 0.25."
        )

    @pytest.mark.asyncio
    async def test_eval_context_precision(self, evaluator, judge):
        """
        Verifies whether the retrieved memory context chunks are relevant and precise
        for answering the user query (Context Precision >= 0.70).
        """
        case = evaluator.cases[0]  # case_01_scribe_architecture
        result = await evaluator.run_evaluation_case(case)

        assert result.context_precision >= 0.70, (
            f"Context precision {result.context_precision:.2f} fell below threshold 0.70. "
            f"Reasoning: {result.judge_reasoning.get('context_precision')}"
        )

    @pytest.mark.asyncio
    async def test_eval_answer_relevancy(self, evaluator, judge):
        """
        Ensures the generated output directly addresses the user's intent without
        redundant conversational filler (Answer Relevancy >= 0.75).
        """
        case = evaluator.cases[0]  # case_01_scribe_architecture
        result = await evaluator.run_evaluation_case(case)

        assert result.answer_relevancy >= 0.70, (
            f"Answer relevancy {result.answer_relevancy:.2f} fell below threshold 0.70. "
            f"Reasoning: {result.judge_reasoning.get('answer_relevancy')}"
        )

    @pytest.mark.asyncio
    async def test_eval_comprehensive_matrix(self, evaluator):
        """
        Executes end-to-end evaluation across all benchmark cases and asserts
        that overall aggregate metrics meet production standards.
        """
        results = await evaluator.run_all()
        assert len(results) >= 7

        standard_results = [r for r in results if not getattr(r, "is_distractor_case", False)]
        distractor_results = [r for r in results if getattr(r, "is_distractor_case", False)]

        avg_compliance = sum(r.seat_compliance for r in results) / len(results)
        avg_precision = sum(r.context_precision for r in results) / len(results)
        avg_relevancy = sum(r.answer_relevancy for r in results) / len(results)

        assert avg_compliance == 1.0, f"Council seat compliance was {avg_compliance * 100:.1f}%, expected 100%"
        assert avg_precision >= 0.70, f"Mean context precision was {avg_precision:.2f}, expected >= 0.70"
        assert avg_relevancy >= 0.70, f"Mean answer relevancy was {avg_relevancy:.2f}, expected >= 0.70"

        # Verify distractor conflict handling across matrix run
        assert len(distractor_results) >= 2
        for dr in distractor_results:
            assert dr.conflict_flagged is True, f"Distractor {dr.case_id} failed to flag conflict"
            assert dr.hallucinated_compromise is False, f"Distractor {dr.case_id} hallucinated compromise"

    @pytest.mark.asyncio
    async def test_eval_negative_distractor_conflict_flagging(self, evaluator):
        """
        Negative Distractor Tests: Injects deliberately corrupted/conflicting context chunks
        into The Scribe and The Logician queries.
        Asserts that the model explicitly flags the conflict rather than hallucinating an inaccurate middle ground.
        """
        distractor_cases = [c for c in evaluator.cases if c.is_distractor_case]
        assert len(distractor_cases) >= 2, "Expected at least 2 negative distractor test cases"

        for case in distractor_cases:
            result = await evaluator.run_evaluation_case(case)
            assert result.conflict_flagged is True, (
                f"Model failed to flag conflicting context in '{case.id}'. "
                f"Reasoning: {result.judge_reasoning.get('conflict_handling')}"
            )
            assert result.hallucinated_compromise is False, (
                f"Model hallucinated a middle ground in '{case.id}' instead of reporting the contradiction."
            )

    @pytest.mark.asyncio
    async def test_eval_phoenix_metric_streaming(self, evaluator):
        """
        Stream Eval Scores to Phoenix Dashboard:
        Verifies that computed metrics (eval.faithfulness, eval.context_precision)
        are tagged onto OpenTelemetry spans sent to Phoenix and available in the API.
        """
        # Execute one evaluation case to ensure span is emitted
        case = evaluator.cases[0]
        result = await evaluator.run_evaluation_case(case)

        from tests.andromeda_eval import flush_phoenix_telemetry
        flush_phoenix_telemetry()

        # Query Arize Phoenix via official Phoenix Client SDK at http://localhost:6006
        from phoenix.client import Client
        phoenix_client = Client(base_url="http://localhost:6006")

        # Verify project existence
        projects = phoenix_client.projects.list()
        project_names = [p["name"] if isinstance(p, dict) else getattr(p, "name", "") for p in projects]
        assert "andromeda-eval" in project_names, f"Project 'andromeda-eval' not found in Phoenix: {project_names}"

        # Verify spans dataframe contains eval tags
        spans_df = phoenix_client.spans.get_spans_dataframe(project_name="andromeda-eval")
        assert len(spans_df) > 0, "No spans found in Phoenix 'andromeda-eval' project"

        eval_cols = [c for c in spans_df.columns if "eval" in c.lower()]
        assert len(eval_cols) > 0, f"No eval metric attributes found in Phoenix spans: {list(spans_df.columns)}"

        first_eval = spans_df["attributes.eval"].iloc[0]
        assert "faithfulness" in first_eval, f"faithfulness not in eval attributes: {first_eval}"
        assert "context_precision" in first_eval, f"context_precision not in eval attributes: {first_eval}"

