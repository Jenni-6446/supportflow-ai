import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


from app.schemas.analysis import (  # noqa: E402
    ChecklistItem,
    ChecklistResultType,
    Classification,
    Confidence,
    InitialTriageResponse,
    IssueCategory,
    IssueType,
    Likelihood,
    MissingInformationItem,
    PossibleCause,
    Priority,
    PriorityAssessment,
)
from app.schemas.diagnosis import (  # noqa: E402
    ChecklistResult,
    CurrentLikelyCause,
    DiagnosticStatus,
    EscalationRecommendation,
    RuledOutCause,
    UpdatedDiagnosisResponse,
)
from app.schemas.documentation import DocumentationResponse  # noqa: E402
from app.schemas.ticket import (  # noqa: E402
    AccountPlatform,
    AffectedUsers,
    ApplicationPlatform,
    DeviceManagementPlatform,
    DeviceOwnership,
    Location,
    OperatingSystem,
    TicketInput,
    Urgency,
)


def test_validates_complete_vpn_ticket_input_payload():
    ticket = TicketInput.model_validate(
        {
            "title": "VPN authentication failed",
            "userMessage": (
                "I cannot connect to VPN from home. It worked yesterday, but "
                "today it says authentication failed."
            ),
            "affectedService": "VPN",
            "deviceType": "Windows laptop",
            "location": "home",
            "affectedUsers": "single_user",
            "agentSelectedUrgency": "medium",
            "businessImpact": "User cannot access internal systems remotely.",
            "errorMessage": "Authentication failed",
            "recentChange": "Unknown",
            "workaroundAvailable": "Unknown",
            "attachments": ["screenshot metadata: vpn-auth-error.png"],
        }
    )

    assert ticket.location == Location.HOME
    assert ticket.affected_users == AffectedUsers.SINGLE_USER
    assert ticket.agent_selected_urgency == Urgency.MEDIUM
    assert ticket.attachments == ["screenshot metadata: vpn-auth-error.png"]
    assert (
        ticket.model_dump(by_alias=True)["userMessage"]
        == "I cannot connect to VPN from home. It worked yesterday, but today it says authentication failed."
    )


def test_validates_ticket_input_with_environment_context():
    ticket = TicketInput.model_validate(
        {
            "title": "VPN authentication failed",
            "userMessage": "Cannot connect to VPN from home.",
            "affectedService": "VPN",
            "deviceType": "Windows laptop",
            "location": "home",
            "affectedUsers": "single_user",
            "agentSelectedUrgency": "medium",
            "businessImpact": "User cannot access internal systems.",
            "environmentContext": {
                "operatingSystem": "windows",
                "accountPlatform": "microsoft_365",
                "deviceManagement": "intune",
                "deviceOwnership": "company_owned",
                "applicationPlatform": "vpn_client",
            },
        }
    )

    assert ticket.environment_context is not None
    assert ticket.environment_context.operating_system == OperatingSystem.WINDOWS
    assert ticket.environment_context.account_platform == AccountPlatform.MICROSOFT_365
    assert (
        ticket.environment_context.device_management
        == DeviceManagementPlatform.INTUNE
    )
    assert ticket.environment_context.device_ownership == DeviceOwnership.COMPANY_OWNED
    assert (
        ticket.environment_context.application_platform
        == ApplicationPlatform.VPN_CLIENT
    )


def test_environment_context_defaults_to_unknown():
    ticket = TicketInput.model_validate(
        {
            "title": "Laptop running slowly",
            "userMessage": "My laptop is very slow after signing in.",
            "affectedService": "Device",
            "deviceType": "Windows laptop",
            "location": "office",
            "affectedUsers": "single_user",
            "agentSelectedUrgency": "low",
            "businessImpact": "User can work but performance is reduced.",
            "environmentContext": {
                "operatingSystem": "windows",
            },
        }
    )

    assert ticket.environment_context is not None
    assert ticket.environment_context.operating_system == OperatingSystem.WINDOWS
    assert ticket.environment_context.account_platform == AccountPlatform.UNKNOWN
    assert (
        ticket.environment_context.device_management
        == DeviceManagementPlatform.UNKNOWN
    )
    assert ticket.environment_context.device_ownership == DeviceOwnership.UNKNOWN
    assert (
        ticket.environment_context.application_platform
        == ApplicationPlatform.UNKNOWN
    )


def test_account_platform_supports_okta_and_company_custom():
    assert AccountPlatform("okta") == AccountPlatform.OKTA
    assert AccountPlatform("company_custom") == AccountPlatform.COMPANY_CUSTOM


def test_validates_complete_initial_triage_response():
    triage = InitialTriageResponse.model_validate(
        {
            "summary": (
                "The user cannot connect to VPN from home after previously being "
                "able to connect. The reported error suggests an authentication "
                "problem."
            ),
            "classification": {
                "category": "vpn_remote_access",
                "subcategory": "VPN",
                "type": "incident",
            },
            "priorityAssessment": {
                "impact": "single_user",
                "urgency": "medium",
                "priority": "P3",
                "confidence": "medium",
                "reasoning": (
                    "The issue appears to affect one user and blocks remote access, "
                    "but there is not yet evidence of a wider outage."
                ),
            },
            "missingInformation": [
                {
                    "question": "Did the user recently change their password?",
                    "reason": (
                        "A recent password change may cause cached credential or "
                        "authentication failures."
                    ),
                }
            ],
            "possibleCauses": [
                {
                    "cause": "Incorrect or cached password",
                    "likelihood": "high",
                    "reason": "The error mentions authentication failure.",
                }
            ],
            "checklist": [
                {
                    "id": "vpn-check-internet",
                    "step": "Confirm normal internet works outside VPN.",
                    "why": "This rules out a general home internet issue.",
                    "expectedResultType": "works_does_not_work",
                },
                {
                    "id": "vpn-check-password-change",
                    "step": "Ask whether the password was recently changed.",
                    "why": "A changed password can leave cached credentials behind.",
                    "expectedResultType": "yes_no",
                },
                {
                    "id": "vpn-capture-error-message",
                    "step": "Record the exact VPN error message.",
                    "why": "The wording helps distinguish authentication failures.",
                    "expectedResultType": "text",
                },
                {
                    "id": "vpn-admin-logs",
                    "step": "Review VPN concentrator logs if escalated.",
                    "why": "Logs are not available in this MVP workspace.",
                    "expectedResultType": "not_applicable",
                },
            ],
            "escalationCriteria": [
                "Escalate if multiple users are affected.",
                (
                    "Escalate if account permissions, certificate, or VPN "
                    "infrastructure issues are suspected."
                ),
            ],
            "safetyNotes": [
                "Do not claim to have checked VPN logs unless an integration exists."
            ],
        }
    )

    assert isinstance(triage.classification, Classification)
    assert isinstance(triage.priority_assessment, PriorityAssessment)
    assert isinstance(triage.missing_information[0], MissingInformationItem)
    assert isinstance(triage.possible_causes[0], PossibleCause)
    assert isinstance(triage.checklist[0], ChecklistItem)
    assert triage.classification.category == IssueCategory.VPN_REMOTE_ACCESS
    assert triage.classification.type == IssueType.INCIDENT
    assert triage.priority_assessment.priority == Priority.P3
    assert triage.priority_assessment.confidence == Confidence.MEDIUM
    assert triage.possible_causes[0].likelihood == Likelihood.HIGH
    assert triage.checklist[0].expected_result_type == ChecklistResultType.WORKS_DOES_NOT_WORK
    assert triage.checklist[1].expected_result_type == ChecklistResultType.YES_NO
    assert triage.checklist[2].expected_result_type == ChecklistResultType.TEXT
    assert triage.checklist[3].expected_result_type == ChecklistResultType.NOT_APPLICABLE


def test_validates_checklist_result_records():
    result = ChecklistResult.model_validate(
        {
            "stepId": "vpn-check-internet",
            "result": "works",
            "evidence": "User can browse public websites normally.",
            "recordedAt": "2026-06-03T15:30:00+10:00",
        }
    )

    assert result.step_id == "vpn-check-internet"
    assert result.result.value == "works"
    assert result.recorded_at.isoformat() == "2026-06-03T15:30:00+10:00"
    assert result.recorded_at.tzinfo is not None


def test_rejects_checklist_result_with_naive_recorded_at():
    with pytest.raises(ValidationError):
        ChecklistResult.model_validate(
            {
                "stepId": "vpn-check-internet",
                "result": "works",
                "evidence": "User can browse public websites normally.",
                "recordedAt": "2026-06-03T15:30:00",
            }
        )


def test_rejects_extra_unknown_fields():
    with pytest.raises(ValidationError):
        TicketInput.model_validate(
            {
                "title": "VPN authentication failed",
                "userMessage": "Cannot connect to VPN.",
                "affectedService": "VPN",
                "deviceType": "Windows laptop",
                "location": "home",
                "affectedUsers": "single_user",
                "agentSelectedUrgency": "medium",
                "businessImpact": "User cannot access internal systems.",
                "unexpectedField": "should be rejected",
            }
        )


def test_rejects_extra_unknown_fields_inside_environment_context():
    with pytest.raises(ValidationError):
        TicketInput.model_validate(
            {
                "title": "VPN authentication failed",
                "userMessage": "Cannot connect to VPN.",
                "affectedService": "VPN",
                "deviceType": "Windows laptop",
                "location": "home",
                "affectedUsers": "single_user",
                "agentSelectedUrgency": "medium",
                "businessImpact": "User cannot access internal systems.",
                "environmentContext": {
                    "operatingSystem": "windows",
                    "realSystemChecked": True,
                },
            }
        )


def test_validates_complete_updated_diagnosis_response():
    diagnosis = UpdatedDiagnosisResponse.model_validate(
        {
            "currentLikelyCause": {
                "cause": "Cached password or account authentication issue",
                "confidence": "medium",
                "reasoning": (
                    "Normal internet works and the VPN error is authentication-related. "
                    "More information is needed about recent password changes and MFA "
                    "behavior."
                ),
            },
            "ruledOutCauses": [
                {
                    "cause": "General home internet outage",
                    "reason": "User can access public websites normally.",
                }
            ],
            "evidenceSummary": [
                "Normal internet connectivity confirmed.",
                "VPN error message is authentication-related.",
            ],
            "nextBestAction": (
                "Ask whether the user recently changed their password and confirm "
                "whether the MFA prompt appears."
            ),
            "escalationRecommendation": {
                "shouldEscalate": False,
                "reason": "Current evidence supports further Level 1 checks.",
            },
            "confidence": "medium",
            "status": "in_progress",
        }
    )

    assert isinstance(diagnosis.current_likely_cause, CurrentLikelyCause)
    assert isinstance(diagnosis.ruled_out_causes[0], RuledOutCause)
    assert isinstance(diagnosis.escalation_recommendation, EscalationRecommendation)
    assert diagnosis.current_likely_cause.confidence == Confidence.MEDIUM
    assert diagnosis.escalation_recommendation.should_escalate is False
    assert diagnosis.status == DiagnosticStatus.IN_PROGRESS
    assert diagnosis.current_troubleshooting_layer is None
    assert diagnosis.completed_layers == []
    assert diagnosis.missing_evidence == []
    assert diagnosis.next_best_actions == [diagnosis.next_best_action]
    assert diagnosis.level1_can_continue is True
    assert diagnosis.level1_blocker_reason == ""


def test_validates_additive_v15_diagnosis_fields():
    diagnosis = UpdatedDiagnosisResponse.model_validate(
        {
            "currentLikelyCause": {
                "cause": "Device Wi-Fi profile issue",
                "confidence": "medium",
                "reasoning": "Scope checks passed and the next unresolved layer is simple user checks.",
            },
            "ruledOutCauses": [],
            "evidenceSummary": ["wifi-see-ssid: yes - Device sees the SSID."],
            "nextBestAction": "Forget and reconnect to the Wi-Fi profile.",
            "currentTroubleshootingLayer": "simple_user_checks",
            "completedLayers": ["scope_impact"],
            "missingEvidence": [
                {
                    "stepId": "wifi-forget-profile",
                    "layer": "simple_user_checks",
                    "question": "Did forgetting and reconnecting to the Wi-Fi profile work?",
                    "reason": "This check has not been recorded yet.",
                }
            ],
            "nextBestActions": [
                "Forget and reconnect to the Wi-Fi profile.",
                "Check whether normal internet works on another network or hotspot.",
            ],
            "level1CanContinue": True,
            "level1BlockerReason": "",
            "escalationRecommendation": {
                "shouldEscalate": False,
                "reason": "Continue progressive checks before escalating.",
            },
            "confidence": "low",
            "status": "in_progress",
        }
    )

    assert diagnosis.current_troubleshooting_layer.value == "simple_user_checks"
    assert [layer.value for layer in diagnosis.completed_layers] == ["scope_impact"]
    assert diagnosis.missing_evidence[0].step_id == "wifi-forget-profile"
    assert diagnosis.next_best_actions[0] == diagnosis.next_best_action
    assert diagnosis.level1_can_continue is True


def test_validates_additive_v15_checklist_item_metadata():
    item = ChecklistItem.model_validate(
        {
            "id": "app-escalation",
            "group": "escalation_admin_infrastructure",
            "step": "Escalate if logs, vendor, or admin review is required.",
            "why": "This requires privileged or external-system access.",
            "expectedResultType": "not_applicable",
            "level1Actionable": False,
            "requiresPrivilegedAccess": True,
            "accessRequirement": "Admin, vendor, log, or infrastructure review.",
            "evidencePrompt": "What evidence shows this requires escalation?",
        }
    )

    assert item.level1_actionable is False
    assert item.requires_privileged_access is True
    assert "Admin" in item.access_requirement
    assert item.evidence_prompt.startswith("What evidence")


def test_validates_documentation_response():
    notes = DocumentationResponse.model_validate(
        {
            "internalNote": (
                "User reports VPN authentication failure from home. Internet "
                "connectivity outside VPN confirmed. Current likely cause is cached "
                "credentials, password, or MFA-related authentication issue."
            ),
            "userResponseDraft": (
                "Thanks for the details. I am checking whether this is related to "
                "your VPN sign-in, saved password, or MFA prompt."
            ),
            "resolutionNote": (
                "VPN access restored after authentication details were corrected and "
                "the VPN client was restarted."
            ),
            "escalationNote": (
                "Please review VPN authentication for the affected user. Level 1 "
                "checks confirmed normal internet access and an authentication "
                "failure at VPN sign-in."
            ),
        }
    )

    assert "VPN authentication failure" in notes.internal_note
    assert "VPN access restored" in notes.resolution_note
