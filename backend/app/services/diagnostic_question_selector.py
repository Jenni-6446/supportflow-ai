from collections.abc import Sequence
from typing import Any

from app.schemas.analysis import IssueCategory
from app.services.diagnostic_question_bank import (
    DiagnosticQuestion,
    questions_for_category,
)


def select_clarification_questions(
    category: IssueCategory,
    user_text: str,
    playbook_missing_information: Sequence[Any] | None = None,
    max_questions: int = 5,
) -> list[dict[str, str]]:
    candidates = questions_for_category(category)
    if not candidates:
        if category != IssueCategory.UNKNOWN and playbook_missing_information:
            return _fallback_questions(playbook_missing_information, max_questions)
        candidates = questions_for_category(IssueCategory.GENERAL_IT)

    selected = _select_from_candidates(
        candidates,
        user_text,
        max_questions=max_questions,
    )
    if len(selected) < 3 and playbook_missing_information:
        return _fallback_questions(playbook_missing_information, max_questions)
    return [_to_public_question(question) for question in selected]


def _select_from_candidates(
    candidates: Sequence[DiagnosticQuestion],
    user_text: str,
    max_questions: int,
) -> list[DiagnosticQuestion]:
    normalized_text = user_text.lower()
    limit = max(1, min(max_questions, 5))
    scored_candidates = []

    for question in candidates:
        if question.requires_admin_access or not question.level1_safe:
            continue
        if _has_any_signal(normalized_text, question.avoid_if_signals):
            continue
        scored_candidates.append((_score(question, normalized_text), question))

    scored_candidates.sort(key=lambda item: item[0], reverse=True)

    selected: list[DiagnosticQuestion] = []
    used_dimensions: set[str] = set()
    for _, question in scored_candidates:
        if question.dimension in used_dimensions:
            continue
        selected.append(question)
        used_dimensions.add(question.dimension)
        if len(selected) == limit:
            return selected

    for _, question in scored_candidates:
        if question in selected:
            continue
        selected.append(question)
        if len(selected) == limit:
            break

    return selected


def _score(question: DiagnosticQuestion, normalized_text: str) -> int:
    signal_score = sum(
        15 for signal in question.signals if signal.lower() in normalized_text
    )
    return question.base_priority + signal_score


def _has_any_signal(normalized_text: str, signals: Sequence[str]) -> bool:
    return any(signal.lower() in normalized_text for signal in signals)


def _to_public_question(question: DiagnosticQuestion) -> dict[str, str]:
    return {
        "question": question.question,
        "reason": question.purpose,
    }


def _fallback_questions(
    playbook_missing_information: Sequence[Any],
    max_questions: int,
) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    limit = max(1, min(max_questions, 5))
    for item in playbook_missing_information:
        question = _fallback_question_text(item)
        reason = _fallback_reason_text(item)
        if not question:
            continue
        questions.append({"question": question, "reason": reason})
        if len(questions) == limit:
            break
    return questions


def _fallback_question_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("question", ""))
    return str(getattr(item, "question", ""))


def _fallback_reason_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("reason", "Collect this information before deeper checks."))
    return str(
        getattr(
            item,
            "reason",
            "Collect this information before deeper checks.",
        )
    )
