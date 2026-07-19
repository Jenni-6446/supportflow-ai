from dataclasses import dataclass, field

from app.schemas.diagnosis import ChecklistResult, ChecklistResultValue
from app.schemas.ticket import AffectedUsers, TicketInput
from app.services.playbooks import Playbook


@dataclass
class EvidenceAssessment:
    suggested_cause: str | None = None
    confidence: str = "low"
    reasoning: str = ""
    ruled_out_causes: list[dict[str, str]] = field(default_factory=list)
    suppressed_action_terms: tuple[str, ...] = ()


@dataclass
class Candidate:
    cause: str
    score: int
    reasons: list[str] = field(default_factory=list)


LIKELIHOOD_BASE_SCORE = {
    "high": 30,
    "medium": 20,
    "low": 10,
}


RECENT_CHANGE_DEPENDENCY_TERMS = (
    "recent",
    "changed",
    "change",
)

LOCAL_PATH_TERMS = (
    "single-user",
    "single user",
    "only me",
    "one user",
    "user-side",
    "device",
    "client",
    "profile",
    "cache",
    "session",
    "local",
    "desktop",
)

SHARED_IMPACT_TERMS = (
    "multiple users",
    "other users",
    "shared",
    "service",
    "system",
    "workflow",
    "network",
    "tenant",
    "outage",
    "wider",
)


def assess_evidence(
    ticket: TicketInput,
    playbook: Playbook,
    checklist_results: list[ChecklistResult],
) -> EvidenceAssessment:
    candidates = _initial_candidates(playbook)
    ruled_out: list[dict[str, str]] = []
    suppressed_terms: set[str] = set()

    results_by_step = {result.step_id: result for result in checklist_results}
    for step in playbook.checklist_steps:
        result = results_by_step.get(step.id)
        if result is None:
            continue
        evidence_text = _known_step_evidence_text(step.id, result)
        if result.result in step.failure_results:
            _adjust_candidate(
                candidates,
                step.fail_cause,
                60,
                f"Recorded check supports: {step.step}",
            )
        if result.result in step.pass_results:
            _adjust_candidate(
                candidates,
                step.fail_cause,
                -36,
                f"Recorded check reduces: {step.step}",
            )
            if step.ruled_out_cause:
                _append_unique(
                    ruled_out,
                    step.ruled_out_cause,
                    result.evidence or "The related check was recorded as not supporting that path.",
                )
                _adjust_candidate(
                    candidates,
                    step.ruled_out_cause,
                    -36,
                    f"Recorded check reduces: {step.step}",
                )
        _apply_text_rules(
            ticket,
            playbook,
            result,
            evidence_text,
            candidates,
            ruled_out,
            suppressed_terms,
        )

    for index, result in enumerate(checklist_results, start=1):
        if result.step_id in results_by_step and any(
            result.step_id == step.id for step in playbook.checklist_steps
        ):
            continue
        _apply_text_rules(
            ticket,
            playbook,
            result,
            f"evidence {index}: {result.step_id} {result.evidence}",
            candidates,
            ruled_out,
            suppressed_terms,
        )

    _apply_ticket_scope(ticket, candidates)
    top = _top_supported_candidate(candidates)
    if top is None:
        return EvidenceAssessment(
            ruled_out_causes=ruled_out,
            suppressed_action_terms=tuple(sorted(suppressed_terms)),
        )

    return EvidenceAssessment(
        suggested_cause=top.cause,
        confidence="medium" if top.score >= 36 else "low",
        reasoning=_reasoning(top),
        ruled_out_causes=ruled_out,
        suppressed_action_terms=tuple(sorted(suppressed_terms)),
    )


def filter_completed_or_contradicted_actions(
    actions: list[str],
    assessment: EvidenceAssessment,
) -> list[str]:
    if not assessment.suppressed_action_terms:
        return actions

    filtered = []
    for action in actions:
        normalized = action.lower()
        if any(term in normalized for term in assessment.suppressed_action_terms):
            continue
        filtered.append(action)
    return filtered or actions[:1]


def _initial_candidates(playbook: Playbook) -> dict[str, Candidate]:
    candidates: dict[str, Candidate] = {}
    for cause in playbook.possible_causes:
        candidates[cause.cause] = Candidate(
            cause=cause.cause,
            score=LIKELIHOOD_BASE_SCORE.get(cause.likelihood, 10),
            reasons=[cause.reason],
        )
    for step in playbook.checklist_steps:
        candidates.setdefault(
            step.fail_cause,
            Candidate(cause=step.fail_cause, score=8, reasons=[]),
        )
    return candidates


def _known_step_evidence_text(
    step_id: str,
    result: ChecklistResult,
) -> str:
    return f"{step_id} result: {result.result.value} evidence: {result.evidence}"


def _apply_text_rules(
    ticket: TicketInput,
    playbook: Playbook,
    result: ChecklistResult,
    raw_text: str,
    candidates: dict[str, Candidate],
    ruled_out: list[dict[str, str]],
    suppressed_terms: set[str],
) -> None:
    text = raw_text.lower()
    affirmative = _is_affirmative(result)
    negative = _is_negative(result)

    if _mentions_recent_change(text):
        if negative or _contains_no_known_change(text):
            _demote_matching(
                candidates,
                RECENT_CHANGE_DEPENDENCY_TERMS,
                34,
                "The user explicitly denied a recent change.",
            )
            _append_unique(
                ruled_out,
                "Recent change-dependent hypothesis",
                "The user answered that there was no recent relevant change.",
            )
        elif affirmative:
            _add_or_adjust(
                candidates,
                "Recent password, account, profile, device, configuration, or access change",
                34,
                "The user reported a recent relevant change.",
            )

    if "webmail" in text:
        if negative:
            _add_or_adjust(
                candidates,
                "Mailbox, account, delivery, access, or service-side boundary needs more confirmation",
                44,
                "The same mailbox does not work in webmail, reducing a desktop-only explanation.",
            )
            _demote_matching(
                candidates,
                ("desktop", "client", "profile", "cache", "local app"),
                28,
                "Webmail also fails, so desktop-only evidence is weaker.",
            )
            _append_unique(
                ruled_out,
                "Outlook desktop-only client path",
                "Webmail was also reported as not working for the same mailbox.",
            )
        elif affirmative:
            _add_or_adjust(
                candidates,
                "Outlook desktop client, profile, cache, or local app path",
                44,
                "Webmail works for the same mailbox, supporting a local client path.",
            )
            _demote_matching(
                candidates,
                ("mail-flow", "service", "policy", "tenant", "quarantine"),
                20,
                "Webmail works, so service-side evidence is weaker.",
            )

    if _mentions_single_user_scope(text):
        _add_or_adjust(
            candidates,
            "Single-user device, account, session, profile, or client path",
            30,
            "Scope evidence points to one user rather than a shared impact.",
        )
        _demote_matching(
            candidates,
            SHARED_IMPACT_TERMS,
            18,
            "Single-user scope reduces wider-impact hypotheses.",
        )
        _append_unique(
            ruled_out,
            "Shared service-wide impact",
            "Evidence says other users are not affected.",
        )

    if _mentions_shared_scope(text):
        _add_or_adjust(
            candidates,
            "Shared service, network, system, location, or workflow impact",
            38,
            "Scope evidence points to multiple users or a shared workflow.",
        )
        _demote_matching(
            candidates,
            LOCAL_PATH_TERMS,
            18,
            "Multiple-user scope reduces local-only hypotheses.",
        )

    if "printer" in text and ("online" in text or "ready" in text):
        if affirmative:
            suppressed_terms.update({"online", "ready"})
            _demote_matching(
                candidates,
                ("offline", "paper", "toner", "jam", "status"),
                28,
                "The printer was reported as online or ready.",
            )
            _append_unique(
                ruled_out,
                "Printer offline or not-ready status",
                "The printer was reported as online or ready.",
            )
        elif negative or "offline" in text:
            _add_or_adjust(
                candidates,
                "Visible printer status, offline, paper, toner, jam, or device error",
                38,
                "Visible printer status evidence points to the device state.",
            )

    if ("mobile hotspot" in text or "another network" in text) and affirmative:
        _add_or_adjust(
            candidates,
            "Local network, DNS, firewall, or home Wi-Fi path",
            38,
            "The workflow works from another network or hotspot.",
        )
        _demote_matching(
            candidates,
            ("account-only", "account state", "saved credential"),
            18,
            "Working from another network weakens an account-only explanation.",
        )

    if _looks_like_no_power_display(text):
        _add_or_adjust(
            candidates,
            "Monitor power, cable, hardware, or physical connection path",
            44,
            "The display has no power light or appears completely off.",
        )
        _demote_matching(
            candidates,
            ("resolution", "duplicate", "extend", "display mode", "scaling"),
            28,
            "No power light weakens OS display-mode hypotheses.",
        )

    if _looks_like_no_signal_display(text):
        _add_or_adjust(
            candidates,
            "Input/source, cable, dock, adapter, or display path",
            40,
            "The display has power but reports no signal.",
        )

    if playbook.issue_category.value == "application_error":
        if _mentions_single_user_scope(text):
            _add_or_adjust(
                candidates,
                "Single-user app session, profile, device, or client path",
                34,
                "Only one user appears affected by the app workflow.",
            )
        if _mentions_shared_scope(text):
            _add_or_adjust(
                candidates,
                "Shared application service, feature, workflow, or system impact",
                42,
                "Other users appear affected by the same app workflow.",
            )


def _apply_ticket_scope(ticket: TicketInput, candidates: dict[str, Candidate]) -> None:
    if ticket.affected_users == AffectedUsers.SINGLE_USER:
        _add_or_adjust(
            candidates,
            "Single-user device, account, session, profile, or client path",
            8,
            "Ticket impact is marked as single user.",
        )
    if ticket.affected_users in {
        AffectedUsers.MULTIPLE_USERS,
        AffectedUsers.DEPARTMENT,
        AffectedUsers.ORGANIZATION,
    }:
        _add_or_adjust(
            candidates,
            "Shared service, network, system, location, or workflow impact",
            12,
            "Ticket impact is marked as broader than one user.",
        )


def _top_supported_candidate(candidates: dict[str, Candidate]) -> Candidate | None:
    supported = [candidate for candidate in candidates.values() if candidate.score >= 34]
    if not supported:
        return None
    supported.sort(key=lambda item: item.score, reverse=True)
    return supported[0]


def _reasoning(candidate: Candidate) -> str:
    reasons = [reason for reason in candidate.reasons if reason]
    if not reasons:
        return "Recorded evidence supports this working hypothesis, but more confirmation is still needed."
    return " ".join(
        [
            "Working hypothesis from recorded evidence:",
            " ".join(_dedupe(reasons)[-2:]),
            "Keep the conclusion tentative until the next check confirms it.",
        ]
    )


def _add_or_adjust(
    candidates: dict[str, Candidate],
    cause: str,
    delta: int,
    reason: str,
) -> None:
    if cause not in candidates:
        candidates[cause] = Candidate(cause=cause, score=0, reasons=[])
    candidate = candidates[cause]
    candidate.score += delta
    if reason not in candidate.reasons:
        candidate.reasons.append(reason)


def _adjust_candidate(
    candidates: dict[str, Candidate],
    cause: str,
    delta: int,
    reason: str,
) -> None:
    _add_or_adjust(candidates, cause, delta, reason)


def _demote_matching(
    candidates: dict[str, Candidate],
    terms: tuple[str, ...],
    delta: int,
    reason: str,
) -> None:
    for candidate in candidates.values():
        normalized = candidate.cause.lower()
        if any(term in normalized for term in terms):
            candidate.score -= delta
            if reason not in candidate.reasons:
                candidate.reasons.append(reason)


def _append_unique(ruled_out: list[dict[str, str]], cause: str, reason: str) -> None:
    if any(item["cause"] == cause for item in ruled_out):
        return
    ruled_out.append({"cause": cause, "reason": reason})


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _is_affirmative(result: ChecklistResult) -> bool:
    return result.result in {
        ChecklistResultValue.YES,
        ChecklistResultValue.WORKS,
    }


def _is_negative(result: ChecklistResult) -> bool:
    return result.result in {
        ChecklistResultValue.NO,
        ChecklistResultValue.DOES_NOT_WORK,
    }


def _mentions_recent_change(text: str) -> bool:
    return "recent" in text or "change" in text or "changed" in text


def _contains_no_known_change(text: str) -> bool:
    return (
        "no known change" in text
        or "answer: no" in text
        or " no " in f" {text} "
        or "none" in text
    )


def _mentions_single_user_scope(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "one user",
            "only me",
            "only this user",
            "this user",
            "other users can",
            "no other users",
            "not other users",
        )
    )


def _mentions_shared_scope(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "multiple users",
            "other users also",
            "other users are affected",
            "everyone",
            "all users",
            "same system",
            "shared",
        )
    )


def _looks_like_no_power_display(text: str) -> bool:
    return (
        "no power light" in text
        or "power light off" in text
        or "completely off" in text
        or "no led" in text
    )


def _looks_like_no_signal_display(text: str) -> bool:
    has_no_signal = "no signal" in text
    has_power = "power light on" in text or "has power" in text or "power but" in text
    return has_no_signal and has_power
