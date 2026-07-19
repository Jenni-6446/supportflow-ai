# IT Support Diagnostic Coverage Taxonomy

This document defines the product-level diagnostic coverage model for SupportFlow AI.
It is not an API schema and does not replace the current playbook engine. The current
playbooks remain the source of truth for checklist behavior. This taxonomy is meant to
guide future playbook design, LLM extraction prompts, clarification questions, and
rule-out logic.

The goal is not to write one playbook for every possible IT issue. The goal is to
cover common diagnostic paths using categories, dimensions, candidate causes, safe
Level 1 questions, safe Level 1 checks, and clear escalation boundaries.

## Account / Login / MFA

- Diagnostic dimensions: affected account or app, password state, MFA behavior,
  lockout state, web vs desktop/mobile behavior, one user vs many users, recent
  password/device/profile change.
- Common candidate causes: incorrect password, expired password, locked account,
  MFA prompt failure, stale saved credential, missing access assignment, account
  policy or identity platform issue.
- Level 1 clarification questions: Which account or app is affected? What exact
  error appears? Does MFA prompt and approval work? Did the user recently change
  password, phone, authenticator, or device? Can the user sign in elsewhere?
- Level 1 checks: confirm exact sign-in path, test known web sign-in page if safe,
  confirm MFA prompt behavior, clear or re-enter saved credentials where allowed,
  compare another browser/device if available.
- Escalation boundaries: account unlock/reset beyond policy, MFA reset, identity
  provider review, conditional access/policy review, directory/admin portal review.
- Example user inputs: "I cannot log in to my work account"; "MFA is not sending a
  code"; "It says my account is locked."

## Network / VPN / Wi-Fi

- Diagnostic dimensions: internet vs VPN vs Wi-Fi, local device vs network-wide,
  wired vs wireless, DNS/DHCP/gateway symptoms, one user vs site-wide, error text,
  recent password/network/router/ISP change.
- Common candidate causes: Wi-Fi disconnected, weak signal, ISP outage, DNS failure,
  DHCP/gateway issue, captive portal, VPN authentication failure, VPN client/profile
  issue, firewall or routing boundary.
- Level 1 clarification questions: Does normal internet work without VPN? Is the
  issue Wi-Fi, VPN, or all network access? What exact error appears? Are other users
  or devices affected? Did anything change recently?
- Level 1 checks: confirm basic connectivity, compare another website/app, reconnect
  Wi-Fi, check VPN client/profile selection, confirm MFA behavior, compare another
  device or network if available.
- Escalation boundaries: firewall, router, switch, ISP, VPN admin portal, logs,
  routing, DNS/DHCP server, infrastructure review.
- Example user inputs: "VPN authentication failed"; "Wi-Fi is connected but nothing
  loads"; "Everyone in the office lost internet."

## Email / Outlook

- Diagnostic dimensions: send vs receive vs sync vs access, Outlook desktop vs
  webmail, one sender/recipient vs all mail, mailbox or shared mailbox, exact error,
  recent password/profile/device change.
- Common candidate causes: Outlook client/profile sync issue, mailbox credential
  issue, webmail/mailbox access issue, sender/recipient-specific delivery issue,
  rule/quarantine/mail-flow/admin boundary.
- Level 1 clarification questions: Is the issue sending, receiving, syncing, or
  opening a mailbox? Does webmail work? Does Outlook desktop show an error? Is it
  one sender/recipient or all mail? When did it start?
- Level 1 checks: compare Outlook desktop with webmail, confirm mailbox access,
  check outbox/sync status visible to the user, capture error text, compare one
  test message where appropriate.
- Escalation boundaries: mail trace, quarantine, mailbox rules requiring admin
  review, Exchange/M365 admin center, tenant policy, transport rule, mailbox access
  configuration.
- Example user inputs: "Outlook is not receiving email"; "Email is stuck in outbox";
  "I cannot open a shared mailbox."

## File / Permission

- Diagnostic dimensions: file, folder, shared drive, Teams/SharePoint/OneDrive path,
  access denied vs missing file vs sync issue, one user vs group, previous access,
  owner or permission model.
- Common candidate causes: missing permission, wrong link/path, expired sharing link,
  sync client issue, file moved/deleted, group membership or platform permission
  boundary.
- Level 1 clarification questions: What exact file/folder/link is affected? What
  error appears? Did the user have access before? Can other permitted users open it?
  Is this a local file, network drive, Teams, SharePoint, or OneDrive item?
- Level 1 checks: verify path/link, confirm error text, compare browser vs sync app
  where safe, test with another permitted user, confirm file was not renamed or moved
  based on visible evidence.
- Escalation boundaries: permission changes, group membership, file owner/admin
  review, SharePoint/OneDrive/Teams admin settings, file server or storage review.
- Example user inputs: "Access denied to a shared folder"; "I cannot open a Teams
  file"; "The network drive says permission denied."

## Printer / Scanner

- Diagnostic dimensions: print vs scan vs copy vs scan-to-email/folder, selected
  printer/scanner, queue behavior, device panel state, one user/device vs many users,
  local printer vs shared printer, destination path or mailbox.
- Common candidate causes: wrong selected printer, stuck local queue, offline printer,
  paper/toner/jam/error state, driver issue, shared print service issue, scan
  destination or mailbox/share boundary.
- Level 1 clarification questions: Which printer or scanner was selected? Does the
  job appear in the queue? Does the device panel show Ready or an error? Can other
  users print or scan? Is this scan-to-email or scan-to-folder?
- Level 1 checks: confirm selected device, check visible device status, check local
  queue/stuck job, compare another document/app, compare another user/device where
  appropriate.
- Escalation boundaries: print server, printer admin portal, MFD admin panel, driver
  deployment, Intune/MDM, scanner share, mailbox scan settings, vendor service.
- Example user inputs: "Nothing printed"; "Printer is offline"; "Scan to email
  fails"; "Scan to folder stopped working."

## Display / Monitor / Dock

- Diagnostic dimensions: monitor power, input source, cable/port/dock path, laptop
  awake state, one display vs all displays, mirrored/extended mode, resolution or
  flicker, recent driver/dock/OS change.
- Common candidate causes: monitor powered off or wrong input, loose cable, dock or
  adapter issue, display mode issue, OS display setting, driver/dock firmware/admin
  boundary, hardware fault.
- Level 1 clarification questions: Is the monitor power light on? Does the computer
  screen still work? Does another cable/port/dock work? Is the display detected by
  the OS? Did it start after sleep, update, or docking change?
- Level 1 checks: confirm power/input, reseat cable/dock, wake/undock/redock,
  check display mode if user-accessible, compare another monitor/cable/port where
  available.
- Escalation boundaries: driver deployment, firmware management, hardware diagnostics,
  device management tools, warranty/vendor repair, docking station fleet issue.
- Example user inputs: "External monitor is blank"; "Dock display has no signal";
  "Projector is not showing my screen."

## Audio / Video / Meeting

- Diagnostic dimensions: microphone vs camera vs speakers, input vs output, selected
  device, Teams/Zoom/browser vs all apps, one meeting vs all meetings, OS permissions,
  headset/cable/Bluetooth state.
- Common candidate causes: wrong selected device, muted microphone, OS permission
  blocked, headset disconnected, Teams/browser client issue, meeting policy/admin
  boundary, room AV hardware issue.
- Level 1 clarification questions: Is the issue microphone, camera, or speaker?
  Does the device work in another app? Does browser work if desktop app fails? Is it
  one meeting or all meetings? What error appears?
- Level 1 checks: confirm selected audio/video devices, mute state, headset
  connection, OS camera/microphone permission, compare another app/browser, restart
  meeting client where safe.
- Escalation boundaries: Teams/M365 admin policy, device management, meeting room
  controller, AV hardware, logs, vendor support, room system configuration.
- Example user inputs: "Teams microphone is not working"; "Others cannot hear me";
  "Meeting room display or speakers are not working."

## Software / Application

- Diagnostic dimensions: install vs update vs launch vs crash vs app error, exact
  app/version, user rights prompt, installer/update source, one user/device vs many,
  network/proxy/certificate dependency.
- Common candidate causes: stale app cache, corrupt install, missing permission,
  admin rights needed, blocked update, incompatible version, vendor outage or admin
  deployment boundary.
- Level 1 clarification questions: Which app and version? Is this install, update,
  launch, or in-app error? What exact message appears? Did it work before? Does it
  affect one device or many?
- Level 1 checks: capture exact error, retry safe user-level install/update if
  allowed, restart app/device where appropriate, compare web version or another
  device, confirm storage/network basics when relevant.
- Escalation boundaries: admin rights, software deployment tools, Intune/MDM, EDR
  blocks, managed browser/app policy, vendor admin portal, license assignment.
- Example user inputs: "Software update fails"; "Installer asks for admin rights";
  "The app crashes after opening."

## Device / Hardware / Performance

- Diagnostic dimensions: slow vs freezing vs crashing vs peripheral failure, device
  age/state, power/battery/storage symptoms visible to user, one app vs whole device,
  recent updates, heat/noise/physical damage.
- Common candidate causes: high resource usage, insufficient storage, failing battery
  or power adapter, peripheral/cable issue, OS update state, hardware fault, security
  or management agent boundary.
- Level 1 clarification questions: Is the whole device slow or only one app? When
  did it start? Is there a visible warning? Does restart temporarily help? Is there
  physical damage, heat, battery, or power behavior?
- Level 1 checks: capture visible symptoms, restart if appropriate, close obvious
  user apps, confirm storage/power indicators visible to user, compare another
  peripheral/cable if safe.
- Escalation boundaries: hardware diagnostics, EDR/security tools, event logs,
  driver/firmware deployment, warranty repair, device replacement, admin rights.
- Example user inputs: "Laptop is very slow"; "Computer freezes"; "Keyboard or mouse
  stopped working."

## Security / Suspicious Activity

- Diagnostic dimensions: suspicious email, account compromise signs, pop-up or
  malware warning, lost/stolen device, unusual login, data exposure risk, whether the
  user clicked a link or entered credentials.
- Common candidate causes: phishing attempt, malicious attachment/link, compromised
  credentials, browser notification scam, lost device, security policy boundary.
- Level 1 clarification questions: What did the user see or click? Did they enter a
  password or MFA code? Is any data exposed? Is the device lost or stolen? Is there a
  screenshot or message text?
- Level 1 checks: preserve evidence, advise user not to click further, disconnect
  from risky action if policy allows, capture sender/link/message details, follow
  internal security escalation process.
- Escalation boundaries: SOC/security team, account containment, EDR, SIEM/logs,
  email security gateway, device wipe, legal/privacy review.
- Example user inputs: "I clicked a suspicious email"; "I see a virus warning";
  "My account sent messages I did not send."

## General Unknown

- Diagnostic dimensions: affected thing, attempted action, visible symptom/error,
  previous working state, scope, work impact, recent changes, safest owner family.
- Common candidate causes: insufficient information, issue belongs to another common
  support path, mixed symptoms, vendor/system/admin boundary, non-IT issue.
- Level 1 clarification questions: What exactly is not working: device, app, account,
  network, file, printer, display, meeting tool, or something else? What were you
  trying to do? Do you see an exact error or warning? Did it work before? Is it only
  you or other users too? Is it blocking work right now?
- Level 1 checks: capture exact symptom and attempted action, confirm scope and
  impact, identify recent change or workaround, sort visible symptoms into a likely
  support family, perform only safe local isolation checks when appropriate.
- Escalation boundaries: unclear ownership after safe clarification, multiple users
  or high business impact, privileged/admin/vendor/system review, any unsafe action.
- Example user inputs: "Something stopped working"; "The system is acting weird";
  "I am not sure what is broken."

## Future Connection To The Engine

The smallest safe next refactor would be internal-only:

1. Add diagnostic dimensions as internal metadata on playbook questions and steps.
2. Let LLM analyze-ticket extract observed dimensions and missing dimensions.
3. Use the taxonomy to select the top 3-5 clarification questions.
4. Keep playbook layers responsible for evidence collection, rule-out logic, and
   escalation boundaries.
5. Keep external API schemas stable until the internal model proves useful.
