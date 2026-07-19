from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Location(str, Enum):
    OFFICE = "office"
    HOME = "home"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class AffectedUsers(str, Enum):
    SINGLE_USER = "single_user"
    MULTIPLE_USERS = "multiple_users"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class OperatingSystem(str, Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    IOS = "ios"
    ANDROID = "android"
    CHROMEOS = "chromeos"
    UNKNOWN = "unknown"


class AccountPlatform(str, Enum):
    MICROSOFT_365 = "microsoft_365"
    GOOGLE_WORKSPACE = "google_workspace"
    ACTIVE_DIRECTORY = "active_directory"
    ENTRA_ID = "entra_id"
    OKTA = "okta"
    LOCAL_ACCOUNT = "local_account"
    COMPANY_CUSTOM = "company_custom"
    UNKNOWN = "unknown"


class DeviceManagementPlatform(str, Enum):
    INTUNE = "intune"
    JAMF = "jamf"
    GROUP_POLICY = "group_policy"
    NONE = "none"
    UNKNOWN = "unknown"


class DeviceOwnership(str, Enum):
    COMPANY_OWNED = "company_owned"
    PERSONAL_BYOD = "personal_byod"
    SHARED_DEVICE = "shared_device"
    UNKNOWN = "unknown"


class ApplicationPlatform(str, Enum):
    MICROSOFT_365 = "microsoft_365"
    GOOGLE_WORKSPACE = "google_workspace"
    ZOOM = "zoom"
    SLACK = "slack"
    BROWSER = "browser"
    VPN_CLIENT = "vpn_client"
    PRINTER_SYSTEM = "printer_system"
    COMPANY_CUSTOM = "company_custom"
    UNKNOWN = "unknown"


class EnvironmentContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    operating_system: OperatingSystem = Field(
        default=OperatingSystem.UNKNOWN,
        alias="operatingSystem",
    )
    account_platform: AccountPlatform = Field(
        default=AccountPlatform.UNKNOWN,
        alias="accountPlatform",
    )
    device_management: DeviceManagementPlatform = Field(
        default=DeviceManagementPlatform.UNKNOWN,
        alias="deviceManagement",
    )
    device_ownership: DeviceOwnership = Field(
        default=DeviceOwnership.UNKNOWN,
        alias="deviceOwnership",
    )
    application_platform: ApplicationPlatform = Field(
        default=ApplicationPlatform.UNKNOWN,
        alias="applicationPlatform",
    )


class TicketInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: str = Field(min_length=1)
    user_message: str = Field(alias="userMessage", min_length=1)
    affected_service: str = Field(alias="affectedService", min_length=1)
    device_type: str = Field(alias="deviceType", min_length=1)
    location: Location
    affected_users: AffectedUsers = Field(alias="affectedUsers")
    agent_selected_urgency: Urgency = Field(alias="agentSelectedUrgency")
    business_impact: str = Field(alias="businessImpact", min_length=1)
    error_message: str = Field(alias="errorMessage", default="")
    recent_change: str = Field(alias="recentChange", default="")
    workaround_available: str = Field(alias="workaroundAvailable", default="")
    attachments: list[str] = Field(default_factory=list)
    environment_context: EnvironmentContext | None = Field(
        default=None,
        alias="environmentContext",
    )
