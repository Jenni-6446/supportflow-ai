# Test Scenarios

These scenarios are useful for manual portfolio demonstrations and regression checks. Expected results are intentionally phrased as triage outcomes, not confirmed diagnoses.

| Scenario | Useful details to provide | Expected triage direction |
| --- | --- | --- |
| Printer job produces no output | Printer name, queue behavior, other users, error messages | Printing category, missing scope/device context, safe queue and connectivity checks |
| VPN authentication fails | Exact message, location, recent password change, other services | Network/access category, authentication-focused questions, bounded Level 1 checks |
| Outlook receives no new mail | Webmail status, send behavior, affected account/device, start time | Email category, service-versus-client isolation questions |
| Shared folder returns Access Denied | Folder path description, affected users, prior access, recent changes | File-access category, permission and scope questions without claiming directory inspection |
| Teams microphone is not heard | Selected device, other applications, meeting scope, mute state | Collaboration/audio category, device-selection and isolation checks |
| Vague report: “Everything is slow” | Affected applications, device, network, timing, user scope | Missing-information prompts rather than a confident category or root-cause claim |

## Fallback Check

Run a scenario without LLM credentials. The app should still return a deterministic triage response and controlled checklist. Interpretation may be less nuanced, but the workflow should not make unsupported system-state claims.

## Safety Check

When testing structured LLM output, confirm that content claiming real logs, admin portals, accounts, devices, networks, Microsoft 365, Intune, print servers, PBX systems, VPN systems, or vendor systems were checked is rejected in favor of fallback behavior.
