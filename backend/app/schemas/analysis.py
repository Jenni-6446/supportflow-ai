from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ticket import Urgency


class IssueType(str, Enum):
    INCIDENT = "incident"
    REQUEST = "request"


class IssueCategory(str, Enum):
    LOGIN_ACCOUNT = "login_account"
    NETWORK_WIFI = "network_wifi"
    SMALL_OFFICE_NETWORK = "small_office_network"
    VOIP_TELEPHONY = "voip_telephony"
    VPN_REMOTE_ACCESS = "vpn_remote_access"
    EMAIL_OUTLOOK = "email_outlook"
    TEAMS_AUDIO_VIDEO = "teams_audio_video"
    PRINTER = "printer"
    DEVICE_PERFORMANCE = "device_performance"
    FILE_ACCESS_PERMISSION = "file_access_permission"
    APPLICATION_ERROR = "application_error"
    HARDWARE_PERIPHERAL = "hardware_peripheral"
    SOFTWARE_INSTALLATION_UPDATE = "software_installation_update"
    DISPLAY_MONITOR = "display_monitor"
    MOBILE_HOTSPOT = "mobile_hotspot"
    GENERAL_IT = "general_it"
    UNKNOWN = "unknown"


class Impact(str, Enum):
    SINGLE_USER = "single_user"
    MULTIPLE_USERS = "multiple_users"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Likelihood(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ChecklistResultType(str, Enum):
    WORKS_DOES_NOT_WORK = "works_does_not_work"
    YES_NO = "yes_no"
    TEXT = "text"
    NOT_APPLICABLE = "not_applicable"


class ChecklistGroup(str, Enum):
    SCOPE_IMPACT = "scope_impact"
    SIMPLE_USER_CHECKS = "simple_user_checks"
    DEVICE_CLIENT_APPLICATION = "device_client_application"
    PLATFORM_PERMISSION_CONFIGURATION = "platform_permission_configuration"
    ESCALATION_ADMIN_INFRASTRUCTURE = "escalation_admin_infrastructure"


class Classification(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    category: IssueCategory
    subcategory: str = Field(min_length=1)
    type: IssueType


class PriorityAssessment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    impact: Impact
    urgency: Urgency
    priority: Priority
    confidence: Confidence
    reasoning: str = Field(min_length=1)


class MissingInformationItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class PossibleCause(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    cause: str = Field(min_length=1)
    likelihood: Likelihood
    reason: str = Field(min_length=1)


class ChecklistItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1)
    group: ChecklistGroup | None = None
    step: str = Field(min_length=1)
    why: str = Field(min_length=1)
    expected_result_type: ChecklistResultType = Field(alias="expectedResultType")
    level1_actionable: bool | None = Field(default=None, alias="level1Actionable")
    requires_privileged_access: bool | None = Field(
        default=None,
        alias="requiresPrivilegedAccess",
    )
    access_requirement: str | None = Field(default=None, alias="accessRequirement")
    evidence_prompt: str | None = Field(default=None, alias="evidencePrompt")


class InitialTriageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    summary: str = Field(min_length=1)
    classification: Classification
    priority_assessment: PriorityAssessment = Field(alias="priorityAssessment")
    missing_information: list[MissingInformationItem] = Field(alias="missingInformation")
    possible_causes: list[PossibleCause] = Field(alias="possibleCauses")
    checklist: list[ChecklistItem]
    escalation_criteria: list[str] = Field(alias="escalationCriteria")
    safety_notes: list[str] = Field(alias="safetyNotes")
