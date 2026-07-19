import sys
from datetime import datetime
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


from app.schemas.analysis import (  # noqa: E402
    ChecklistGroup,
    ChecklistResultType,
    InitialTriageResponse,
    IssueCategory,
)
from app.schemas.diagnosis import (  # noqa: E402
    ChecklistResult,
    ChecklistResultValue,
    UpdatedDiagnosisResponse,
)
from app.schemas.documentation import DocumentationResponse  # noqa: E402
from app.schemas.ticket import TicketInput  # noqa: E402
from app.services.mock_ai_provider import MockAIProvider  # noqa: E402
from app.services.playbooks import (  # noqa: E402
    Playbook,
    PlaybookCause,
    PlaybookStep,
)


def make_ticket(overrides: dict) -> TicketInput:
    payload = {
        "title": "Support issue",
        "userMessage": "User reports an IT issue.",
        "affectedService": "General IT",
        "deviceType": "Windows laptop",
        "location": "home",
        "affectedUsers": "single_user",
        "agentSelectedUrgency": "medium",
        "businessImpact": "User productivity is affected.",
    }
    payload.update(overrides)
    return TicketInput.model_validate(payload)


def make_result(
    step_id: str,
    result: str,
    evidence: str = "",
) -> ChecklistResult:
    return ChecklistResult.model_validate(
        {
            "stepId": step_id,
            "result": result,
            "evidence": evidence,
            "recordedAt": datetime.now().astimezone().isoformat(),
        }
    )


def test_vpn_ticket_returns_vpn_remote_access_category():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": (
                "I cannot connect to VPN from home. It worked yesterday, but "
                "today it says authentication failed."
            ),
            "affectedService": "VPN",
            "errorMessage": "Authentication failed",
            "environmentContext": {
                "operatingSystem": "windows",
                "accountPlatform": "microsoft_365",
                "applicationPlatform": "vpn_client",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)

    assert isinstance(response, InitialTriageResponse)
    assert response.classification.category == IssueCategory.VPN_REMOTE_ACCESS
    assert response.classification.subcategory == "VPN"


def test_vpn_ticket_returns_platform_aware_checklist_items():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "errorMessage": "Authentication failed",
            "environmentContext": {
                "operatingSystem": "windows",
                "accountPlatform": "microsoft_365",
                "applicationPlatform": "vpn_client",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    checklist_text = " ".join(item.step for item in response.checklist).lower()

    assert "internet" in checklist_text
    assert "saved credential" in checklist_text or "password" in checklist_text
    assert "mfa" in checklist_text
    assert "vpn client" in checklist_text
    assert response.escalation_criteria
    assert response.safety_notes


def test_vpn_checklist_uses_progressive_layer_groups():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "errorMessage": "Authentication failed",
            "environmentContext": {
                "operatingSystem": "windows",
                "accountPlatform": "microsoft_365",
                "applicationPlatform": "vpn_client",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    grouped_steps = {
        item.id: item.group.value if item.group else None
        for item in response.checklist
    }

    assert grouped_steps["vpn-confirm-internet"] == ChecklistGroup.SCOPE_IMPACT.value
    assert (
        grouped_steps["vpn-password-change"]
        == ChecklistGroup.SIMPLE_USER_CHECKS.value
    )
    assert (
        grouped_steps["vpn-client-opens"]
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION.value
    )
    assert (
        grouped_steps["vpn-escalation-review"]
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE.value
    )


def test_playbook_checklist_includes_v15_metadata():
    ticket = make_ticket(
        {
            "title": "Internal app error",
            "userMessage": "The company portal shows an unexpected error after submit.",
            "affectedService": "Company Portal",
            "errorMessage": "Unexpected error",
            "environmentContext": {
                "applicationPlatform": "company_custom",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    checklist_by_id = {item.id: item for item in response.checklist}

    scope_step = checklist_by_id["application-error-scope"]
    escalation_step = checklist_by_id["application-error-escalation"]

    assert scope_step.level1_actionable is True
    assert scope_step.requires_privileged_access is False
    assert scope_step.evidence_prompt
    assert escalation_step.level1_actionable is False
    assert escalation_step.requires_privileged_access is True
    assert "admin" in escalation_step.access_requirement.lower()
    assert "vendor" in escalation_step.access_requirement.lower()


def test_vpn_diagnosis_layer1_failure_focuses_on_connectivity():
    ticket = make_ticket(
        {
            "title": "VPN will not connect",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "environmentContext": {
                "applicationPlatform": "vpn_client",
            },
        }
    )
    results = [
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-confirm-internet",
                "result": "does_not_work",
                "evidence": "Public websites do not load either.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert "local internet" in response.current_likely_cause.cause.lower()
    assert "Layer 1" in response.current_likely_cause.reasoning
    assert "normal internet" in response.next_best_action.lower()
    assert response.escalation_recommendation.should_escalate is False


def test_vpn_diagnosis_layer2_auth_issue_after_basic_checks_pass():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "errorMessage": "Authentication failed",
            "environmentContext": {
                "applicationPlatform": "vpn_client",
            },
        }
    )
    results = [
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-confirm-internet",
                "result": "works",
                "evidence": "Public websites open normally.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-confirm-scope",
                "result": "no",
                "evidence": "No other users are affected.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-password-change",
                "result": "yes",
                "evidence": "The user changed their password this morning.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert "authentication" in response.current_likely_cause.cause.lower()
    assert "credential" in response.current_likely_cause.cause.lower()
    assert "Layer 1" in response.current_likely_cause.reasoning
    assert "Layer 2" in response.current_likely_cause.reasoning
    assert "saved credential" in response.next_best_action.lower()


def test_vpn_diagnosis_layer3_client_issue_after_auth_checks_pass():
    ticket = make_ticket(
        {
            "title": "VPN profile missing",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "environmentContext": {
                "applicationPlatform": "vpn_client",
            },
        }
    )
    results = [
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-confirm-internet",
                "result": "works",
                "evidence": "Public websites open normally.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-confirm-scope",
                "result": "no",
                "evidence": "Only this user is affected.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-password-change",
                "result": "no",
                "evidence": "No recent password change.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-saved-credentials",
                "result": "no",
                "evidence": "No saved credential prompt appears.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-mfa-behavior",
                "result": "works",
                "evidence": "MFA prompt appears and approval succeeds.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-profile-selected",
                "result": "does_not_work",
                "evidence": "Expected VPN profile is missing.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert "client" in response.current_likely_cause.cause.lower()
    assert "profile" in response.current_likely_cause.cause.lower()
    assert "Layer 2" in response.current_likely_cause.reasoning
    assert "Layer 3" in response.current_likely_cause.reasoning


def test_vpn_diagnosis_escalates_after_layers_one_to_three_pass():
    ticket = make_ticket(
        {
            "title": "VPN still fails after local checks",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "environmentContext": {
                "applicationPlatform": "vpn_client",
            },
        }
    )
    now = datetime.now().astimezone().isoformat()
    results = [
        ChecklistResult.model_validate(
            {
                "stepId": step_id,
                "result": result,
                "evidence": evidence,
                "recordedAt": now,
            }
        )
        for step_id, result, evidence in [
            ("vpn-confirm-internet", "works", "Public websites open normally."),
            ("vpn-confirm-scope", "no", "Only this user is affected."),
            ("vpn-capture-error-message", "works", "Authentication failed."),
            ("vpn-recent-change", "no", "No recent device or location change."),
            ("vpn-password-change", "no", "No recent password change."),
            ("vpn-saved-credentials", "no", "Saved credentials were not used."),
            ("vpn-mfa-behavior", "works", "MFA prompt appears and approval succeeds."),
            ("vpn-client-opens", "works", "VPN client opens normally."),
            ("vpn-profile-selected", "works", "Expected profile is selected."),
            ("vpn-client-error", "works", "No additional client error appears."),
        ]
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.escalation_recommendation.should_escalate is True
    assert response.status.value == "ready_to_escalate"
    assert "admin" in response.next_best_action.lower()
    assert "Layer 4" in response.current_likely_cause.reasoning


def test_vpn_diagnosis_with_missing_evidence_asks_for_next_layer_information():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "environmentContext": {
                "applicationPlatform": "vpn_client",
            },
        }
    )

    response = MockAIProvider().update_diagnosis(ticket, [])

    assert "more vpn evidence needed" in response.current_likely_cause.cause.lower()
    assert "Layer 1" in response.current_likely_cause.reasoning
    assert "normal internet" in response.next_best_action.lower()
    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence
    assert response.next_best_actions[0] == response.next_best_action
    assert response.level1_can_continue is True
    assert response.level1_blocker_reason == ""


def test_generic_diagnosis_no_evidence_starts_at_scope_impact():
    ticket = make_ticket(
        {
            "title": "Office Wi-Fi not connecting",
            "userMessage": "My laptop cannot connect to office Wi-Fi.",
            "affectedService": "Wi-Fi",
        }
    )

    response = MockAIProvider().update_diagnosis(ticket, [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.completed_layers == []
    assert response.missing_evidence
    assert response.missing_evidence[0].step_id == "wifi-see-ssid"
    assert len(response.next_best_actions) <= 3
    assert response.next_best_actions[0] == response.next_best_action
    assert response.level1_can_continue is True


def test_generic_diagnosis_user_unsure_is_missing_evidence():
    ticket = make_ticket(
        {
            "title": "Office Wi-Fi not connecting",
            "userMessage": "My laptop cannot connect to office Wi-Fi.",
            "affectedService": "Wi-Fi",
        }
    )
    results = [
        make_result(
            "wifi-see-ssid",
            "user_unsure",
            "User is not sure which network name should appear.",
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence
    assert response.missing_evidence[0].step_id == "wifi-see-ssid"
    assert "not sure" in response.missing_evidence[0].reason.lower()


def test_generic_diagnosis_early_layer_failure_focuses_on_that_layer():
    ticket = make_ticket(
        {
            "title": "Office Wi-Fi not connecting",
            "userMessage": "My laptop cannot connect to office Wi-Fi.",
            "affectedService": "Wi-Fi",
        }
    )
    results = [
        make_result(
            "wifi-see-ssid",
            "no",
            "The office SSID does not appear on this laptop.",
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert "ssid" in response.current_likely_cause.cause.lower()
    assert response.next_best_actions[0] == response.next_best_action
    assert "office SSID" in response.current_likely_cause.reasoning
    assert response.escalation_recommendation.should_escalate is False


def test_generic_diagnosis_passed_checks_produce_ruled_out_causes():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "environmentContext": {
                "applicationPlatform": "vpn_client",
            },
        }
    )
    results = [
        make_result(
            "vpn-confirm-internet",
            "works",
            "Public websites open normally.",
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)
    ruled_out_causes = {item.cause for item in response.ruled_out_causes}

    assert "General internet connectivity issue" in ruled_out_causes


def test_generic_diagnosis_escalates_when_next_step_requires_privileged_access():
    ticket = make_ticket(
        {
            "title": "Internal app error",
            "userMessage": "The company portal shows an unexpected error after submit.",
            "affectedService": "Company Portal",
            "errorMessage": "Unexpected error",
            "environmentContext": {
                "applicationPlatform": "company_custom",
            },
        }
    )
    results = [
        make_result("application-error-scope", "works", "Only one user reported it."),
        make_result(
            "application-error-basic-retry",
            "works",
            "Retrying the submit action gives the same result.",
        ),
        make_result(
            "application-error-device-client",
            "works",
            "The same error appears in another browser.",
        ),
        make_result(
            "application-error-platform-permission",
            "no",
            "No known access or policy change.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.status.value == "ready_to_escalate"
    assert response.level1_can_continue is False
    assert "admin" in response.level1_blocker_reason.lower()
    assert "vendor" in response.level1_blocker_reason.lower()


def test_generic_failed_privileged_step_uses_metadata_escalation_reason():
    playbook = Playbook(
        issue_category=IssueCategory.APPLICATION_ERROR,
        subcategory="Privileged application",
        keywords=(),
        missing_information=(),
        possible_causes=(
            PlaybookCause(
                "Privileged application review required",
                "medium",
                "This synthetic playbook checks failed-step metadata.",
            ),
        ),
        checklist_steps=(
            PlaybookStep(
                id="privileged-log-review",
                layer=ChecklistGroup.DEVICE_CLIENT_APPLICATION,
                step="Review the application logs.",
                why="Log review requires access outside Level 1.",
                expected_result_type=ChecklistResultType.WORKS_DOES_NOT_WORK,
                fail_cause="Application logs require privileged review",
                requires_privileged_access=True,
                level1_actionable=False,
                access_requirement="Admin log access is required.",
                escalation_reason="Admin logs require escalation.",
            ),
        ),
        escalation_criteria=("Escalate when admin log access is required.",),
        interpretation_rules=("Do not claim logs were checked without evidence.",),
    )

    response = MockAIProvider()._generic_updated_diagnosis(
        playbook,
        [
            make_result(
                "privileged-log-review",
                "does_not_work",
                "Level 1 cannot access the application logs.",
            )
        ],
    )

    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    assert response.level1_blocker_reason == "Admin logs require escalation."
    assert response.escalation_recommendation.reason == "Admin logs require escalation."


def test_non_vpn_category_uses_generic_progressive_diagnosis():
    ticket = make_ticket(
        {
            "title": "Office Wi-Fi not connecting",
            "userMessage": "My laptop cannot connect to office Wi-Fi.",
            "affectedService": "Wi-Fi",
        }
    )
    results = [
        make_result("wifi-see-ssid", "yes", "The device sees the office SSID."),
        make_result(
            "wifi-other-devices",
            "yes",
            "Another laptop can connect to the same Wi-Fi.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert ChecklistGroup.SCOPE_IMPACT in response.completed_layers
    assert response.missing_evidence[0].step_id == "wifi-forget-profile"
    assert "wi-fi profile" in response.next_best_actions[0].lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_wifi_ticket_returns_network_wifi_category():
    ticket = make_ticket(
        {
            "title": "Office Wi-Fi not connecting",
            "userMessage": "My laptop cannot connect to office Wi-Fi.",
            "affectedService": "Wi-Fi",
            "deviceType": "Windows laptop",
            "environmentContext": {
                "operatingSystem": "windows",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)

    assert response.classification.category == IssueCategory.NETWORK_WIFI


def test_wifi_ticket_returns_wifi_specific_checklist_items():
    ticket = make_ticket(
        {
            "title": "Wireless network issue",
            "userMessage": "The device can see wireless but cannot connect to WiFi.",
            "affectedService": "Network",
            "deviceType": "Windows laptop",
            "environmentContext": {
                "operatingSystem": "windows",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    checklist_text = " ".join(item.step for item in response.checklist).lower()
    missing_questions = " ".join(
        item.question for item in response.missing_information
    ).lower()

    assert "ssid" in checklist_text
    assert "other devices" in checklist_text or "other users" in checklist_text
    assert "forget" in checklist_text and "wi-fi profile" in checklist_text
    assert "hotspot" in checklist_text
    assert "can the device see the wi-fi network" in missing_questions
    assert "multiple users" in " ".join(response.escalation_criteria).lower()


def test_network_drive_wording_does_not_classify_as_wifi():
    ticket = make_ticket(
        {
            "title": "Cannot access network drive",
            "userMessage": "The user cannot open a network folder from File Explorer.",
            "affectedService": "File share",
            "deviceType": "Windows laptop",
            "environmentContext": {
                "operatingSystem": "windows",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)

    assert response.classification.category != IssueCategory.NETWORK_WIFI


def make_file_access_ticket(overrides: dict | None = None) -> TicketInput:
    payload = {
        "title": "Shared folder access denied",
        "userMessage": (
            "The user cannot open a shared folder and sees access denied."
        ),
        "affectedService": "File share",
        "deviceType": "Windows laptop",
        "environmentContext": {
            "operatingSystem": "windows",
            "applicationPlatform": "microsoft_365",
        },
    }
    if overrides:
        payload.update(overrides)
    return make_ticket(payload)


def assert_no_fake_file_admin_claims(text: str) -> None:
    lowered = text.lower()
    forbidden_claims = (
        "acls were checked",
        "group membership was checked",
        "file server permissions were checked",
        "sharepoint admin settings were checked",
        "onedrive admin settings were checked",
        "m365 admin center was checked",
        "iam was checked",
        "admin portal was checked",
    )
    for claim in forbidden_claims:
        assert claim not in lowered


def test_file_access_no_evidence_starts_with_resource_scope():
    response = MockAIProvider().update_diagnosis(make_file_access_ticket(), [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "file-access-confirm-resource"
    assert "path" in response.next_best_actions[0].lower()
    assert "url" in response.next_best_actions[0].lower()
    assert response.level1_can_continue is True


def test_file_access_unsure_resource_creates_missing_evidence():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(),
        [
            make_result(
                "file-access-confirm-resource",
                "user_unsure",
                "The user is not sure whether this is SharePoint or a network drive.",
            )
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "file-access-confirm-resource"
    assert "sharepoint" in response.missing_evidence[0].reason.lower()
    assert "network drive" in response.missing_evidence[0].reason.lower()


def test_file_access_one_user_advances_into_level1_checks():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(),
        [
            make_result(
                "file-access-confirm-resource",
                "works",
                "The resource is a shared folder at \\\\fileserver\\finance.",
            ),
            make_result(
                "file-access-scope-error",
                "works",
                "Only one user sees access denied.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert response.missing_evidence[0].step_id == "file-access-previous-access"
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_file_access_multiple_users_suggests_shared_resource_escalation():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(
            {
                "title": "Multiple users cannot access shared folder",
                "userMessage": "Multiple users cannot access the same file share.",
                "affectedUsers": "multiple_users",
            }
        ),
        [
            make_result(
                "file-access-confirm-resource",
                "works",
                "The resource is a shared folder at \\\\fileserver\\finance.",
            ),
            make_result(
                "file-access-scope-error",
                "needs_escalation",
                "Several users cannot access the same shared resource.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert "shared" in response.current_likely_cause.cause.lower()
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False


def test_file_access_wrong_path_or_disconnected_vpn_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(
            {
                "title": "Network drive path not found",
                "userMessage": (
                    "The mapped network drive is unavailable while the user is remote."
                ),
            }
        ),
        [
            make_result(
                "file-access-confirm-resource",
                "works",
                "The user is opening mapped drive F: for \\\\fileserver\\finance.",
            ),
            make_result("file-access-scope-error", "works", "Only one user is affected."),
            make_result("file-access-previous-access", "no", "No confirmed prior access."),
            make_result(
                "file-access-path-network",
                "does_not_work",
                "The path is not reachable because the user is disconnected from VPN.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    likely_cause = response.current_likely_cause.cause.lower()
    assert "path" in likely_cause
    assert "vpn" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_file_access_permitted_user_comparison_moves_toward_permission_boundary():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(),
        [
            make_result(
                "file-access-confirm-resource",
                "works",
                "The resource is a SharePoint library URL.",
            ),
            make_result("file-access-scope-error", "works", "Only one user is affected."),
            make_result("file-access-previous-access", "no", "No confirmed prior access."),
            make_result("file-access-path-network", "works", "The URL is correct."),
            make_result(
                "file-access-known-permitted-user",
                "yes",
                "Another known permitted user can open the same resource.",
            ),
            make_result(
                "file-access-client-isolation",
                "does_not_work",
                "The affected user gets access denied in browser and Teams.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    assert response.missing_evidence[0].step_id == (
        "file-access-visible-permission-boundary"
    )
    assert response.level1_can_continue is True


def test_file_access_alternate_access_path_success_points_to_local_client_issue():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(),
        [
            make_result(
                "file-access-confirm-resource",
                "works",
                "The resource is a Teams file backed by SharePoint.",
            ),
            make_result("file-access-scope-error", "works", "Only one user is affected."),
            make_result("file-access-previous-access", "no", "No recent access change."),
            make_result("file-access-path-network", "works", "The URL is correct."),
            make_result(
                "file-access-known-permitted-user",
                "yes",
                "Another permitted user can access the file.",
            ),
            make_result(
                "file-access-client-isolation",
                "works",
                "The file opens in browser but not through the OneDrive sync client.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    likely_cause = response.current_likely_cause.cause.lower()
    assert "client" in likely_cause
    assert "sync" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_file_access_visible_permission_boundary_avoids_fake_admin_claims():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(),
        [
            make_result(
                "file-access-confirm-resource",
                "works",
                "The resource is a SharePoint library URL.",
            ),
            make_result("file-access-scope-error", "works", "Only one user is affected."),
            make_result("file-access-previous-access", "no", "No recent access change."),
            make_result("file-access-path-network", "works", "The URL is correct."),
            make_result(
                "file-access-known-permitted-user",
                "yes",
                "Another permitted user can open the same resource.",
            ),
            make_result(
                "file-access-client-isolation",
                "does_not_work",
                "The affected user gets the same visible message in browser and Teams.",
            ),
            make_result(
                "file-access-visible-permission-boundary",
                "user_unsure",
                "The user can see access denied but is unsure about request access, owner, lock, or sync details.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    assert "access denied" in diagnosis_text(response).lower()
    assert response.level1_can_continue is True
    assert_no_fake_file_admin_claims(diagnosis_text(response))


def test_file_access_safe_checks_pass_then_escalates_to_admin_review():
    response = MockAIProvider().update_diagnosis(
        make_file_access_ticket(),
        [
            make_result(
                "file-access-confirm-resource",
                "works",
                "The resource is a SharePoint folder URL.",
            ),
            make_result("file-access-scope-error", "works", "Only one user is affected."),
            make_result("file-access-previous-access", "no", "No recent access change."),
            make_result("file-access-path-network", "works", "The URL is correct."),
            make_result(
                "file-access-known-permitted-user",
                "yes",
                "Another permitted user can access the same folder.",
            ),
            make_result(
                "file-access-client-isolation",
                "does_not_work",
                "The affected user gets the same access denied message in browser and sync client.",
            ),
            make_result(
                "file-access-visible-permission-boundary",
                "works",
                "The visible message says request access from the folder owner.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.status.value == "ready_to_escalate"
    assert response.level1_can_continue is False
    escalation_actions = " ".join(response.next_best_actions).lower()
    assert "file admin" in escalation_actions
    assert "privileged review" in escalation_actions


def test_file_access_checklist_and_diagnosis_do_not_claim_admin_checks():
    ticket = make_file_access_ticket()
    triage = MockAIProvider().analyze_ticket(ticket)
    diagnosis = MockAIProvider().update_diagnosis(ticket, [])
    checklist_text = " ".join(
        " ".join(
            item
            for item in [
                checklist_item.step,
                checklist_item.why,
                checklist_item.evidence_prompt or "",
                checklist_item.access_requirement or "",
            ]
            if item
        )
        for checklist_item in triage.checklist
    )

    assert_no_fake_file_admin_claims(checklist_text)
    assert_no_fake_file_admin_claims(diagnosis_text(diagnosis))


@pytest.mark.parametrize(
    ("overrides", "expected_category"),
    [
        (
            {
                "title": "Office network switch has no internet",
                "userMessage": "Several desks in the small office cannot reach the internet.",
                "affectedService": "Office network",
                "affectedUsers": "multiple_users",
            },
            "small_office_network",
        ),
        (
            {
                "title": "Desk phone cannot make calls",
                "userMessage": "The VoIP phone has no dial tone and calls fail.",
                "affectedService": "Telephony",
            },
            "voip_telephony",
        ),
        (
            {
                "title": "Shared folder access denied",
                "userMessage": "The user cannot open a file share and sees permission denied.",
                "affectedService": "File share",
            },
            "file_access_permission",
        ),
        (
            {
                "title": "Laptop very slow after startup",
                "userMessage": "The device performance is poor and apps take minutes to open.",
                "affectedService": "Device",
            },
            "device_performance",
        ),
        (
            {
                "title": "USB headset not detected",
                "userMessage": "The hardware peripheral is plugged in but not recognized.",
                "affectedService": "Hardware",
            },
            "hardware_peripheral",
        ),
        (
            {
                "title": "Software update will not install",
                "userMessage": "The application installer fails during the update.",
                "affectedService": "Software installation",
            },
            "software_installation_update",
        ),
        (
            {
                "title": "Second monitor has no display",
                "userMessage": "The external monitor is connected but the display is blank.",
                "affectedService": "Monitor",
            },
            "display_monitor",
        ),
        (
            {
                "title": "Mobile hotspot will not connect",
                "userMessage": "The laptop cannot connect through the mobile hotspot.",
                "affectedService": "Hotspot",
            },
            "mobile_hotspot",
        ),
    ],
)
def test_playbooks_classify_broad_it_categories(overrides: dict, expected_category: str):
    ticket = make_ticket(overrides)

    response = MockAIProvider().analyze_ticket(ticket)
    groups = {item.group for item in response.checklist}

    assert response.classification.category.value == expected_category
    assert ChecklistGroup.SCOPE_IMPACT in groups
    assert ChecklistGroup.SIMPLE_USER_CHECKS in groups
    assert ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE in groups
    assert response.possible_causes
    assert response.escalation_criteria


def test_small_office_network_no_evidence_starts_with_scope():
    ticket = make_ticket(
        {
            "title": "Small office network outage",
            "userMessage": "The office network is not working.",
            "affectedService": "Office network",
            "affectedUsers": "unknown",
        }
    )

    response = MockAIProvider().update_diagnosis(ticket, [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "small-office-network-scope"
    assert "one device" in response.next_best_actions[0].lower()
    assert response.level1_can_continue is True


def test_small_office_network_single_laptop_continues_level1_device_checks():
    ticket = make_ticket(
        {
            "title": "One laptop cannot use office network",
            "userMessage": "One laptop cannot reach the office network but other devices work.",
            "affectedService": "Office network",
        }
    )
    results = [
        make_result(
            "small-office-network-scope",
            "works",
            "Only one laptop is affected; other devices work.",
        ),
        make_result(
            "small-office-network-network-path",
            "works",
            "The issue appears local to this laptop, not a Wi-Fi-only or wired-only outage.",
        ),
        make_result(
            "small-office-network-router-modem",
            "works",
            "Router and modem show online/service.",
        ),
        make_result(
            "small-office-network-switch-link",
            "works",
            "Visible switch power and link lights look normal.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert response.missing_evidence[0].step_id == "small-office-network-ip-address"
    assert "ip address" in response.next_best_actions[0].lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_small_office_network_multiple_wired_desks_escalates():
    ticket = make_ticket(
        {
            "title": "Several wired desks lost network",
            "userMessage": "Multiple wired desks in the small office lost network access.",
            "affectedService": "Office network",
            "affectedUsers": "multiple_users",
        }
    )
    results = [
        make_result(
            "small-office-network-scope",
            "needs_escalation",
            "Several wired desks are affected at the same time.",
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert "wider office network" in response.current_likely_cause.cause.lower()
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False


def test_small_office_network_no_valid_ip_points_to_dhcp_or_addressing():
    ticket = make_ticket(
        {
            "title": "Laptop has no office network",
            "userMessage": "One laptop cannot reach the LAN.",
            "affectedService": "Office network",
        }
    )
    results = [
        make_result("small-office-network-scope", "works", "One laptop only."),
        make_result(
            "small-office-network-network-path",
            "works",
            "No wider wired or Wi-Fi outage is reported.",
        ),
        make_result(
            "small-office-network-router-modem",
            "works",
            "Router and modem show online/service.",
        ),
        make_result(
            "small-office-network-switch-link",
            "works",
            "Visible link lights look normal.",
        ),
        make_result(
            "small-office-network-ip-address",
            "does_not_work",
            "The device has a 169.254 self-assigned address.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert "dhcp" in response.current_likely_cause.cause.lower()
    assert "address" in response.current_likely_cause.cause.lower()
    assert response.escalation_recommendation.should_escalate is False


def test_small_office_network_gateway_works_but_dns_fails_points_to_dns():
    ticket = make_ticket(
        {
            "title": "Office network DNS failure",
            "userMessage": "The laptop can reach the gateway but names do not resolve.",
            "affectedService": "Office network",
        }
    )
    results = [
        make_result("small-office-network-scope", "works", "One laptop only."),
        make_result("small-office-network-network-path", "works", "No wider outage."),
        make_result("small-office-network-router-modem", "works", "Internet status looks online."),
        make_result("small-office-network-switch-link", "works", "Link light is present."),
        make_result("small-office-network-ip-address", "works", "The device has a valid LAN IP."),
        make_result("small-office-network-gateway", "works", "The default gateway replies."),
        make_result(
            "small-office-network-dns",
            "does_not_work",
            "Gateway responds, but DNS name lookup fails.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert "dns" in response.current_likely_cause.cause.lower()
    assert "resolution" in response.next_best_action.lower()
    assert response.escalation_recommendation.should_escalate is False


def test_small_office_network_all_local_checks_pass_escalates_to_infrastructure():
    ticket = make_ticket(
        {
            "title": "Small office network still failing",
            "userMessage": "Level 1 checks did not find a local device issue.",
            "affectedService": "Office network",
        }
    )
    results = [
        make_result("small-office-network-scope", "works", "One device path is confirmed."),
        make_result("small-office-network-network-path", "works", "Network path is clarified."),
        make_result("small-office-network-router-modem", "works", "Router/modem appears online."),
        make_result("small-office-network-switch-link", "works", "Switch/link lights appear normal."),
        make_result("small-office-network-ip-address", "works", "Device has a valid IP."),
        make_result("small-office-network-gateway", "works", "Gateway replies."),
        make_result("small-office-network-dns", "works", "DNS resolves test names."),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    escalation_actions = " ".join(response.next_best_actions).lower()
    assert "isp" in escalation_actions
    assert "firewall" in escalation_actions


def test_voip_no_evidence_starts_with_scope():
    ticket = make_ticket(
        {
            "title": "Desk phone issue",
            "userMessage": "The desk phone cannot make calls.",
            "affectedService": "Telephony",
        }
    )

    response = MockAIProvider().update_diagnosis(ticket, [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "voip-scope"
    assert "one desk phone" in response.next_best_actions[0].lower()
    assert response.level1_can_continue is True


def test_voip_one_phone_no_power_points_to_poe_or_phone_power():
    ticket = make_ticket(
        {
            "title": "Desk phone has no power",
            "userMessage": "One VoIP desk phone will not turn on.",
            "affectedService": "Telephony",
        }
    )
    results = [
        make_result("voip-scope", "works", "Only one desk phone is affected."),
        make_result("voip-call-path", "works", "Only this phone is affected before calls start."),
        make_result("voip-power-poe", "does_not_work", "The phone has no power or boot screen."),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "poe" in response.current_likely_cause.cause.lower()
    assert "power" in response.current_likely_cause.cause.lower()
    assert response.escalation_recommendation.should_escalate is False


def test_voip_phone_link_but_no_ip_points_to_dhcp_or_voice_vlan():
    ticket = make_ticket(
        {
            "title": "Desk phone has network link but no IP",
            "userMessage": "The VoIP phone is connected but does not receive an IP address.",
            "affectedService": "Telephony",
        }
    )
    results = [
        make_result("voip-scope", "works", "Only one desk phone is affected."),
        make_result("voip-call-path", "works", "Calls cannot start from this phone."),
        make_result("voip-power-poe", "works", "The phone powers on."),
        make_result("voip-cable-link", "works", "Ethernet link light is present."),
        make_result("voip-ip-address", "does_not_work", "The phone does not receive an IP address."),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert "dhcp" in response.current_likely_cause.cause.lower()
    assert "vlan" in response.current_likely_cause.cause.lower()
    assert response.escalation_recommendation.should_escalate is False


def test_voip_phone_has_ip_but_not_registered_points_to_pbx_registration():
    ticket = make_ticket(
        {
            "title": "Desk phone not registered",
            "userMessage": "The VoIP phone has an IP address but says not registered.",
            "affectedService": "Telephony",
        }
    )
    results = [
        make_result("voip-scope", "works", "Only one desk phone is affected."),
        make_result("voip-call-path", "works", "Registration blocks all call paths."),
        make_result("voip-power-poe", "works", "The phone powers on."),
        make_result("voip-cable-link", "works", "Ethernet link is present."),
        make_result("voip-ip-address", "works", "The phone has a valid IP address."),
        make_result("voip-call-quality", "works", "No call quality symptom because calls do not start."),
        make_result("voip-registration", "no", "The phone display says not registered."),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    assert "pbx" in response.current_likely_cause.cause.lower()
    assert "registration" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True


def test_voip_multiple_phones_affected_escalates():
    ticket = make_ticket(
        {
            "title": "Multiple desk phones down",
            "userMessage": "Several desk phones cannot make calls.",
            "affectedService": "Telephony",
            "affectedUsers": "multiple_users",
        }
    )
    results = [
        make_result(
            "voip-scope",
            "needs_escalation",
            "Several desk phones are affected at the same time.",
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert "wider telephony" in response.current_likely_cause.cause.lower()
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False


def test_voip_call_quality_symptoms_point_to_jitter_qos_or_network_quality():
    ticket = make_ticket(
        {
            "title": "VoIP calls are choppy",
            "userMessage": "Calls have delay, choppy audio, and dropped words.",
            "affectedService": "Telephony",
        }
    )
    results = [
        make_result("voip-scope", "works", "One user reports the issue so far."),
        make_result("voip-call-path", "works", "External calls are affected."),
        make_result("voip-power-poe", "works", "The phone powers on normally."),
        make_result("voip-cable-link", "works", "Ethernet link is present."),
        make_result("voip-ip-address", "works", "The phone has a valid IP."),
        make_result(
            "voip-call-quality",
            "does_not_work",
            "Calls have delay, jitter, choppy audio, and dropped words.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert "jitter" in response.current_likely_cause.cause.lower()
    assert "qos" in response.current_likely_cause.cause.lower()
    assert response.escalation_recommendation.should_escalate is False


def test_unknown_issue_uses_general_it_playbook_without_guessing():
    ticket = make_ticket(
        {
            "title": "Something is acting weird",
            "userMessage": "The user says things are not working but has no clear details.",
            "affectedService": "Unknown",
            "deviceType": "Unknown",
            "location": "unknown",
            "affectedUsers": "unknown",
            "agentSelectedUrgency": "unknown",
            "businessImpact": "Unknown.",
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    checklist_by_id = {item.id: item for item in response.checklist}
    checklist_text = " ".join(item.step for item in response.checklist).lower()
    missing_questions = " ".join(
        item.question for item in response.missing_information
    ).lower()

    assert response.classification.category == IssueCategory.GENERAL_IT
    assert response.priority_assessment.priority.value == "unknown"
    assert "exact error" in missing_questions
    assert "what exactly is not working" in missing_questions
    assert "trying to do" in missing_questions
    assert "other users" in missing_questions
    assert "blocking work" in missing_questions
    assert "clarify what exactly is not working" in checklist_text
    assert "more information" in response.possible_causes[0].cause.lower()
    assert set(checklist_by_id) == {
        "general-capture-symptom",
        "general-scope",
        "general-recent-change",
        "general-issue-family",
        "general-device-app",
        "general-user-visible-boundary",
        "general-escalation",
    }
    capture_prompt = checklist_by_id["general-capture-symptom"].evidence_prompt.lower()
    scope_prompt = checklist_by_id["general-scope"].evidence_prompt.lower()
    issue_family = checklist_by_id["general-issue-family"]

    assert "exact wording" in capture_prompt
    assert "affected thing" in capture_prompt
    assert "attempted action" in capture_prompt
    assert "visible error or warning" in capture_prompt
    assert "when it started" in capture_prompt
    assert "only the user" in scope_prompt
    assert "other users" in scope_prompt
    assert "one device" in scope_prompt
    assert "one place" in scope_prompt
    assert "business workflow" in scope_prompt
    assert issue_family.group == ChecklistGroup.SIMPLE_USER_CHECKS
    assert issue_family.level1_actionable is True
    assert issue_family.requires_privileged_access is False
    assert "device" in issue_family.evidence_prompt.lower()
    assert "account" in issue_family.evidence_prompt.lower()
    assert "vendor" in issue_family.evidence_prompt.lower()


def test_general_it_diagnosis_with_no_evidence_asks_for_missing_information():
    ticket = make_ticket(
        {
            "title": "Unclear support issue",
            "userMessage": "The user needs help but did not provide symptoms.",
            "affectedService": "Unknown",
            "affectedUsers": "unknown",
            "agentSelectedUrgency": "unknown",
            "businessImpact": "Unknown.",
        }
    )

    response = MockAIProvider().update_diagnosis(ticket, [])

    assert response.current_likely_cause.cause == "More information needed"
    assert "scope_impact" in response.current_likely_cause.reasoning
    assert "missing information" in response.next_best_action.lower()
    assert response.escalation_recommendation.should_escalate is False
    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT


def test_general_it_user_unsure_returns_missing_evidence_prompt():
    ticket = make_ticket(
        {
            "title": "Unclear support issue",
            "userMessage": "The user cannot explain what is failing.",
            "affectedService": "Unknown",
            "affectedUsers": "unknown",
            "agentSelectedUrgency": "unknown",
            "businessImpact": "Unknown.",
        }
    )
    results = [
        make_result(
            "general-capture-symptom",
            "user_unsure",
            "The user is unsure which exact action fails.",
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "general-capture-symptom"
    question = response.missing_evidence[0].question.lower()
    assert "exact wording" in question
    assert "affected thing" in question
    assert "attempted action" in question


def test_general_it_safe_local_isolation_remains_level1_actionable():
    ticket = make_ticket(
        {
            "title": "Unknown app issue",
            "userMessage": "The user can describe the issue but the owner is unclear.",
            "affectedService": "Unknown",
        }
    )
    results = [
        make_result("general-capture-symptom", "works", "The submit button fails."),
        make_result("general-scope", "works", "One user on one laptop is affected."),
        make_result("general-recent-change", "works", "No recent change found."),
        make_result(
            "general-issue-family",
            "works",
            "Visible evidence points toward a browser or app path.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False
    assert "private window" in " ".join(response.next_best_actions).lower()


def test_general_it_escalates_after_local_evidence_reaches_owner_boundary():
    ticket = make_ticket(
        {
            "title": "Unknown business app issue",
            "userMessage": "The user can reproduce the issue but local checks pass.",
            "affectedService": "Unknown",
        }
    )
    results = [
        make_result("general-capture-symptom", "works", "Error appears on submit."),
        make_result("general-scope", "works", "One team workflow is affected."),
        make_result("general-recent-change", "works", "No recent change found."),
        make_result(
            "general-issue-family",
            "works",
            "Visible evidence suggests the owner is unclear.",
        ),
        make_result(
            "general-device-app",
            "does_not_work",
            "Same result after safe browser and device isolation checks.",
        ),
        make_result(
            "general-user-visible-boundary",
            "works",
            "User-facing message captured; no backend system was checked.",
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    assert response.current_troubleshooting_layer == (
        ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert "responsible owner" in " ".join(response.next_best_actions).lower()


def test_general_it_safe_steps_do_not_claim_privileged_systems_were_checked():
    ticket = make_ticket(
        {
            "title": "Something is acting weird",
            "userMessage": "The user says things are not working.",
            "affectedService": "Unknown",
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)

    for item in response.checklist:
        text = " ".join(
            [
                item.step,
                item.why,
                item.evidence_prompt or "",
            ]
        ).lower()
        if item.id == "general-escalation":
            continue
        assert item.level1_actionable is True
        assert item.requires_privileged_access is False
        assert "admin portal was checked" not in text
        assert "logs were checked" not in text
        assert "cloud console was checked" not in text
        assert "vendor dashboard was checked" not in text


def test_old_general_it_diagnosis_payload_still_validates():
    response = UpdatedDiagnosisResponse.model_validate(
        {
            "currentLikelyCause": {
                "cause": "More information needed",
                "confidence": "low",
                "reasoning": "Legacy payload without v1.5 additive fields.",
            },
            "ruledOutCauses": [],
            "evidenceSummary": ["No checklist evidence recorded yet."],
            "nextBestAction": "Collect missing information.",
            "escalationRecommendation": {
                "shouldEscalate": False,
                "reason": "Continue information gathering.",
            },
            "confidence": "low",
            "status": "in_progress",
        }
    )

    assert response.next_best_action == "Collect missing information."
    assert response.current_troubleshooting_layer is None
    assert response.next_best_actions == ["Collect missing information."]


def test_teams_macos_ticket_returns_macos_and_teams_checklist_wording():
    ticket = make_ticket(
        {
            "title": "Teams microphone not working",
            "userMessage": "People cannot hear me in Teams meetings.",
            "affectedService": "Microsoft Teams",
            "deviceType": "MacBook",
            "environmentContext": {
                "operatingSystem": "macos",
                "accountPlatform": "microsoft_365",
                "applicationPlatform": "microsoft_365",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    checklist_text = " ".join(item.step for item in response.checklist).lower()

    assert response.classification.category == IssueCategory.TEAMS_AUDIO_VIDEO
    assert "selected microphone" in checklist_text
    assert "macos microphone permission" in checklist_text
    assert "browser" in checklist_text and "desktop app" in checklist_text
    assert "another app" in checklist_text


def test_teams_windows_ticket_returns_windows_microphone_wording():
    ticket = make_ticket(
        {
            "title": "Teams microphone not working",
            "userMessage": "People cannot hear me in Teams meetings.",
            "affectedService": "Microsoft Teams",
            "deviceType": "Windows laptop",
            "environmentContext": {
                "operatingSystem": "windows",
                "accountPlatform": "microsoft_365",
                "applicationPlatform": "microsoft_365",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    checklist_text = " ".join(item.step for item in response.checklist).lower()

    assert response.classification.category == IssueCategory.TEAMS_AUDIO_VIDEO
    assert "windows microphone" in checklist_text
    assert "windows microphone privacy" in checklist_text


def make_teams_ticket(overrides: dict | None = None) -> TicketInput:
    payload = {
        "title": "Teams microphone not working",
        "userMessage": "People cannot hear me in Teams meetings.",
        "affectedService": "Microsoft Teams",
        "deviceType": "Windows laptop",
        "environmentContext": {
            "operatingSystem": "windows",
            "accountPlatform": "microsoft_365",
            "applicationPlatform": "microsoft_365",
        },
    }
    if overrides:
        payload.update(overrides)
    return make_ticket(payload)


def assert_no_fake_teams_admin_claims(text: str) -> None:
    lowered = text.lower()
    forbidden_claims = (
        "teams admin center was checked",
        "m365 admin center was checked",
        "microsoft 365 admin center was checked",
        "tenant policy was checked",
        "intune was checked",
        "device management was checked",
        "meeting room systems were checked",
        "teams logs were checked",
        "logs were checked",
        "hardware inventory was checked",
    )
    for claim in forbidden_claims:
        assert claim not in lowered


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "title": "Teams microphone not working",
            "userMessage": "Others cannot hear the user in Teams meetings.",
            "affectedService": "Microsoft Teams",
        },
        {
            "title": "Teams camera not working",
            "userMessage": "The camera is not detected in a Teams meeting.",
            "affectedService": "Microsoft Teams",
        },
        {
            "title": "Teams speaker audio issue",
            "userMessage": "The user cannot hear others in Teams.",
            "affectedService": "Microsoft Teams",
        },
        {
            "title": "Teams meeting audio issue",
            "userMessage": "Audio input and output fail during Teams meetings.",
            "affectedService": "Microsoft Teams",
        },
    ],
)
def test_teams_audio_video_classification_handles_common_av_symptoms(
    overrides: dict,
):
    response = MockAIProvider().analyze_ticket(make_teams_ticket(overrides))

    assert response.classification.category == IssueCategory.TEAMS_AUDIO_VIDEO


def test_teams_audio_video_checklist_uses_detailed_layered_progression():
    response = MockAIProvider().analyze_ticket(make_teams_ticket())
    checklist_by_id = {item.id: item for item in response.checklist}

    assert list(checklist_by_id) == [
        "teams-confirm-symptom",
        "teams-affected-scope",
        "teams-selected-device",
        "teams-other-app-comparison",
        "teams-browser-desktop-comparison",
        "teams-os-permission-device-setting",
        "teams-visible-policy-boundary",
        "teams-admin-desktop-review",
    ]
    assert checklist_by_id["teams-confirm-symptom"].group == ChecklistGroup.SCOPE_IMPACT
    assert checklist_by_id["teams-selected-device"].group == (
        ChecklistGroup.SIMPLE_USER_CHECKS
    )
    assert checklist_by_id["teams-other-app-comparison"].group == (
        ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert checklist_by_id["teams-os-permission-device-setting"].group == (
        ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert checklist_by_id["teams-visible-policy-boundary"].group == (
        ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    escalation_step = checklist_by_id["teams-admin-desktop-review"]
    assert escalation_step.group == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    assert escalation_step.level1_actionable is False
    assert escalation_step.requires_privileged_access is True
    access_text = escalation_step.access_requirement.lower()
    assert "teams admin" in access_text
    assert "m365" in access_text
    assert "desktop support" in access_text


def test_teams_audio_video_no_evidence_starts_with_scope_and_next_actions():
    response = MockAIProvider().update_diagnosis(make_teams_ticket(), [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "teams-confirm-symptom"
    assert "symptom" in response.next_best_actions[0].lower()
    assert "business impact" in response.next_best_actions[0].lower()
    assert 1 <= len(response.next_best_actions) <= 3
    assert response.next_best_actions[0] == response.next_best_action
    assert response.level1_can_continue is True


def test_teams_audio_video_user_unsure_creates_missing_evidence_prompt():
    response = MockAIProvider().update_diagnosis(
        make_teams_ticket(),
        [
            make_result(
                "teams-confirm-symptom",
                "user_unsure",
                "The user is unsure whether microphone, camera, or speaker is failing.",
            )
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "teams-confirm-symptom"
    assert "unsure" in response.missing_evidence[0].reason.lower()
    prompt = response.missing_evidence[0].question.lower()
    assert "microphone" in prompt
    assert "camera" in prompt
    assert "speaker" in prompt


def test_teams_selected_device_issue_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_teams_ticket(),
        [
            make_result(
                "teams-confirm-symptom",
                "works",
                "Others cannot hear the user.",
            ),
            make_result(
                "teams-affected-scope",
                "works",
                "One user and all meetings are affected.",
            ),
            make_result(
                "teams-selected-device",
                "no",
                "Teams is using the laptop microphone instead of the headset.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "selected" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_teams_os_permission_issue_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_teams_ticket(),
        [
            make_result("teams-confirm-symptom", "works", "Camera is not detected."),
            make_result("teams-affected-scope", "works", "Only one user is affected."),
            make_result("teams-selected-device", "yes", "Expected camera is selected."),
            make_result(
                "teams-other-app-comparison",
                "does_not_work",
                "Camera does not work in the Windows Camera app either.",
            ),
            make_result(
                "teams-browser-desktop-comparison",
                "does_not_work",
                "The same issue appears in browser and desktop.",
            ),
            make_result(
                "teams-os-permission-device-setting",
                "no",
                "Windows camera privacy permission is disabled for desktop apps.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    likely_cause = response.current_likely_cause.cause.lower()
    assert "permission" in likely_cause
    assert "device" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_teams_other_app_success_points_to_teams_client_settings_issue():
    response = MockAIProvider().update_diagnosis(
        make_teams_ticket(),
        [
            make_result("teams-confirm-symptom", "works", "Microphone fails in Teams."),
            make_result("teams-affected-scope", "works", "Only one user is affected."),
            make_result("teams-selected-device", "yes", "Expected headset microphone is selected."),
            make_result(
                "teams-other-app-comparison",
                "works",
                "The microphone works in Voice Recorder but not in Teams.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    likely_cause = response.current_likely_cause.cause.lower()
    assert "teams" in likely_cause
    assert "client" in likely_cause or "settings" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_teams_device_fails_all_apps_points_to_device_os_hardware_issue():
    response = MockAIProvider().update_diagnosis(
        make_teams_ticket(),
        [
            make_result("teams-confirm-symptom", "works", "Camera is not detected."),
            make_result("teams-affected-scope", "works", "Only one user is affected."),
            make_result("teams-selected-device", "yes", "Expected camera is selected."),
            make_result(
                "teams-other-app-comparison",
                "does_not_work",
                "Camera fails in Teams and in the Windows Camera app.",
            ),
            make_result(
                "teams-browser-desktop-comparison",
                "does_not_work",
                "Camera fails in browser and desktop.",
            ),
            make_result(
                "teams-os-permission-device-setting",
                "no",
                "The camera is not detected by Windows privacy/device settings.",
            ),
        ],
    )

    likely_cause = response.current_likely_cause.cause.lower()
    assert "device" in likely_cause
    assert "hardware" in likely_cause or "os" in likely_cause
    assert response.level1_can_continue is True


def test_teams_browser_success_points_to_desktop_client_issue():
    response = MockAIProvider().update_diagnosis(
        make_teams_ticket(),
        [
            make_result("teams-confirm-symptom", "works", "Speaker output fails in Teams desktop."),
            make_result("teams-affected-scope", "works", "Only one user is affected."),
            make_result("teams-selected-device", "yes", "Expected speaker is selected."),
            make_result(
                "teams-other-app-comparison",
                "does_not_work",
                "Other apps do not isolate the issue clearly.",
            ),
            make_result(
                "teams-browser-desktop-comparison",
                "works",
                "Teams browser audio works, but Teams desktop audio fails.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    likely_cause = response.current_likely_cause.cause.lower()
    assert "desktop" in likely_cause
    assert "client" in likely_cause or "cache" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_teams_local_checks_pass_then_escalates_at_admin_boundary():
    response = MockAIProvider().update_diagnosis(
        make_teams_ticket(),
        [
            make_result("teams-confirm-symptom", "works", "Microphone fails in all Teams meetings."),
            make_result("teams-affected-scope", "works", "Multiple users report the same meeting audio issue."),
            make_result("teams-selected-device", "yes", "Expected microphone and speaker are selected."),
            make_result(
                "teams-other-app-comparison",
                "does_not_work",
                "The symptom is not isolated by another app comparison.",
            ),
            make_result(
                "teams-browser-desktop-comparison",
                "does_not_work",
                "The same issue appears in Teams browser and desktop.",
            ),
            make_result(
                "teams-os-permission-device-setting",
                "yes",
                "OS microphone and camera permissions are enabled.",
            ),
            make_result(
                "teams-visible-policy-boundary",
                "works",
                "The visible Teams message says the meeting policy may block audio.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.status.value == "ready_to_escalate"
    assert response.level1_can_continue is False
    actions = " ".join(response.next_best_actions).lower()
    assert "teams admin" in actions
    assert "desktop support" in actions
    assert_no_fake_teams_admin_claims(diagnosis_text(response))


def test_teams_checklist_and_diagnosis_do_not_claim_admin_system_checks():
    ticket = make_teams_ticket()
    triage = MockAIProvider().analyze_ticket(ticket)
    diagnosis = MockAIProvider().update_diagnosis(ticket, [])
    checklist_text = " ".join(
        " ".join(
            item
            for item in [
                checklist_item.step,
                checklist_item.why,
                checklist_item.evidence_prompt or "",
                checklist_item.access_requirement or "",
            ]
            if item
        )
        for checklist_item in triage.checklist
    )

    assert_no_fake_teams_admin_claims(checklist_text)
    assert_no_fake_teams_admin_claims(diagnosis_text(diagnosis))


def test_teams_sign_in_issue_prefers_login_account_category():
    response = MockAIProvider().analyze_ticket(
        make_teams_ticket(
            {
                "title": "Cannot sign in to Teams",
                "userMessage": "The user cannot sign in to Teams because MFA approval fails.",
                "errorMessage": "MFA approval failed",
            }
        )
    )

    assert response.classification.category == IssueCategory.LOGIN_ACCOUNT


def test_outlook_email_issue_is_not_stolen_by_teams_audio_video():
    response = MockAIProvider().analyze_ticket(
        make_outlook_ticket(
            {
                "title": "Outlook email not received after Teams meeting",
                "userMessage": "The user did not receive an expected Outlook email after a Teams meeting.",
            }
        )
    )

    assert response.classification.category == IssueCategory.EMAIL_OUTLOOK


def test_meeting_room_display_projector_not_classified_as_teams_audio_video():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Meeting room projector display blank",
                "userMessage": "The meeting room display is blank when connected to the projector.",
                "affectedService": "Meeting room display",
                "deviceType": "Meeting room PC",
                "affectedUsers": "multiple_users",
            }
        )
    )

    assert response.classification.category == IssueCategory.DISPLAY_MONITOR


@pytest.mark.parametrize("account_platform", ["okta", "microsoft_365"])
def test_login_account_ticket_with_identity_platform_returns_login_category(
    account_platform: str,
):
    ticket = make_ticket(
        {
            "title": "User cannot sign in",
            "userMessage": "The user cannot sign in and may need MFA help.",
            "affectedService": "Account",
            "environmentContext": {
                "accountPlatform": account_platform,
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)

    assert response.classification.category == IssueCategory.LOGIN_ACCOUNT


def make_login_ticket(overrides: dict | None = None) -> TicketInput:
    payload = {
        "title": "User cannot sign in",
        "userMessage": "The user cannot sign in and may need MFA help.",
        "affectedService": "Account",
        "environmentContext": {
            "accountPlatform": "microsoft_365",
        },
    }
    if overrides:
        payload.update(overrides)
    return make_ticket(payload)


def assert_no_fake_identity_admin_claims(text: str) -> None:
    lowered = text.lower()
    forbidden_claims = (
        "sign-in logs were checked",
        "entra id was checked",
        "ad was checked",
        "okta was checked",
        "conditional access was checked",
        "licensing was checked",
        "admin portal was checked",
    )
    for claim in forbidden_claims:
        assert claim not in lowered


def diagnosis_text(response: UpdatedDiagnosisResponse) -> str:
    return " ".join(
        [
            response.current_likely_cause.cause,
            response.current_likely_cause.reasoning,
            response.next_best_action,
            " ".join(response.next_best_actions),
            response.escalation_recommendation.reason,
            response.level1_blocker_reason,
            " ".join(response.evidence_summary),
            " ".join(item.question for item in response.missing_evidence),
            " ".join(item.reason for item in response.missing_evidence),
        ]
    )


def make_outlook_ticket(overrides: dict | None = None) -> TicketInput:
    payload = {
        "title": "Outlook not receiving email",
        "userMessage": "The user has not received expected emails in Outlook today.",
        "affectedService": "Outlook",
        "environmentContext": {
            "accountPlatform": "microsoft_365",
            "applicationPlatform": "microsoft_365",
        },
    }
    if overrides:
        payload.update(overrides)
    return make_ticket(payload)


def assert_no_fake_email_admin_claims(text: str) -> None:
    lowered = text.lower()
    forbidden_claims = (
        "m365 admin center was checked",
        "microsoft 365 admin center was checked",
        "mail trace was checked",
        "quarantine was checked",
        "mailbox rules were checked",
        "exchange logs were checked",
        "entra id was checked",
        "tenant policy was checked",
    )
    for claim in forbidden_claims:
        assert claim not in lowered


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "title": "Outlook not receiving email",
            "userMessage": "Expected emails have not arrived in Outlook today.",
            "affectedService": "Outlook",
        },
        {
            "title": "Cannot send email",
            "userMessage": "Messages stay in the outbox and never send.",
            "affectedService": "Email",
        },
        {
            "title": "Outlook sync error",
            "userMessage": "Outlook shows a sync error and mail is not updating.",
            "affectedService": "Outlook",
        },
        {
            "title": "Shared mailbox access issue",
            "userMessage": "The user cannot open a shared mailbox in Outlook.",
            "affectedService": "Email",
        },
    ],
)
def test_outlook_email_classification_handles_common_mail_symptoms(
    overrides: dict,
):
    response = MockAIProvider().analyze_ticket(make_outlook_ticket(overrides))

    assert response.classification.category == IssueCategory.EMAIL_OUTLOOK


def test_outlook_email_checklist_uses_detailed_layered_progression():
    response = MockAIProvider().analyze_ticket(make_outlook_ticket())
    checklist_by_id = {item.id: item for item in response.checklist}

    assert list(checklist_by_id) == [
        "outlook-confirm-symptom",
        "outlook-affected-scope",
        "outlook-send-receive-direction",
        "outlook-recent-change",
        "outlook-client-webmail-comparison",
        "outlook-client-profile-outbox-sync",
        "outlook-visible-mailbox-boundary",
        "outlook-email-admin-review",
    ]
    assert checklist_by_id["outlook-confirm-symptom"].group == (
        ChecklistGroup.SCOPE_IMPACT
    )
    assert checklist_by_id["outlook-send-receive-direction"].group == (
        ChecklistGroup.SIMPLE_USER_CHECKS
    )
    assert checklist_by_id["outlook-client-webmail-comparison"].group == (
        ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert checklist_by_id["outlook-visible-mailbox-boundary"].group == (
        ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    escalation_step = checklist_by_id["outlook-email-admin-review"]
    assert escalation_step.group == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    assert escalation_step.level1_actionable is False
    assert escalation_step.requires_privileged_access is True
    assert "email" in escalation_step.access_requirement.lower()
    assert "m365" in escalation_step.access_requirement.lower()


def test_outlook_email_no_evidence_starts_with_scope_and_useful_next_actions():
    response = MockAIProvider().update_diagnosis(make_outlook_ticket(), [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "outlook-confirm-symptom"
    assert "symptom" in response.next_best_actions[0].lower()
    assert "business impact" in response.next_best_actions[0].lower()
    assert 1 <= len(response.next_best_actions) <= 3
    assert response.next_best_actions[0] == response.next_best_action
    assert response.level1_can_continue is True


def test_outlook_email_user_unsure_creates_missing_evidence_prompt():
    response = MockAIProvider().update_diagnosis(
        make_outlook_ticket(),
        [
            make_result(
                "outlook-confirm-symptom",
                "user_unsure",
                "The user is unsure whether sending, receiving, sync, or access is failing.",
            )
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "outlook-confirm-symptom"
    assert "unsure" in response.missing_evidence[0].reason.lower()
    assert "send" in response.missing_evidence[0].question.lower()
    assert "receive" in response.missing_evidence[0].question.lower()


def test_outlook_email_recent_change_keeps_level1_on_user_side_cause():
    response = MockAIProvider().update_diagnosis(
        make_outlook_ticket(),
        [
            make_result(
                "outlook-confirm-symptom",
                "works",
                "The symptom is email stuck in the outbox.",
            ),
            make_result(
                "outlook-affected-scope",
                "works",
                "Only one user and all recipients are affected.",
            ),
            make_result(
                "outlook-send-receive-direction",
                "works",
                "Sending is affected; receiving still works.",
            ),
            make_result(
                "outlook-recent-change",
                "yes",
                "The user changed password and Outlook profile settings this morning.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    likely_cause = response.current_likely_cause.cause.lower()
    assert "recent" in likely_cause
    assert "password" in likely_cause or "profile" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_outlook_email_webmail_success_points_to_desktop_client_issue():
    response = MockAIProvider().update_diagnosis(
        make_outlook_ticket(),
        [
            make_result("outlook-confirm-symptom", "works", "Outlook desktop is not syncing."),
            make_result("outlook-affected-scope", "works", "Only one user is affected."),
            make_result(
                "outlook-send-receive-direction",
                "works",
                "Receive and sync are affected in Outlook desktop.",
            ),
            make_result("outlook-recent-change", "no", "No recent password or device change."),
            make_result(
                "outlook-client-webmail-comparison",
                "works",
                "Webmail shows current mail but Outlook desktop does not sync.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    likely_cause = response.current_likely_cause.cause.lower()
    assert "outlook desktop" in likely_cause
    assert "client" in likely_cause or "profile" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_outlook_email_mailbox_boundary_escalates_without_fake_admin_claims():
    response = MockAIProvider().update_diagnosis(
        make_outlook_ticket(),
        [
            make_result("outlook-confirm-symptom", "works", "The mailbox cannot receive mail."),
            make_result(
                "outlook-affected-scope",
                "works",
                "One user is affected and all senders are impacted.",
            ),
            make_result(
                "outlook-send-receive-direction",
                "works",
                "Receiving is affected for all senders.",
            ),
            make_result("outlook-recent-change", "no", "No recent user-side change."),
            make_result(
                "outlook-client-webmail-comparison",
                "does_not_work",
                "Webmail also does not show the expected messages.",
            ),
            make_result(
                "outlook-client-profile-outbox-sync",
                "works",
                "The same receive problem appears outside the desktop profile.",
            ),
            make_result(
                "outlook-visible-mailbox-boundary",
                "works",
                "The user-visible message suggests mailbox access or delivery review is needed.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.status.value == "ready_to_escalate"
    assert response.level1_can_continue is False
    assert "email" in " ".join(response.next_best_actions).lower()
    assert "m365" in " ".join(response.next_best_actions).lower()
    assert_no_fake_email_admin_claims(diagnosis_text(response))


def test_outlook_email_checklist_and_diagnosis_do_not_claim_admin_system_checks():
    ticket = make_outlook_ticket()
    triage = MockAIProvider().analyze_ticket(ticket)
    diagnosis = MockAIProvider().update_diagnosis(ticket, [])
    checklist_text = " ".join(
        " ".join(
            item
            for item in [
                checklist_item.step,
                checklist_item.why,
                checklist_item.evidence_prompt or "",
                checklist_item.access_requirement or "",
            ]
            if item
        )
        for checklist_item in triage.checklist
    )

    assert_no_fake_email_admin_claims(checklist_text)
    assert_no_fake_email_admin_claims(diagnosis_text(diagnosis))


def test_outlook_login_issue_prefers_login_account_category():
    response = MockAIProvider().analyze_ticket(
        make_outlook_ticket(
            {
                "title": "Cannot sign in to Outlook",
                "userMessage": "The user cannot sign in to Outlook because MFA approval fails.",
                "affectedService": "Email",
                "errorMessage": "MFA approval failed",
            }
        )
    )

    assert response.classification.category == IssueCategory.LOGIN_ACCOUNT


def test_teams_file_access_is_not_stolen_by_teams_audio_video():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Cannot access Teams file",
                "userMessage": "The user gets access denied opening a Teams file.",
                "affectedService": "Microsoft Teams",
                "environmentContext": {
                    "accountPlatform": "microsoft_365",
                    "applicationPlatform": "microsoft_365",
                },
            }
        )
    )

    assert response.classification.category == IssueCategory.FILE_ACCESS_PERMISSION


def test_login_account_no_evidence_starts_with_platform_scope():
    response = MockAIProvider().update_diagnosis(make_login_ticket(), [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "login-confirm-platform"
    assert "platform" in response.next_best_actions[0].lower()
    assert "account type" in response.next_best_actions[0].lower()
    assert response.level1_can_continue is True


def test_login_account_unsure_platform_creates_missing_evidence():
    response = MockAIProvider().update_diagnosis(
        make_login_ticket(),
        [
            make_result(
                "login-confirm-platform",
                "user_unsure",
                "The user is not sure whether this is Microsoft 365 or Okta.",
            )
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "login-confirm-platform"
    assert "microsoft 365" in response.missing_evidence[0].reason.lower()


def test_login_account_recent_password_change_points_to_saved_credential_issue():
    response = MockAIProvider().update_diagnosis(
        make_login_ticket(),
        [
            make_result(
                "login-confirm-platform",
                "works",
                "The user is signing in to Microsoft 365 webmail.",
            ),
            make_result(
                "login-confirm-scope-error",
                "works",
                "Only one user sees incorrect password after a reset.",
            ),
            make_result(
                "login-recent-password-change",
                "yes",
                "The password was reset this morning and the app may have saved the old password.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "password" in response.current_likely_cause.cause.lower()
    assert "credential" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_login_account_mfa_failure_points_to_user_visible_mfa_issue():
    response = MockAIProvider().update_diagnosis(
        make_login_ticket(),
        [
            make_result("login-confirm-platform", "works", "The app is Microsoft 365."),
            make_result(
                "login-confirm-scope-error",
                "works",
                "Only one user is affected and MFA approval fails.",
            ),
            make_result(
                "login-recent-password-change",
                "no",
                "No recent password change.",
            ),
            make_result(
                "login-mfa-behavior",
                "does_not_work",
                "MFA prompt appears but number matching fails after the user changed phones.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "mfa" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_login_account_alternate_browser_success_points_to_client_issue():
    response = MockAIProvider().update_diagnosis(
        make_login_ticket(),
        [
            make_result("login-confirm-platform", "works", "The app is Microsoft 365."),
            make_result("login-confirm-scope-error", "works", "Only one user is affected."),
            make_result("login-recent-password-change", "no", "No recent password change."),
            make_result("login-mfa-behavior", "works", "MFA prompt and approval work."),
            make_result(
                "login-browser-device-isolation",
                "works",
                "Sign-in works in a private window but not the regular browser profile.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert "browser" in response.current_likely_cause.cause.lower()
    assert "client" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_login_account_visible_account_boundary_hands_off_without_fake_admin_claims():
    response = MockAIProvider().update_diagnosis(
        make_login_ticket(),
        [
            make_result("login-confirm-platform", "works", "The app is Microsoft 365."),
            make_result(
                "login-confirm-scope-error",
                "works",
                "Only one user sees account locked after sign-in.",
            ),
            make_result("login-recent-password-change", "no", "No recent password change."),
            make_result("login-mfa-behavior", "works", "MFA prompt and approval work."),
            make_result(
                "login-browser-device-isolation",
                "does_not_work",
                "The same account locked message appears in another browser.",
            ),
            make_result(
                "login-visible-account-boundary",
                "works",
                "The visible message says account locked and access denied.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert "account locked" in " ".join(response.evidence_summary).lower()
    assert_no_fake_identity_admin_claims(diagnosis_text(response))


def test_login_account_safe_checks_pass_then_escalates_to_identity_admin_review():
    response = MockAIProvider().update_diagnosis(
        make_login_ticket(),
        [
            make_result("login-confirm-platform", "works", "The app is Microsoft 365."),
            make_result("login-confirm-scope-error", "works", "Only one user is affected."),
            make_result("login-recent-password-change", "no", "No recent password change."),
            make_result("login-mfa-behavior", "works", "MFA prompt and approval work."),
            make_result(
                "login-browser-device-isolation",
                "does_not_work",
                "The sign-in failure is the same in another browser and device.",
            ),
            make_result(
                "login-visible-account-boundary",
                "works",
                "The visible message says license required.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.status.value == "ready_to_escalate"
    assert response.level1_can_continue is False
    escalation_actions = " ".join(response.next_best_actions).lower()
    assert "identity admin" in escalation_actions
    assert "privileged review" in escalation_actions


def test_login_account_escalation_step_has_identity_privileged_metadata():
    ticket = make_login_ticket()
    response = MockAIProvider().analyze_ticket(ticket)
    checklist_by_id = {item.id: item for item in response.checklist}

    escalation_step = checklist_by_id["login-identity-admin-review"]

    assert escalation_step.group == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    assert escalation_step.level1_actionable is False
    assert escalation_step.requires_privileged_access is True
    assert "identity admin" in escalation_step.access_requirement.lower()
    assert "iam" in escalation_step.access_requirement.lower()
    assert "service desk" in escalation_step.access_requirement.lower()


def test_login_account_checklist_and_diagnosis_do_not_claim_identity_admin_checks():
    ticket = make_login_ticket()
    triage = MockAIProvider().analyze_ticket(ticket)
    diagnosis = MockAIProvider().update_diagnosis(ticket, [])
    checklist_text = " ".join(
        " ".join(
            item
            for item in [
                checklist_item.step,
                checklist_item.why,
                checklist_item.evidence_prompt or "",
                checklist_item.access_requirement or "",
            ]
            if item
        )
        for checklist_item in triage.checklist
    )

    assert_no_fake_identity_admin_claims(checklist_text)
    assert_no_fake_identity_admin_claims(diagnosis_text(diagnosis))


def make_printer_scanner_ticket(overrides: dict | None = None) -> TicketInput:
    payload = {
        "title": "Cannot print to office printer",
        "userMessage": "The user sent a document to the office printer but nothing printed.",
        "affectedService": "Printer",
        "environmentContext": {
            "applicationPlatform": "printer_system",
        },
    }
    if overrides:
        payload.update(overrides)
    return make_ticket(payload)


def assert_no_fake_print_admin_claims(text: str) -> None:
    lowered = text.lower()
    forbidden_claims = (
        "print server was checked",
        "print servers were checked",
        "printer admin portal was checked",
        "mfd admin panel was checked",
        "driver deployment systems were checked",
        "intune was checked",
        "mdm was checked",
        "windows print server logs were checked",
        "spooler logs were checked",
        "scanner shares were checked",
        "scanner share was checked",
        "mailbox scan settings were checked",
        "device inventory was checked",
    )
    for claim in forbidden_claims:
        assert claim not in lowered


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "title": "Cannot print to office printer",
            "userMessage": "The print job never comes out.",
            "affectedService": "Printer",
        },
        {
            "title": "Printer offline",
            "userMessage": "The office printer shows offline.",
            "affectedService": "Printer",
        },
        {
            "title": "Print job stuck",
            "userMessage": "The document is stuck in the local print queue.",
            "affectedService": "Printer",
        },
        {
            "title": "Scanner not working",
            "userMessage": "The scanner on the office MFD is not working.",
            "affectedService": "Scanner",
        },
        {
            "title": "Scan to email fails",
            "userMessage": "The MFD scan-to-email workflow fails for the user.",
            "affectedService": "Scanner",
        },
        {
            "title": "Scan to folder fails",
            "userMessage": "The scanner cannot scan to the shared folder destination.",
            "affectedService": "Scanner",
        },
    ],
)
def test_printer_scanner_classification_handles_common_symptoms(overrides: dict):
    response = MockAIProvider().analyze_ticket(make_printer_scanner_ticket(overrides))

    assert response.classification.category == IssueCategory.PRINTER


def test_printer_scanner_checklist_uses_detailed_layered_progression():
    response = MockAIProvider().analyze_ticket(make_printer_scanner_ticket())
    checklist_by_id = {item.id: item for item in response.checklist}

    assert list(checklist_by_id) == [
        "printer-confirm-symptom",
        "printer-affected-scope",
        "printer-selected-device-destination",
        "printer-visible-device-status",
        "printer-local-queue-client",
        "printer-known-working-comparison",
        "printer-visible-platform-boundary",
        "printer-admin-vendor-review",
    ]
    assert checklist_by_id["printer-confirm-symptom"].group == ChecklistGroup.SCOPE_IMPACT
    assert checklist_by_id["printer-selected-device-destination"].group == (
        ChecklistGroup.SIMPLE_USER_CHECKS
    )
    assert checklist_by_id["printer-local-queue-client"].group == (
        ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert checklist_by_id["printer-visible-platform-boundary"].group == (
        ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    escalation_step = checklist_by_id["printer-admin-vendor-review"]
    assert escalation_step.group == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    assert escalation_step.level1_actionable is False
    assert escalation_step.requires_privileged_access is True
    access_text = escalation_step.access_requirement.lower()
    assert "desktop support" in access_text
    assert "print team" in access_text
    assert "mfd vendor" in access_text


def test_printer_scanner_no_evidence_starts_with_scope_and_next_actions():
    response = MockAIProvider().update_diagnosis(make_printer_scanner_ticket(), [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "printer-confirm-symptom"
    assert "symptom" in response.next_best_actions[0].lower()
    assert "business impact" in response.next_best_actions[0].lower()
    assert 1 <= len(response.next_best_actions) <= 3
    assert response.next_best_actions[0] == response.next_best_action
    assert response.level1_can_continue is True


def test_printer_scanner_user_unsure_creates_missing_evidence_prompt():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(),
        [
            make_result(
                "printer-confirm-symptom",
                "user_unsure",
                "The user is unsure whether print, scan, or scan-to-email is failing.",
            )
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "printer-confirm-symptom"
    assert "unsure" in response.missing_evidence[0].reason.lower()
    prompt = response.missing_evidence[0].question.lower()
    assert "print" in prompt
    assert "scan" in prompt


def test_printer_wrong_selected_device_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(),
        [
            make_result("printer-confirm-symptom", "works", "The user cannot print."),
            make_result("printer-affected-scope", "works", "Only one user is affected."),
            make_result(
                "printer-selected-device-destination",
                "no",
                "The user selected a stale printer queue instead of the office MFD.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "selected" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_printer_visible_offline_paper_toner_jam_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(),
        [
            make_result("printer-confirm-symptom", "works", "The user cannot print."),
            make_result("printer-affected-scope", "works", "Only one user is affected."),
            make_result(
                "printer-selected-device-destination",
                "yes",
                "The selected printer is correct.",
            ),
            make_result(
                "printer-visible-device-status",
                "no",
                "The printer display shows paper jam and toner low.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    likely_cause = response.current_likely_cause.cause.lower()
    assert "paper" in likely_cause or "toner" in likely_cause or "jam" in likely_cause
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_printer_stuck_local_queue_points_to_local_device_client_issue():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(),
        [
            make_result("printer-confirm-symptom", "works", "The user cannot print."),
            make_result("printer-affected-scope", "works", "Only one user is affected."),
            make_result("printer-selected-device-destination", "yes", "The selected printer is correct."),
            make_result("printer-visible-device-status", "yes", "The printer is online and ready."),
            make_result(
                "printer-local-queue-client",
                "yes",
                "The print job is stuck in this laptop's local print queue.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    likely_cause = response.current_likely_cause.cause.lower()
    assert "local" in likely_cause
    assert "queue" in likely_cause
    assert response.level1_can_continue is True


def test_printer_other_users_can_print_points_to_local_user_device_path():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(),
        [
            make_result("printer-confirm-symptom", "works", "The user cannot print."),
            make_result("printer-affected-scope", "works", "Only one user is affected."),
            make_result("printer-selected-device-destination", "yes", "The selected printer is correct."),
            make_result("printer-visible-device-status", "yes", "The printer is online and ready."),
            make_result("printer-local-queue-client", "no", "No local queue blockage is visible."),
            make_result(
                "printer-known-working-comparison",
                "yes",
                "Another user can print to the same printer from another laptop.",
            ),
        ],
    )

    likely_cause = response.current_likely_cause.cause.lower()
    assert "local" in likely_cause
    assert "user" in likely_cause or "device" in likely_cause
    assert response.level1_can_continue is True


def test_printer_multiple_users_cannot_print_points_to_shared_print_impact():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(
            {
                "title": "Multiple users cannot print to office printer",
                "userMessage": "Multiple users cannot print to the same office printer.",
                "affectedUsers": "multiple_users",
            }
        ),
        [
            make_result("printer-confirm-symptom", "works", "Printing fails."),
            make_result(
                "printer-affected-scope",
                "needs_escalation",
                "Multiple users cannot print to the same shared printer.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    likely_cause = response.current_likely_cause.cause.lower()
    assert "shared" in likely_cause
    assert "print" in likely_cause
    assert response.escalation_recommendation.should_escalate is True


def test_scanner_destination_failure_points_to_platform_boundary():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(
            {
                "title": "Scan to email fails",
                "userMessage": "The scanner works locally but scan-to-email fails.",
                "affectedService": "Scanner",
            }
        ),
        [
            make_result("printer-confirm-symptom", "works", "Scan-to-email fails."),
            make_result("printer-affected-scope", "works", "Only one user is affected."),
            make_result(
                "printer-selected-device-destination",
                "yes",
                "The correct MFD and email destination are selected.",
            ),
            make_result("printer-visible-device-status", "yes", "The MFD is online and ready."),
            make_result("printer-local-queue-client", "no", "No local print queue issue applies."),
            make_result(
                "printer-known-working-comparison",
                "no",
                "Local copy and scan preview work, but scan-to-email does not arrive.",
            ),
            make_result(
                "printer-visible-platform-boundary",
                "works",
                "The MFD shows scan destination failed for email delivery.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    likely_cause = response.current_likely_cause.cause.lower()
    assert "scan" in likely_cause
    assert "destination" in likely_cause or "platform" in likely_cause
    assert response.level1_can_continue is True


def test_printer_safe_local_checks_pass_then_escalates_to_admin_boundary():
    response = MockAIProvider().update_diagnosis(
        make_printer_scanner_ticket(),
        [
            make_result("printer-confirm-symptom", "works", "Printing fails."),
            make_result("printer-affected-scope", "works", "Only one user is affected."),
            make_result("printer-selected-device-destination", "yes", "The selected printer is correct."),
            make_result("printer-visible-device-status", "yes", "The printer is online and ready."),
            make_result("printer-local-queue-client", "no", "No local queue blockage is visible."),
            make_result(
                "printer-known-working-comparison",
                "no",
                "No known working comparison is available and the issue remains.",
            ),
            make_result(
                "printer-visible-platform-boundary",
                "does_not_work",
                "No additional user-visible error is available after safe checks.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.status.value == "ready_to_escalate"
    assert response.level1_can_continue is False
    actions = " ".join(response.next_best_actions).lower()
    assert "desktop support" in actions
    assert "print team" in actions
    assert_no_fake_print_admin_claims(diagnosis_text(response))


def test_printer_checklist_and_diagnosis_do_not_claim_admin_system_checks():
    ticket = make_printer_scanner_ticket()
    triage = MockAIProvider().analyze_ticket(ticket)
    diagnosis = MockAIProvider().update_diagnosis(ticket, [])
    checklist_text = " ".join(
        " ".join(
            item
            for item in [
                checklist_item.step,
                checklist_item.why,
                checklist_item.evidence_prompt or "",
                checklist_item.access_requirement or "",
            ]
            if item
        )
        for checklist_item in triage.checklist
    )

    assert_no_fake_print_admin_claims(checklist_text)
    assert_no_fake_print_admin_claims(diagnosis_text(diagnosis))


def test_printer_wording_does_not_steal_generic_hardware_peripheral_issue():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "USB headset not detected",
                "userMessage": "The hardware peripheral is plugged in but not recognized.",
                "affectedService": "Hardware",
            }
        )
    )

    assert response.classification.category == IssueCategory.HARDWARE_PERIPHERAL


def test_outlook_email_delivery_not_stolen_by_scan_to_email_mention():
    response = MockAIProvider().analyze_ticket(
        make_outlook_ticket(
            {
                "title": "Outlook email not received",
                "userMessage": (
                    "The user did not receive an expected Outlook email; "
                    "someone incorrectly mentioned scan-to-email."
                ),
            }
        )
    )

    assert response.classification.category == IssueCategory.EMAIL_OUTLOOK


def test_file_share_access_not_stolen_unless_scan_to_folder_is_dominant():
    response = MockAIProvider().analyze_ticket(
        make_file_access_ticket(
            {
                "title": "Shared folder access denied",
                "userMessage": (
                    "The user cannot open a shared folder. This is not a "
                    "scanner scan-to-folder issue."
                ),
            }
        )
    )

    assert response.classification.category == IssueCategory.FILE_ACCESS_PERMISSION


def test_display_projector_issue_remains_display_monitor():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Projector display is blank",
                "userMessage": "The meeting room projector display is blank.",
                "affectedService": "Projector",
                "deviceType": "Projector",
            }
        )
    )

    assert response.classification.category == IssueCategory.DISPLAY_MONITOR


def make_display_ticket(overrides: dict | None = None) -> TicketInput:
    payload = {
        "title": "External monitor is blank",
        "userMessage": "The user's external monitor is connected but shows no signal.",
        "affectedService": "External monitor",
        "deviceType": "Windows laptop",
    }
    if overrides:
        payload.update(overrides)
    return make_ticket(payload)


def assert_no_fake_display_admin_claims(text: str) -> None:
    lowered = text.lower()
    forbidden_claims = (
        "intune was checked",
        "mdm was checked",
        "hardware diagnostics were checked",
        "driver deployment tools were checked",
        "driver deployment system was checked",
        "firmware tools were checked",
        "av systems were checked",
        "av system was checked",
        "logs were checked",
        "device inventory was checked",
        "vendor systems were checked",
        "vendor system was checked",
    )
    for claim in forbidden_claims:
        assert claim not in lowered


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "title": "External monitor is blank",
            "userMessage": "The external monitor is connected but the screen is blank.",
            "affectedService": "Monitor",
        },
        {
            "title": "Docking station display issue",
            "userMessage": "The dock does not detect the external display over USB-C.",
            "affectedService": "Docking station",
        },
        {
            "title": "Projector no signal",
            "userMessage": "The meeting room projector shows no signal over HDMI.",
            "affectedService": "Projector",
            "deviceType": "Projector",
        },
    ],
)
def test_display_monitor_classification_handles_common_symptoms(overrides: dict):
    response = MockAIProvider().analyze_ticket(make_display_ticket(overrides))

    assert response.classification.category == IssueCategory.DISPLAY_MONITOR


def test_display_monitor_checklist_uses_detailed_layered_progression():
    response = MockAIProvider().analyze_ticket(make_display_ticket())
    checklist_by_id = {item.id: item for item in response.checklist}

    assert list(checklist_by_id) == [
        "display-confirm-symptom",
        "display-affected-path",
        "display-affected-scope",
        "display-power-input-cable",
        "display-layout-resolution",
        "display-direct-dock-comparison",
        "display-known-good-comparison",
        "display-visible-boundary",
        "display-admin-vendor-review",
    ]
    assert checklist_by_id["display-confirm-symptom"].group == ChecklistGroup.SCOPE_IMPACT
    assert checklist_by_id["display-power-input-cable"].group == ChecklistGroup.SIMPLE_USER_CHECKS
    assert (
        checklist_by_id["display-direct-dock-comparison"].group
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert (
        checklist_by_id["display-visible-boundary"].group
        == ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    assert (
        checklist_by_id["display-admin-vendor-review"].group
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert checklist_by_id["display-admin-vendor-review"].requires_privileged_access is True
    assert checklist_by_id["display-admin-vendor-review"].level1_actionable is False


def test_display_monitor_no_evidence_starts_with_scope_and_next_actions():
    response = MockAIProvider().update_diagnosis(make_display_ticket(), [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "display-confirm-symptom"
    assert "symptom" in response.next_best_actions[0].lower()
    assert "business impact" in response.next_best_actions[0].lower()
    assert 1 <= len(response.next_best_actions) <= 3
    assert response.next_best_actions[0] == response.next_best_action
    assert response.level1_can_continue is True


def test_display_monitor_user_unsure_creates_missing_evidence_prompt():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(),
        [
            make_result(
                "display-confirm-symptom",
                "user_unsure",
                "The user is unsure whether the laptop screen, external monitor, dock, or projector is affected.",
            )
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence
    assert response.missing_evidence[0].step_id == "display-confirm-symptom"
    assert "laptop screen" in response.missing_evidence[0].reason.lower()
    assert response.level1_can_continue is True


def test_display_wrong_input_source_or_cable_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(),
        [
            make_result("display-confirm-symptom", "works", "The external monitor is blank."),
            make_result("display-affected-path", "works", "The external monitor path is affected."),
            make_result("display-affected-scope", "works", "Only one desk is affected."),
            make_result(
                "display-power-input-cable",
                "no",
                "The monitor is on HDMI 2 while the laptop is connected to HDMI 1.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "input" in response.current_likely_cause.cause.lower()
    assert "cable" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_display_layout_resolution_issue_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(),
        [
            make_result("display-confirm-symptom", "works", "The monitor displays the wrong layout."),
            make_result("display-affected-path", "works", "External monitor path is affected."),
            make_result("display-affected-scope", "works", "Only one user is affected."),
            make_result("display-power-input-cable", "yes", "Power, input, and cable look correct."),
            make_result(
                "display-layout-resolution",
                "does_not_work",
                "Windows is set to duplicate when the user expects extend, and scaling is wrong.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    assert "duplicate" in response.current_likely_cause.cause.lower()
    assert "resolution" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_display_direct_laptop_works_but_dock_fails_points_to_dock_path():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(
            {
                "title": "Docking station display issue",
                "userMessage": "The monitor works direct to laptop but fails through the dock.",
                "affectedService": "Docking station",
            }
        ),
        [
            make_result("display-confirm-symptom", "works", "External display is blank through dock."),
            make_result("display-affected-path", "works", "Dock path is affected."),
            make_result("display-affected-scope", "works", "Only one desk is affected."),
            make_result("display-power-input-cable", "yes", "Power, input, and cable look correct."),
            make_result("display-layout-resolution", "works", "Display settings are visible and correct."),
            make_result(
                "display-direct-dock-comparison",
                "works",
                "Direct laptop connection works, but the same display fails through the dock.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    assert "dock" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True


def test_display_known_good_comparison_isolates_local_path():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(),
        [
            make_result("display-confirm-symptom", "works", "External monitor flickers."),
            make_result("display-affected-path", "works", "External monitor path is affected."),
            make_result("display-affected-scope", "works", "Only one device is affected."),
            make_result("display-power-input-cable", "yes", "Power, input, and cable look correct."),
            make_result("display-layout-resolution", "works", "Display settings look correct."),
            make_result("display-direct-dock-comparison", "does_not_work", "Direct versus dock does not isolate it."),
            make_result(
                "display-known-good-comparison",
                "works",
                "Another HDMI cable and another monitor work from the same laptop.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    assert "cable" in response.current_likely_cause.cause.lower()
    assert "display" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True


def test_display_multiple_users_or_same_room_failure_reaches_escalation_boundary():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(
            {
                "title": "Meeting room projector no signal for everyone",
                "userMessage": "Multiple users see no signal on the same meeting room projector.",
                "affectedService": "Projector",
                "affectedUsers": "multiple_users",
            }
        ),
        [
            make_result("display-confirm-symptom", "works", "Projector shows no signal."),
            make_result("display-affected-path", "works", "Meeting room projector path is affected."),
            make_result(
                "display-affected-scope",
                "needs_escalation",
                "Multiple users fail on the same room display.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    assert "multiple users" in response.current_likely_cause.cause.lower()


def test_display_safe_local_checks_pass_then_escalates_to_admin_boundary():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(),
        [
            make_result("display-confirm-symptom", "works", "External monitor is blank."),
            make_result("display-affected-path", "works", "External monitor path is affected."),
            make_result("display-affected-scope", "works", "Only one user is affected."),
            make_result("display-power-input-cable", "yes", "Power, input, cable, and adapter look correct."),
            make_result("display-layout-resolution", "works", "Duplicate, extend, resolution, and scaling look correct."),
            make_result("display-direct-dock-comparison", "does_not_work", "Direct and dock paths both fail."),
            make_result("display-known-good-comparison", "does_not_work", "Known-good cable, port, and display do not isolate it."),
            make_result(
                "display-visible-boundary",
                "works",
                "Visible evidence suggests driver, firmware, hardware, managed dock, or vendor review is needed.",
            ),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    assert "admin" in response.level1_blocker_reason.lower()
    assert "display" in response.current_likely_cause.cause.lower()
    assert_no_fake_display_admin_claims(diagnosis_text(response))


def test_display_admin_boundary_flips_level1_false_after_safe_checks_pass():
    response = MockAIProvider().update_diagnosis(
        make_display_ticket(),
        [
            make_result("display-confirm-symptom", "works", "Display issue confirmed."),
            make_result("display-affected-path", "works", "External monitor path confirmed."),
            make_result("display-affected-scope", "works", "Only one user is affected."),
            make_result("display-power-input-cable", "yes", "Physical display path looks correct."),
            make_result("display-layout-resolution", "works", "Display layout settings look correct."),
            make_result("display-direct-dock-comparison", "does_not_work", "Dock comparison does not isolate it."),
            make_result("display-known-good-comparison", "does_not_work", "Known-good comparison does not isolate it."),
            make_result("display-visible-boundary", "does_not_work", "No additional user-visible boundary message."),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    assert "admin" in response.level1_blocker_reason.lower()


def test_display_checklist_and_diagnosis_do_not_claim_admin_system_checks():
    ticket = make_display_ticket()
    triage = MockAIProvider().analyze_ticket(ticket)
    diagnosis = MockAIProvider().update_diagnosis(ticket, [])
    checklist_text = " ".join(
        " ".join(
            item
            for item in [
                checklist_item.step,
                checklist_item.why,
                checklist_item.evidence_prompt or "",
                checklist_item.access_requirement or "",
            ]
        )
        for checklist_item in triage.checklist
    )

    assert_no_fake_display_admin_claims(checklist_text)
    assert_no_fake_display_admin_claims(diagnosis_text(diagnosis))


def test_teams_audio_video_not_stolen_by_display_monitor():
    response = MockAIProvider().analyze_ticket(
        make_teams_ticket(
            {
                "title": "Teams camera not working",
                "userMessage": "The camera preview is blank in Teams but meeting display is fine.",
            }
        )
    )

    assert response.classification.category == IssueCategory.TEAMS_AUDIO_VIDEO


def test_generic_usb_peripheral_not_stolen_by_display_monitor():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "USB keyboard not detected",
                "userMessage": "The USB keyboard is plugged in but not recognized.",
                "affectedService": "Hardware",
            }
        )
    )

    assert response.classification.category == IssueCategory.HARDWARE_PERIPHERAL


def test_printer_scanner_not_stolen_by_display_monitor():
    response = MockAIProvider().analyze_ticket(
        make_printer_scanner_ticket(
            {
                "title": "Printer display shows paper jam",
                "userMessage": "The printer display says paper jam and scan-to-folder is not working.",
            }
        )
    )

    assert response.classification.category == IssueCategory.PRINTER


def test_browser_or_application_rendering_issue_not_display_monitor():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Company portal page renders incorrectly",
                "userMessage": "The web application page is blank in Chrome but the physical monitor works.",
                "affectedService": "Company Portal",
                "environmentContext": {
                    "applicationPlatform": "company_custom",
                },
            }
        )
    )

    assert response.classification.category == IssueCategory.APPLICATION_ERROR


def test_device_performance_freezing_not_display_monitor():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Laptop freezes during startup",
                "userMessage": "The laptop freezes and is slow after startup, but the physical screen works.",
                "affectedService": "Device",
            }
        )
    )

    assert response.classification.category == IssueCategory.DEVICE_PERFORMANCE


def make_software_ticket(overrides: dict | None = None) -> TicketInput:
    payload = {
        "title": "Software update will not install",
        "userMessage": "The application installer fails during the update.",
        "affectedService": "Software installation",
        "deviceType": "Windows laptop",
    }
    if overrides:
        payload.update(overrides)
    return make_ticket(payload)


def assert_no_fake_software_admin_claims(text: str) -> None:
    lowered = text.lower()
    forbidden_claims = (
        "intune was checked",
        "mdm was checked",
        "edr was checked",
        "software deployment tools were checked",
        "licensing systems were checked",
        "windows event logs were checked",
        "event logs were checked",
        "registry was checked",
        "vendor installer logs were checked",
        "package repositories were checked",
        "package repository was checked",
        "admin portals were checked",
        "admin portal was checked",
    )
    for claim in forbidden_claims:
        assert claim not in lowered


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "title": "Installer fails",
            "userMessage": "The installer fails with an error before the app installs.",
            "affectedService": "Software installation",
        },
        {
            "title": "Software update fails",
            "userMessage": "The software update fails before it reaches the current version.",
            "affectedService": "Software update",
        },
        {
            "title": "Patch blocked",
            "userMessage": "The monthly patch is blocked and will not apply.",
            "affectedService": "Software patch",
        },
    ],
)
def test_software_install_update_classification_handles_common_symptoms(overrides: dict):
    response = MockAIProvider().analyze_ticket(make_software_ticket(overrides))

    assert response.classification.category == IssueCategory.SOFTWARE_INSTALLATION_UPDATE


def test_software_install_update_checklist_uses_detailed_layered_progression():
    response = MockAIProvider().analyze_ticket(make_software_ticket())
    checklist_by_id = {item.id: item for item in response.checklist}

    assert list(checklist_by_id) == [
        "software-confirm-action",
        "software-app-version-error",
        "software-affected-scope",
        "software-approved-source",
        "software-restart-disk-readiness",
        "software-version-install-state",
        "software-visible-admin-boundary",
        "software-admin-deployment-review",
    ]
    assert checklist_by_id["software-confirm-action"].group == ChecklistGroup.SCOPE_IMPACT
    assert checklist_by_id["software-approved-source"].group == ChecklistGroup.SIMPLE_USER_CHECKS
    assert (
        checklist_by_id["software-version-install-state"].group
        == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    )
    assert (
        checklist_by_id["software-visible-admin-boundary"].group
        == ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    assert (
        checklist_by_id["software-admin-deployment-review"].group
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert checklist_by_id["software-admin-deployment-review"].requires_privileged_access is True
    assert checklist_by_id["software-admin-deployment-review"].level1_actionable is False


def test_software_install_update_no_evidence_starts_with_scope_and_next_actions():
    response = MockAIProvider().update_diagnosis(make_software_ticket(), [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "software-confirm-action"
    assert "install" in response.next_best_actions[0].lower()
    assert "business impact" in response.next_best_actions[0].lower()
    assert 1 <= len(response.next_best_actions) <= 3
    assert response.next_best_actions[0] == response.next_best_action
    assert response.level1_can_continue is True


def test_software_install_update_user_unsure_creates_missing_evidence_prompt():
    response = MockAIProvider().update_diagnosis(
        make_software_ticket(),
        [
            make_result(
                "software-confirm-action",
                "user_unsure",
                "The user is unsure whether this is an install, update, uninstall, or patch issue.",
            )
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence
    assert response.missing_evidence[0].step_id == "software-confirm-action"
    assert "install" in response.missing_evidence[0].reason.lower()
    assert response.level1_can_continue is True


def test_software_wrong_or_unapproved_source_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_software_ticket(),
        [
            make_result("software-confirm-action", "works", "The user is trying to install the app."),
            make_result("software-app-version-error", "works", "App, version, OS, and error are captured."),
            make_result("software-affected-scope", "works", "Only one device is affected."),
            make_result(
                "software-approved-source",
                "no",
                "The user downloaded an installer from an unapproved website instead of company software center.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "approved" in response.current_likely_cause.cause.lower()
    assert "source" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_software_restart_pending_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_software_ticket(),
        [
            make_result("software-confirm-action", "works", "Update fails."),
            make_result("software-app-version-error", "works", "Version and error are captured."),
            make_result("software-affected-scope", "works", "Only one device is affected."),
            make_result("software-approved-source", "yes", "The user used company software center."),
            make_result(
                "software-restart-disk-readiness",
                "no",
                "The device shows restart pending before the update can continue.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.SIMPLE_USER_CHECKS
    assert "restart" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_software_visible_disk_space_issue_stays_level1_actionable():
    response = MockAIProvider().update_diagnosis(
        make_software_ticket(),
        [
            make_result("software-confirm-action", "works", "Install fails."),
            make_result("software-app-version-error", "works", "Error says not enough space."),
            make_result("software-affected-scope", "works", "Only one device is affected."),
            make_result("software-approved-source", "yes", "Approved installer is used."),
            make_result(
                "software-restart-disk-readiness",
                "no",
                "User-visible storage shows the disk is almost full.",
            ),
        ],
    )

    assert "disk" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False


def test_software_version_or_previous_install_state_points_to_install_path():
    response = MockAIProvider().update_diagnosis(
        make_software_ticket(),
        [
            make_result("software-confirm-action", "works", "App update fails."),
            make_result("software-app-version-error", "works", "App version and OS are captured."),
            make_result("software-affected-scope", "works", "Only one device is affected."),
            make_result("software-approved-source", "yes", "Approved source is used."),
            make_result("software-restart-disk-readiness", "yes", "No restart pending and disk space is visible."),
            make_result(
                "software-version-install-state",
                "does_not_work",
                "The app was previously installed at an old version and the update path fails.",
            ),
        ],
    )

    assert response.current_troubleshooting_layer == ChecklistGroup.DEVICE_CLIENT_APPLICATION
    assert "version" in response.current_likely_cause.cause.lower()
    assert response.level1_can_continue is True


@pytest.mark.parametrize(
    "evidence",
    [
        "The installer prompts for admin rights before it can continue.",
        "The company portal says deployment is managed by Intune and MDM policy.",
        "The installer says package deployment is required from software center.",
        "The update says no license is assigned for this software.",
    ],
)
def test_software_visible_admin_or_license_boundary_flips_level1_false(evidence: str):
    response = MockAIProvider().update_diagnosis(
        make_software_ticket(),
        [
            make_result("software-confirm-action", "works", "Install or update fails."),
            make_result("software-app-version-error", "works", "App, version, OS, and error are captured."),
            make_result("software-affected-scope", "works", "Only one device is affected."),
            make_result("software-approved-source", "yes", "Approved source is used."),
            make_result("software-restart-disk-readiness", "yes", "No restart pending and disk space is visible."),
            make_result("software-version-install-state", "works", "Previous install state is captured."),
            make_result("software-visible-admin-boundary", "works", evidence),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    assert_no_fake_software_admin_claims(diagnosis_text(response))


def test_software_safe_local_checks_pass_then_escalates_to_admin_boundary():
    response = MockAIProvider().update_diagnosis(
        make_software_ticket(),
        [
            make_result("software-confirm-action", "works", "Software update fails."),
            make_result("software-app-version-error", "works", "App, version, OS, and error are captured."),
            make_result("software-affected-scope", "works", "Only one user and device are affected."),
            make_result("software-approved-source", "yes", "Approved company source is used."),
            make_result("software-restart-disk-readiness", "yes", "No restart pending and disk space is visible."),
            make_result("software-version-install-state", "works", "Previous install and version state are captured."),
            make_result("software-visible-admin-boundary", "does_not_work", "No user-visible admin or license boundary is shown."),
        ],
    )

    assert (
        response.current_troubleshooting_layer
        == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
    )
    assert response.escalation_recommendation.should_escalate is True
    assert response.level1_can_continue is False
    assert "admin" in response.level1_blocker_reason.lower()


def test_software_checklist_and_diagnosis_do_not_claim_admin_system_checks():
    ticket = make_software_ticket()
    triage = MockAIProvider().analyze_ticket(ticket)
    diagnosis = MockAIProvider().update_diagnosis(ticket, [])
    checklist_text = " ".join(
        " ".join(
            item
            for item in [
                checklist_item.step,
                checklist_item.why,
                checklist_item.evidence_prompt or "",
                checklist_item.access_requirement or "",
            ]
        )
        for checklist_item in triage.checklist
    )

    assert_no_fake_software_admin_claims(checklist_text)
    assert_no_fake_software_admin_claims(diagnosis_text(diagnosis))


def test_application_runtime_error_after_launch_remains_application_error():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Application crashes after launch",
                "userMessage": "The company app launches, then shows an unexpected runtime error after submit.",
                "affectedService": "Company Portal",
                "environmentContext": {
                    "applicationPlatform": "company_custom",
                },
            }
        )
    )

    assert response.classification.category == IssueCategory.APPLICATION_ERROR


def test_login_mfa_failure_during_software_portal_access_remains_login():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Cannot sign in to software portal",
                "userMessage": "The user cannot sign in to the software portal because MFA approval fails.",
                "affectedService": "Software portal",
                "errorMessage": "MFA approval failed",
            }
        )
    )

    assert response.classification.category == IssueCategory.LOGIN_ACCOUNT


def test_device_slow_after_update_remains_device_performance_without_update_failure():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Laptop slow after update",
                "userMessage": "The device is slow and freezes after a recent update, but no install or update is currently failing.",
                "affectedService": "Device",
            }
        )
    )

    assert response.classification.category == IssueCategory.DEVICE_PERFORMANCE


def test_install_update_failure_dominates_device_performance_wording():
    response = MockAIProvider().analyze_ticket(
        make_software_ticket(
            {
                "title": "Software update fails and device is slow",
                "userMessage": "The software update fails with an installer error; the laptop is also slow.",
            }
        )
    )

    assert response.classification.category == IssueCategory.SOFTWARE_INSTALLATION_UPDATE


def test_browser_extension_or_website_issue_not_software_without_install_failure():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "Website extension issue",
                "userMessage": "A browser extension causes a website rendering issue, but no install or update failed.",
                "affectedService": "Browser",
                "environmentContext": {
                    "applicationPlatform": "browser",
                },
            }
        )
    )

    assert response.classification.category != IssueCategory.SOFTWARE_INSTALLATION_UPDATE


def test_printer_driver_wording_keeps_printer_when_printing_is_dominant():
    response = MockAIProvider().analyze_ticket(
        make_printer_scanner_ticket(
            {
                "title": "Printer will not print after driver update",
                "userMessage": "The printer will not print after a driver update.",
            }
        )
    )

    assert response.classification.category == IssueCategory.PRINTER


def test_display_driver_wording_keeps_display_when_physical_output_is_dominant():
    response = MockAIProvider().analyze_ticket(
        make_display_ticket(
            {
                "title": "External monitor blank after display driver update",
                "userMessage": "The physical external monitor is blank after a display driver update.",
            }
        )
    )

    assert response.classification.category == IssueCategory.DISPLAY_MONITOR


def test_printer_ticket_returns_printer_category():
    ticket = make_ticket(
        {
            "title": "Cannot print to office printer",
            "userMessage": "I sent my document to the printer but nothing came out.",
            "affectedService": "Printer",
            "environmentContext": {
                "applicationPlatform": "printer_system",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)

    assert response.classification.category == IssueCategory.PRINTER


def test_printer_no_evidence_prioritizes_scope_before_simple_user_checks():
    ticket = make_ticket(
        {
            "title": "Cannot print to office printer",
            "userMessage": "I sent my document to the printer but nothing came out.",
            "affectedService": "Printer",
            "environmentContext": {
                "applicationPlatform": "printer_system",
            },
        }
    )

    response = MockAIProvider().update_diagnosis(ticket, [])

    assert response.current_troubleshooting_layer == ChecklistGroup.SCOPE_IMPACT
    assert response.missing_evidence[0].step_id == "printer-confirm-symptom"
    assert "symptom" in response.next_best_actions[0].lower()
    assert "business impact" in response.next_best_actions[0].lower()
    assert "selected printer" not in response.next_best_actions[0].lower()


def test_unknown_company_custom_ticket_returns_general_or_application_fallback():
    ticket = make_ticket(
        {
            "title": "Internal app error",
            "userMessage": "The company portal shows a vague error after submit.",
            "affectedService": "Company Portal",
            "errorMessage": "Unexpected error",
            "environmentContext": {
                "applicationPlatform": "company_custom",
                "accountPlatform": "company_custom",
            },
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    checklist_text = " ".join(item.step for item in response.checklist).lower()
    missing_questions = " ".join(
        item.question for item in response.missing_information
    ).lower()

    assert response.classification.category in {
        IssueCategory.GENERAL_IT,
        IssueCategory.APPLICATION_ERROR,
    }
    assert "exact error" in checklist_text or "exact error" in missing_questions
    assert "responsible team" in " ".join(response.escalation_criteria).lower()
    assert response.safety_notes


def test_general_it_unknown_fallback_asks_safe_broad_clarifying_questions():
    ticket = make_ticket(
        {
            "title": "Something is not working",
            "userMessage": "Something stopped working and I am not sure what it is.",
            "affectedService": "Unknown",
            "deviceType": "Unknown",
            "location": "unknown",
            "affectedUsers": "unknown",
            "agentSelectedUrgency": "unknown",
            "businessImpact": "Unknown",
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    questions = " ".join(
        item.question for item in response.missing_information
    ).lower()
    causes = " ".join(item.cause for item in response.possible_causes).lower()

    assert response.classification.category == IssueCategory.GENERAL_IT
    assert "what exactly is not working" in questions
    assert "trying to do" in questions
    assert "error message or warning" in questions
    assert "work before" in questions
    assert "only you or other users" in questions
    assert "blocking work" in questions
    assert "more information" in causes
    assert "definitely" not in causes


def test_general_it_unknown_fallback_avoids_old_ticket_form_questions():
    ticket = make_ticket(
        {
            "title": "Unknown workstation problem",
            "userMessage": "Something near my workstation is not behaving normally.",
            "affectedService": "Unknown",
            "businessImpact": "Unknown",
        }
    )

    response = MockAIProvider().analyze_ticket(ticket)
    questions = " ".join(
        item.question for item in response.missing_information
    ).lower()
    checklist_text = " ".join(item.step for item in response.checklist).lower()

    assert response.classification.category == IssueCategory.GENERAL_IT
    assert "who is affected, where are they located" not in questions
    assert "location" not in checklist_text
    assert "account or application" not in checklist_text


def test_general_it_unknown_diagnosis_no_evidence_stays_uncertain_and_safe():
    ticket = make_ticket(
        {
            "title": "Something is not working",
            "userMessage": "Something stopped working and I am not sure what it is.",
            "affectedService": "Unknown",
            "affectedUsers": "unknown",
            "agentSelectedUrgency": "unknown",
            "businessImpact": "Unknown",
        }
    )

    response = MockAIProvider().update_diagnosis(ticket, [])
    next_actions = " ".join(response.next_best_actions).lower()

    assert response.current_likely_cause.cause == "More information needed"
    assert response.confidence.value == "low"
    assert response.level1_can_continue is True
    assert response.escalation_recommendation.should_escalate is False
    assert "what exactly is not working" in next_actions
    assert "trying to do" in next_actions
    assert "scope" in next_actions or "only you" in next_actions


def test_update_diagnosis_returns_valid_response():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "environmentContext": {
                "operatingSystem": "windows",
                "applicationPlatform": "vpn_client",
            },
        }
    )
    results = [
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-confirm-internet",
                "result": "works",
                "evidence": "Public websites open normally.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        )
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)

    assert isinstance(response, UpdatedDiagnosisResponse)
    assert response.current_likely_cause.cause
    assert response.confidence.value in {"low", "medium", "high"}
    assert response.status.value in {"in_progress", "ready_to_escalate"}
    assert results[0].result == ChecklistResultValue.WORKS


def test_update_diagnosis_uses_human_readable_ruled_out_cause_names():
    ticket = make_ticket(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "environmentContext": {
                "applicationPlatform": "vpn_client",
            },
        }
    )
    results = [
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-confirm-internet",
                "result": "works",
                "evidence": "Public websites open normally.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "teams-other-app",
                "result": "works",
                "evidence": "Microphone works in Voice Recorder.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
        ChecklistResult.model_validate(
            {
                "stepId": "printer-other-users",
                "result": "works",
                "evidence": "Another user can print successfully.",
                "recordedAt": datetime.now().astimezone().isoformat(),
            }
        ),
    ]

    response = MockAIProvider().update_diagnosis(ticket, results)
    ruled_out_causes = {item.cause for item in response.ruled_out_causes}

    assert "General internet connectivity issue" in ruled_out_causes
    assert "Hardware microphone issue outside Teams" in ruled_out_causes
    assert "Shared printer or print service issue" in ruled_out_causes


def test_generate_documentation_returns_valid_response():
    provider = MockAIProvider()
    ticket = make_ticket(
        {
            "title": "Outlook not receiving email",
            "userMessage": "I have not received any emails in Outlook today.",
            "affectedService": "Outlook",
            "environmentContext": {
                "accountPlatform": "microsoft_365",
                "applicationPlatform": "microsoft_365",
            },
        }
    )
    diagnosis = provider.update_diagnosis(ticket, [])

    response = provider.generate_documentation(ticket, diagnosis)

    assert isinstance(response, DocumentationResponse)
    assert "Outlook not receiving email" in response.internal_note
    assert response.user_response_draft
    assert response.resolution_note
    assert response.escalation_note


def missing_question_text(response: InitialTriageResponse) -> str:
    return " ".join(
        item.question for item in response.missing_information
    ).lower()


def test_display_monitor_clarification_questions_are_symptom_specific():
    response = MockAIProvider().analyze_ticket(
        make_display_ticket(
            {
                "title": "Monitor turns off after long use",
                "userMessage": "monitor was off after a long time period used",
                "affectedService": "External monitor",
            }
        )
    )

    questions = missing_question_text(response)

    assert response.classification.category == IssueCategory.DISPLAY_MONITOR
    assert "power light" in questions
    assert "mouse" in questions or "keyboard" in questions
    assert "wake" in questions
    assert "computer" in questions or "laptop" in questions
    assert "dock" in questions or "hdmi" in questions or "usb-c" in questions
    assert "account" not in questions
    assert "application" not in questions


def test_login_clarification_questions_are_identity_specific():
    response = MockAIProvider().analyze_ticket(
        make_login_ticket(
            {
                "title": "Cannot log in",
                "userMessage": "I cannot log in to my work account",
            }
        )
    )

    questions = missing_question_text(response)

    assert response.classification.category == IssueCategory.LOGIN_ACCOUNT
    assert "account" in questions or "application" in questions
    assert "error" in questions
    assert "mfa" in questions
    assert "password" in questions


def test_vpn_clarification_questions_are_remote_access_specific():
    response = MockAIProvider().analyze_ticket(
        make_ticket(
            {
                "title": "VPN cannot connect",
                "userMessage": "VPN cannot connect",
                "affectedService": "VPN",
                "environmentContext": {
                    "applicationPlatform": "vpn_client",
                },
            }
        )
    )

    questions = missing_question_text(response)

    assert response.classification.category == IssueCategory.VPN_REMOTE_ACCESS
    assert "vpn error" in questions
    assert "internet" in questions
    assert "network" in questions or "wi-fi" in questions or "wifi" in questions
    assert "password" in questions or "mfa" in questions


def test_printer_clarification_questions_are_print_specific():
    response = MockAIProvider().analyze_ticket(
        make_printer_scanner_ticket(
            {
                "title": "Printer online but nothing prints",
                "userMessage": "Printer is online but nothing prints",
            }
        )
    )

    questions = missing_question_text(response)

    assert response.classification.category == IssueCategory.PRINTER
    assert "correct printer" in questions
    assert "queue" in questions
    assert "other users" in questions
    assert "app" in questions or "all apps" in questions
    assert "is the printer online" not in questions


def test_file_access_clarification_questions_are_permission_specific():
    response = MockAIProvider().analyze_ticket(
        make_file_access_ticket(
            {
                "title": "Shared folder access issue",
                "userMessage": "I cannot access a shared folder",
            }
        )
    )

    questions = missing_question_text(response)

    assert response.classification.category == IssueCategory.FILE_ACCESS_PERMISSION
    assert "path" in questions or "sharepoint" in questions or "shared drive" in questions
    assert "permission" in questions or "access denied" in questions
    assert "before" in questions or "previous" in questions
    assert "other" in questions and "users" in questions
