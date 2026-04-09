from scripts.run_eval import EvalCase, EvalObservation, evaluate_case, exit_code_for_results


def test_evaluate_case_passes_exact_lookup_with_expected_tool() -> None:
    case = EvalCase(
        id="duty-cycle",
        question="What's the duty cycle?",
        expected_answer="25%, 200A",
        expected_mode="exact_lookup",
        expected_tool="lookup_duty_cycle",
    )
    observation = EvalObservation(
        answer="The rated duty cycle is 25% at 200A on 240V.",
        tools_called=["lookup_duty_cycle"],
    )

    result = evaluate_case(case, observation)

    assert result.status == "passed"
    assert not result.issues


def test_evaluate_case_fails_when_expected_tool_missing() -> None:
    case = EvalCase(
        id="duty-cycle",
        question="What's the duty cycle?",
        expected_answer="25%",
        expected_mode="exact_lookup",
        expected_tool="lookup_duty_cycle",
    )
    observation = EvalObservation(
        answer="The rated duty cycle is 25% at 200A on 240V.",
        tools_called=["search_manual"],
    )

    result = evaluate_case(case, observation)

    assert result.status == "failed"
    assert any("lookup_duty_cycle" in issue for issue in result.issues)


def test_evaluate_case_requires_artifact_for_diagram_mode() -> None:
    case = EvalCase(
        id="tig-polarity",
        question="Show TIG polarity",
        expected_mode="diagram",
        expected_tool="lookup_polarity",
    )
    observation = EvalObservation(
        answer="Use DCEN for TIG.",
        tools_called=["lookup_polarity"],
        has_artifact=False,
    )

    result = evaluate_case(case, observation)

    assert result.status == "failed"
    assert any("artifact" in issue.lower() for issue in result.issues)


def test_evaluate_case_requires_image_for_image_retrieval_mode() -> None:
    case = EvalCase(
        id="front-panel",
        question="What are the front panel controls?",
        expected_mode="image_retrieval",
    )
    observation = EvalObservation(
        answer="Here are the front panel controls.",
        tools_called=["get_page_image"],
        has_image=False,
    )

    result = evaluate_case(case, observation)

    assert result.status == "failed"
    assert any("image" in issue.lower() for issue in result.issues)


def test_evaluate_case_passes_clarification_mode_when_requested() -> None:
    case = EvalCase(
        id="ambiguous-duty-cycle",
        question="What's the duty cycle?",
        expected_mode="clarification",
    )
    observation = EvalObservation(answer="", has_clarification=True)

    result = evaluate_case(case, observation)

    assert result.status == "passed"


def test_exit_code_is_non_zero_for_needs_review() -> None:
    assert exit_code_for_results(failed=0, needs_review=1) == 1
