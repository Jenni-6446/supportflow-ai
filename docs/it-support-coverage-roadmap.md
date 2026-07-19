# IT Support Coverage Roadmap

## Product Positioning

This project is not a generic AI chatbot. It is a structured troubleshooting coach and evidence-driven IT support troubleshooting engine.

The system helps Level 1 and Level 2 support agents identify:

- Issue category
- Current troubleshooting layer
- Missing evidence
- Ruled-out causes
- Current likely cause
- Next 1-3 best actions
- Whether Level 1 can continue
- When escalation is required and why

The product goal is consistent diagnostic guidance: gather evidence, move from simple to complex checks, avoid unsupported guesses, and escalate with clean context when privileged review is required.

## Coverage Strategy

Coverage should expand in layers rather than trying to hardcode every possible IT scenario.

- **Core detailed playbooks**: High-frequency, high-value scenarios with clear diagnostic progression. These should have 5-8 high-quality steps, v1.5 metadata, and backend tests.
- **Medium-depth playbooks**: Common support issues that need structured guidance but do not yet require the full detailed standard.
- **General IT fallback**: A professional uncertainty handler for vague, long-tail, or unsupported issues.
- **Future AI-assisted classification and explanation**: AI may help parse messy user text, suggest categories, summarize evidence, and draft notes, while the playbook engine controls diagnosis progression.
- **Future knowledge base and read-only integrations**: These should be evidence sources only. They should not replace the playbook engine or allow unsupported claims.

## Current Implementation Status

Phase 1 is implemented:

- Small Office Network detailed playbook
- VoIP / Telephony detailed playbook

Phase 2 is implemented:

- Login / Account / MFA detailed playbook
- File Access / Permission detailed playbook

Phase 3.1 is implemented:

- Outlook / Email detailed playbook

Phase 3.2 is implemented:

- Teams Audio / Video detailed playbook

Phase 3.3 is implemented:

- Printer / Scanner detailed playbook polish

Phase 4.1 is implemented:

- Display / Monitor / Docking Station detailed playbook

Phase 4.2 is implemented:

- Software Install / Update detailed playbook

The Outlook / Email detailed playbook covers:

- Exact email symptom and business impact
- Send, receive, sync, access, mailbox-specific, and stuck outbox symptoms
- One user, multiple users, one sender, one recipient, all senders, or all mail scope
- Recent password, account, Outlook profile, device, or mailbox access changes
- Outlook desktop versus webmail comparison
- Outlook client state, sync, outbox, profile, cached-mode, and timing evidence
- Visible mailbox, delivery, quarantine notice, rule, shared-mailbox access, or policy boundary evidence
- Email / M365 admin escalation for privileged mailbox, mail-flow, trace, log, identity, or policy review

The Teams Audio / Video detailed playbook covers:

- Exact Teams audio/video symptom and business impact
- Microphone, camera, speaker, audio input, audio output, headset, and device-detection symptoms
- One user, one meeting, multiple users, or all Teams meetings scope
- Selected Teams microphone, camera, speaker, headset, and audio device checks
- Other-app comparison to isolate Teams-specific behavior from device or OS behavior
- Teams browser versus Teams desktop comparison
- Visible OS permission and device-setting evidence
- Visible Teams meeting, device, policy, permission, or organization-boundary evidence
- Teams admin, M365 admin, Desktop support, device management, or hardware escalation boundaries

The Printer / Scanner detailed playbook covers:

- Exact print, scan, copy, scan-to-email, or scan-to-folder symptom and business impact
- One user, one device, multiple users, shared printer, or everyone-affected scope
- Selected printer, scanner, queue, and scan destination evidence
- Visible printer or MFD state, including offline, paper, toner, jam, or front-panel error
- Local print queue, stuck job, driver/client symptom, and user-device path evidence
- Comparison with another user or another device where appropriate
- Visible driver, queue, scanner destination, mailbox, folder, or permission-boundary evidence
- Desktop support, Print team, MFD vendor, M365, File admin, or privileged print/scanner escalation boundaries

The Display / Monitor / Docking Station detailed playbook covers:

- Exact physical display symptom and business impact
- Laptop screen, external monitor, dock, projector, cable, adapter, USB-C, HDMI, DisplayPort, and display layout paths
- One user, one device, one desk or room, multiple users, or shared display/dock/projector scope
- Visible power, input/source, cable seating, dock connection, adapter path, and no-signal state
- Duplicate versus extend mode, resolution, scaling, and visible OS display detection evidence
- Direct laptop connection versus dock-path comparison
- Known-good cable, port, display, projector, dock, or device comparison
- Desktop support, AV support, MDM/Intune admin, hardware, warranty, or vendor escalation boundaries

The Software Install / Update detailed playbook covers:

- Exact software action and business impact: install, update, uninstall, patch, or version issue
- App name, current/target version, operating system, and exact visible installer/update error
- One user/device versus multiple devices scope
- Approved installer/source, company software center, or self-service portal evidence
- Restart pending, visible disk space, and basic device readiness checks
- Previous install state, app version mismatch, and local install/update path evidence
- Visible admin rights, license, managed deployment, package deployment, EDR/application-control, or vendor boundary evidence
- Desktop support, packaging, MDM/Intune, licensing, security/EDR, system support, or vendor escalation boundaries

The File Access / Permission detailed playbook covers:

- Exact path, URL, and resource type
- Shared folders, network drives, mapped drives, SharePoint, OneDrive, and Teams files
- Exact visible error
- Previous access history
- VPN and office network context
- Permitted-user comparison
- Client, browser, sync, and mapped-drive isolation
- Visible permission boundary evidence
- File admin, data owner, M365 admin, and IAM escalation

Latest backend verification: 187 passed, 0 failed.

The current Playbook Engine v1.5 supports:

- Progressive diagnosis
- Step metadata
- `missingEvidence`
- `nextBestActions`
- `level1CanContinue`
- `level1BlockerReason`
- Escalation recommendation

VPN-specific behavior remains preserved, while generic progressive diagnosis supports non-VPN playbooks.

## Coverage Matrix

| Category | Example issues | Priority | Current depth | Target depth | Level 1 checks | Level 2 / admin boundary | Escalation owner | Timing / phase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VPN Remote Access | Authentication failed, client will not connect, MFA prompt issue | High | Detailed | Detailed plus polish | Internet outside VPN, scope, error, password, MFA, client, profile | VPN logs, conditional access, cert/profile provisioning, account state | Network / IAM | Existing core |
| Wi-Fi / Network | Cannot join SSID, wireless drops, one device cannot connect | High | Medium | Detailed | SSID visibility, other users, profile reset, hotspot test | AP/controller, network policy, wireless infrastructure | Network | Later polish |
| Small Office Network | Router, switch, LAN, DHCP, DNS, office outage | High | Detailed | Detailed | Scope, Wi-Fi vs wired, modem/router lights, switch lights, IP, gateway, DNS | ISP, firewall, switch, DHCP, DNS, VLAN, router access | Network / ISP | Phase 1 completed |
| VoIP / Telephony | Desk phone down, no dial tone, not registered, choppy calls | High | Detailed | Detailed | Scope, call path, power/PoE, link light, IP, phone display registration, call quality | PBX, SIP trunk, carrier, voice VLAN, QoS, vendor review | Voice / Network / Vendor | Phase 1 completed |
| Login / Account / MFA | Cannot sign in, locked account, MFA issue, password problem | High | Detailed | Detailed | Platform, scope, error, password timing, MFA behavior, browser/device test | Account state, reset, licensing, conditional access, sign-in logs | IAM / Service Desk | Phase 2 completed |
| Outlook / Email | Not receiving mail, sync error, send failure, mailbox access | High | Detailed | Detailed | Symptom, scope, send/receive direction, recent change, webmail comparison, Outlook client state | Mail flow, mailbox rules, quarantine, tenant policy, trace/log/admin review | Email / M365 | Phase 3.1 completed |
| Teams Audio / Video | Mic not working, camera issue, meeting audio problem | High | Detailed | Detailed | Symptom, scope, selected audio/video device, other-app comparison, browser vs desktop, OS permission/device setting | Teams policy, tenant configuration, device management, Desktop/hardware review | M365 / Desktop | Phase 3.2 completed |
| Printer / Scanner | Cannot print, scanner not working, queue stuck, scan-to-email or scan-to-folder failure | High | Detailed | Detailed | Symptom, scope, selected printer/scanner/queue/destination, visible device state, local queue, other-user/device comparison | Print server, driver deployment, MFD admin, scanner share, mailbox scan settings, file destination permissions | Desktop / Print / M365 / File Admin | Phase 3.3 completed |
| File Access / Permission | Access denied, shared folder unavailable, network drive issue | High | Detailed | Detailed | Exact path, URL/resource type, scope, previous access, VPN/network context, permitted-user comparison, client/browser/sync/mapped-drive isolation, visible permission boundary | ACLs, group membership, share permissions, data owner approval, SharePoint/OneDrive settings, file server, M365 admin, IAM review | IAM / File Admin | Phase 2 completed |
| Application Error | Internal portal error, vendor app error, submit failure | High | Generic | Medium | Exact error, scope, browser/device comparison, recent change | Logs, code, vendor, admin portal, app owner review | App Owner / Vendor | Later |
| Device Performance | Slow laptop, freezing, high startup time | Medium | Generic | Medium | Reboot, scope, storage, startup apps, recent changes, safe user checks | EDR, hardware diagnostics, admin tools, rebuild decision | Desktop | Phase 4 |
| Software Install / Update | Installer fails, patch error, app update blocked, uninstall failure, version issue | Medium | Detailed | Detailed | Action/impact, app/version/OS/error, scope, approved source, restart pending, visible disk space, previous install/version state | Admin rights, Intune/MDM, software deployment, EDR/application control, licensing, event logs, registry/system repair, package repository, admin portal, vendor review | Desktop / Packaging / MDM / Licensing / Security / Vendor | Phase 4.2 completed |
| Hardware / Peripheral | USB device, headset, keyboard, mouse not detected | Medium | Generic | Medium | Cable, port, different device, OS detection, battery/power | Replacement, warranty, driver deployment, device admin | Desktop / Vendor | Phase 4 or fallback |
| Display / Monitor / Docking Station | External monitor blank, dock not working, projector issue, no signal, flickering, layout/resolution issue | Medium | Detailed | Detailed | Symptom, physical display path, scope, power/input/cable/dock/adapter state, display mode, resolution/scaling, direct-vs-dock and known-good comparison | Driver deployment, dock firmware, hardware diagnostics, managed dock policy, MDM/Intune, AV room system, warranty/replacement, vendor review | Desktop / AV / MDM / Vendor | Phase 4.1 completed |
| OneDrive / SharePoint Sync | Sync stuck, file conflict, library not syncing | Medium | Missing / generic | Medium | Web access, sync client status, path length, storage, account context | Tenant policy, library config, permissions, admin center | M365 | Phase 5 |
| Browser Issue | Site fails, login loop, certificate warning, extension issue | Medium | Missing / generic | Medium | Other browser, private window, cache, extensions, network path | Proxy, certificate, site owner, app owner review | Desktop / Network / App Owner | Phase 4 |
| Mobile / Hotspot | Hotspot will not connect, mobile data issue, tethering fails | Medium | Generic | Medium | Signal, data enabled, tethering setting, other device test | Carrier, MDM policy, device enrollment | Carrier / MDM | Phase 5 |
| Meeting Room AV | Room display, camera, microphone, room PC issue | Medium | Missing | Medium | Input source, cables, room PC status, Teams device state | Room system admin, firmware, AV vendor | AV / Desktop / Vendor | Phase 5 |
| Phishing Email | Suspicious email, malicious attachment, spoofed sender | High | Missing | Escalation-focused | Do not click, collect sender, subject, time, screenshot/header if safe | Quarantine, mail trace, security tooling, threat analysis | Security | Phase 6 |
| Suspicious Login | Unknown MFA prompt, impossible travel, user denies login | High | Missing | Escalation-focused | Confirm user activity, time, MFA prompt, affected account | Sign-in logs, session revocation, password reset policy | Security / IAM | Phase 6 |
| Malware Alert | AV alert, suspicious process, infected device concern | High | Missing | Escalation-focused | Isolate device if instructed, preserve evidence, capture alert details | EDR console, containment, forensic review | Security | Phase 6 |
| Lost / Stolen Device | Missing laptop, stolen phone, lost company device | High | Missing | Escalation-focused | Confirm device, user, time, location, ownership | Remote lock/wipe, legal/security process, MDM action | Security / MDM | Phase 6 |
| Clicked Suspicious Link | User clicked phish, entered credentials, downloaded file | High | Missing | Escalation-focused | Disconnect if needed, capture URL/time/action, confirm credentials entered | Account containment, EDR, mail trace, password/session actions | Security / IAM | Phase 6 |
| Unknown Issue | Vague report, incomplete symptom, unclear owner | High | Basic fallback | Strong fallback | Exact symptom, scope, impact, recent change, context discovery | Responsible owner unclear, privileged system access needed | Triage / Responsible Team | Always |
| Vendor-specific App | Niche app error, vendor SaaS issue, custom workflow problem | Medium | Generic | Fallback or medium | Exact error, scope, browser/device, recent change, workaround | Vendor logs, admin console, app owner review | App Owner / Vendor | Fallback |
| Backend / Server / Database / Cloud Infrastructure | Server error, database issue, cloud outage, API failure | Low for Level 1 | Generic | Escalation-focused fallback | Capture impact, exact error, scope, time, affected service | Logs, metrics, cloud console, database/admin access | Infrastructure / Cloud / DBA | Fallback |

## Implementation Phases

### Phase 1: Completed

- Small Office Network
- VoIP / Telephony

### Phase 2: Completed

- Login / Account / MFA
- File Access / Permission

### Phase 3.1: Completed

- Outlook / Email

### Phase 3.2: Completed

- Teams Audio / Video

### Phase 3.3: Completed

- Printer / Scanner polish

### Phase 4.1: Completed

- Display / Monitor / Docking Station

### Phase 4.2: Completed

- Software Install / Update

### Phase 4: Remaining Candidates

- Device Performance
- Browser Issue

### Phase 5

- OneDrive / SharePoint Sync
- Meeting Room AV
- Mobile / Hotspot

### Phase 6

- Security triage playbooks

## Playbook Quality Standard

A high-quality detailed playbook should include:

- 5-8 strong troubleshooting steps
- Appropriate diagnostic layers
- `fail_cause`
- Pass/fail result mapping
- `ruled_out_cause` where useful
- `evidence_prompt`
- `next_action`
- Level 1 boundary metadata
- Escalation metadata
- Backend tests for no evidence, early failure, missing evidence, ruled-out causes, next actions, and escalation

Detailed playbooks should be promoted only when the category is common enough and the evidence path is clear enough to justify this standard.

## General IT Fallback Principle

General IT fallback should act as a professional uncertainty handler. It should:

- Capture the exact symptom and error
- Confirm scope and business impact
- Ask about recent change
- Identify whether the issue smells like device, app, account, network, security, or vendor
- Suggest only safe Level 1 checks
- Avoid inventing unsupported admin or system causes
- Escalate with clean evidence when the owner is unclear or privileged access is required

The fallback should keep the agent moving without pretending the system understands more than the evidence supports.

## AI Provider Strategy

AI can help with:

- Parsing messy user text
- Category suggestions
- Summarizing evidence
- Rewriting explanations
- Drafting internal notes and escalation notes
- Proposing future playbook content for human review

AI must not:

- Control diagnosis progression independently
- Claim logs, accounts, admin portals, MDM, PBX, VPN, Entra ID, Intune, or Microsoft 365 were checked unless a real integration returns data
- Bypass playbook layers
- Invent system states

The playbook engine should remain the source of truth for current layer, missing evidence, completed layers, next actions, Level 1 boundary, and escalation recommendation.

## Risks and Controls

| Risk | Control |
| --- | --- |
| Too many shallow playbooks | Only promote categories to detailed playbooks when they have tests and clear diagnostic value. |
| Drifting into a generic chatbot | Keep diagnosis progression in the engine, not in free-form AI text. |
| Adding integrations too early | Add integrations later only as read-only evidence providers. |
| Overengineering branching logic | Prefer linear progressive playbooks until evidence shows a real branching need. |
| Trying to cover every vendor product | Use General IT fallback and vendor escalation patterns for long-tail products. |
| Weak portfolio signal | Prioritize common, interview-worthy support scenarios with clear tests and professional escalation logic. |

## Next Immediate Step

After Phase 4.2, the next development step should be review and then decide whether to pause backend expansion and move to frontend MVP / end-to-end usability testing:

1. Review Phase 4.2 before deciding the next direction.
2. Prefer pausing backend playbook expansion and moving to frontend MVP / end-to-end usability testing.
3. Keep Device Performance generic or medium-depth for now because it is broad.
4. Keep Browser Issue waiting until a Browser issue category decision is made.
5. Continue avoiding knowledge base search, real integrations, auth, SQLite, admin panel, or auto-remediation.
