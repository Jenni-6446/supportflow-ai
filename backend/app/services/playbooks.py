from dataclasses import dataclass

from app.schemas.analysis import (
    ChecklistGroup,
    ChecklistResultType,
    IssueCategory,
)
from app.schemas.diagnosis import ChecklistResultValue


@dataclass(frozen=True)
class MissingInformation:
    question: str
    reason: str


@dataclass(frozen=True)
class PlaybookCause:
    cause: str
    likelihood: str
    reason: str


@dataclass(frozen=True)
class PlaybookStep:
    id: str
    layer: ChecklistGroup
    step: str
    why: str
    expected_result_type: ChecklistResultType
    fail_cause: str
    failure_results: tuple[ChecklistResultValue, ...] = (
        ChecklistResultValue.DOES_NOT_WORK,
    )
    pass_results: tuple[ChecklistResultValue, ...] = (
        ChecklistResultValue.WORKS,
    )
    ruled_out_cause: str | None = None
    level1_actionable: bool = True
    requires_privileged_access: bool = False
    access_requirement: str | None = None
    evidence_prompt: str | None = None
    next_action: str | None = None
    escalation_reason: str | None = None


@dataclass(frozen=True)
class Playbook:
    issue_category: IssueCategory
    subcategory: str
    keywords: tuple[str, ...]
    missing_information: tuple[MissingInformation, ...]
    possible_causes: tuple[PlaybookCause, ...]
    checklist_steps: tuple[PlaybookStep, ...]
    escalation_criteria: tuple[str, ...]
    interpretation_rules: tuple[str, ...]


COMMON_LAYER_ORDER: tuple[ChecklistGroup, ...] = (
    ChecklistGroup.SCOPE_IMPACT,
    ChecklistGroup.SIMPLE_USER_CHECKS,
    ChecklistGroup.DEVICE_CLIENT_APPLICATION,
    ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
    ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
)


LAYER_LABELS: dict[ChecklistGroup, str] = {
    ChecklistGroup.SCOPE_IMPACT: "scope_impact",
    ChecklistGroup.SIMPLE_USER_CHECKS: "simple_user_checks",
    ChecklistGroup.DEVICE_CLIENT_APPLICATION: "device_client_application",
    ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION: (
        "platform_permission_configuration"
    ),
    ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE: (
        "escalation_admin_infrastructure"
    ),
}


PRIVILEGED_ACCESS_TERMS: tuple[str, ...] = (
    "admin",
    "vendor",
    "log review",
    "logs",
    "infrastructure",
    "external-system",
    "external system",
    "system review",
    "tenant configuration",
    "admin portal",
    "print server",
)


DEFAULT_PRIVILEGED_ACCESS_REQUIREMENT = (
    "Admin, vendor, log, infrastructure, or external-system review is required."
)


def _requires_privileged_access(
    layer: ChecklistGroup,
    text: str,
    explicit: bool,
) -> bool:
    if explicit or layer == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE:
        return True
    lowered = text.lower()
    return any(term in lowered for term in PRIVILEGED_ACCESS_TERMS)


def _step(
    id: str,
    layer: ChecklistGroup,
    step: str,
    why: str,
    expected_result_type: ChecklistResultType,
    fail_cause: str,
    failure_results: tuple[ChecklistResultValue, ...] = (
        ChecklistResultValue.DOES_NOT_WORK,
    ),
    pass_results: tuple[ChecklistResultValue, ...] = (
        ChecklistResultValue.WORKS,
    ),
    ruled_out_cause: str | None = None,
    level1_actionable: bool | None = None,
    requires_privileged_access: bool = False,
    access_requirement: str | None = None,
    evidence_prompt: str | None = None,
    next_action: str | None = None,
    escalation_reason: str | None = None,
) -> PlaybookStep:
    is_privileged = _requires_privileged_access(
        layer,
        f"{step} {why} {fail_cause} {access_requirement or ''} {escalation_reason or ''}",
        requires_privileged_access,
    )
    if level1_actionable is None:
        level1_actionable = not is_privileged
    if is_privileged and access_requirement is None:
        access_requirement = DEFAULT_PRIVILEGED_ACCESS_REQUIREMENT
    if is_privileged and escalation_reason is None:
        escalation_reason = access_requirement
    return PlaybookStep(
        id=id,
        layer=layer,
        step=step,
        why=why,
        expected_result_type=expected_result_type,
        fail_cause=fail_cause,
        failure_results=failure_results,
        pass_results=pass_results,
        ruled_out_cause=ruled_out_cause,
        level1_actionable=level1_actionable,
        requires_privileged_access=is_privileged,
        access_requirement=access_requirement,
        evidence_prompt=evidence_prompt or f"Record evidence for: {step}",
        next_action=next_action,
        escalation_reason=escalation_reason,
    )


def _common_missing_information(subject: str) -> tuple[MissingInformation, ...]:
    return (
        MissingInformation(
            question=f"What exact error or symptom appears for the {subject} issue?",
            reason="Exact wording and timing are needed before narrowing the cause.",
        ),
        MissingInformation(
            question="Who is affected: one user, multiple users, a team, or everyone?",
            reason="Scope determines priority and whether escalation is appropriate.",
        ),
        MissingInformation(
            question="What changed recently on the device, account, application, or location?",
            reason="Recent changes often explain the next diagnostic layer.",
        ),
    )


def _generic_steps(prefix: str, subject: str) -> tuple[PlaybookStep, ...]:
    return (
        _step(
            id=f"{prefix}-scope",
            layer=ChecklistGroup.SCOPE_IMPACT,
            step=f"Confirm scope and impact for the {subject} issue.",
            why="Start by separating one-user issues from wider service impact.",
            expected_result_type=ChecklistResultType.TEXT,
            fail_cause=f"Unclear scope or impact for {subject}",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
        ),
        _step(
            id=f"{prefix}-basic-retry",
            layer=ChecklistGroup.SIMPLE_USER_CHECKS,
            step=f"Confirm the user repeated the basic {subject} action and captured the result.",
            why="Simple repeatable checks catch common user-side or transient failures.",
            expected_result_type=ChecklistResultType.WORKS_DOES_NOT_WORK,
            fail_cause=f"Basic user-side {subject} check still fails",
        ),
        _step(
            id=f"{prefix}-device-client",
            layer=ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            step=f"Check whether the device, client, or application behaves normally for {subject}.",
            why="Device or client symptoms should be considered before platform changes.",
            expected_result_type=ChecklistResultType.WORKS_DOES_NOT_WORK,
            fail_cause=f"Device, client, or application issue affecting {subject}",
        ),
        _step(
            id=f"{prefix}-platform-permission",
            layer=ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            step=f"Ask whether access, permission, configuration, or policy review is needed for {subject}.",
            why="This layer may require privileged review and should not be guessed.",
            expected_result_type=ChecklistResultType.YES_NO,
            fail_cause=f"Platform, permission, or configuration issue affecting {subject}",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
        ),
        _step(
            id=f"{prefix}-escalation",
            layer=ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            step=f"Escalate if admin, vendor, infrastructure, or external-system review is required for {subject}.",
            why="The mock provider cannot check real systems and should hand off when privileged review is needed.",
            expected_result_type=ChecklistResultType.NOT_APPLICABLE,
            fail_cause=f"{subject} requires admin or infrastructure review",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
        ),
    )


def _generic_playbook(
    category: IssueCategory,
    subcategory: str,
    keywords: tuple[str, ...],
    subject: str,
    causes: tuple[PlaybookCause, ...] | None = None,
    escalation_criteria: tuple[str, ...] | None = None,
) -> Playbook:
    return Playbook(
        issue_category=category,
        subcategory=subcategory,
        keywords=keywords,
        missing_information=_common_missing_information(subject),
        possible_causes=causes
        or (
            PlaybookCause(
                cause=f"{subcategory} user-side, device-side, or configuration issue",
                likelihood="medium",
                reason="The playbook starts broad and narrows from evidence.",
            ),
            PlaybookCause(
                cause=f"{subcategory} may require responsible team review",
                likelihood="medium",
                reason="Later diagnostic layers may require admin or vendor access.",
            ),
        ),
        checklist_steps=_generic_steps(category.value.replace("_", "-"), subject),
        escalation_criteria=escalation_criteria
        or (
            f"Escalate if multiple users are affected by {subject}.",
            f"Escalate if admin, vendor, infrastructure, or external-system review is required for {subject}.",
        ),
        interpretation_rules=(
            "If an early layer fails, focus there before moving deeper.",
            "If evidence is missing, ask for missing information instead of guessing.",
            "If privileged system access is required, recommend escalation.",
        ),
    )


VPN_REMOTE_ACCESS_PLAYBOOK = Playbook(
    issue_category=IssueCategory.VPN_REMOTE_ACCESS,
    subcategory="VPN",
    keywords=("vpn", "remote access", "remote-access"),
    missing_information=(
        MissingInformation(
            question="Is normal internet access working outside the VPN?",
            reason="This separates local connectivity from VPN-specific issues.",
        ),
        MissingInformation(
            question="Is this affecting one user or multiple users?",
            reason="Scope determines whether to continue user-side checks or escalate.",
        ),
        MissingInformation(
            question="What is the exact VPN error message?",
            reason="Exact wording helps identify authentication, MFA, client, or profile symptoms.",
        ),
        MissingInformation(
            question="What changed recently: password, MFA, device, network, or location?",
            reason="Recent changes often identify the next diagnostic layer.",
        ),
    ),
    possible_causes=(
        PlaybookCause(
            cause="Local internet or scope issue",
            likelihood="medium",
            reason="VPN troubleshooting should start by ruling out basic connectivity and scope.",
        ),
        PlaybookCause(
            cause="Saved credential, password, or MFA issue",
            likelihood="high",
            reason="VPN authentication wording often points to user-side sign-in checks.",
        ),
        PlaybookCause(
            cause="VPN client state or profile issue",
            likelihood="medium",
            reason="Client and profile checks come after basic and authentication layers.",
        ),
    ),
    checklist_steps=(
        _step(
            "vpn-confirm-internet",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm normal internet connectivity works outside the VPN.",
            "This rules out a general home or local network issue.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Local internet or basic connectivity issue",
            ruled_out_cause="General internet connectivity issue",
        ),
        _step(
            "vpn-confirm-scope",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether multiple users are affected, or whether this is one user only.",
            "Multiple affected users may indicate wider VPN or network impact.",
            ChecklistResultType.YES_NO,
            "Possible wider VPN or network impact",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Wider multi-user VPN outage",
        ),
        _step(
            "vpn-capture-error-message",
            ChecklistGroup.SCOPE_IMPACT,
            "Record the exact VPN error message shown to the user.",
            "The error wording guides the next layer without guessing.",
            ChecklistResultType.TEXT,
            "Missing VPN error detail",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing VPN error detail",
        ),
        _step(
            "vpn-recent-change",
            ChecklistGroup.SCOPE_IMPACT,
            "Ask whether there was a recent password, MFA, device, network, or location change.",
            "Recent changes often explain which layer should be checked next.",
            ChecklistResultType.YES_NO,
            "Recent change may explain the VPN issue",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Recent device, location, account, or network change",
        ),
        _step(
            "vpn-password-change",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Ask whether the user recently changed their password.",
            "A password change can leave saved VPN credentials out of date.",
            ChecklistResultType.YES_NO,
            "VPN authentication or saved credential issue",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Recent password change as trigger",
        ),
        _step(
            "vpn-saved-credentials",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Ask whether saved or cached VPN credentials may still use an old password.",
            "Cached or saved credentials can cause authentication failures.",
            ChecklistResultType.YES_NO,
            "VPN authentication or saved credential issue",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Saved or cached credential issue",
        ),
        _step(
            "vpn-mfa-behavior",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Confirm whether the MFA prompt appears and approval succeeds.",
            "MFA behavior helps narrow identity versus VPN client issues.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "VPN authentication or MFA issue",
            ruled_out_cause="MFA prompt or approval failure",
        ),
        _step(
            "vpn-client-opens",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Confirm the VPN client opens normally.",
            "A client startup issue points to the device or application layer.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "VPN client or VPN profile issue",
            ruled_out_cause="VPN client startup issue",
        ),
        _step(
            "vpn-profile-selected",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Confirm the expected VPN profile is selected.",
            "A missing or wrong profile can block remote access before authentication completes.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "VPN client or VPN profile issue",
            ruled_out_cause="Wrong or missing VPN profile",
        ),
        _step(
            "vpn-client-error",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Record any VPN client error message after the profile is selected.",
            "Client error details help decide whether Level 1 can continue or escalation is needed.",
            ChecklistResultType.TEXT,
            "Additional VPN client error",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Additional VPN client error",
        ),
        _step(
            "vpn-escalation-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate if local, authentication, and client checks pass but account permissions, "
                "MFA state, conditional access, certificate/profile provisioning, or VPN infrastructure review is needed."
            ),
            "These checks require admin access or external system review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Remote access configuration or account state requires admin review",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users are affected or a VPN outage is suspected.",
        "Escalate if account permissions, MFA state, conditional access, certificate/profile provisioning, or VPN infrastructure review is needed.",
    ),
    interpretation_rules=(
        "If scope_impact fails, focus on local connectivity or wider impact first.",
        "If scope_impact passes and simple_user_checks fail, diagnose authentication, saved credential, or MFA issues.",
        "If simple_user_checks pass and device_client_application fails, diagnose VPN client or profile issues.",
        "If local layers pass and the issue remains, escalate for admin or remote access review.",
    ),
)


NETWORK_WIFI_PLAYBOOK = Playbook(
    issue_category=IssueCategory.NETWORK_WIFI,
    subcategory="Wi-Fi/network",
    keywords=(
        "wifi",
        "wi-fi",
        "wireless",
        "ssid",
        "cannot connect to office wi-fi",
        "cannot connect to wifi",
    ),
    missing_information=(
        MissingInformation(
            question="Can the device see the Wi-Fi network?",
            reason="This separates SSID visibility from profile or password issues.",
        ),
        MissingInformation(
            question="Is the issue affecting only this device or other users too?",
            reason="Scope separates device configuration from wider wireless impact.",
        ),
        MissingInformation(
            question="Is there an error message?",
            reason="Exact wording can identify password, profile, or authentication failures.",
        ),
        MissingInformation(
            question="Did the device recently update or move location?",
            reason="Recent OS updates or location changes can affect Wi-Fi profiles and coverage.",
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Wi-Fi password/profile issue",
            "high",
            "The ticket describes a wireless connection failure.",
        ),
        PlaybookCause(
            "Device wireless adapter or OS network setting issue",
            "medium",
            "The issue may be specific to one device or operating system.",
        ),
        PlaybookCause(
            "Access point or wider network issue",
            "medium",
            "Other affected users would suggest infrastructure scope.",
        ),
    ),
    checklist_steps=(
        _step(
            "wifi-see-ssid",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether the device can see the SSID for the Wi-Fi network.",
            "If the SSID is not visible, coverage, adapter, or access point issues are more likely.",
            ChecklistResultType.YES_NO,
            "SSID visibility, wireless adapter, or access point issue",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
        ),
        _step(
            "wifi-other-devices",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether other devices or other users can connect to the same Wi-Fi.",
            "This separates one-device issues from wider wireless impact.",
            ChecklistResultType.YES_NO,
            "Possible wider Wi-Fi or access point issue",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
        ),
        _step(
            "wifi-forget-profile",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Forget and reconnect to the Wi-Fi profile if appropriate for the environment.",
            "A stale Wi-Fi profile or saved password can block connection.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Wi-Fi password or saved profile issue",
        ),
        _step(
            "wifi-hotspot-test",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Check whether normal internet works on another network or hotspot.",
            "This helps isolate the device from the office wireless network.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Device network stack or adapter issue",
        ),
        _step(
            "wifi-escalation",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            "Escalate if access point, network infrastructure, or admin review is needed.",
            "Infrastructure review is outside this mock provider.",
            ChecklistResultType.NOT_APPLICABLE,
            "Wi-Fi infrastructure requires review",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users are affected.",
        "Escalate if access point, network infrastructure, or admin review is needed.",
    ),
    interpretation_rules=(
        "If scope_impact fails, focus on SSID visibility and wider impact.",
        "If simple_user_checks fail, focus on Wi-Fi profile or password.",
        "If device_client_application fails, focus on local adapter or OS network state.",
    ),
)


SMALL_OFFICE_NETWORK_PLAYBOOK = Playbook(
    issue_category=IssueCategory.SMALL_OFFICE_NETWORK,
    subcategory="Small office network",
    keywords=("office network", "router", "switch", "lan", "small office"),
    missing_information=(
        MissingInformation(
            question="Is this affecting one device, several desks, or the whole office?",
            reason="Scope determines whether Level 1 should continue locally or escalate.",
        ),
        MissingInformation(
            question="Is Wi-Fi only, wired LAN only, or both affected?",
            reason="The affected network path points toward client, wireless, switch, router, or ISP layers.",
        ),
        MissingInformation(
            question="Do router, modem, or switch lights show any obvious fault?",
            reason="Visible physical status can identify a simple infrastructure symptom without claiming admin access.",
        ),
        MissingInformation(
            question="Does an affected device have a valid IP address, gateway access, and DNS resolution?",
            reason="IP, gateway, and DNS evidence separates local addressing from routing or name-resolution issues.",
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Single-device local network configuration issue",
            "medium",
            "A single affected device should be checked before infrastructure escalation.",
        ),
        PlaybookCause(
            "Router, modem, switch, DHCP, DNS, or ISP issue",
            "medium",
            "Multiple affected desks or network paths suggest shared infrastructure.",
        ),
        PlaybookCause(
            "DNS resolver or default gateway reachability issue",
            "medium",
            "Gateway and DNS checks narrow the network layer after physical checks pass.",
        ),
    ),
    checklist_steps=(
        _step(
            "small-office-network-scope",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether one device, several desks, or the whole office is affected.",
            "Scope separates a local device issue from a wider office network incident.",
            ChecklistResultType.TEXT,
            "Possible wider office network impact",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt="Record whether one device, several desks, or the whole office is affected.",
            next_action="Confirm whether one device, several desks, or the whole office is affected.",
        ),
        _step(
            "small-office-network-network-path",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether Wi-Fi only, wired LAN only, or both are affected.",
            "The affected path helps distinguish wireless, switch, router, or ISP scope.",
            ChecklistResultType.TEXT,
            "Unclear affected network path",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt="Record whether Wi-Fi only, wired LAN only, or both are affected.",
            next_action="Confirm whether Wi-Fi only, wired LAN only, or both are affected.",
        ),
        _step(
            "small-office-network-router-modem",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Check whether router or modem internet status lights show online/service.",
            "Visible router or modem status can reveal a WAN or ISP symptom before device checks.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Router, modem, WAN, or ISP connectivity issue",
            ruled_out_cause="Obvious router/modem service-light outage",
            evidence_prompt="Record router/modem service or internet light state if safely visible.",
            next_action="Check whether router or modem internet status lights show online/service.",
        ),
        _step(
            "small-office-network-switch-link",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Check switch power and affected port/link lights where safely visible.",
            "Power or link lights can reveal a switch, cable, or port problem without logging into equipment.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Switch power, cable, or port/link issue",
            ruled_out_cause="Obvious switch power or affected port/link-light issue",
            evidence_prompt="Record switch power and affected port/link-light state if safely visible.",
            next_action="Check switch power and affected port/link lights where safely visible.",
        ),
        _step(
            "small-office-network-ip-address",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Check whether the affected device has a valid IP address, not APIPA or self-assigned.",
            "Invalid or self-assigned addressing points to DHCP, VLAN, adapter, or local network issues.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "DHCP or local network addressing issue",
            ruled_out_cause="Invalid APIPA or self-assigned IP address",
            evidence_prompt="Record the device IP address and whether it is valid for the office network.",
            next_action="Check whether the affected device has a valid IP address, not APIPA or self-assigned.",
        ),
        _step(
            "small-office-network-gateway",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Check whether the default gateway is reachable from the affected device.",
            "Gateway reachability separates local LAN path issues from upstream or DNS issues.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Default gateway or local LAN reachability issue",
            ruled_out_cause="Default gateway reachability issue",
            evidence_prompt="Record whether the affected device can reach the default gateway.",
            next_action="Check whether the default gateway is reachable from the affected device.",
        ),
        _step(
            "small-office-network-dns",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Check whether DNS resolution works when gateway or internet path appears reachable.",
            "If the gateway is reachable but names do not resolve, DNS becomes the likely layer.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "DNS resolver or name-resolution configuration issue",
            ruled_out_cause="DNS resolver or name-resolution issue",
            evidence_prompt="Record whether DNS name lookup works after gateway reachability is known.",
            next_action="Check DNS resolution after confirming gateway reachability.",
        ),
        _step(
            "small-office-network-escalation",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            "Escalate for ISP, router, firewall, switch, DHCP, DNS, VLAN, or infrastructure review.",
            "These checks require privileged infrastructure access or external provider review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Small office network infrastructure review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "ISP, router, firewall, switch, DHCP, DNS, VLAN, or infrastructure review is required."
            ),
            evidence_prompt="Summarize completed Level 1 network checks before escalation.",
            next_action=(
                "Escalate for ISP, router, firewall, switch, DHCP, DNS, VLAN, or infrastructure review."
            ),
            escalation_reason=(
                "The remaining checks require ISP, router, firewall, switch, DHCP, DNS, VLAN, or infrastructure access."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if several desks, multiple users, or the whole office are affected.",
        "Escalate if ISP, router, firewall, switch, DHCP, DNS, VLAN, or infrastructure review is required.",
    ),
    interpretation_rules=(
        "Use scope_impact to decide whether this is local or wider infrastructure impact.",
        "Check visible router/modem and switch/link state before device network settings.",
        "Use IP, gateway, and DNS evidence to narrow DHCP, LAN, routing, or resolver causes.",
        "Do not claim router, firewall, switch, ISP, DHCP, DNS, or VLAN systems were checked unless evidence was recorded.",
    ),
)


VOIP_TELEPHONY_PLAYBOOK = Playbook(
    issue_category=IssueCategory.VOIP_TELEPHONY,
    subcategory="VoIP/telephony",
    keywords=("voip", "desk phone", "dial tone", "phone call", "telephony", "pbx"),
    missing_information=(
        MissingInformation(
            question="Is one desk phone, several phones, or the whole office affected?",
            reason="Scope separates a single handset issue from a telephony or network incident.",
        ),
        MissingInformation(
            question="Are internal calls, external calls, inbound calls, outbound calls, or all calls affected?",
            reason="The affected call path points toward phone, PBX, carrier, or network layers.",
        ),
        MissingInformation(
            question="Does the phone have power, link, IP address, and registration status?",
            reason="Power, link, addressing, and registration narrow the next diagnostic layer.",
        ),
        MissingInformation(
            question="Is the symptom no calls, one-way audio, dropped calls, delay, or choppy audio?",
            reason="Call quality symptoms point toward latency, jitter, packet loss, QoS, or network review.",
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Phone power, PoE, cable, or local link issue",
            "medium",
            "Single-phone failures often start with power and Ethernet link checks.",
        ),
        PlaybookCause(
            "Voice VLAN, DHCP, SIP/PBX registration, or extension issue",
            "medium",
            "A powered phone with network symptoms needs IP and registration evidence.",
        ),
        PlaybookCause(
            "Telephony network quality, PBX, carrier, or vendor issue",
            "medium",
            "Multiple phones or call quality symptoms may require network or telephony escalation.",
        ),
    ),
    checklist_steps=(
        _step(
            "voip-scope",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether one desk phone, several phones, or all phones are affected.",
            "Scope separates a single handset issue from wider telephony or network impact.",
            ChecklistResultType.TEXT,
            "Possible wider telephony or network impact",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt="Record whether one desk phone, several phones, or all phones are affected.",
            next_action="Confirm whether one desk phone, several phones, or all phones are affected.",
        ),
        _step(
            "voip-call-path",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether internal, external, inbound, outbound, or all calls are affected.",
            "Call-path evidence distinguishes local phone behavior from PBX, trunk, carrier, or routing issues.",
            ChecklistResultType.TEXT,
            "Unclear affected telephony call path",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt="Record which call paths are affected: internal, external, inbound, outbound, or all calls.",
            next_action="Confirm whether internal, external, inbound, outbound, or all calls are affected.",
        ),
        _step(
            "voip-power-poe",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Confirm the phone has power or PoE and boots normally.",
            "A phone that does not power on should be checked before PBX or network assumptions.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Phone power, PoE, adapter, or handset boot issue",
            ruled_out_cause="Phone power or PoE boot issue",
            evidence_prompt="Record whether the phone powers on and boots normally.",
            next_action="Confirm the phone has power or PoE and boots normally.",
        ),
        _step(
            "voip-cable-link",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Check Ethernet cable seating and phone/network link light.",
            "A missing link light points to cable, wall jack, switch port, or phone network port issues.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Ethernet cable, wall jack, switch port, or phone link issue",
            ruled_out_cause="Ethernet cable or phone/network link-light issue",
            evidence_prompt="Record Ethernet cable seating and whether a phone/network link light is present.",
            next_action="Check Ethernet cable seating and phone/network link light.",
        ),
        _step(
            "voip-ip-address",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Check whether the phone receives a valid IP address.",
            "A phone with no valid IP may have DHCP, voice VLAN, or local network addressing trouble.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "DHCP, voice VLAN, or phone network addressing issue",
            ruled_out_cause="Phone DHCP, voice VLAN, or IP addressing issue",
            evidence_prompt="Record the phone IP address or whether the display shows no valid IP.",
            next_action="Check whether the phone receives a valid IP address.",
        ),
        _step(
            "voip-call-quality",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Capture whether calls have delay, choppy audio, dropped calls, one-way audio, or packet loss symptoms.",
            "Call quality evidence points toward latency, jitter, packet loss, QoS, or network quality layers.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "VoIP call quality issue involving latency, jitter, packet loss, QoS, or network quality",
            ruled_out_cause="Latency, jitter, packet loss, QoS, or network quality symptom",
            evidence_prompt="Record delay, choppy audio, dropped calls, one-way audio, or packet loss symptoms.",
            next_action="Capture VoIP call quality symptoms such as delay, jitter, choppy audio, dropped calls, or one-way audio.",
        ),
        _step(
            "voip-registration",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            "Check whether the phone display shows registered or online with the PBX or phone system.",
            "Reading the phone display can identify registration state without checking PBX settings.",
            ChecklistResultType.YES_NO,
            "SIP, PBX, extension, or phone-system registration issue",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Phone display registration issue",
            evidence_prompt="Record whether the phone display shows registered, online, unregistered, or registration failed.",
            next_action="Check whether the phone display shows registered or online with the PBX or phone system.",
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "voip-escalation",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            "Escalate for PBX, SIP trunk, voice VLAN, QoS, carrier, vendor, or network team review.",
            "These checks require telephony admin, carrier, vendor, or network infrastructure review.",
            ChecklistResultType.NOT_APPLICABLE,
            "VoIP telephony infrastructure or vendor review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "PBX, SIP trunk, voice VLAN, QoS, carrier, vendor, or network team review is required."
            ),
            evidence_prompt="Summarize completed Level 1 phone, link, IP, registration, and call-quality evidence.",
            next_action=(
                "Escalate for PBX, SIP trunk, voice VLAN, QoS, carrier, vendor, or network team review."
            ),
            escalation_reason=(
                "The remaining checks require PBX, SIP trunk, voice VLAN, QoS, carrier, vendor, or network team access."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if several phones, a department, or all phones are affected.",
        "Escalate if PBX, SIP trunk, carrier, vendor, voice VLAN, QoS, or network team review is required.",
    ),
    interpretation_rules=(
        "Use scope and call path before assuming a handset, PBX, carrier, or network cause.",
        "Check power and Ethernet link before IP, registration, or call quality layers.",
        "Reading a phone display is Level 1 actionable; PBX/admin portal review requires escalation.",
        "Do not claim PBX, SIP trunk, carrier, QoS, or network systems were checked unless evidence was recorded.",
    ),
)


GENERAL_IT_PLAYBOOK = Playbook(
    issue_category=IssueCategory.GENERAL_IT,
    subcategory="General IT",
    keywords=(),
    missing_information=(
        MissingInformation(
            question=(
                "What exactly is not working: device, app, account, network, "
                "file, printer, display, meeting tool, or something else?"
            ),
            reason=(
                "Unknown issues should first be routed to the safest visible "
                "diagnostic family before choosing deeper checks."
            ),
        ),
        MissingInformation(
            question="What were you trying to do when it failed?",
            reason=(
                "The attempted action helps distinguish device, app, account, "
                "network, file, peripheral, or workflow problems."
            ),
        ),
        MissingInformation(
            question="Do you see an exact error message or warning?",
            reason=(
                "Visible messages are safe Level 1 evidence and can identify "
                "the responsible support owner without admin access."
            ),
        ),
        MissingInformation(
            question="Did it work before?",
            reason=(
                "A previously working path points toward a recent change, "
                "outage, device state, account state, or configuration boundary."
            ),
        ),
        MissingInformation(
            question="Is it affecting only you or other users too?",
            reason=(
                "Scope helps decide whether Level 1 should continue with local "
                "checks or prepare escalation with collected evidence."
            ),
        ),
        MissingInformation(
            question="Is it blocking work right now?",
            reason=(
                "Business impact and urgency should be confirmed before "
                "assigning priority or escalating."
            ),
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "More information needed before choosing a troubleshooting path",
            "medium",
            "The ticket does not contain enough specific evidence for a narrower playbook.",
        ),
        PlaybookCause(
            "Unknown issue may belong to a common IT support path",
            "medium",
            (
                "Safe clarification should determine whether this is closer to "
                "device, app, account, network, file, printer, display, meeting, "
                "security, vendor, or another owner."
            ),
        ),
        PlaybookCause(
            "Support review may be needed if the owner remains unclear",
            "medium",
            (
                "If broad clarification and safe local checks do not identify a "
                "Level 1 path, escalate with the collected evidence."
            ),
        ),
    ),
    checklist_steps=(
        _step(
            "general-capture-symptom",
            ChecklistGroup.SCOPE_IMPACT,
            "Clarify what exactly is not working and what the user was trying to do.",
            "The system should collect missing evidence before guessing.",
            ChecklistResultType.TEXT,
            "Insufficient symptom detail",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Record the affected thing, attempted action, exact symptom, "
                "exact wording of any visible error or warning, and when it "
                "started."
            ),
            next_action=(
                "Clarify what exactly is not working and what the user was "
                "trying to do before choosing a troubleshooting path."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "general-scope",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether this affects only the user, other users, one device, one place, or a wider workflow, and whether work is blocked.",
            "Scope, repeatability, and impact determine priority and next checks.",
            ChecklistResultType.TEXT,
            "Unclear scope, repeatability, or business impact",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing scope and impact evidence",
            evidence_prompt=(
                "Record whether this affects only the user, other users, one "
                "device, one place, or a wider business workflow, and whether "
                "work is blocked."
            ),
            next_action=(
                "Confirm whether the issue affects only you or other users too, "
                "and whether it is blocking work."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "general-recent-change",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Ask whether it worked before, what changed recently, and whether a workaround is available.",
            "Recent changes and workarounds guide urgency and the safest next check.",
            ChecklistResultType.TEXT,
            "Recent change or workaround needs clarification",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Record whether it worked before, what changed in the affected "
                "path, and whether the user has any temporary workaround."
            ),
            next_action=(
                "Record whether it worked before, what changed recently, and "
                "whether a workaround exists before deeper checks."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "general-issue-family",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Sort visible symptoms into the safest likely support family.",
            "The fallback path should sort observable evidence before guessing at a cause.",
            ChecklistResultType.TEXT,
            "Observable owner family is unclear",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Based only on visible evidence, record whether this seems closer "
                "to device, app, account, network, file, printer, display, "
                "meeting/audio-video, security, vendor, or unknown owner."
            ),
            next_action=(
                "Choose the safest matching local check based on the visible "
                "symptom family."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "general-device-app",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Try safe local isolation checks when appropriate.",
            (
                "Restarting the app, trying another browser, a private window, "
                "another device, another network, or a known-good device can "
                "separate local behavior from wider behavior."
            ),
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Device, browser, or application-specific issue",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Single local device, browser, or application path",
            evidence_prompt=(
                "Record whether a restart, alternate browser, private window, "
                "another device, another network, or known-good device changes "
                "the result."
            ),
            next_action=(
                "Try a safe local isolation check such as alternate browser, "
                "private window, another device, another network, or known-good "
                "device where appropriate."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "general-user-visible-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            "Record user-facing access, account, network, security, or service messages.",
            (
                "Visible messages help identify the responsible owner without "
                "claiming unseen system checks."
            ),
            ChecklistResultType.TEXT,
            "User-facing ownership or access indicators are unclear",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Capture visible messages such as access denied, permission "
                "required, account locked, security warning, vendor outage banner, "
                "or service unavailable. Do not state that admin portals, logs, "
                "MDM, PBX, Microsoft 365, Entra ID, Intune, VPN logs, cloud "
                "consoles, or vendor dashboards were checked."
            ),
            next_action=(
                "Record only user-visible boundary evidence, then decide whether "
                "a responsible owner review is needed."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "general-escalation",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            "Escalate to the responsible team if the system, vendor, or admin owner must review it.",
            "The mock provider cannot inspect external systems.",
            ChecklistResultType.NOT_APPLICABLE,
            "Responsible team review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            evidence_prompt=(
                "Prepare the exact symptom, scope, recent change, safe local "
                "checks tried, and user-visible boundary evidence for escalation."
            ),
            next_action=(
                "Escalate to the responsible owner with recorded evidence when "
                "ownership is unclear or privileged review is required."
            ),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Responsible owner, admin, vendor, log, infrastructure, or "
                "external-system review is required."
            ),
            escalation_reason=(
                "The issue needs responsible owner or privileged review beyond "
                "safe Level 1 checks."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users are affected or business impact is high.",
        "Escalate when the owner is unclear after safe Level 1 evidence gathering.",
        "Escalate to the responsible team if admin, vendor, or external-system review is required.",
    ),
    interpretation_rules=(
        "Ask missing-information questions before assigning a specific cause.",
        "Use scope_impact evidence to decide priority and whether escalation is needed.",
        "Do not guess internal system behavior without evidence.",
        "Only record user-visible messages unless a real integration supplies system evidence.",
    ),
)


TEAMS_AUDIO_VIDEO_PLAYBOOK = Playbook(
    issue_category=IssueCategory.TEAMS_AUDIO_VIDEO,
    subcategory="Teams audio/video",
    keywords=(
        "teams audio",
        "teams meeting audio",
        "meeting audio",
        "audio input",
        "audio output",
        "microphone",
        "mic",
        "camera",
        "webcam",
        "speaker",
        "teams headset",
        "cannot hear",
        "can't hear",
        "people cannot hear",
        "others cannot hear",
        "camera not detected",
    ),
    missing_information=(
        MissingInformation(
            question=(
                "What exact Teams audio or video symptom is occurring, and "
                "what business work is blocked?"
            ),
            reason=(
                "Microphone, camera, speaker, input, output, and device "
                "detection symptoms need different safe checks."
            ),
        ),
        MissingInformation(
            question=(
                "Is this affecting one user, one meeting, multiple users, or "
                "all Teams meetings?"
            ),
            reason="Scope separates local device issues from meeting or service-impact symptoms.",
        ),
        MissingInformation(
            question=(
                "Which microphone, camera, speaker, headset, or audio device "
                "is selected in Teams?"
            ),
            reason="Wrong Teams device selection is a common Level 1 cause.",
        ),
        MissingInformation(
            question=(
                "Does the same microphone, camera, speaker, or headset work "
                "in another app and in Teams browser versus desktop?"
            ),
            reason=(
                "Other-app and browser-versus-desktop comparisons isolate "
                "Teams client symptoms from OS or hardware symptoms."
            ),
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Incorrect Teams microphone, camera, speaker, or headset selection",
            "high",
            "Teams may be using a different audio or video device than the user expects.",
        ),
        PlaybookCause(
            "Teams desktop client, settings, profile, cache, or browser/Desktop difference",
            "medium",
            "If the device works elsewhere, Teams client or profile state is more likely.",
        ),
        PlaybookCause(
            "{operating_system} microphone, camera, speaker, device setting, or hardware issue",
            "medium",
            "If the device fails across apps, OS permission, device detection, or hardware is more likely.",
        ),
        PlaybookCause(
            "Teams policy, tenant configuration, device management, or M365 admin review may be required",
            "medium",
            "Some symptoms require privileged review after Level 1 evidence is collected.",
        ),
    ),
    checklist_steps=(
        _step(
            "teams-confirm-symptom",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm the exact Teams audio or video symptom and business "
                "impact: microphone, camera, speaker, audio input, audio "
                "output, headset, or device detection."
            ),
            "The first step is to identify the failing Teams meeting workflow.",
            ChecklistResultType.TEXT,
            "Unclear Teams audio/video symptom and business impact",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing Teams audio/video symptom and business impact",
            evidence_prompt=(
                "Record the exact Teams symptom and business impact, including "
                "microphone, camera, speaker, audio input, audio output, "
                "headset, or device detection."
            ),
            next_action=(
                "Confirm the exact Teams audio/video symptom and business "
                "impact before moving deeper."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "teams-affected-scope",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm whether this affects one user, one meeting, multiple "
                "users, or all Teams meetings."
            ),
            "Scope determines whether Level 1 should continue local checks or prepare escalation evidence.",
            ChecklistResultType.TEXT,
            "Unclear Teams audio/video affected scope",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing Teams audio/video affected-scope evidence",
            evidence_prompt=(
                "Record affected scope: one user, one meeting, multiple users, "
                "all meetings, or a specific meeting organizer or room."
            ),
            next_action=(
                "Confirm whether the issue affects one user, one meeting, "
                "multiple users, or all Teams meetings."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "teams-selected-device",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Confirm the selected microphone, camera, speaker, headset, "
                "or audio device matches the expected device in Teams device settings."
            ),
            "Wrong selected devices are common and safe for Level 1 to verify.",
            ChecklistResultType.YES_NO,
            "Incorrect Teams microphone, camera, speaker, headset, or selected device",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Incorrect Teams selected microphone, camera, speaker, headset, or audio device",
            evidence_prompt=(
                "Record the selected Teams microphone, camera, speaker, "
                "headset, and whether they match the expected devices."
            ),
            next_action=(
                "Verify the expected microphone, camera, speaker, or headset "
                "is selected in Teams device settings."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "teams-other-app-comparison",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Test the same microphone, camera, speaker, or headset in "
                "another app."
            ),
            "A successful other-app test points back to Teams client settings rather than hardware.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Teams client, meeting device setting, or Teams app-specific issue",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Teams-only audio/video issue isolated from other apps",
            evidence_prompt=(
                "Record whether the same microphone, camera, speaker, or "
                "headset works in another safe app such as Camera, Voice "
                "Recorder, browser test page, or system sound settings."
            ),
            next_action=(
                "Compare the same audio/video device in another safe app to "
                "separate Teams-specific behavior from device or OS behavior."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "teams-browser-desktop-comparison",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Compare Teams browser behavior with the Teams desktop app where appropriate.",
            "Browser versus desktop comparison can isolate Teams desktop client, profile, or cache symptoms.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Teams desktop client, profile, cache, or browser-versus-desktop issue",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Teams desktop-only client, profile, or cache issue",
            evidence_prompt=(
                "Record whether Teams browser works while Teams desktop fails, "
                "or whether the same issue appears in both clients."
            ),
            next_action=(
                "Compare Teams browser and Teams desktop for the same meeting "
                "audio/video symptom."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "teams-os-permission-device-setting",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "{teams_os_permission_step}",
            "Operating systems and device settings can block microphone, camera, speaker, or headset access.",
            ChecklistResultType.YES_NO,
            "{operating_system} permission, device detection, OS setting, or hardware issue",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Operating system permission, device detection, OS setting, or hardware issue",
            evidence_prompt=(
                "Record visible OS-level permission and device-setting evidence "
                "for microphone, camera, speaker, headset, and device detection. "
                "Do not claim Intune, hardware inventory, logs, or device "
                "management systems were checked."
            ),
            next_action=(
                "Check visible OS microphone/camera permission and device "
                "settings for the affected audio/video device."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "teams-visible-policy-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            (
                "Record visible Teams meeting, device, policy, permission, "
                "or organization-setting messages only."
            ),
            "Visible boundary messages prepare a clean escalation without claiming admin-system checks.",
            ChecklistResultType.TEXT,
            "Visible Teams policy, meeting, device, or organization boundary needs review",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing visible Teams policy, meeting, device, or organization-boundary evidence",
            evidence_prompt=(
                "Capture visible messages only, such as device disabled, "
                "camera blocked, microphone blocked, meeting policy restriction, "
                "organization setting, or exact Teams error. Do not claim Teams "
                "admin center, M365 admin center, tenant policy, Intune, device "
                "management, meeting room systems, logs, or hardware inventory checks."
            ),
            next_action=(
                "Record only user-visible Teams, device, permission, policy, "
                "or organization-boundary evidence before escalation."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "teams-admin-desktop-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate for Teams admin center, M365 admin center, tenant "
                "policy, Intune, device management, meeting room system, log, "
                "hardware inventory, Desktop support, or hardware review."
            ),
            "These checks require Teams admin, M365 admin, Desktop support, device management, or hardware review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Teams policy, tenant configuration, device management, Desktop support, or hardware review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Teams admin, M365 admin, Desktop support, device management, "
                "or hardware review is required."
            ),
            evidence_prompt=(
                "Summarize collected symptom, business impact, scope, selected "
                "device, other-app comparison, browser/Desktop comparison, OS "
                "permission, and visible Teams boundary evidence."
            ),
            next_action=(
                "Summarize the collected Teams Audio / Video evidence and "
                "escalate to Teams admin, M365 admin, Desktop support, or "
                "device management for privileged review."
            ),
            escalation_reason=(
                "The remaining checks require Teams admin, M365 admin, Desktop "
                "support, device management, or hardware review."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users or all meetings are affected after local evidence is collected.",
        "Escalate if local selected-device, other-app, browser/Desktop, and OS permission checks do not isolate the issue.",
        "Escalate if Teams admin center, M365 admin center, tenant policy, Intune, device management, meeting room systems, logs, hardware inventory, Desktop support, or hardware review is required.",
    ),
    interpretation_rules=(
        "Confirm exact symptom, business impact, affected scope, and selected device before deeper checks.",
        "Use other-app and Teams browser/Desktop comparisons to isolate Teams client behavior from OS or hardware behavior.",
        "Use only user-visible OS permission, device setting, Teams error, and boundary evidence for Level 1 diagnosis.",
        "Do not claim Teams admin center, M365 admin center, tenant policy, Intune, device management, meeting room systems, logs, or hardware inventory were checked without a real integration.",
        "If safe local checks pass and privileged Teams, M365, Desktop, device management, or hardware review is needed, escalate with collected evidence.",
    ),
)


PRINTER_PLAYBOOK = Playbook(
    issue_category=IssueCategory.PRINTER,
    subcategory="Printer/scanner",
    keywords=(
        "printer",
        "print",
        "printing",
        "print job",
        "print queue",
        "scanner",
        "scan-to-email",
        "scan to email",
        "scan-to-folder",
        "scan to folder",
        "mfd",
        "multifunction device",
    ),
    missing_information=(
        MissingInformation(
            question=(
                "What exact printer or scanner symptom is occurring, and what "
                "business work is blocked?"
            ),
            reason=(
                "Print, scan, copy, scan-to-email, and scan-to-folder symptoms "
                "have different safe checks and escalation paths."
            ),
        ),
        MissingInformation(
            question=(
                "Can other users print or scan to the same printer or scanner, "
                "or is this affecting only one user or device?"
            ),
            reason="Scope separates local device issues from shared printer or scanner impact.",
        ),
        MissingInformation(
            question=(
                "Which printer or scanner, queue, and scan destination is selected?"
            ),
            reason="Wrong queues, stale printer objects, or wrong scan destinations are common Level 1 causes.",
        ),
        MissingInformation(
            question=(
                "What visible device, queue, scanner, or destination error appears?"
            ),
            reason=(
                "Visible status and error evidence helps decide whether Level 1 "
                "can continue or escalation is needed."
            ),
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Wrong selected printer, scanner, queue, or scan destination",
            "high",
            "Users may print or scan through the wrong queue, stale object, or destination.",
        ),
        PlaybookCause(
            "Visible printer or MFD state such as offline, paper, toner, jam, or device error",
            "medium",
            "Physical or front-panel status can block print, copy, or scan output.",
        ),
        PlaybookCause(
            "Local queue, driver, user device, or client path issue",
            "medium",
            "A one-user or one-device issue often starts with local queue and client evidence.",
        ),
        PlaybookCause(
            "Shared print service, scanner destination, print server, MFD, or admin review may be required",
            "medium",
            "Some printer and scanner symptoms require privileged review after safe evidence is collected.",
        ),
    ),
    checklist_steps=(
        _step(
            "printer-confirm-symptom",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm the exact printer or scanner symptom and business "
                "impact: print, scan, copy, scan-to-email, or scan-to-folder."
            ),
            "The first step is to identify which output or scanning workflow is failing.",
            ChecklistResultType.TEXT,
            "Unclear printer or scanner symptom and business impact",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing printer or scanner symptom and business impact",
            evidence_prompt=(
                "Record the exact symptom and business impact, including "
                "print, scan, copy, scan-to-email, scan-to-folder, stuck job, "
                "offline device, or visible error."
            ),
            next_action=(
                "Confirm the exact printer/scanner symptom and business impact "
                "before moving deeper."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "printer-affected-scope",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm whether this affects one user, one device, multiple "
                "users, or everyone using the same printer, scanner, queue, or "
                "destination."
            ),
            "Scope separates local device paths from shared printer, scanner, or print-service impact.",
            ChecklistResultType.TEXT,
            "Shared printer, scanner, queue, or print service impact",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing printer or scanner affected-scope evidence",
            evidence_prompt=(
                "Record whether one user, one device, multiple users, or "
                "everyone is affected, and whether the same printer, scanner, "
                "queue, or destination is involved."
            ),
            next_action=(
                "Confirm affected scope across users, devices, printer/scanner, "
                "queue, and destination."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "printer-selected-device-destination",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Confirm the selected printer, scanner, queue, and scan target "
                "destination are correct."
            ),
            "Wrong selected devices, stale queues, and wrong scan destinations are safe Level 1 checks.",
            ChecklistResultType.YES_NO,
            "Wrong selected printer, scanner, queue, or scan destination",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Wrong selected printer, scanner, queue, or scan destination",
            evidence_prompt=(
                "Record the selected printer or scanner, queue name, device "
                "name, and scan target destination for scan-to-email or "
                "scan-to-folder."
            ),
            next_action=(
                "Verify the selected printer/scanner, queue, and scan target "
                "destination are correct."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "printer-visible-device-status",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Check visible printer or MFD status: online, ready, paper, "
                "toner, jam, offline, or front-panel error."
            ),
            "Visible device state can block printing, copying, or scanning before deeper checks.",
            ChecklistResultType.YES_NO,
            "Visible printer or MFD offline, paper, toner, jam, or device error",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Printer or MFD offline, paper, toner, jam, or visible device error",
            evidence_prompt=(
                "Record visible device status only: online, ready, offline, "
                "paper, toner, jam, tray, scanner error, or front-panel message."
            ),
            next_action=(
                "Check visible printer/MFD status for offline, paper, toner, "
                "jam, scanner, or front-panel errors."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "printer-local-queue-client",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Check whether the print job is stuck in the local print queue or client path.",
            "A local queue or client issue can block printing from one user device.",
            ChecklistResultType.YES_NO,
            "Stuck local print queue or local device/client print path issue",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Stuck local print queue or local device/client print path issue",
            evidence_prompt=(
                "Record visible local queue/client evidence only, such as "
                "stuck job, paused queue, offline queue, app-specific print "
                "failure, or whether print preview creates the job."
            ),
            next_action=(
                "Check visible local print queue and client path evidence for "
                "stuck jobs or paused/offline queues."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "printer-known-working-comparison",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Compare with another known working user or device for the same "
                "printer, scanner, queue, or destination where appropriate."
            ),
            "A known-working comparison separates local user/device paths from shared device impact.",
            ChecklistResultType.YES_NO,
            "Local user, device, driver, queue mapping, or client path issue",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Shared printer, scanner, queue, or destination unavailable to another user/device",
            evidence_prompt=(
                "Record whether another known working user or device can print "
                "or scan to the same device, queue, or destination. Do not "
                "expose sensitive scanned content."
            ),
            next_action=(
                "Compare with another known working user or device for the same "
                "printer/scanner path where appropriate."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "printer-visible-platform-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            (
                "Record visible driver, queue, scanner destination, scan-to-email, "
                "scan-to-folder, mailbox, or permission boundary messages only."
            ),
            "Visible boundary evidence prepares a clean handoff without claiming backend system checks.",
            ChecklistResultType.TEXT,
            "Visible scanner destination, queue, driver, mailbox, folder, or permission boundary needs review",
            failure_results=(ChecklistResultValue.WORKS, ChecklistResultValue.USER_UNSURE),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Missing visible driver, queue, scanner destination, mailbox, folder, or permission boundary evidence",
            evidence_prompt=(
                "Capture visible messages only, such as driver unavailable, "
                "queue unavailable, scan destination failed, scan-to-email "
                "failed, scan-to-folder failed, access denied, mailbox rejected, "
                "or exact MFD error. Do not claim print servers, printer admin "
                "portals, MFD admin panels, driver deployment systems, Intune, "
                "MDM, Windows print server logs, spooler logs, scanner shares, "
                "mailbox scan settings, or device inventory were checked."
            ),
            next_action=(
                "Record only user-visible driver, queue, scanner destination, "
                "mailbox, folder, or permission boundary evidence before escalation."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "printer-admin-vendor-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate for print server, printer admin portal, MFD admin "
                "panel, driver deployment, Intune, MDM, Windows print server "
                "log, spooler log, scanner share, mailbox scan setting, device "
                "inventory, Desktop support, Print team, File admin, M365, or "
                "MFD vendor review."
            ),
            "These checks require Desktop support, Print team, MFD vendor, M365, File admin, or privileged system review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Print server, driver deployment, scanner destination, MFD, mailbox, file, or device administration review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Desktop support, Print team, MFD vendor, M365, File admin, "
                "or privileged print/scanner review is required."
            ),
            evidence_prompt=(
                "Summarize collected symptom, business impact, affected scope, "
                "selected device/destination, visible device status, local queue, "
                "known-working comparison, and visible platform-boundary evidence."
            ),
            next_action=(
                "Summarize the collected Printer / Scanner evidence and "
                "escalate to Desktop support, Print team, MFD vendor, M365, "
                "or File admin for privileged review."
            ),
            escalation_reason=(
                "The remaining checks require Desktop support, Print team, "
                "MFD vendor, M365, File admin, or privileged print/scanner review."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users or everyone is affected by the same printer, scanner, queue, or destination.",
        "Escalate if safe selected-device, visible-status, local queue, and known-working comparisons do not isolate the issue.",
        "Escalate if print server, printer admin portal, MFD admin panel, driver deployment, Intune, MDM, Windows print server logs, spooler logs, scanner shares, mailbox scan settings, device inventory, Desktop support, Print team, M365, File admin, or MFD vendor review is required.",
    ),
    interpretation_rules=(
        "Confirm exact printer/scanner symptom, business impact, affected scope, and selected device/destination before deeper checks.",
        "Use visible device status, local queue, and known-working comparisons before admin escalation.",
        "Use only user-visible device, queue, scanner, destination, mailbox, folder, and permission evidence for Level 1 diagnosis.",
        "Do not claim print servers, printer admin portals, MFD admin panels, driver deployment systems, Intune, MDM, Windows print server logs, spooler logs, scanner shares, mailbox scan settings, or device inventory were checked without a real integration.",
        "If safe local checks pass and privileged print, scanner, MFD, M365, or file-admin review is needed, escalate with collected evidence.",
    ),
)


OUTLOOK_PLAYBOOK = Playbook(
    issue_category=IssueCategory.EMAIL_OUTLOOK,
    subcategory="Outlook/email",
    keywords=(
        "outlook",
        "email",
        "mail",
        "mailbox",
        "webmail",
        "outbox",
        "sync error",
        "mail delivery",
        "shared mailbox",
    ),
    missing_information=(
        MissingInformation(
            question=(
                "What exact Outlook or email symptom is occurring, and what "
                "business work is blocked?"
            ),
            reason=(
                "Sending, receiving, sync, access, outbox, and shared-mailbox "
                "symptoms have different safe checks and escalation paths."
            ),
        ),
        MissingInformation(
            question=(
                "Is this affecting one user, multiple users, one sender, one "
                "recipient, or all mail?"
            ),
            reason=(
                "Scope separates local Outlook issues from mailbox, delivery, "
                "or service-impact symptoms."
            ),
        ),
        MissingInformation(
            question=(
                "Does the same mailbox work in webmail, and what visible error "
                "or timing detail appears?"
            ),
            reason=(
                "Webmail comparison and visible messages help isolate Outlook "
                "desktop from mailbox or delivery boundaries."
            ),
        ),
        MissingInformation(
            question=(
                "Was there a recent password, account, Outlook profile, device, "
                "or mailbox access change?"
            ),
            reason=(
                "Recent user-side changes often explain Outlook sync, access, "
                "or outbox symptoms without requiring admin checks."
            ),
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Outlook desktop client, profile, cache, sync, or outbox issue",
            "medium",
            "Outlook symptoms should be compared with webmail before assuming a service-side cause.",
        ),
        PlaybookCause(
            "Recent password, account, profile, device, or mailbox access change",
            "medium",
            "Recent changes commonly explain one-user Outlook and email access symptoms.",
        ),
        PlaybookCause(
            "Mailbox, delivery, quarantine, rule, mail-flow, or policy review may be required",
            "medium",
            "If safe local checks do not isolate the issue, Email or M365 admin review may be required.",
        ),
    ),
    checklist_steps=(
        _step(
            "outlook-confirm-symptom",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm the exact Outlook or email symptom and business "
                "impact: send, receive, sync, access, mailbox-specific, or "
                "stuck outbox."
            ),
            "The first step is to identify what mail workflow is actually failing.",
            ChecklistResultType.TEXT,
            "Unclear Outlook or email symptom and business impact",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing Outlook or email symptom and business impact",
            evidence_prompt=(
                "Record the exact symptom and business impact, including "
                "whether this is send, receive, sync, access, mailbox-specific, "
                "or stuck outbox."
            ),
            next_action=(
                "Confirm the exact Outlook or email symptom and business "
                "impact before moving deeper."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "outlook-affected-scope",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm whether this affects one user, multiple users, one "
                "sender, one recipient, or all mail."
            ),
            "Scope determines whether Level 1 should continue local checks or prepare escalation evidence.",
            ChecklistResultType.TEXT,
            "Unclear Outlook or email affected scope",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing Outlook or email affected-scope evidence",
            evidence_prompt=(
                "Record affected scope: one user, multiple users, one sender, "
                "one recipient, all senders or recipients, or all mail."
            ),
            next_action=(
                "Confirm affected scope across users, senders, recipients, and "
                "mail directions."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "outlook-send-receive-direction",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Confirm whether sending, receiving, both directions, sync, "
                "mailbox access, or outbox delivery is affected."
            ),
            "Mail direction and symptom type guide the next safe check.",
            ChecklistResultType.TEXT,
            "Unclear email send/receive direction",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing send, receive, sync, access, or outbox direction evidence",
            evidence_prompt=(
                "Record whether sending, receiving, both directions, sync, "
                "mailbox access, or outbox delivery is affected."
            ),
            next_action=(
                "Confirm whether the issue affects sending, receiving, sync, "
                "mailbox access, or outbox delivery."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "outlook-recent-change",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Ask whether there was a recent password, account, Outlook "
                "profile, device, or mailbox access change."
            ),
            "Recent user-side or profile changes can explain Outlook symptoms before deeper review.",
            ChecklistResultType.YES_NO,
            "Recent password, account, Outlook profile, device, or mailbox access change",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Recent password, account, profile, device, or mailbox access change",
            evidence_prompt=(
                "Record any recent password, account, Outlook profile, device, "
                "mailbox access, or shared-mailbox change."
            ),
            next_action=(
                "Confirm recent password, account, Outlook profile, device, or "
                "mailbox access changes."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "outlook-client-webmail-comparison",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            "Compare Outlook desktop app behavior with webmail for the same mailbox.",
            "If webmail works while Outlook desktop fails, the issue is likely local to the client, profile, or cache.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Outlook desktop client, profile, cache, or local app issue",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Outlook desktop-only client, profile, or cache issue",
            evidence_prompt=(
                "Record whether webmail works for the same mailbox. If webmail "
                "works but Outlook desktop fails, capture that client-isolation evidence."
            ),
            next_action=(
                "Compare the same mailbox in webmail and Outlook desktop to "
                "isolate local client behavior."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "outlook-client-profile-outbox-sync",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Record Outlook client state: connected or offline, visible sync "
                "error, stuck outbox, profile behavior, or cached-mode symptom."
            ),
            "Visible client state helps isolate safe Level 1 Outlook profile or outbox evidence.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Outlook profile, cached mode, sync, offline, or outbox issue",
            failure_results=(ChecklistResultValue.DOES_NOT_WORK,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Outlook profile, cached mode, sync, offline, or outbox issue",
            evidence_prompt=(
                "Record visible Outlook client state only: connected, offline, "
                "sync error, stuck outbox, profile behavior, cached-mode symptom, "
                "and exact timing."
            ),
            next_action=(
                "Capture visible Outlook client state, sync error, outbox, "
                "profile, and timing evidence."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "outlook-visible-mailbox-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            (
                "Record visible mailbox, delivery, quarantine notice, rule, "
                "shared-mailbox access, or policy boundary messages only."
            ),
            (
                "Visible boundary evidence prepares a clean handoff without "
                "claiming backend mail-system checks."
            ),
            ChecklistResultType.TEXT,
            "Visible mailbox, delivery, rule, quarantine, access, or policy boundary needs review",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing visible mailbox, delivery, access, or policy boundary evidence",
            evidence_prompt=(
                "Capture visible messages only, such as mailbox access denied, "
                "shared mailbox unavailable, delivery failure, quarantine notice, "
                "rule-related behavior, policy warning, or exact error. Do not "
                "claim M365 admin center, mail trace, quarantine, mailbox rules, "
                "Exchange logs, Entra ID, or tenant policy checks."
            ),
            next_action=(
                "Record only user-visible mailbox, delivery, access, or policy "
                "boundary evidence before deciding whether escalation is needed."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "outlook-email-admin-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate for mailbox access, mail-flow, quarantine, mailbox "
                "rule, mail trace, Exchange log, Entra ID, M365 admin center, "
                "or tenant policy review."
            ),
            "These checks require Email or M365 admin privileged review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Mailbox, mail-flow, quarantine, rule, trace, log, identity, or policy review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Email / M365 admin privileged review is required."
            ),
            evidence_prompt=(
                "Summarize collected symptom, business impact, affected scope, "
                "send/receive direction, recent change, webmail comparison, "
                "Outlook client state, visible error, and mailbox-boundary evidence."
            ),
            next_action=(
                "Summarize the collected Outlook / Email evidence and escalate "
                "to Email / M365 admin for privileged review."
            ),
            escalation_reason=(
                "The remaining checks require Email / M365 admin privileged review."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users, all mail, or shared mailbox access appears affected after scope is confirmed.",
        "Escalate if webmail is also affected and safe Outlook client checks do not isolate the issue.",
        "Escalate if mailbox access, mail-flow, quarantine, mailbox rule, mail trace, Exchange log, Entra ID, M365 admin center, or tenant policy review is required.",
    ),
    interpretation_rules=(
        "Confirm exact symptom, business impact, affected scope, and send/receive direction before deeper checks.",
        "Compare Outlook desktop with webmail before assuming mailbox or mail-flow causes.",
        "Use only user-visible client, outbox, sync, error, and mailbox-boundary evidence for Level 1 diagnosis.",
        "Do not claim M365 admin center, mail trace, quarantine, mailbox rules, Exchange logs, Entra ID, or tenant policy were checked without a real integration.",
        "If safe local checks pass and privileged Email or M365 review is needed, escalate with collected evidence.",
    ),
)


LOGIN_ACCOUNT_PLAYBOOK = Playbook(
    issue_category=IssueCategory.LOGIN_ACCOUNT,
    subcategory="Login/account",
    keywords=(
        "login",
        "log in",
        "sign in",
        "sign-in",
        "signin",
        "cannot sign in",
        "password",
        "mfa",
        "account",
        "account locked",
        "locked out",
        "conditional access",
        "number matching",
    ),
    missing_information=(
        MissingInformation(
            question=(
                "Which exact platform, application, and account type is the user "
                "trying to access?"
            ),
            reason=(
                "Microsoft 365, Windows/AD, Okta, VPN, SaaS, and internal-system "
                "sign-ins may have different owners and escalation paths."
            ),
        ),
        MissingInformation(
            question=(
                "What exact visible sign-in error appears, and where in the "
                "sign-in flow does it fail?"
            ),
            reason=(
                "Exact wording separates password, MFA, account lock, policy, "
                "license, permission, and client symptoms."
            ),
        ),
        MissingInformation(
            question="Is this affecting one user or multiple users?",
            reason=(
                "Scope determines whether Level 1 should continue with user-visible "
                "checks or prepare a wider identity escalation."
            ),
        ),
        MissingInformation(
            question="Was there a recent password reset, device change, or MFA phone change?",
            reason=(
                "Recent account and MFA changes often explain user-side sign-in "
                "failures without requiring backend checks."
            ),
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Authentication issue in {account_platform}",
            "medium",
            "Login and account wording appears in the ticket.",
        ),
        PlaybookCause(
            "Recent password reset or saved credential issue",
            "medium",
            "Password changes can leave apps, browsers, or clients using stale credentials.",
        ),
        PlaybookCause(
            "User-visible MFA prompt or approval issue",
            "medium",
            "MFA prompts, number matching, changed phones, or denied approvals are common sign-in blockers.",
        ),
        PlaybookCause(
            "Identity account, policy, license, or permission review may be required",
            "medium",
            "Some login failures require privileged identity review after Level 1 evidence is collected.",
        ),
    ),
    checklist_steps=(
        _step(
            "login-confirm-platform",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm the exact platform, application, account type, and where "
                "sign-in fails."
            ),
            "This prevents applying the wrong identity troubleshooting path.",
            ChecklistResultType.TEXT,
            "Unclear login platform, application, account type, or sign-in point",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing login platform, application, account type, or sign-in point",
            evidence_prompt=(
                "Record the exact platform, application, account type, and where "
                "the sign-in flow fails."
            ),
            next_action=(
                "Confirm the exact platform, application, account type, and where "
                "sign-in fails."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "login-confirm-scope-error",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Record whether one user or multiple users are affected and the "
                "exact visible sign-in error."
            ),
            (
                "Scope and exact error wording separate user-side issues from "
                "possible wider identity impact."
            ),
            ChecklistResultType.TEXT,
            "Missing login scope or exact visible sign-in error",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing login scope or exact visible sign-in error",
            evidence_prompt=(
                "Record the exact visible error and affected scope, such as "
                "incorrect password, account locked, MFA denied, Conditional "
                "Access blocked, license required, access denied, one user, or "
                "multiple users. Record only user-visible evidence."
            ),
            next_action=(
                "Capture the exact visible sign-in error and whether one user or "
                "multiple users are affected."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "login-recent-password-change",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Ask whether the password was recently changed or reset and "
                "whether saved credentials may be stale."
            ),
            "Recent password changes can leave browsers, apps, and clients using old credentials.",
            ChecklistResultType.YES_NO,
            "Recent password reset or saved credential issue",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Recent password reset or stale saved credential trigger",
            evidence_prompt=(
                "Record password reset timing and whether any browser, app, or "
                "client may still be using a saved old password."
            ),
            next_action=(
                "Guide a safe user-side credential check, such as retrying with "
                "the current password or clearing saved credentials where appropriate."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "login-mfa-behavior",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Confirm the user-visible MFA prompt and approval behavior.",
            (
                "MFA evidence can be collected from prompts and user actions "
                "without checking identity backend systems."
            ),
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "User-visible MFA prompt or approval issue",
            failure_results=(ChecklistResultValue.DOES_NOT_WORK,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="User-visible MFA prompt or approval failure",
            evidence_prompt=(
                "Record whether no prompt appears, the prompt fails, the user "
                "changed phones, approval is unavailable, number matching fails, "
                "or the prompt was denied."
            ),
            next_action=(
                "Collect the exact MFA behavior and identify whether MFA reset "
                "or identity admin review is needed."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "login-browser-device-isolation",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Compare sign-in in a private window, another browser, another "
                "device, and app versus web where safe."
            ),
            "Alternate client paths separate browser, app, or device state from account state.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Browser, device, or client sign-in issue",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Browser, device, or client-only sign-in issue",
            evidence_prompt=(
                "Record whether sign-in works in a private window, another "
                "browser, another device, or app versus web."
            ),
            next_action=(
                "Try a safe alternate sign-in path, such as private window, "
                "another browser, another device, or app versus web."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "login-visible-account-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            (
                "Record user-visible account, lock, license, access denied, "
                "permission, policy, or security messages only."
            ),
            (
                "Visible messages support a clean identity handoff without "
                "claiming unseen backend checks."
            ),
            ChecklistResultType.TEXT,
            "User-visible account, permission, policy, or security message needs identity review",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing user-visible account, permission, policy, or security boundary evidence",
            evidence_prompt=(
                "Capture visible messages only, such as account locked, license "
                "required, access denied, permission required, policy block, or "
                "security warning. Do not claim checks of sign-in logs, Entra ID, "
                "AD, Okta, Conditional Access, licensing, IAM admin portals, or "
                "identity admin portals."
            ),
            next_action=(
                "Record the user-visible boundary message and prepare the "
                "evidence needed for identity review if local checks do not resolve it."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "login-identity-admin-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate for account lock review, MFA reset, sign-in logs, "
                "Conditional Access, licensing, group membership, Entra ID, AD, "
                "Okta, or identity admin review."
            ),
            "These checks require privileged identity, IAM, or service desk review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Identity account state, MFA, policy, licensing, or permission review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Identity admin, IAM, or service desk privileged review is required."
            ),
            evidence_prompt=(
                "Summarize collected platform, scope, exact error, password, "
                "MFA, browser/device, and user-visible boundary evidence."
            ),
            next_action=(
                "Summarize the collected Login/MFA evidence and escalate to "
                "identity admin, IAM, or the service desk team for privileged review."
            ),
            escalation_reason=(
                "The remaining checks require identity admin, IAM, or service "
                "desk privileged access."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users are affected or a wider identity outage is suspected.",
        "Escalate if account lock review, MFA reset, sign-in logs, Conditional Access, licensing, group membership, Entra ID, AD, Okta, or identity admin review is required.",
    ),
    interpretation_rules=(
        "Confirm platform, application, account type, scope, and exact visible error before deeper checks.",
        "Use only user-visible password, MFA, browser, device, and visible account evidence for Level 1 diagnosis.",
        "If safe local checks pass and privileged identity review is needed, escalate with collected evidence.",
        "Do not claim identity backend systems were checked unless a real integration returns that evidence.",
    ),
)


FILE_ACCESS_PERMISSION_PLAYBOOK = Playbook(
    issue_category=IssueCategory.FILE_ACCESS_PERMISSION,
    subcategory="File access/permission",
    keywords=(
        "file access",
        "file permission",
        "file share",
        "shared folder",
        "network drive",
        "mapped drive",
        "permission denied",
        "access denied",
        "path not found",
        "cannot connect to file share",
        "cannot connect to shared folder",
        "cannot connect to network drive",
        "request access",
        "file locked",
        "sync issue",
        "sharepoint file",
        "onedrive file",
        "teams file",
    ),
    missing_information=(
        MissingInformation(
            question=(
                "What exact file path, SharePoint link, shared drive, or "
                "folder location is the user trying to open?"
            ),
            reason=(
                "Shared folders, network drives, mapped drives, SharePoint, "
                "OneDrive, Teams files, and local files have different safe "
                "checks and escalation owners."
            ),
        ),
        MissingInformation(
            question=(
                "What exact permission or access error appears, such as access "
                "denied, permission required, path not found, or request access?"
            ),
            reason=(
                "Exact error and scope separate wrong path, local client, "
                "permission, shared resource, and service-impact symptoms."
            ),
        ),
        MissingInformation(
            question="Did the user previously have access, and what changed recently?",
            reason=(
                "Prior access and recent team, role, path, or ownership changes "
                "help identify the next troubleshooting layer."
            ),
        ),
        MissingInformation(
            question=(
                "Can other permitted users access the same file path, link, "
                "shared drive, or folder?"
            ),
            reason=(
                "Other-user comparison separates a local path or client issue "
                "from a permission, group, owner, or shared-resource issue."
            ),
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Wrong path, disconnected VPN, unavailable office network path, or mapped-drive path issue",
            "medium",
            "File access issues often start with path and network context evidence.",
        ),
        PlaybookCause(
            "Local client, browser, sync client, Teams file view, or mapped-drive issue",
            "medium",
            "Alternate access paths can isolate local device or client behavior.",
        ),
        PlaybookCause(
            "User-specific permission, ownership, group membership, or data-owner review may be required",
            "medium",
            "If the resource exists and other permitted users can access it, privileged permission review may be needed.",
        ),
    ),
    checklist_steps=(
        _step(
            "file-access-confirm-resource",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm the exact path, URL, resource type, and where the user "
                "is trying to access it."
            ),
            "The resource type determines the safest Level 1 checks and likely owner.",
            ChecklistResultType.TEXT,
            "Unclear file path, URL, resource type, or access location",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing file path, URL, resource type, or access location",
            evidence_prompt=(
                "Record the exact path or URL, resource type, mapped drive "
                "letter if relevant, and where the user is trying to access it."
            ),
            next_action=(
                "Confirm the exact path or URL, resource type, mapped drive "
                "letter if relevant, and access location."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "file-access-scope-error",
            ChecklistGroup.SCOPE_IMPACT,
            "Record the exact visible error and whether one user or multiple users are affected.",
            "Error wording and scope separate user-specific access from shared resource impact.",
            ChecklistResultType.TEXT,
            "Possible shared file resource or access service impact",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing file access error or affected scope evidence",
            evidence_prompt=(
                "Record the exact visible error and affected scope, such as "
                "access denied, permission required, path not found, cannot "
                "connect, file locked, sync issue, one user, or multiple users."
            ),
            next_action=(
                "Capture the exact visible error and whether one user or "
                "multiple users are affected."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "file-access-previous-access",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Ask whether the user previously had access and what changed.",
            (
                "Previous access can point to role, team, ownership, path, or "
                "permission changes that need clean evidence."
            ),
            ChecklistResultType.YES_NO,
            "Previous access changed, removed, or affected by role, team, or path change",
            failure_results=(ChecklistResultValue.YES,),
            pass_results=(ChecklistResultValue.NO,),
            ruled_out_cause="Previous access or recent access-change trigger",
            evidence_prompt=(
                "Record whether the user previously had access, when it last "
                "worked, and any role, team, owner, path, or location change."
            ),
            next_action=(
                "Confirm whether the user previously had access and record what "
                "changed before moving to path and network checks."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "file-access-path-network",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Confirm path or URL correctness and VPN or office network status "
                "for network drives."
            ),
            (
                "Wrong paths and missing VPN or office-network reachability are "
                "safe Level 1 checks before permission review."
            ),
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Wrong path, disconnected VPN, unavailable office network path, or mapped-drive path issue",
            failure_results=(ChecklistResultValue.DOES_NOT_WORK,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Wrong path, disconnected VPN, or unavailable network file path",
            evidence_prompt=(
                "Record whether the path or URL is correct, whether VPN or the "
                "office network is required, and whether the mapped drive path "
                "matches the expected resource."
            ),
            next_action=(
                "Verify the path or URL and confirm VPN, office network, or "
                "mapped-drive context where relevant."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "file-access-known-permitted-user",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Check whether another known permitted user can access the same "
                "resource without exposing sensitive content."
            ),
            (
                "A permitted-user comparison separates shared resource impact "
                "from affected-user permission boundaries."
            ),
            ChecklistResultType.YES_NO,
            "Shared file resource, service, or path issue affecting permitted users",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Shared file resource unavailable to another permitted user",
            evidence_prompt=(
                "Record whether another known permitted user can access the same "
                "resource. Do not expose sensitive files or bypass permissions."
            ),
            next_action=(
                "Compare with another known permitted user if appropriate, "
                "without exposing sensitive content or bypassing permissions."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "file-access-client-isolation",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Compare File Explorer, browser or web access, OneDrive sync "
                "client, Teams file view, or mapped-drive reconnect where appropriate."
            ),
            (
                "Alternate access paths help isolate local client, sync, browser, "
                "Teams, or mapped-drive behavior."
            ),
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Local client, browser, sync client, Teams file view, or mapped-drive issue",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Local client, browser, sync client, Teams, or mapped-drive-only issue",
            evidence_prompt=(
                "Record whether access works through File Explorer, browser or "
                "web, OneDrive sync client, Teams file view, or mapped-drive "
                "reconnect where appropriate."
            ),
            next_action=(
                "Try a safe alternate access path such as browser, File Explorer, "
                "OneDrive sync, Teams file view, or mapped-drive reconnect."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "file-access-visible-permission-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            (
                "Record visible permission, request access, owner, file locked, "
                "sync conflict, or access indicator only."
            ),
            (
                "Visible boundary messages help prepare a clean permission handoff "
                "without claiming backend checks."
            ),
            ChecklistResultType.TEXT,
            "Visible file access, permission, ownership, lock, or sync boundary needs clarification",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Missing visible file permission, owner, lock, or sync boundary evidence",
            evidence_prompt=(
                "Capture visible messages only, such as access denied, request "
                "access, owner shown, file locked, sync conflict, or permission "
                "required. Do not claim ACLs, group membership, file server "
                "permissions, SharePoint or OneDrive admin settings, M365 admin, "
                "IAM, or admin portal checks."
            ),
            next_action=(
                "Record only the user-visible permission, owner, lock, sync, or "
                "access indicator before deciding whether privileged review is needed."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "file-access-admin-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate for ACLs, group membership, share permissions, data "
                "owner approval, SharePoint or OneDrive library settings, file "
                "server, M365 admin, or IAM review."
            ),
            "These checks require file admin, data owner, M365 admin, or IAM privileged review.",
            ChecklistResultType.NOT_APPLICABLE,
            "File access permissions, ownership, library settings, or IAM review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "File admin, data owner, M365 admin, or IAM privileged review is required."
            ),
            evidence_prompt=(
                "Summarize collected path, URL, resource type, visible error, "
                "scope, previous access, VPN or network context, permitted-user "
                "comparison, client isolation, and visible permission evidence."
            ),
            next_action=(
                "Summarize the collected File Access evidence and escalate to "
                "file admin, data owner, M365 admin, or IAM for privileged review."
            ),
            escalation_reason=(
                "The remaining checks require file admin, data owner, M365 admin, "
                "or IAM privileged access."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users are affected by the same file resource or a shared service impact is suspected.",
        "Escalate if ACLs, group membership, share permissions, data owner approval, SharePoint or OneDrive library settings, file server, M365 admin, or IAM review is required.",
    ),
    interpretation_rules=(
        "Confirm exact resource, visible error, and affected scope before deeper checks.",
        "Use only user-visible path, network, comparison, client, sync, and permission evidence for Level 1 diagnosis.",
        "If safe local checks pass and privileged permission review is needed, escalate with collected evidence.",
        "Do not claim file access backend systems were checked unless a real integration returns that evidence.",
    ),
)


SOFTWARE_INSTALLATION_UPDATE_PLAYBOOK = Playbook(
    issue_category=IssueCategory.SOFTWARE_INSTALLATION_UPDATE,
    subcategory="Software installation/update",
    keywords=(
        "installer fails",
        "installer error",
        "install fails",
        "install failure",
        "will not install",
        "cannot install",
        "software update fails",
        "update fails",
        "update failure",
        "patch blocked",
        "patch is blocked",
        "uninstall fails",
        "uninstall failure",
        "version mismatch",
        "app version issue",
        "software center",
        "package deployment",
    ),
    missing_information=(
        MissingInformation(
            question=(
                "What exact software action is failing and what is the business "
                "impact: install, update, uninstall, patch, or version issue?"
            ),
            reason="The playbook must confirm the software action before moving into source, device, or policy checks.",
        ),
        MissingInformation(
            question="What app name, target version, operating system, and exact visible installer or update error are shown?",
            reason="Version, OS, and visible error evidence are needed before inferring a cause.",
        ),
        MissingInformation(
            question="Is one user/device affected, or are multiple devices seeing the same install or update failure?",
            reason="Scope separates a local install path from managed deployment, package, or service impact.",
        ),
        MissingInformation(
            question="Was the installer or update launched from an approved source such as company software center or self-service portal?",
            reason="Source evidence separates user-side installer problems from managed software delivery boundaries.",
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Wrong or unapproved installer/source",
            "high",
            "Using an unapproved installer or source can fail before privileged review is needed.",
        ),
        PlaybookCause(
            "Restart pending, insufficient visible disk space, or basic device readiness issue",
            "medium",
            "Safe user-visible readiness checks should be completed before deeper review.",
        ),
        PlaybookCause(
            "App version, previous install state, or local install/update path issue",
            "medium",
            "Version and previous install evidence can explain one-device install or update failures.",
        ),
        PlaybookCause(
            "Admin rights, managed deployment, licensing, EDR, package, or vendor review may be required",
            "medium",
            "Visible boundary messages can indicate that Level 1 should hand off instead of guessing.",
        ),
    ),
    checklist_steps=(
        _step(
            "software-confirm-action",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm the exact software action and business impact: install, "
                "update, uninstall, patch, or app version issue."
            ),
            "Start by identifying the software workflow before checking local source or device readiness.",
            ChecklistResultType.TEXT,
            "Unclear software install, update, uninstall, patch, version, or business impact",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Record the exact software action, affected app, and business "
                "impact: install, update, uninstall, patch, or version issue."
            ),
            next_action=(
                "Confirm whether this is an install, update, uninstall, patch, "
                "or version issue and record business impact."
            ),
        ),
        _step(
            "software-app-version-error",
            ChecklistGroup.SCOPE_IMPACT,
            "Capture the app name, target/current version, operating system, and exact visible installer or update error.",
            "App, version, OS, and error evidence keep the diagnosis grounded in observable facts.",
            ChecklistResultType.TEXT,
            "Missing app name, version, OS, or exact visible installer/update error",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Record app name, target/current version, OS, and exact visible "
                "installer, update, uninstall, patch, or version error."
            ),
            next_action="Capture app name, version, OS, and exact visible software error.",
        ),
        _step(
            "software-affected-scope",
            ChecklistGroup.SCOPE_IMPACT,
            "Confirm whether one user/device or multiple devices are affected by the same software install/update issue.",
            "Scope separates one-device install state from wider package, deployment, or service impact.",
            ChecklistResultType.TEXT,
            "Multiple devices or wider software deployment impact",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Unclear or wider software install/update scope",
            evidence_prompt="Record whether one user/device or multiple devices are affected.",
            next_action="Confirm affected scope for the software install/update issue.",
        ),
        _step(
            "software-approved-source",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Confirm the installer or update comes from an approved source, "
                "company software center, or self-service portal where applicable."
            ),
            "Wrong or unapproved sources are safe Level 1 evidence before deeper device or policy checks.",
            ChecklistResultType.YES_NO,
            "Wrong or unapproved installer/source",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Wrong or unapproved installer/source",
            evidence_prompt=(
                "Record whether the installer, update, patch, or uninstall path "
                "comes from an approved source, company software center, or self-service portal."
            ),
            next_action="Confirm the software source is approved before retrying or escalating.",
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "software-restart-disk-readiness",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            "Check user-visible restart pending state, visible disk space, and basic device readiness for the install or update.",
            "Restart pending and visible disk space issues are safe Level 1 checks.",
            ChecklistResultType.YES_NO,
            "Restart pending, insufficient visible disk space, or basic device readiness issue",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Restart pending, visible disk space, or basic device readiness issue",
            evidence_prompt=(
                "Record whether a restart is pending, visible disk space appears "
                "sufficient, and the device is ready for a safe retry."
            ),
            next_action="Check restart pending state, visible disk space, and basic device readiness.",
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "software-version-install-state",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Confirm previous install state, current version, target version, "
                "and whether this is a new install, update, uninstall, or version mismatch."
            ),
            "Previous install and version state can isolate local app install/update behavior.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "App version mismatch, previous install state, or local install/update path issue",
            failure_results=(ChecklistResultValue.DOES_NOT_WORK,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="App version, previous install state, or local install/update path issue",
            evidence_prompt=(
                "Record whether the app was previously installed, current and "
                "target versions, and whether the local install/update/uninstall path fails."
            ),
            next_action="Confirm previous install state and current versus target version.",
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "software-visible-admin-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            (
                "Record visible boundary evidence only, such as admin rights "
                "prompt, license message, managed deployment message, package "
                "deployment requirement, EDR/application-control block, or vendor installer message."
            ),
            "Visible boundary evidence prepares a clean handoff without claiming hidden software-management checks.",
            ChecklistResultType.TEXT,
            "Admin rights, licensing, managed deployment, package, EDR/application-control, or vendor boundary",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Visible admin, licensing, managed deployment, package, EDR/application-control, or vendor boundary",
            evidence_prompt=(
                "Capture user-visible boundary evidence only. Do not claim "
                "Intune, MDM, EDR, software deployment tools, licensing systems, "
                "Windows event logs, registry, vendor installer logs, package "
                "repositories, or admin portal checks without a real integration."
            ),
            next_action=(
                "Record only user-visible admin-rights, license, managed "
                "deployment, EDR/application-control, package, or vendor boundary evidence."
            ),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Desktop support, software packaging, MDM/Intune admin, "
                "licensing admin, security/EDR, or vendor privileged review is required."
            ),
            escalation_reason=(
                "The visible software boundary requires privileged software, "
                "licensing, deployment, security, or vendor review."
            ),
        ),
        _step(
            "software-admin-deployment-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate if admin rights, Intune or MDM, software deployment, "
                "EDR/application control, licensing, Windows event logs, registry "
                "or system repair, package repository, admin portal, or vendor review is required."
            ),
            "These checks require Desktop, packaging, MDM, licensing, security, system, or vendor privileged review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Privileged software install/update review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Desktop support, software packaging, MDM/Intune admin, "
                "licensing admin, security/EDR, system support, or vendor privileged review is required."
            ),
            evidence_prompt=(
                "Summarize collected action, impact, app/version/OS/error, "
                "scope, source, restart/disk readiness, previous install/version "
                "state, and user-visible boundary evidence."
            ),
            next_action=(
                "Summarize the collected Software Install/Update evidence and "
                "escalate to Desktop, packaging, MDM/Intune, licensing, security, system, or vendor support."
            ),
            escalation_reason=(
                "The remaining checks require privileged Desktop, software "
                "deployment, MDM/Intune, licensing, security/EDR, system, or vendor access."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple devices are affected by the same software install/update failure.",
        "Escalate if admin rights, Intune or MDM, software deployment, EDR/application control, licensing, event logs, registry/system repair, package repository, admin portal, or vendor review is required.",
    ),
    interpretation_rules=(
        "Confirm exact software action, business impact, app, version, OS, visible error, and scope before deeper checks.",
        "Use only user-visible installer/source, restart, disk space, version, previous-install, and boundary evidence for Level 1 diagnosis.",
        "Do not claim Intune, MDM, EDR, software deployment tools, licensing systems, Windows event logs, registry, vendor installer logs, package repositories, or admin portals were checked without a real integration.",
        "If safe local checks pass and privileged software deployment, licensing, security, system, or vendor review is needed, escalate with collected evidence.",
    ),
)


DISPLAY_MONITOR_PLAYBOOK = Playbook(
    issue_category=IssueCategory.DISPLAY_MONITOR,
    subcategory="Display/monitor/docking station",
    keywords=(
        "monitor",
        "display",
        "screen",
        "projector",
        "hdmi",
        "displayport",
        "usb-c",
        "blank",
        "no signal",
        "dock",
        "docking station",
        "external monitor",
        "second monitor",
        "flickering",
        "resolution",
        "scaling",
        "duplicate",
        "extend",
    ),
    missing_information=(
        MissingInformation(
            question=(
                "When the monitor goes off, is the power light on, blinking, "
                "or completely off?"
            ),
            reason="Power-light state separates power, sleep, no-signal, and display-input symptoms.",
        ),
        MissingInformation(
            question=(
                "Does moving the mouse or pressing the keyboard wake the "
                "screen back up?"
            ),
            reason="Wake behavior points toward normal power-saving or sleep behavior before deeper display checks.",
        ),
        MissingInformation(
            question=(
                "Is the computer or laptop still running while only the "
                "monitor turns off?"
            ),
            reason="This separates monitor/display output from full device sleep, shutdown, or performance symptoms.",
        ),
        MissingInformation(
            question=(
                "Are you using a laptop screen, external monitor, docking "
                "station, HDMI, DisplayPort, USB-C, adapter, or projector?"
            ),
            reason="The affected display path determines the safest Level 1 checks for cable, input, dock, adapter, or layout.",
        ),
        MissingInformation(
            question=(
                "Did anything change before this started, such as a new cable, "
                "dock, display setting, power or sleep setting, or system update?"
            ),
            reason="Recent display-path or power-setting changes help pick the next diagnostic layer without asking account or application questions.",
        ),
    ),
    possible_causes=(
        PlaybookCause(
            "Wrong display input/source, loose cable, adapter, or dock connection",
            "high",
            "Input, cable, adapter, and dock connection issues are common safe Level 1 checks.",
        ),
        PlaybookCause(
            "Duplicate/extend, resolution, scaling, or local OS display state issue",
            "medium",
            "User-visible display settings can explain layout and resolution symptoms.",
        ),
        PlaybookCause(
            "Dock, cable, port, display, projector, or local hardware path issue",
            "medium",
            "Direct connection and known-good comparison can isolate the local display path.",
        ),
        PlaybookCause(
            "Driver, firmware, managed dock policy, AV system, warranty, or vendor review may be required",
            "medium",
            "If safe local display checks do not isolate the issue, privileged or specialist review may be required.",
        ),
    ),
    checklist_steps=(
        _step(
            "display-confirm-symptom",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm the exact display symptom and business impact: blank "
                "external monitor, laptop screen issue, projector no signal, "
                "flicker, wrong resolution, or dock display problem."
            ),
            "Start by separating physical display output from app rendering, login, or performance symptoms.",
            ChecklistResultType.TEXT,
            "Unclear display symptom or business impact",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Record the exact display symptom, affected work, and whether "
                "this is physical output rather than an app rendering issue."
            ),
            next_action="Confirm the exact display symptom and business impact.",
        ),
        _step(
            "display-affected-path",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Identify whether the affected path is laptop screen, external "
                "monitor, dock, projector, cable, adapter, USB-C, HDMI, "
                "DisplayPort, or display layout."
            ),
            "The affected path determines which safe Level 1 checks apply.",
            ChecklistResultType.TEXT,
            "Unclear display path or component",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(ChecklistResultValue.WORKS,),
            evidence_prompt=(
                "Record the affected display path: laptop panel, external "
                "monitor, projector, dock, cable, adapter, port, or layout."
            ),
            next_action="Identify the affected display path or component.",
        ),
        _step(
            "display-affected-scope",
            ChecklistGroup.SCOPE_IMPACT,
            (
                "Confirm whether one user, one device, one desk or room, "
                "multiple users, or the same monitor, dock, or projector is affected."
            ),
            "Scope separates a local display path from shared room, display, dock, or hardware impact.",
            ChecklistResultType.TEXT,
            "Multiple users, same room display, shared dock, or shared display path impact",
            failure_results=(
                ChecklistResultValue.USER_UNSURE,
                ChecklistResultValue.NEEDS_ESCALATION,
            ),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Unclear or wider display scope",
            evidence_prompt=(
                "Record whether one user/device/desk is affected or whether "
                "multiple users share the same room display, dock, monitor, or projector failure."
            ),
            next_action="Confirm affected scope for the display issue.",
        ),
        _step(
            "display-power-input-cable",
            ChecklistGroup.SIMPLE_USER_CHECKS,
            (
                "Check visible power, selected input/source, cable seating, "
                "dock connection, adapter path, and obvious no-signal state."
            ),
            "Wrong source, loose cable, or adapter/dock connection should be checked before deeper device work.",
            ChecklistResultType.YES_NO,
            "Wrong input/source, cable, adapter, dock connection, or visible no-signal path",
            failure_results=(ChecklistResultValue.NO,),
            pass_results=(ChecklistResultValue.YES,),
            ruled_out_cause="Wrong input/source, cable, adapter, dock connection, or visible no-signal path",
            evidence_prompt=(
                "Record monitor or projector power, selected input/source, "
                "cable type, dock connection, adapter path, and visible no-signal state."
            ),
            next_action=(
                "Check power, input/source, cable seating, dock connection, "
                "and adapter path."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "display-layout-resolution",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Check user-visible display mode, duplicate versus extend, "
                "resolution, scaling, and whether the OS detects the display."
            ),
            "Display layout and resolution symptoms can often be isolated with user-visible OS settings.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Duplicate/extend mode, resolution, scaling, or visible OS display state issue",
            failure_results=(ChecklistResultValue.DOES_NOT_WORK,),
            pass_results=(ChecklistResultValue.WORKS,),
            ruled_out_cause="Duplicate/extend, resolution, scaling, or visible OS display state issue",
            evidence_prompt=(
                "Record duplicate/extend mode, resolution, scaling, and "
                "whether the OS visibly detects the display."
            ),
            next_action=(
                "Check duplicate/extend mode, resolution, scaling, and visible "
                "OS display detection."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "display-direct-dock-comparison",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Compare direct laptop-to-display connection with the dock path "
                "where appropriate."
            ),
            "If direct connection works while the dock path fails, the issue likely sits in the dock, cable, port, or adapter path.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Dock, cable, adapter, or port path issue isolated by direct connection comparison",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Dock, cable, adapter, or port path isolated by direct connection comparison",
            evidence_prompt=(
                "Record whether direct laptop-to-display works while the dock, "
                "USB-C, HDMI, DisplayPort, or adapter path fails."
            ),
            next_action="Compare direct laptop display connection with the dock path.",
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "display-known-good-comparison",
            ChecklistGroup.DEVICE_CLIENT_APPLICATION,
            (
                "Compare with another cable, port, display, projector, dock, or "
                "device where safe and available."
            ),
            "Known-good comparison helps isolate a local cable, port, display, dock, adapter, or device path.",
            ChecklistResultType.WORKS_DOES_NOT_WORK,
            "Known-good cable, port, display, dock, adapter, or device comparison isolates local display path",
            failure_results=(ChecklistResultValue.WORKS,),
            pass_results=(ChecklistResultValue.DOES_NOT_WORK,),
            ruled_out_cause="Known-good cable, port, display, dock, adapter, or device comparison",
            evidence_prompt=(
                "Record whether another cable, port, display, projector, dock, "
                "or device changes the result."
            ),
            next_action=(
                "Compare with another cable, port, display, projector, dock, "
                "or device where safe and available."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "display-visible-boundary",
            ChecklistGroup.PLATFORM_PERMISSION_CONFIGURATION,
            (
                "Record user-visible boundary evidence only, such as display not "
                "detected, driver-related message, firmware prompt, managed dock "
                "message, replacement need, or AV room display symptom."
            ),
            "Visible boundary evidence prepares a clean handoff without claiming hidden system checks.",
            ChecklistResultType.TEXT,
            "Visible driver, firmware, managed dock, AV room, hardware, warranty, or vendor boundary evidence",
            failure_results=(ChecklistResultValue.USER_UNSURE,),
            pass_results=(
                ChecklistResultValue.WORKS,
                ChecklistResultValue.DOES_NOT_WORK,
            ),
            ruled_out_cause="Missing visible display boundary evidence",
            evidence_prompt=(
                "Capture user-visible evidence only. Do not claim Intune, MDM, "
                "hardware diagnostics, driver deployment tools, firmware tools, "
                "AV systems, logs, device inventory, or vendor system checks without a real integration."
            ),
            next_action=(
                "Record only user-visible display, dock, driver, firmware, "
                "hardware, warranty, or AV room boundary evidence."
            ),
            level1_actionable=True,
            requires_privileged_access=False,
        ),
        _step(
            "display-admin-vendor-review",
            ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE,
            (
                "Escalate if driver deployment, dock firmware, hardware "
                "diagnostics, managed dock policy, MDM or Intune, AV room "
                "system, warranty or replacement approval, or vendor review is required."
            ),
            "These checks require Desktop, AV, MDM, hardware, warranty, or vendor privileged review.",
            ChecklistResultType.NOT_APPLICABLE,
            "Driver, firmware, managed dock policy, hardware, AV room, warranty, or vendor review required",
            failure_results=(ChecklistResultValue.NEEDS_ESCALATION,),
            pass_results=(ChecklistResultValue.NOT_TESTED,),
            level1_actionable=False,
            requires_privileged_access=True,
            access_requirement=(
                "Desktop support, AV support, MDM or Intune admin, hardware "
                "support, warranty approval, or vendor privileged review is required."
            ),
            evidence_prompt=(
                "Summarize collected symptom, business impact, affected path, "
                "scope, power/input/cable state, layout and resolution state, "
                "direct-versus-dock comparison, known-good comparison, and "
                "user-visible boundary evidence."
            ),
            next_action=(
                "Summarize the collected Display/Monitor/Dock evidence and "
                "escalate to Desktop, AV, MDM, hardware, warranty, or vendor support."
            ),
            escalation_reason=(
                "The remaining checks require Desktop, AV, MDM or Intune, "
                "hardware, warranty, or vendor privileged access."
            ),
        ),
    ),
    escalation_criteria=(
        "Escalate if multiple users, the same room display, or a shared dock/projector path is affected.",
        "Escalate if driver deployment, dock firmware, hardware diagnostics, managed dock policy, MDM or Intune, AV room system, warranty approval, replacement, or vendor review is required.",
    ),
    interpretation_rules=(
        "Confirm exact display symptom, business impact, affected path, and scope before deeper checks.",
        "Use only user-visible power, input/source, cable, adapter, dock, display settings, and comparison evidence for Level 1 diagnosis.",
        "Do not claim Intune, MDM, hardware diagnostics, driver deployment tools, firmware tools, AV systems, logs, device inventory, or vendor systems were checked without a real integration.",
        "If safe local checks pass and privileged Desktop, AV, MDM, hardware, warranty, or vendor review is needed, escalate with collected evidence.",
    ),
)


PLAYBOOKS: dict[IssueCategory, Playbook] = {
    IssueCategory.VPN_REMOTE_ACCESS: VPN_REMOTE_ACCESS_PLAYBOOK,
    IssueCategory.NETWORK_WIFI: NETWORK_WIFI_PLAYBOOK,
    IssueCategory.SMALL_OFFICE_NETWORK: SMALL_OFFICE_NETWORK_PLAYBOOK,
    IssueCategory.VOIP_TELEPHONY: VOIP_TELEPHONY_PLAYBOOK,
    IssueCategory.PRINTER: PRINTER_PLAYBOOK,
    IssueCategory.TEAMS_AUDIO_VIDEO: TEAMS_AUDIO_VIDEO_PLAYBOOK,
    IssueCategory.EMAIL_OUTLOOK: OUTLOOK_PLAYBOOK,
    IssueCategory.LOGIN_ACCOUNT: LOGIN_ACCOUNT_PLAYBOOK,
    IssueCategory.FILE_ACCESS_PERMISSION: FILE_ACCESS_PERMISSION_PLAYBOOK,
    IssueCategory.APPLICATION_ERROR: _generic_playbook(
        IssueCategory.APPLICATION_ERROR,
        "Application error",
        ("app error", "application error", "portal error", "unexpected error"),
        "application error",
        escalation_criteria=(
            "Escalate to the responsible team if this is a company custom system.",
            "Escalate if logs, code, vendor, or admin review is required.",
        ),
    ),
    IssueCategory.DEVICE_PERFORMANCE: _generic_playbook(
        IssueCategory.DEVICE_PERFORMANCE,
        "Device performance",
        ("slow", "performance", "freezing", "lag", "startup"),
        "device performance",
    ),
    IssueCategory.HARDWARE_PERIPHERAL: _generic_playbook(
        IssueCategory.HARDWARE_PERIPHERAL,
        "Hardware/peripheral",
        ("hardware", "peripheral", "usb", "headset", "keyboard", "mouse", "not detected"),
        "hardware or peripheral",
    ),
    IssueCategory.SOFTWARE_INSTALLATION_UPDATE: SOFTWARE_INSTALLATION_UPDATE_PLAYBOOK,
    IssueCategory.DISPLAY_MONITOR: DISPLAY_MONITOR_PLAYBOOK,
    IssueCategory.MOBILE_HOTSPOT: _generic_playbook(
        IssueCategory.MOBILE_HOTSPOT,
        "Mobile hotspot",
        ("mobile hotspot", "hotspot", "tethering"),
        "mobile hotspot",
    ),
    IssueCategory.GENERAL_IT: GENERAL_IT_PLAYBOOK,
}


def get_playbook(category: IssueCategory) -> Playbook:
    return PLAYBOOKS.get(category, GENERAL_IT_PLAYBOOK)
