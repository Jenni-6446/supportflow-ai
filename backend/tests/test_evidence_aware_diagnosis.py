import sys
from datetime import datetime
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


from app.schemas.analysis import IssueCategory  # noqa: E402
from app.schemas.diagnosis import ChecklistResult  # noqa: E402
from app.schemas.ticket import TicketInput  # noqa: E402
from app.services.mock_ai_provider import MockAIProvider  # noqa: E402


UNSAFE_CLAIMS = (
    "logs show",
    "admin center confirms",
    "mail trace confirms",
    "checked exchange logs",
    "checked entra",
    "checked intune",
    "confirmed " + "root cause",
    "definitely",
)


def make_ticket(overrides: dict) -> TicketInput:
    payload = {
        "title": "Support issue",
        "userMessage": "User reports an IT issue.",
        "affectedService": "General IT",
        "deviceType": "Windows laptop",
        "location": "office",
        "affectedUsers": "unknown",
        "agentSelectedUrgency": "medium",
        "businessImpact": "User productivity is affected.",
        "errorMessage": "",
        "recentChange": "Unknown",
        "workaroundAvailable": "Unknown",
        "attachments": [],
        "environmentContext": {
            "operatingSystem": "windows",
            "accountPlatform": "microsoft_365",
            "deviceManagement": "intune",
            "deviceOwnership": "company_owned",
            "applicationPlatform": "unknown",
        },
    }
    payload.update(overrides)
    return TicketInput.model_validate(payload)


def result(step_id: str, value: str, evidence: str = "") -> ChecklistResult:
    return ChecklistResult.model_validate(
        {
            "stepId": step_id,
            "result": value,
            "evidence": evidence,
            "recordedAt": datetime.now().astimezone().isoformat(),
        }
    )


def clarification(index: int, question: str, answer: str, value: str) -> ChecklistResult:
    return result(
        f"clarification-{index}",
        value,
        f"Clarification answer. Question: {question} Answer: {answer}",
    )


def response_text(response) -> str:
    return response.model_dump_json(by_alias=True).lower()


@pytest.mark.parametrize(
    ("ticket", "expected_categories"),
    [
        (
            make_ticket(
                {
                    "title": "Outlook not receiving emails",
                    "userMessage": "Outlook is not receiving emails.",
                    "affectedService": "Outlook",
                }
            ),
            {IssueCategory.EMAIL_OUTLOOK},
        ),
        (
            make_ticket(
                {
                    "title": "Outlook desktop fails but webmail works",
                    "userMessage": "Outlook desktop will not sync but webmail works.",
                    "affectedService": "Outlook",
                }
            ),
            {IssueCategory.EMAIL_OUTLOOK},
        ),
        (
            make_ticket(
                {
                    "title": "Webmail also fails for the same mailbox",
                    "userMessage": "The mailbox fails in Outlook and webmail.",
                    "affectedService": "Email",
                }
            ),
            {IssueCategory.EMAIL_OUTLOOK},
        ),
        (
            make_ticket(
                {
                    "title": "Printer is online but nothing prints",
                    "userMessage": "The printer is online but nothing prints.",
                    "affectedService": "Printer",
                    "environmentContext": {"applicationPlatform": "printer_system"},
                }
            ),
            {IssueCategory.PRINTER},
        ),
        (
            make_ticket(
                {
                    "title": "Printer offline",
                    "userMessage": "The office printer shows offline.",
                    "affectedService": "Printer",
                    "environmentContext": {"applicationPlatform": "printer_system"},
                }
            ),
            {IssueCategory.PRINTER},
        ),
        (
            make_ticket(
                {
                    "title": "VPN authentication failed",
                    "userMessage": "VPN says authentication failed.",
                    "affectedService": "VPN",
                    "errorMessage": "Authentication failed",
                    "environmentContext": {"applicationPlatform": "vpn_client"},
                }
            ),
            {IssueCategory.VPN_REMOTE_ACCESS},
        ),
        (
            make_ticket(
                {
                    "title": "VPN fails on home Wi-Fi",
                    "userMessage": "VPN works on mobile hotspot but not home Wi-Fi.",
                    "affectedService": "VPN",
                    "environmentContext": {"applicationPlatform": "vpn_client"},
                }
            ),
            {IssueCategory.VPN_REMOTE_ACCESS},
        ),
        (
            make_ticket(
                {
                    "title": "Monitor says no signal",
                    "userMessage": "The external monitor says no signal.",
                    "affectedService": "External monitor",
                }
            ),
            {IssueCategory.DISPLAY_MONITOR},
        ),
        (
            make_ticket(
                {
                    "title": "Monitor completely off",
                    "userMessage": "The monitor has no power light and is completely off.",
                    "affectedService": "External monitor",
                }
            ),
            {IssueCategory.DISPLAY_MONITOR},
        ),
        (
            make_ticket(
                {
                    "title": "Teams microphone not working",
                    "userMessage": "People cannot hear me in Teams.",
                    "affectedService": "Microsoft Teams",
                }
            ),
            {IssueCategory.TEAMS_AUDIO_VIDEO},
        ),
        (
            make_ticket(
                {
                    "title": "Cannot access shared folder",
                    "userMessage": "The shared folder says access denied.",
                    "affectedService": "File share",
                    "errorMessage": "Access denied",
                }
            ),
            {IssueCategory.FILE_ACCESS_PERMISSION},
        ),
        (
            make_ticket(
                {
                    "title": "Wi-Fi keeps disconnecting",
                    "userMessage": "The laptop Wi-Fi keeps disconnecting.",
                    "affectedService": "Wi-Fi",
                }
            ),
            {IssueCategory.NETWORK_WIFI, IssueCategory.SMALL_OFFICE_NETWORK},
        ),
        (
            make_ticket(
                {
                    "title": "Cannot sign in to work account",
                    "userMessage": "I cannot sign in to my work account.",
                    "affectedService": "Microsoft 365",
                }
            ),
            {IssueCategory.LOGIN_ACCOUNT},
        ),
        (
            make_ticket(
                {
                    "title": "MFA prompt not appearing",
                    "userMessage": "The MFA prompt is not appearing when I sign in.",
                    "affectedService": "Microsoft 365",
                }
            ),
            {IssueCategory.LOGIN_ACCOUNT},
        ),
        (
            make_ticket(
                {
                    "title": "Staff app clock-in location issue",
                    "userMessage": "The staff app will not let me clock in at the right location.",
                    "affectedService": "Staff app",
                }
            ),
            {IssueCategory.APPLICATION_ERROR},
        ),
        (
            make_ticket(
                {
                    "title": "Something stopped working",
                    "userMessage": "Something stopped working.",
                    "affectedService": "Unknown",
                }
            ),
            {IssueCategory.GENERAL_IT},
        ),
        (
            make_ticket(
                {
                    "title": "Application form cannot be submitted",
                    "userMessage": "The company app form cannot be submitted.",
                    "affectedService": "Company app",
                    "environmentContext": {"applicationPlatform": "company_custom"},
                }
            ),
            {IssueCategory.APPLICATION_ERROR},
        ),
        (
            make_ticket(
                {
                    "title": "File works for other users but not this user",
                    "userMessage": "Other users can open the file but this user gets access denied.",
                    "affectedService": "File share",
                    "errorMessage": "Access denied",
                }
            ),
            {IssueCategory.FILE_ACCESS_PERMISSION},
        ),
        (
            make_ticket(
                {
                    "title": "Multiple users cannot access same system",
                    "userMessage": "Multiple users cannot access the same business system.",
                    "affectedService": "Business system",
                    "affectedUsers": "multiple_users",
                }
            ),
            {IssueCategory.APPLICATION_ERROR, IssueCategory.GENERAL_IT},
        ),
        (
            make_ticket(
                {
                    "title": "One user cannot open one app feature",
                    "userMessage": "One user cannot open one feature in the business app.",
                    "affectedService": "Business app",
                    "affectedUsers": "single_user",
                    "environmentContext": {"applicationPlatform": "company_custom"},
                }
            ),
            {IssueCategory.APPLICATION_ERROR},
        ),
    ],
)
def test_representative_it_issue_smoke_set(ticket, expected_categories):
    response = MockAIProvider().analyze_ticket(ticket)
    text = response_text(response)

    assert response.summary
    assert response.classification.category in expected_categories
    assert response.missing_information
    assert response.possible_causes
    assert "root cause " + "found" not in text
    assert all(claim not in text for claim in UNSAFE_CLAIMS)


def test_email_recent_change_no_and_webmail_fails_demotes_recent_change_direction():
    ticket = make_ticket(
        {
            "title": "Outlook is not receiving emails",
            "userMessage": "Outlook is not receiving emails.",
            "affectedService": "Outlook",
            "affectedUsers": "single_user",
            "recentChange": "No known change",
        }
    )
    response = MockAIProvider().update_diagnosis(
        ticket,
        [
            clarification(
                1,
                "Is this affecting one user, multiple users, one sender, one recipient, or all mail?",
                "One user",
                "works",
            ),
            clarification(
                2,
                "Does the same mailbox work in webmail, and what visible error or timing detail appears?",
                "No",
                "no",
            ),
            clarification(
                3,
                "Was there a recent password, account, Outlook profile, device, or mailbox access change?",
                "No",
                "no",
            ),
        ],
    )
    cause = response.current_likely_cause.cause.lower()

    assert "recent password" not in cause
    assert "recent" not in cause
    assert any(term in cause for term in ("mailbox", "delivery", "mail-flow", "access"))


def test_email_webmail_works_supports_outlook_client_direction():
    ticket = make_ticket(
        {
            "title": "Outlook desktop is not receiving emails",
            "userMessage": "Outlook desktop is not receiving emails.",
            "affectedService": "Outlook",
            "affectedUsers": "single_user",
            "recentChange": "No known change",
        }
    )
    response = MockAIProvider().update_diagnosis(
        ticket,
        [
            clarification(
                1,
                "Does the same mailbox work in webmail, and what visible error or timing detail appears?",
                "Yes",
                "yes",
            ),
            clarification(
                2,
                "Was there a recent password, account, Outlook profile, device, or mailbox access change?",
                "No",
                "no",
            ),
        ],
    )
    cause = response.current_likely_cause.cause.lower()

    assert "recent" not in cause
    assert any(term in cause for term in ("outlook desktop", "client", "profile", "cache"))


def test_printer_online_answer_prevents_repeating_online_status_step():
    ticket = make_ticket(
        {
            "title": "Printer is online but nothing prints",
            "userMessage": "The printer is online but nothing prints.",
            "affectedService": "Printer",
            "environmentContext": {"applicationPlatform": "printer_system"},
        }
    )
    response = MockAIProvider().update_diagnosis(
        ticket,
        [
            result("printer-confirm-symptom", "works", "User cannot print."),
            result("printer-affected-scope", "works", "One user is affected."),
            clarification(1, "Is the printer online or ready?", "Yes", "yes"),
        ],
    )
    actions = " ".join(response.next_best_actions).lower()

    assert "online" not in actions
    assert "ready" not in actions


def test_monitor_no_power_light_changes_direction_from_resolution_to_power_path():
    ticket = make_ticket(
        {
            "title": "Monitor completely off",
            "userMessage": "The monitor is completely off.",
            "affectedService": "External monitor",
        }
    )
    response = MockAIProvider().update_diagnosis(
        ticket,
        [
            clarification(
                1,
                "When the monitor goes off, is the power light on, blinking, or completely off?",
                "No power light",
                "works",
            ),
        ],
    )
    cause = response.current_likely_cause.cause.lower()

    assert any(term in cause for term in ("power", "cable", "hardware"))
    assert "resolution" not in cause


def test_scope_answers_change_application_direction_between_user_and_shared_impact():
    ticket = make_ticket(
        {
            "title": "Business app feature will not open",
            "userMessage": "A business app feature will not open.",
            "affectedService": "Business app",
            "environmentContext": {"applicationPlatform": "company_custom"},
        }
    )
    provider = MockAIProvider()

    single_user = provider.update_diagnosis(
        ticket,
        [
            clarification(
                1,
                "Is it affecting only you or other users too?",
                "Only me",
                "works",
            )
        ],
    )
    multiple_users = provider.update_diagnosis(
        make_ticket(
            {
                "title": "Business app feature will not open",
                "userMessage": "A business app feature will not open.",
                "affectedService": "Business app",
                "affectedUsers": "multiple_users",
                "environmentContext": {"applicationPlatform": "company_custom"},
            }
        ),
        [
            clarification(
                1,
                "Is it affecting only you or other users too?",
                "Other users also affected",
                "works",
            )
        ],
    )

    assert single_user.current_likely_cause.cause != multiple_users.current_likely_cause.cause
    assert any(
        term in single_user.current_likely_cause.cause.lower()
        for term in ("user", "device", "session", "profile", "client")
    )
    assert any(
        term in multiple_users.current_likely_cause.cause.lower()
        for term in ("shared", "service", "system", "workflow", "multiple")
    )
