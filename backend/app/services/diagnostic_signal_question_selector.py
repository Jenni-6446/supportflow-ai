from typing import Any

from app.schemas.analysis import IssueCategory


APPLICATION_WORKFLOW_SIGNALS = {
    "application_workflow_failed",
    "business_application_workflow_failed",
    "software_application_workflow_failed",
}

LOCATION_WORKFLOW_SIGNALS = {
    "location_based_verification",
    "geofence_verification",
    "gps_verification",
}

TIME_ATTENDANCE_SIGNALS = {
    "time_attendance_or_clock_in_workflow",
    "clock_in_workflow",
    "punch_in_workflow",
    "check_in_workflow",
}

SIGNAL_ALIASES = {
    "app_workflow_failed": "application_workflow_failed",
    "application_failure": "application_workflow_failed",
    "business_app_failure": "business_application_workflow_failed",
    "location_verification": "location_based_verification",
    "location_issue": "location_based_verification",
    "geofence_issue": "geofence_verification",
    "gps_issue": "gps_verification",
    "clock_in": "time_attendance_or_clock_in_workflow",
    "punch_in": "time_attendance_or_clock_in_workflow",
    "check_in": "time_attendance_or_clock_in_workflow",
}


def has_signal(draft: Any, signal_name: str) -> bool:
    return signal_name.lower() in _normalized_signals(draft)


def corrected_category_for_semantic_signals(
    category: IssueCategory,
    draft: Any,
) -> IssueCategory:
    if category not in {IssueCategory.GENERAL_IT, IssueCategory.UNKNOWN}:
        return category
    if _has_any_signal(draft, APPLICATION_WORKFLOW_SIGNALS):
        return IssueCategory.APPLICATION_ERROR
    return category


def select_signal_based_questions(
    category: IssueCategory,
    ticket_text: str,
    draft: Any,
    max_questions: int = 5,
) -> list[dict[str, str]]:
    if _is_application_location_workflow(category, draft):
        return _application_location_workflow_questions(
            ticket_text,
            draft,
            max_questions,
        )
    if _is_application_workflow(category, draft):
        return _application_workflow_questions(draft, max_questions)
    return []


def signal_based_possible_causes(
    category: IssueCategory,
    ticket_text: str,
    draft: Any,
) -> list[dict[str, str]]:
    if _is_application_location_workflow(category, draft):
        return [
            {
                "cause": "Location permission or geofence verification issue",
                "likelihood": "high",
                "reason": "The issue involves a location-based app workflow and the user says they are at the expected location.",
            },
            {
                "cause": "App session, cache, or app state issue",
                "likelihood": "medium",
                "reason": "A single app workflow can fail because of local app state before admin review is needed.",
            },
            {
                "cause": "Phone network connectivity issue",
                "likelihood": "medium",
                "reason": "Location-based workflows may need network access to validate the action.",
            },
            {
                "cause": "App service or specific feature issue",
                "likelihood": "medium",
                "reason": "If only this workflow fails, the app feature or service path may be affected.",
            },
            {
                "cause": "Account/profile/permission issue",
                "likelihood": "medium",
                "reason": "The user's app profile or permissions may affect whether they can complete this workflow.",
            },
            {
                "cause": "Outdated app version or device time/location setting issue",
                "likelihood": "low",
                "reason": "App version, device time, and location settings can affect location-based validation.",
            },
        ]

    if _is_application_workflow(category, draft):
        return [
            {
                "cause": "App feature or workflow issue",
                "likelihood": "medium",
                "reason": "The issue is tied to a specific action or workflow in the application.",
            },
            {
                "cause": "App session, cache, or app state issue",
                "likelihood": "medium",
                "reason": "A single application workflow can fail because of local app or browser state.",
            },
            {
                "cause": "Network connectivity issue",
                "likelihood": "medium",
                "reason": "Business app form submissions and workflows may need reliable network access.",
            },
            {
                "cause": "Account/profile/permission issue",
                "likelihood": "medium",
                "reason": "The user's profile or permissions may affect whether the workflow can be completed.",
            },
            {
                "cause": "Recent app, browser, or device state change",
                "likelihood": "low",
                "reason": "Recent local changes can affect browser or app workflow behavior.",
            },
        ]

    return []


def _application_location_workflow_questions(
    ticket_text: str,
    draft: Any,
    max_questions: int,
) -> list[dict[str, str]]:
    app = _clean_text(getattr(draft, "app_or_service", None)) or "the app"
    action = _clean_text(getattr(draft, "user_action", None)) or "complete the action"
    user_claims_location = has_signal(draft, "user_claims_correct_location") or any(
        phrase in ticket_text.lower()
        for phrase in (
            "right location",
            "correct location",
            "at the location",
            "at the job site",
            "on site",
            "onsite",
        )
    )
    location_question = (
        f"Does {app} still show a location or geofence error even though you are on site?"
        if user_claims_location
        else f"Does {app} say it cannot verify your location or that you are outside the allowed area?"
    )

    questions = [
        {
            "question": f"What exact message does {app} show when you try to {action}?",
            "reason": "Exact visible wording separates location verification, account/profile, network, and app workflow symptoms.",
        },
        {
            "question": location_question,
            "reason": "This checks whether the app is failing location or geofence verification without asking the user to prove their location again.",
        },
        {
            "question": f"Is location permission enabled for {app}, and are phone Location Services/GPS turned on?",
            "reason": "Location permission and GPS state are safe Level 1 checks for location-based app workflows.",
        },
        {
            "question": f"Can you use other features in {app}, or only this action fails?",
            "reason": "Feature scope separates one workflow failure from a wider app or account issue.",
        },
        {
            "question": "Are other users able to complete the same action at the same location?",
            "reason": "Scope separates a single user/device path from location, service, or feature-level impact.",
        },
        {
            "question": "Did this work before, and when did it start failing?",
            "reason": "Timing helps connect the issue to app state, device changes, location changes, or service behavior.",
        },
    ]
    return questions[: max(1, min(max_questions, 5))]


def _application_workflow_questions(
    draft: Any,
    max_questions: int,
) -> list[dict[str, str]]:
    app = _clean_text(getattr(draft, "app_or_service", None)) or "the app"
    action = _clean_text(getattr(draft, "user_action", None)) or "complete the action"

    questions = [
        {
            "question": f"What exact message does {app} show when you try to {action}?",
            "reason": "Exact visible wording separates form validation, access, session, network, and service-side workflow symptoms.",
        },
        {
            "question": f"Which feature, page, or form in {app} is affected?",
            "reason": "This separates one workflow or form from a wider application issue.",
        },
        {
            "question": f"Can you use other features in {app}, or only {action} fails?",
            "reason": "Feature scope helps distinguish local app state from an affected app feature or account path.",
        },
        {
            "question": f"Are other users affected by the same {app} workflow?",
            "reason": "Scope separates a single-user/device issue from a wider application or service impact.",
        },
        {
            "question": "Did this work before, and when did it start failing?",
            "reason": "Timing helps connect the issue to recent changes, app state, account changes, or service behavior.",
        },
    ]
    return questions[: max(1, min(max_questions, 5))]


def _is_application_workflow(category: IssueCategory, draft: Any) -> bool:
    return category == IssueCategory.APPLICATION_ERROR and _has_any_signal(
        draft,
        APPLICATION_WORKFLOW_SIGNALS,
    )


def _is_application_location_workflow(category: IssueCategory, draft: Any) -> bool:
    return (
        _is_application_workflow(category, draft)
        and _has_any_signal(draft, LOCATION_WORKFLOW_SIGNALS)
    )


def _has_any_signal(draft: Any, signal_names: set[str]) -> bool:
    signals = _normalized_signals(draft)
    return any(signal in signals for signal in signal_names)


def _normalized_signals(draft: Any) -> set[str]:
    normalized = {
        str(signal).strip().lower().replace("-", "_").replace(" ", "_")
        for signal in getattr(draft, "diagnostic_signals", [])
        if str(signal).strip()
    }
    return normalized | {
        SIGNAL_ALIASES[signal]
        for signal in normalized
        if signal in SIGNAL_ALIASES
    }


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split()).strip()
