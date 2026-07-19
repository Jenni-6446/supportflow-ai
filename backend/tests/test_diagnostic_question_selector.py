import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


from app.schemas.analysis import IssueCategory  # noqa: E402
from app.schemas.ticket import TicketInput  # noqa: E402
from app.services.diagnostic_question_selector import (  # noqa: E402
    select_clarification_questions,
)
from app.services.mock_ai_provider import MockAIProvider  # noqa: E402


def question_text(questions: list[dict[str, str]]) -> str:
    return " ".join(item["question"] for item in questions).lower()


def assert_public_question_shape(questions: list[dict[str, str]]) -> None:
    assert 3 <= len(questions) <= 5
    for question in questions:
        assert set(question) == {"question", "reason"}
        assert question["question"]
        assert question["reason"]


def test_display_monitor_questions_are_relevant_and_safe():
    questions = select_clarification_questions(
        IssueCategory.DISPLAY_MONITOR,
        "monitor was off after a long time period used",
    )

    text = question_text(questions)

    assert_public_question_shape(questions)
    assert any(
        term in text
        for term in ("monitor", "power", "wake", "sleep", "computer", "laptop", "dock", "cable")
    )
    assert "account" not in text
    assert "mfa" not in text
    assert "password" not in text
    assert "application" not in text


def test_login_account_questions_cover_identity_differentiators():
    questions = select_clarification_questions(
        IssueCategory.LOGIN_ACCOUNT,
        "I cannot log in to my work account",
    )

    text = question_text(questions)

    assert_public_question_shape(questions)
    assert "account" in text
    assert "app" in text or "service" in text
    assert "error message" in text
    assert "mfa" in text
    assert "password" in text
    assert "only you" in text or "other users" in text


def test_vpn_questions_cover_remote_access_differentiators():
    questions = select_clarification_questions(
        IssueCategory.VPN_REMOTE_ACCESS,
        "VPN cannot connect",
    )

    text = question_text(questions)

    assert_public_question_shape(questions)
    assert "vpn error" in text
    assert "normal websites" in text or "internet" in text
    assert "home wi-fi" in text or "network" in text
    assert "mfa" in text or "password" in text


def test_printer_questions_skip_online_question_when_already_known():
    questions = select_clarification_questions(
        IssueCategory.PRINTER,
        "Printer is online but nothing prints",
    )

    text = question_text(questions)

    assert_public_question_shape(questions)
    assert "correct printer" in text
    assert "print queue" in text
    assert "other users" in text
    assert "document" in text or "app" in text
    assert "is the printer online" not in text


def test_file_permission_questions_cover_access_differentiators():
    questions = select_clarification_questions(
        IssueCategory.FILE_ACCESS_PERMISSION,
        "I cannot access a shared folder",
    )

    text = question_text(questions)

    assert_public_question_shape(questions)
    assert "folder path" in text or "link" in text or "shared drive" in text
    assert "permission" in text or "access error" in text
    assert "before" in text or "previous" in text
    assert "other users" in text


def test_unknown_issue_uses_safe_general_clarifying_questions():
    questions = select_clarification_questions(
        IssueCategory.GENERAL_IT,
        "Something stopped working",
    )

    text = question_text(questions)

    assert_public_question_shape(questions)
    assert "what exactly is not working" in text
    assert "trying to do" in text
    assert "error message" in text or "unusual behavior" in text
    assert "only you" in text or "other users" in text
    assert "root cause" not in text
    assert "definitely" not in text


def test_mock_provider_uses_question_selector_for_printer_intake():
    ticket = TicketInput.model_validate(
        {
            "title": "Printer is online but nothing prints",
            "userMessage": "Printer is online but nothing prints",
            "affectedService": "Printer",
            "deviceType": "Windows laptop",
            "location": "office",
            "affectedUsers": "single_user",
            "agentSelectedUrgency": "medium",
            "businessImpact": "User cannot print a needed document.",
            "environmentContext": {
                "applicationPlatform": "printer_system",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    text = " ".join(
        item.question for item in response.missing_information
    ).lower()

    assert "correct printer" in text
    assert "print job appear in the print queue" in text
    assert "other users" in text
    assert "document/app" in text
    assert "is the printer online" not in text
    assert set(response.missing_information[0].model_dump(by_alias=True)) == {
        "question",
        "reason",
    }
