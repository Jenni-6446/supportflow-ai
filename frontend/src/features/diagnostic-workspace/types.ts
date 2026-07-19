export type Location = "office" | "home" | "remote" | "unknown";
export type AffectedUsers =
  | "single_user"
  | "multiple_users"
  | "department"
  | "organization"
  | "unknown";
export type Urgency = "low" | "medium" | "high" | "critical" | "unknown";
export type OperatingSystem =
  | "windows"
  | "macos"
  | "linux"
  | "ios"
  | "android"
  | "chromeos"
  | "unknown";
export type AccountPlatform =
  | "microsoft_365"
  | "google_workspace"
  | "active_directory"
  | "entra_id"
  | "okta"
  | "local_account"
  | "company_custom"
  | "unknown";
export type DeviceManagementPlatform =
  | "intune"
  | "jamf"
  | "group_policy"
  | "none"
  | "unknown";
export type DeviceOwnership =
  | "company_owned"
  | "personal_byod"
  | "shared_device"
  | "unknown";
export type ApplicationPlatform =
  | "microsoft_365"
  | "google_workspace"
  | "zoom"
  | "slack"
  | "browser"
  | "vpn_client"
  | "printer_system"
  | "company_custom"
  | "unknown";

export type IssueCategory =
  | "login_account"
  | "network_wifi"
  | "small_office_network"
  | "voip_telephony"
  | "vpn_remote_access"
  | "email_outlook"
  | "teams_audio_video"
  | "printer"
  | "device_performance"
  | "file_access_permission"
  | "application_error"
  | "hardware_peripheral"
  | "software_installation_update"
  | "display_monitor"
  | "mobile_hotspot"
  | "general_it"
  | "unknown";
export type IssueType = "incident" | "request";
export type Impact =
  | "single_user"
  | "multiple_users"
  | "department"
  | "organization"
  | "unknown";
export type Priority = "P1" | "P2" | "P3" | "P4" | "unknown";
export type Confidence = "low" | "medium" | "high";
export type Likelihood = "low" | "medium" | "high";
export type ChecklistResultType =
  | "works_does_not_work"
  | "yes_no"
  | "text"
  | "not_applicable";
export type ChecklistGroup =
  | "scope_impact"
  | "simple_user_checks"
  | "device_client_application"
  | "platform_permission_configuration"
  | "escalation_admin_infrastructure";
export type ChecklistResultValue =
  | "works"
  | "does_not_work"
  | "yes"
  | "no"
  | "not_tested"
  | "user_unsure"
  | "needs_escalation";
export type DiagnosticStatus =
  | "draft"
  | "analyzed"
  | "in_progress"
  | "ready_to_resolve"
  | "ready_to_escalate";

export interface EnvironmentContext {
  operatingSystem: OperatingSystem;
  accountPlatform: AccountPlatform;
  deviceManagement: DeviceManagementPlatform;
  deviceOwnership: DeviceOwnership;
  applicationPlatform: ApplicationPlatform;
}

export interface TicketInput {
  title: string;
  userMessage: string;
  affectedService: string;
  deviceType: string;
  location: Location;
  affectedUsers: AffectedUsers;
  agentSelectedUrgency: Urgency;
  businessImpact: string;
  errorMessage: string;
  recentChange: string;
  workaroundAvailable: string;
  attachments: string[];
  environmentContext: EnvironmentContext;
}

export interface Classification {
  category: IssueCategory;
  subcategory: string;
  type: IssueType;
}

export interface PriorityAssessment {
  impact: Impact;
  urgency: Urgency;
  priority: Priority;
  confidence: Confidence;
  reasoning: string;
}

export interface MissingInformationItem {
  question: string;
  reason: string;
}

export interface PossibleCause {
  cause: string;
  likelihood: Likelihood;
  reason: string;
}

export interface ChecklistItem {
  id: string;
  group?: ChecklistGroup | null;
  step: string;
  why: string;
  expectedResultType: ChecklistResultType;
  level1Actionable?: boolean | null;
  requiresPrivilegedAccess?: boolean | null;
  accessRequirement?: string | null;
  evidencePrompt?: string | null;
}

export interface InitialTriageResponse {
  summary: string;
  classification: Classification;
  priorityAssessment: PriorityAssessment;
  missingInformation: MissingInformationItem[];
  possibleCauses: PossibleCause[];
  checklist: ChecklistItem[];
  escalationCriteria: string[];
  safetyNotes: string[];
}

export interface ChecklistResult {
  stepId: string;
  result: ChecklistResultValue;
  evidence: string;
  recordedAt: string;
}

export interface CurrentLikelyCause {
  cause: string;
  confidence: Confidence;
  reasoning: string;
}

export interface RuledOutCause {
  cause: string;
  reason: string;
}

export interface EscalationRecommendation {
  shouldEscalate: boolean;
  reason: string;
}

export interface MissingEvidenceItem {
  stepId: string;
  layer: ChecklistGroup;
  question: string;
  reason: string;
}

export interface UpdatedDiagnosisResponse {
  currentLikelyCause: CurrentLikelyCause;
  ruledOutCauses: RuledOutCause[];
  evidenceSummary: string[];
  nextBestAction: string;
  currentTroubleshootingLayer?: ChecklistGroup | null;
  completedLayers?: ChecklistGroup[];
  missingEvidence?: MissingEvidenceItem[];
  nextBestActions?: string[];
  level1CanContinue?: boolean;
  level1BlockerReason?: string;
  escalationRecommendation: EscalationRecommendation;
  confidence: Confidence;
  status: DiagnosticStatus;
}

export interface DocumentationResponse {
  internalNote: string;
  userResponseDraft: string;
  resolutionNote: string;
  escalationNote: string;
}

export interface DemoTicketScenario {
  id: string;
  label: string;
  ticket: TicketInput;
}

export interface ClarificationAnswer {
  question: string;
  selectedOption: string;
  details: string;
}

export const emptyTicket: TicketInput = {
  title: "",
  userMessage: "",
  affectedService: "",
  deviceType: "",
  location: "unknown",
  affectedUsers: "unknown",
  agentSelectedUrgency: "medium",
  businessImpact: "",
  errorMessage: "",
  recentChange: "",
  workaroundAvailable: "",
  attachments: [],
  environmentContext: {
    operatingSystem: "unknown",
    accountPlatform: "unknown",
    deviceManagement: "unknown",
    deviceOwnership: "unknown",
    applicationPlatform: "unknown"
  }
};

export const vpnDemoTicket: TicketInput = {
  title: "VPN authentication failed",
  userMessage:
    "I cannot connect to VPN from home. It worked yesterday, but today it says authentication failed.",
  affectedService: "VPN",
  deviceType: "Windows laptop",
  location: "home",
  affectedUsers: "single_user",
  agentSelectedUrgency: "medium",
  businessImpact: "User cannot access internal systems remotely.",
  errorMessage: "Authentication failed",
  recentChange: "Unknown",
  workaroundAvailable: "Unknown",
  attachments: ["screenshot metadata: vpn-auth-error.png"],
  environmentContext: {
    operatingSystem: "windows",
    accountPlatform: "microsoft_365",
    deviceManagement: "intune",
    deviceOwnership: "company_owned",
    applicationPlatform: "vpn_client"
  }
};

export const demoTicketScenarios: DemoTicketScenario[] = [
  {
    id: "vpn-authentication-failed",
    label: "VPN authentication failed",
    ticket: vpnDemoTicket
  },
  {
    id: "outlook-not-receiving-email",
    label: "Outlook not receiving email",
    ticket: {
      title: "Outlook not receiving email",
      userMessage: "The user has not received expected emails in Outlook today.",
      affectedService: "Outlook",
      deviceType: "Windows laptop",
      location: "office",
      affectedUsers: "single_user",
      agentSelectedUrgency: "medium",
      businessImpact: "User may miss customer and internal messages.",
      errorMessage: "",
      recentChange: "No known change",
      workaroundAvailable: "User can check webmail if available.",
      attachments: ["screenshot metadata: outlook-inbox-sync.png"],
      environmentContext: {
        operatingSystem: "windows",
        accountPlatform: "microsoft_365",
        deviceManagement: "intune",
        deviceOwnership: "company_owned",
        applicationPlatform: "microsoft_365"
      }
    }
  },
  {
    id: "teams-microphone-not-working",
    label: "Teams microphone not working",
    ticket: {
      title: "Teams microphone not working",
      userMessage: "People cannot hear the user in Teams meetings.",
      affectedService: "Microsoft Teams",
      deviceType: "Windows laptop",
      location: "office",
      affectedUsers: "single_user",
      agentSelectedUrgency: "medium",
      businessImpact: "User cannot participate in scheduled meetings.",
      errorMessage: "",
      recentChange: "New headset was connected this morning.",
      workaroundAvailable: "User can join by phone if needed.",
      attachments: ["screenshot metadata: teams-audio-device.png"],
      environmentContext: {
        operatingSystem: "windows",
        accountPlatform: "microsoft_365",
        deviceManagement: "intune",
        deviceOwnership: "company_owned",
        applicationPlatform: "microsoft_365"
      }
    }
  },
  {
    id: "printer-cannot-print",
    label: "Printer cannot print",
    ticket: {
      title: "Cannot print to office printer",
      userMessage: "The user sent a document to the office printer but nothing printed.",
      affectedService: "Printer",
      deviceType: "Windows laptop",
      location: "office",
      affectedUsers: "single_user",
      agentSelectedUrgency: "medium",
      businessImpact: "User cannot print required documents.",
      errorMessage: "",
      recentChange: "Unknown",
      workaroundAvailable: "Another printer may be available on the floor.",
      attachments: ["screenshot metadata: print-queue.png"],
      environmentContext: {
        operatingSystem: "windows",
        accountPlatform: "microsoft_365",
        deviceManagement: "intune",
        deviceOwnership: "company_owned",
        applicationPlatform: "printer_system"
      }
    }
  },
  {
    id: "scanner-scan-to-email-fails",
    label: "Scanner scan-to-email fails",
    ticket: {
      title: "Scan to email fails",
      userMessage: "The scanner works locally but scan-to-email fails for the user.",
      affectedService: "Scanner",
      deviceType: "Multifunction printer",
      location: "office",
      affectedUsers: "single_user",
      agentSelectedUrgency: "medium",
      businessImpact: "User cannot send scanned paperwork to recipients.",
      errorMessage: "Scan destination failed",
      recentChange: "Unknown",
      workaroundAvailable: "User can save locally and attach manually.",
      attachments: ["screenshot metadata: mfd-scan-error.png"],
      environmentContext: {
        operatingSystem: "unknown",
        accountPlatform: "microsoft_365",
        deviceManagement: "unknown",
        deviceOwnership: "shared_device",
        applicationPlatform: "printer_system"
      }
    }
  },
  {
    id: "external-monitor-blank-through-dock",
    label: "External monitor blank through dock",
    ticket: {
      title: "External monitor blank through dock",
      userMessage: "The monitor works direct to the laptop but is blank through the docking station.",
      affectedService: "External monitor",
      deviceType: "Windows laptop",
      location: "office",
      affectedUsers: "single_user",
      agentSelectedUrgency: "medium",
      businessImpact: "User has reduced workspace and cannot use second display.",
      errorMessage: "No signal",
      recentChange: "User moved desks today.",
      workaroundAvailable: "Direct HDMI connection works temporarily.",
      attachments: ["screenshot metadata: monitor-no-signal.png"],
      environmentContext: {
        operatingSystem: "windows",
        accountPlatform: "microsoft_365",
        deviceManagement: "intune",
        deviceOwnership: "company_owned",
        applicationPlatform: "unknown"
      }
    }
  },
  {
    id: "software-update-fails",
    label: "Software update fails",
    ticket: {
      title: "Software update fails",
      userMessage: "The software update fails with an installer error before reaching the current version.",
      affectedService: "Software update",
      deviceType: "Windows laptop",
      location: "office",
      affectedUsers: "single_user",
      agentSelectedUrgency: "medium",
      businessImpact: "User cannot access the required app version.",
      errorMessage: "Installer error",
      recentChange: "App update was released this week.",
      workaroundAvailable: "Old app version still opens for read-only work.",
      attachments: ["screenshot metadata: installer-error.png"],
      environmentContext: {
        operatingSystem: "windows",
        accountPlatform: "microsoft_365",
        deviceManagement: "intune",
        deviceOwnership: "company_owned",
        applicationPlatform: "unknown"
      }
    }
  },
  {
    id: "file-access-denied",
    label: "File access denied",
    ticket: {
      title: "Shared folder access denied",
      userMessage: "The user cannot open a shared folder and sees access denied.",
      affectedService: "File share",
      deviceType: "Windows laptop",
      location: "remote",
      affectedUsers: "single_user",
      agentSelectedUrgency: "high",
      businessImpact: "User cannot access project documents needed today.",
      errorMessage: "Access denied",
      recentChange: "User changed role last week.",
      workaroundAvailable: "A teammate can send individual files if urgent.",
      attachments: ["screenshot metadata: access-denied.png"],
      environmentContext: {
        operatingSystem: "windows",
        accountPlatform: "active_directory",
        deviceManagement: "intune",
        deviceOwnership: "company_owned",
        applicationPlatform: "unknown"
      }
    }
  },
  {
    id: "small-office-network-outage",
    label: "Small office network outage",
    ticket: {
      title: "Small office network outage",
      userMessage: "Several desks in the small office cannot reach the internet.",
      affectedService: "Office network",
      deviceType: "Windows laptop",
      location: "office",
      affectedUsers: "multiple_users",
      agentSelectedUrgency: "high",
      businessImpact: "Multiple users cannot access cloud and internal systems.",
      errorMessage: "",
      recentChange: "No known change",
      workaroundAvailable: "Some users can use mobile hotspot.",
      attachments: ["screenshot metadata: network-unreachable.png"],
      environmentContext: {
        operatingSystem: "windows",
        accountPlatform: "microsoft_365",
        deviceManagement: "intune",
        deviceOwnership: "company_owned",
        applicationPlatform: "unknown"
      }
    }
  },
  {
    id: "voip-phone-not-registered",
    label: "VoIP phone not registered",
    ticket: {
      title: "Desk phone not registered",
      userMessage: "The desk phone has network link but the display says not registered.",
      affectedService: "Telephony",
      deviceType: "Desk phone",
      location: "office",
      affectedUsers: "single_user",
      agentSelectedUrgency: "medium",
      businessImpact: "User cannot receive desk phone calls.",
      errorMessage: "Not registered",
      recentChange: "Phone was moved to a different desk.",
      workaroundAvailable: "User can use softphone temporarily.",
      attachments: ["screenshot metadata: phone-not-registered.png"],
      environmentContext: {
        operatingSystem: "unknown",
        accountPlatform: "unknown",
        deviceManagement: "none",
        deviceOwnership: "company_owned",
        applicationPlatform: "unknown"
      }
    }
  }
];

export const checklistResultOptions: ChecklistResultValue[] = [
  "not_tested",
  "works",
  "does_not_work",
  "yes",
  "no",
  "user_unsure",
  "needs_escalation"
];
