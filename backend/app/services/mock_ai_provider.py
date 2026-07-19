import re
from types import SimpleNamespace

from app.schemas.analysis import (
    ChecklistGroup,
    Impact,
    InitialTriageResponse,
    IssueCategory,
    Priority,
)
from app.schemas.diagnosis import (
    ChecklistResult,
    ChecklistResultValue,
    UpdatedDiagnosisResponse,
)
from app.schemas.documentation import DocumentationResponse
from app.schemas.ticket import (
    AccountPlatform,
    AffectedUsers,
    ApplicationPlatform,
    OperatingSystem,
    TicketInput,
    Urgency,
)
from app.services.ai_provider import AIProvider
from app.services.diagnostic_question_selector import select_clarification_questions
from app.services.diagnostic_signal_question_selector import (
    select_signal_based_questions,
    signal_based_possible_causes,
)
from app.services.evidence_aware_diagnosis import (
    EvidenceAssessment,
    assess_evidence,
    filter_completed_or_contradicted_actions,
)
from app.services.playbooks import (
    COMMON_LAYER_ORDER,
    PLAYBOOKS,
    Playbook,
    PlaybookStep,
    get_playbook,
)


CLASSIFICATION_ORDER: tuple[IssueCategory, ...] = (
    IssueCategory.VPN_REMOTE_ACCESS,
    IssueCategory.MOBILE_HOTSPOT,
    IssueCategory.PRINTER,
    IssueCategory.FILE_ACCESS_PERMISSION,
    IssueCategory.TEAMS_AUDIO_VIDEO,
    IssueCategory.EMAIL_OUTLOOK,
    IssueCategory.LOGIN_ACCOUNT,
    IssueCategory.VOIP_TELEPHONY,
    IssueCategory.DISPLAY_MONITOR,
    IssueCategory.HARDWARE_PERIPHERAL,
    IssueCategory.SOFTWARE_INSTALLATION_UPDATE,
    IssueCategory.DEVICE_PERFORMANCE,
    IssueCategory.SMALL_OFFICE_NETWORK,
    IssueCategory.NETWORK_WIFI,
    IssueCategory.APPLICATION_ERROR,
)


GLOBAL_RULED_OUT_CAUSES: dict[str, str] = {
    "vpn-confirm-internet": "General internet connectivity issue",
    "teams-other-app": "Hardware microphone issue outside Teams",
    "printer-other-users": "Shared printer or print service issue",
}


LOGIN_AUTH_TERMS: tuple[str, ...] = (
    "cannot sign in",
    "can't sign in",
    "unable to sign in",
    "sign in",
    "sign-in",
    "login",
    "log in",
    "mfa",
    "multi-factor",
    "account locked",
    "locked out",
    "incorrect password",
    "password reset",
)


EMAIL_DELIVERY_OR_MAILBOX_TERMS: tuple[str, ...] = (
    "not receiving",
    "cannot receive",
    "can't receive",
    "did not receive",
    "not received",
    "cannot send",
    "can't send",
    "send email",
    "receive email",
    "outbox",
    "sync error",
    "mailbox access",
    "shared mailbox",
    "mail delivery",
    "delivery failure",
    "missing email",
    "emails have not arrived",
)


FILE_ACCESS_TERMS: tuple[str, ...] = (
    "file share",
    "shared folder",
    "network drive",
    "mapped drive",
    "permission denied",
    "access denied",
    "cannot open",
)


PRINT_SCAN_TERMS: tuple[str, ...] = (
    "printer",
    "print",
    "printing",
    "scanner",
    "scan-to-email",
    "scan to email",
    "scan-to-folder",
    "scan to folder",
    "mfd",
)


SOFTWARE_INSTALL_UPDATE_TERMS: tuple[str, ...] = (
    "installer fails",
    "installer error",
    "install fails",
    "install failure",
    "will not install",
    "won't install",
    "cannot install",
    "can't install",
    "software update fails",
    "update fails",
    "update failure",
    "patch blocked",
    "patch is blocked",
    "patch will not",
    "uninstall fails",
    "uninstall failure",
    "app version issue",
    "version mismatch",
    "package deployment",
    "admin rights prompt",
)


SOFTWARE_NEGATION_TERMS: tuple[str, ...] = (
    "no install or update failed",
    "no install or update is currently failing",
    "no install failed",
    "no update failed",
    "without an install failure",
    "without an update failure",
)


DEVICE_PERFORMANCE_TERMS: tuple[str, ...] = (
    "slow",
    "performance",
    "freezing",
    "freezes",
    "freeze",
    "lag",
    "startup",
    "unresponsive",
)


DISPLAY_OUTPUT_TERMS: tuple[str, ...] = (
    "external monitor",
    "second monitor",
    "projector",
    "dock",
    "docking station",
    "hdmi",
    "displayport",
    "usb-c",
    "no signal",
    "blank display",
    "blank screen",
    "flickering display",
    "resolution",
    "scaling",
    "duplicate",
    "extend",
)

APP_LOCATION_WORKFLOW_ACTION_TERMS: tuple[str, ...] = (
    "clock in",
    "clock-in",
    "punch in",
    "punch-in",
    "check in",
    "check-in",
    "attendance",
)

APP_LOCATION_WORKFLOW_APP_TERMS: tuple[str, ...] = (
    "staff app",
    "roster app",
    "delivery app",
    "attendance app",
    " app",
    "app ",
    " portal",
    "portal ",
    "through my ",
    "through the ",
    "through ",
)

APP_LOCATION_WORKFLOW_LOCATION_TERMS: tuple[str, ...] = (
    "location",
    "right location",
    "correct location",
    "allowed location",
    "job site",
    "on site",
    "onsite",
    "gps",
    "geofence",
)


class MockAIProvider(AIProvider):
    def analyze_ticket(self, ticket: TicketInput) -> InitialTriageResponse:
        category = self._classify(ticket)
        playbook = get_playbook(category)
        return InitialTriageResponse.model_validate(
            self._playbook_payload(ticket, playbook)
        )

    def update_diagnosis(
        self,
        ticket: TicketInput,
        checklist_results: list[ChecklistResult],
    ) -> UpdatedDiagnosisResponse:
        category = self._classify(ticket)
        playbook = get_playbook(category)
        if category == IssueCategory.VPN_REMOTE_ACCESS:
            return self._vpn_updated_diagnosis(ticket, playbook, checklist_results)
        return self._generic_updated_diagnosis(ticket, playbook, checklist_results)

    def generate_documentation(
        self,
        ticket: TicketInput,
        diagnosis: UpdatedDiagnosisResponse,
    ) -> DocumentationResponse:
        cause = diagnosis.current_likely_cause.cause
        next_action = diagnosis.next_best_action
        return DocumentationResponse.model_validate(
            {
                "internalNote": (
                    f"{ticket.title}: {ticket.user_message} Current likely cause: "
                    f"{cause}. Next action: {next_action}"
                ),
                "userResponseDraft": (
                    "Thanks for the details. I am working through a structured "
                    "troubleshooting checklist and may ask you to confirm a few "
                    "items so we can narrow the cause."
                ),
                "resolutionNote": (
                    f"Resolved after following guided troubleshooting for "
                    f"{ticket.affected_service}. Final cause should be confirmed "
                    "by the agent before closing the ticket."
                ),
                "escalationNote": (
                    f"Please review the issue for {ticket.affected_service}. "
                    f"Current likely cause: {cause}. Evidence collected: "
                    f"{'; '.join(diagnosis.evidence_summary) or 'No checklist evidence recorded yet.'}"
                ),
            }
        )

    def _playbook_payload(self, ticket: TicketInput, playbook: Playbook) -> dict:
        payload = self._base_payload(ticket, playbook)
        payload["missingInformation"] = self._missing_information_payload(
            ticket,
            playbook,
        )
        payload["possibleCauses"] = [
            {
                "cause": self._format_playbook_text(cause.cause, ticket),
                "likelihood": cause.likelihood,
                "reason": self._format_playbook_text(cause.reason, ticket),
            }
            for cause in playbook.possible_causes
        ]
        self._apply_app_location_workflow_fallback(ticket, playbook, payload)
        payload["checklist"] = [
            {
                "id": step.id,
                "group": step.layer.value,
                "step": self._format_playbook_text(step.step, ticket),
                "why": self._format_playbook_text(step.why, ticket),
                "expectedResultType": step.expected_result_type.value,
                "level1Actionable": step.level1_actionable,
                "requiresPrivilegedAccess": step.requires_privileged_access,
                "accessRequirement": (
                    self._format_playbook_text(step.access_requirement, ticket)
                    if step.access_requirement
                    else None
                ),
                "evidencePrompt": (
                    self._format_playbook_text(step.evidence_prompt, ticket)
                    if step.evidence_prompt
                    else None
                ),
            }
            for step in playbook.checklist_steps
        ]
        payload["escalationCriteria"] = [
            self._format_playbook_text(item, ticket)
            for item in playbook.escalation_criteria
        ]
        return payload

    def _apply_app_location_workflow_fallback(
        self,
        ticket: TicketInput,
        playbook: Playbook,
        payload: dict,
    ) -> None:
        ticket_text = self._ticket_text(ticket)
        if (
            playbook.issue_category != IssueCategory.APPLICATION_ERROR
            or not self._looks_like_application_location_workflow(ticket_text)
        ):
            return

        draft = self._application_location_workflow_draft(ticket)
        signal_questions = select_signal_based_questions(
            playbook.issue_category,
            ticket_text,
            draft,
        )
        signal_causes = signal_based_possible_causes(
            playbook.issue_category,
            ticket_text,
            draft,
        )
        if signal_questions:
            payload["missingInformation"] = signal_questions
        if signal_causes:
            payload["possibleCauses"] = signal_causes

    def _missing_information_payload(
        self,
        ticket: TicketInput,
        playbook: Playbook,
    ) -> list[dict[str, str]]:
        try:
            selected_questions = select_clarification_questions(
                playbook.issue_category,
                self._ticket_text(ticket),
                playbook.missing_information,
            )
        except Exception:
            selected_questions = [
                {
                    "question": item.question,
                    "reason": item.reason,
                }
                for item in playbook.missing_information
            ]

        return [
            {
                "question": self._format_playbook_text(item["question"], ticket),
                "reason": self._format_playbook_text(item["reason"], ticket),
            }
            for item in selected_questions
        ]

    def _base_payload(self, ticket: TicketInput, playbook: Playbook) -> dict:
        return {
            "summary": self._summary(ticket),
            "classification": {
                "category": playbook.issue_category.value,
                "subcategory": playbook.subcategory,
                "type": "incident",
            },
            "priorityAssessment": {
                "impact": self._impact(ticket).value,
                "urgency": ticket.agent_selected_urgency.value,
                "priority": self._priority(ticket).value,
                "confidence": "medium",
                "reasoning": (
                    "Priority is guided by the fixed impact and urgency matrix. "
                    "If scope or urgency is unclear, collect missing information "
                    "before increasing priority."
                ),
            },
            "missingInformation": [],
            "possibleCauses": [],
            "checklist": [],
            "escalationCriteria": [],
            "safetyNotes": self._safety_notes(),
        }

    def _generic_updated_diagnosis(
        self,
        ticket: TicketInput | Playbook,
        playbook: Playbook | list[ChecklistResult],
        checklist_results: list[ChecklistResult] | None = None,
    ) -> UpdatedDiagnosisResponse:
        if checklist_results is None:
            playbook, checklist_results = ticket, playbook
            ticket = self._placeholder_ticket_for_playbook(playbook)
        assert isinstance(ticket, TicketInput)
        assert isinstance(playbook, Playbook)

        evidence_summary = self._evidence_summary(checklist_results)
        results_by_step = {result.step_id: result for result in checklist_results}
        assessment = assess_evidence(ticket, playbook, checklist_results)
        ruled_out_causes = self._combined_ruled_out_causes(
            playbook,
            checklist_results,
            assessment,
        )
        explicit_escalation = any(
            result.result == ChecklistResultValue.NEEDS_ESCALATION
            for result in checklist_results
        )

        if not checklist_results:
            next_actions = self.determine_next_best_actions(playbook, results_by_step)
            next_best_action = (
                f"Collect missing information: {next_actions[0]}"
                if next_actions
                else (
                    "Collect missing information and complete the first "
                    "scope_impact checks."
                )
            )
            return UpdatedDiagnosisResponse.model_validate(
                {
                    "currentLikelyCause": {
                        "cause": (
                            "More information needed"
                            if playbook.issue_category == IssueCategory.GENERAL_IT
                            else f"More {playbook.subcategory} evidence needed"
                        ),
                        "confidence": "low",
                        "reasoning": (
                            "No checklist evidence has been recorded. Start with "
                            "scope_impact and ask missing-information questions "
                            "before guessing at deeper causes."
                        ),
                    },
                    "ruledOutCauses": ruled_out_causes,
                    "evidenceSummary": evidence_summary,
                    "nextBestAction": next_best_action,
                    **self._progressive_response_fields(
                        playbook,
                        checklist_results,
                        next_best_action,
                        should_escalate=False,
                        assessment=assessment,
                    ),
                    "escalationRecommendation": {
                        "shouldEscalate": False,
                        "reason": "Evidence is missing, so continue information gathering first.",
                    },
                    "confidence": "low",
                    "status": "in_progress",
                }
            )

        failed_step, failed_result = self._first_failed_step(
            playbook, results_by_step
        )
        if failed_step is not None and failed_result is not None:
            metadata_requires_escalation = (
                failed_step.requires_privileged_access
                or not failed_step.level1_actionable
            )
            should_escalate = (
                explicit_escalation
                or failed_step.layer == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
                or metadata_requires_escalation
            )
            metadata_escalation_reason = (
                failed_step.escalation_reason or failed_step.access_requirement
            )
            escalation_reason = ""
            if should_escalate:
                escalation_reason = (
                    metadata_escalation_reason
                    if metadata_requires_escalation and metadata_escalation_reason
                    else (
                        "A checklist result indicates escalation is needed."
                        if explicit_escalation
                        else "The next action requires admin, vendor, infrastructure, or external-system review."
                    )
                )
            next_best_action = (
                "Prepare escalation for the responsible team."
                if should_escalate
                else f"Continue {failed_step.layer.value}: {failed_step.step}"
            )
            likely_cause = assessment.suggested_cause or failed_step.fail_cause
            likely_confidence = (
                assessment.confidence
                if assessment.suggested_cause
                else ("high" if should_escalate else "medium")
            )
            likely_reasoning = (
                f"Evidence in {failed_step.layer.value} failed: "
                f"{failed_result.evidence or failed_step.step}. "
                "Focus on this layer before moving deeper."
            )
            return UpdatedDiagnosisResponse.model_validate(
                {
                    "currentLikelyCause": {
                        "cause": likely_cause,
                        "confidence": likely_confidence,
                        "reasoning": likely_reasoning,
                    },
                    "ruledOutCauses": ruled_out_causes,
                    "evidenceSummary": evidence_summary,
                    "nextBestAction": next_best_action,
                    **self._progressive_response_fields(
                        playbook,
                        checklist_results,
                        next_best_action,
                        should_escalate=should_escalate,
                        blocker_reason=escalation_reason,
                        assessment=assessment,
                    ),
                    "escalationRecommendation": {
                        "shouldEscalate": should_escalate,
                        "reason": (
                            escalation_reason
                            if should_escalate
                            else "Continue local and user-side checks before escalating."
                        ),
                    },
                    "confidence": "high" if should_escalate else "medium",
                    "status": (
                        "ready_to_escalate" if should_escalate else "in_progress"
                    ),
                }
            )

        next_step = self._next_unresolved_step(playbook, results_by_step)
        if next_step is None or next_step.layer == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE:
            next_best_action = (
                "Escalate to the responsible support team with the "
                "recorded evidence and completed checklist results."
            )
            suggested_admin_boundary_cause = (
                assessment.suggested_cause
                if self._assessment_has_specific_direction(assessment)
                else None
            )
            likely_cause = suggested_admin_boundary_cause or (
                f"{playbook.subcategory} may require admin or infrastructure review"
            )
            likely_confidence = (
                assessment.confidence if suggested_admin_boundary_cause else "medium"
            )
            likely_reasoning = (
                assessment.reasoning
                if suggested_admin_boundary_cause
                else (
                "Earlier playbook layers have not failed based on the "
                "recorded evidence. The remaining layer is "
                "escalation_admin_infrastructure, so escalation is "
                "recommended rather than claiming system checks."
                )
            )
            return UpdatedDiagnosisResponse.model_validate(
                {
                    "currentLikelyCause": {
                        "cause": likely_cause,
                        "confidence": likely_confidence,
                        "reasoning": likely_reasoning,
                    },
                    "ruledOutCauses": ruled_out_causes,
                    "evidenceSummary": evidence_summary,
                    "nextBestAction": next_best_action,
                    **self._progressive_response_fields(
                        playbook,
                        checklist_results,
                        next_best_action,
                        should_escalate=True,
                        blocker_reason=(
                            "The next layer requires admin, vendor, log, infrastructure, or external-system review."
                        ),
                        assessment=assessment,
                    ),
                    "escalationRecommendation": {
                        "shouldEscalate": True,
                        "reason": "The next layer requires admin, vendor, log, infrastructure, or external-system review.",
                    },
                    "confidence": "medium",
                    "status": "ready_to_escalate",
                }
            )

        next_best_action = f"Continue {next_step.layer.value}: {next_step.step}"
        likely_cause = assessment.suggested_cause or (
            f"{playbook.subcategory} evidence is still incomplete"
        )
        likely_confidence = assessment.confidence if assessment.suggested_cause else "low"
        likely_reasoning = assessment.reasoning or (
            "Recorded evidence has not identified a failed layer yet. "
            f"The next playbook layer to complete is {next_step.layer.value}."
        )
        return UpdatedDiagnosisResponse.model_validate(
            {
                "currentLikelyCause": {
                    "cause": likely_cause,
                    "confidence": likely_confidence,
                    "reasoning": likely_reasoning,
                },
                "ruledOutCauses": ruled_out_causes,
                "evidenceSummary": evidence_summary,
                "nextBestAction": next_best_action,
                **self._progressive_response_fields(
                    playbook,
                    checklist_results,
                    next_best_action,
                    should_escalate=explicit_escalation,
                    blocker_reason=(
                        "A checklist result indicates escalation is needed."
                        if explicit_escalation
                        else ""
                    ),
                    assessment=assessment,
                ),
                "escalationRecommendation": {
                    "shouldEscalate": explicit_escalation,
                    "reason": (
                        "A checklist result indicates escalation is needed."
                        if explicit_escalation
                        else "Continue progressive checks before escalating."
                    ),
                },
                "confidence": "low",
                "status": (
                    "ready_to_escalate" if explicit_escalation else "in_progress"
                ),
            }
        )

    def _vpn_updated_diagnosis(
        self,
        ticket: TicketInput,
        playbook: Playbook,
        checklist_results: list[ChecklistResult],
    ) -> UpdatedDiagnosisResponse:
        results = {result.step_id: result for result in checklist_results}
        evidence_summary = self._evidence_summary(checklist_results)
        ruled_out_causes = self._ruled_out_causes(playbook, checklist_results)
        explicit_escalation = any(
            result.result == ChecklistResultValue.NEEDS_ESCALATION
            for result in checklist_results
        )

        cause = "More VPN evidence needed"
        confidence = "low"
        status = "in_progress"
        should_escalate = explicit_escalation
        escalation_reason = (
            "A checklist result indicates escalation is needed."
            if explicit_escalation
            else "Continue scope_impact checks before escalating."
        )
        reasoning = (
            "Layer 1 scope_impact checks have not been recorded yet. Ask the "
            "user to confirm normal internet access outside VPN, scope, exact "
            "error message, and recent changes before guessing at deeper causes."
        )
        next_best_action = (
            "Ask whether normal internet works outside VPN, whether other users "
            "are affected, what exact error appears, and what changed recently."
        )

        internet_result = results.get("vpn-confirm-internet")
        scope_result = results.get("vpn-confirm-scope")

        if self._result_fails(internet_result):
            cause = "Local internet or basic connectivity issue"
            confidence = "high"
            reasoning = (
                "Layer 1 scope_impact checks found that normal internet outside "
                "VPN does not work. Focus on local connectivity before continuing "
                "VPN authentication, client, or admin checks."
            )
            next_best_action = (
                "Restore or confirm normal internet connectivity outside VPN, "
                "then rerun the VPN-specific checks."
            )
            should_escalate = explicit_escalation
            escalation_reason = (
                "Escalate only if local connectivity cannot be restored within "
                "Level 1 scope or a separate checklist result requests escalation."
            )
        elif self._result_affirms(scope_result):
            cause = "Possible wider VPN or network impact"
            confidence = "medium"
            should_escalate = True
            status = "ready_to_escalate"
            reasoning = (
                "Layer 1 scope_impact checks indicate multiple users may be "
                "affected. This should move to escalation instead of deeper "
                "user-side credential or device checks."
            )
            next_best_action = (
                "Prepare an escalation note with affected scope and user evidence "
                "for the responsible network or remote access team."
            )
            escalation_reason = "Multiple users appear to be affected."
        elif not checklist_results:
            pass
        elif self._has_vpn_authentication_evidence(ticket, results):
            cause = "VPN authentication or saved credential issue"
            confidence = "high"
            reasoning = (
                "Layer 1 scope_impact checks are sufficiently ruled out for this "
                "ticket, and Layer 2 simple_user_checks show password, saved "
                "credential, or MFA evidence. Do not jump to admin causes until "
                "these user-side checks are resolved or exhausted."
            )
            next_best_action = (
                "Confirm the recent password change, clear or update saved "
                "credentials if appropriate, and verify that the MFA prompt "
                "appears and approval succeeds."
            )
            escalation_reason = "Current evidence supports further Level 1 authentication checks."
        elif not self._vpn_authentication_layer_complete(results):
            reasoning = (
                "Layer 1 scope_impact checks have not shown a local connectivity "
                "failure. Layer 2 simple_user_checks are still incomplete, so ask "
                "for password-change, saved-credential, and MFA evidence before "
                "moving to client or admin causes."
            )
            next_best_action = (
                "Ask whether the password changed recently, whether saved VPN "
                "credentials are being reused, and whether MFA prompt and approval "
                "work as expected."
            )
        elif self._has_vpn_client_evidence(results):
            cause = "VPN client or VPN profile issue"
            confidence = "high"
            reasoning = (
                "Layer 1 scope_impact checks and Layer 2 simple_user_checks are "
                "sufficiently ruled out. Layer 3 device_client_application checks "
                "point to the VPN client opening, profile selection, or client "
                "error state."
            )
            next_best_action = (
                "Confirm the VPN client opens normally, select the expected VPN "
                "profile, record the client error, and escalate if profile "
                "provisioning or device-management review is required."
            )
            escalation_reason = "Current evidence supports further Level 1 client/device checks."
        elif not self._vpn_client_layer_complete(results):
            reasoning = (
                "Layer 1 scope_impact checks and Layer 2 simple_user_checks are "
                "sufficiently ruled out. Layer 3 device_client_application checks "
                "are next and should be completed before admin escalation."
            )
            next_best_action = (
                "Confirm the VPN client opens normally, the expected profile is "
                "selected, and any VPN client error message is recorded."
            )
            escalation_reason = "Continue client/device checks before escalating."
        else:
            cause = "Remote access configuration or account state requires admin review"
            confidence = "medium"
            should_escalate = True
            status = "ready_to_escalate"
            reasoning = (
                "Layer 1 scope_impact, Layer 2 simple_user_checks, and Layer 3 "
                "device_client_application checks have been sufficiently ruled "
                "out. Layer 4 escalation_admin_infrastructure requires admin or "
                "remote access review, so the mock provider recommends escalation "
                "and does not claim external systems were checked."
            )
            next_best_action = (
                "Escalate for admin review of account permissions, MFA "
                "registration/state, conditional access, certificate/profile "
                "provisioning, or VPN infrastructure/log review by the "
                "responsible team."
            )
            escalation_reason = (
                "Layers 1-3 are sufficiently ruled out and the next layer requires "
                "admin access or external system review."
            )

        if explicit_escalation and not should_escalate:
            should_escalate = True
            status = "ready_to_escalate"
        elif should_escalate:
            status = "ready_to_escalate"

        return UpdatedDiagnosisResponse.model_validate(
            {
                "currentLikelyCause": {
                    "cause": cause,
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                "ruledOutCauses": ruled_out_causes,
                "evidenceSummary": evidence_summary,
                "nextBestAction": next_best_action,
                **self._progressive_response_fields(
                    playbook,
                    checklist_results,
                    next_best_action,
                    should_escalate=should_escalate,
                    blocker_reason=escalation_reason if should_escalate else "",
                ),
                "escalationRecommendation": {
                    "shouldEscalate": should_escalate,
                    "reason": escalation_reason,
                },
                "confidence": confidence,
                "status": status,
            }
        )

    def _classify(self, ticket: TicketInput) -> IssueCategory:
        text = self._ticket_text(ticket)
        app_platform = self._application_platform(ticket)

        if app_platform == ApplicationPlatform.VPN_CLIENT or "vpn" in text:
            return IssueCategory.VPN_REMOTE_ACCESS
        if app_platform == ApplicationPlatform.PRINTER_SYSTEM:
            return IssueCategory.PRINTER
        if app_platform == ApplicationPlatform.COMPANY_CUSTOM:
            return IssueCategory.APPLICATION_ERROR
        if self._looks_like_application_location_workflow(text):
            return IssueCategory.APPLICATION_ERROR
        if self._looks_like_login_issue(text):
            return IssueCategory.LOGIN_ACCOUNT
        if self._looks_like_email_issue(text):
            return IssueCategory.EMAIL_OUTLOOK
        if self._looks_like_file_access_issue(text):
            return IssueCategory.FILE_ACCESS_PERMISSION
        if self._looks_like_software_install_update_issue(text):
            return IssueCategory.SOFTWARE_INSTALLATION_UPDATE
        if self._looks_like_device_performance_issue(text):
            return IssueCategory.DEVICE_PERFORMANCE

        for category in CLASSIFICATION_ORDER:
            if (
                category == IssueCategory.SOFTWARE_INSTALLATION_UPDATE
                and not self._looks_like_software_install_update_issue(text)
            ):
                continue
            playbook = PLAYBOOKS[category]
            if any(keyword in text for keyword in playbook.keywords):
                return category
        return IssueCategory.GENERAL_IT

    def _looks_like_login_issue(self, text: str) -> bool:
        if not any(term in text for term in LOGIN_AUTH_TERMS):
            return False
        return not any(term in text for term in EMAIL_DELIVERY_OR_MAILBOX_TERMS)

    def _looks_like_email_issue(self, text: str) -> bool:
        return any(term in text for term in EMAIL_DELIVERY_OR_MAILBOX_TERMS)

    def _looks_like_file_access_issue(self, text: str) -> bool:
        if not any(term in text for term in FILE_ACCESS_TERMS):
            return False
        if "not a scanner" in text or "not scanner" in text:
            return True
        return not any(term in text for term in PRINT_SCAN_TERMS)

    def _looks_like_software_install_update_issue(self, text: str) -> bool:
        if any(term in text for term in SOFTWARE_NEGATION_TERMS):
            return False
        return any(term in text for term in SOFTWARE_INSTALL_UPDATE_TERMS)

    def _looks_like_device_performance_issue(self, text: str) -> bool:
        if not any(term in text for term in DEVICE_PERFORMANCE_TERMS):
            return False
        return not any(term in text for term in DISPLAY_OUTPUT_TERMS)

    def determine_current_layer(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
    ) -> ChecklistGroup:
        failed_step, _ = self.detect_failed_step(playbook, results_by_step)
        if failed_step is not None:
            return failed_step.layer

        next_step = self._next_progressive_step(playbook, results_by_step)
        if next_step is not None:
            return next_step.layer

        return ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE

    def determine_completed_layers(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
    ) -> list[ChecklistGroup]:
        completed_layers: list[ChecklistGroup] = []
        for layer in COMMON_LAYER_ORDER:
            layer_steps = [
                step for step in playbook.checklist_steps if step.layer == layer
            ]
            if not layer_steps:
                continue
            if all(
                self._step_result_passes(step, results_by_step.get(step.id))
                for step in layer_steps
            ):
                completed_layers.append(layer)
                continue
            break
        return completed_layers

    def detect_failed_step(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
    ) -> tuple[PlaybookStep | None, ChecklistResult | None]:
        return self._first_failed_step(playbook, results_by_step)

    def determine_missing_evidence(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
    ) -> list[dict[str, str]]:
        missing_evidence = []
        for layer in COMMON_LAYER_ORDER:
            for step in playbook.checklist_steps:
                if step.layer != layer:
                    continue
                result = results_by_step.get(step.id)
                if not self._step_result_is_missing(result):
                    continue
                reason = (
                    result.evidence
                    if result is not None and result.evidence
                    else "This check has not been recorded yet."
                )
                if result is not None and result.result == ChecklistResultValue.USER_UNSURE:
                    reason = result.evidence or "The user is unsure about this check."
                missing_evidence.append(
                    {
                        "stepId": step.id,
                        "layer": step.layer.value,
                        "question": step.evidence_prompt
                        or f"Record evidence for: {step.step}",
                        "reason": reason,
                    }
                )
        return missing_evidence

    def determine_next_best_actions(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
    ) -> list[str]:
        failed_step, _ = self.detect_failed_step(playbook, results_by_step)
        first_step = self._next_progressive_step(
            playbook,
            results_by_step,
            failed_step,
        )
        if first_step is None:
            return []

        actions = []
        first_seen = False
        for layer in COMMON_LAYER_ORDER:
            for step in playbook.checklist_steps:
                if step.layer != layer:
                    continue
                if step.id == first_step.id:
                    first_seen = True
                if not first_seen:
                    continue
                if step.id != first_step.id and not self._step_is_unresolved(
                    step,
                    results_by_step.get(step.id),
                ):
                    continue
                action = step.next_action or step.step
                if action not in actions:
                    actions.append(action)
                if len(actions) == 3:
                    return actions
        return actions

    def determine_level_one_can_continue(
        self,
        next_step: PlaybookStep | None,
        should_escalate: bool,
    ) -> bool:
        if should_escalate:
            return False
        if next_step is None:
            return True
        return next_step.level1_actionable and not next_step.requires_privileged_access

    def determine_escalation_from_next_step(
        self,
        next_step: PlaybookStep | None,
        checklist_results: list[ChecklistResult],
    ) -> tuple[bool, str]:
        if any(
            result.result == ChecklistResultValue.NEEDS_ESCALATION
            for result in checklist_results
        ):
            return True, "A checklist result indicates escalation is needed."

        if next_step is None:
            return False, ""

        if (
            next_step.requires_privileged_access
            or not next_step.level1_actionable
            or next_step.layer == ChecklistGroup.ESCALATION_ADMIN_INFRASTRUCTURE
        ):
            return (
                True,
                next_step.escalation_reason
                or next_step.access_requirement
                or "The next action requires privileged or external-system review.",
            )

        return False, ""

    def _progressive_response_fields(
        self,
        playbook: Playbook,
        checklist_results: list[ChecklistResult],
        primary_action: str,
        should_escalate: bool | None = None,
        blocker_reason: str = "",
        assessment: EvidenceAssessment | None = None,
    ) -> dict:
        results_by_step = {result.step_id: result for result in checklist_results}
        failed_step, _ = self.detect_failed_step(playbook, results_by_step)
        next_step = self._next_progressive_step(
            playbook,
            results_by_step,
            failed_step,
        )
        inferred_escalation, inferred_reason = (
            self.determine_escalation_from_next_step(next_step, checklist_results)
        )
        if should_escalate is None:
            should_escalate = inferred_escalation
        if should_escalate and not blocker_reason:
            blocker_reason = inferred_reason

        next_best_actions = self.determine_next_best_actions(
            playbook,
            results_by_step,
        )
        if primary_action:
            next_best_actions = [
                primary_action,
                *[action for action in next_best_actions if action != primary_action],
            ]
        next_best_actions = next_best_actions[:3] or [primary_action]
        if assessment is not None:
            next_best_actions = filter_completed_or_contradicted_actions(
                next_best_actions,
                assessment,
            )

        return {
            "currentTroubleshootingLayer": self.determine_current_layer(
                playbook,
                results_by_step,
            ).value,
            "completedLayers": [
                layer.value
                for layer in self.determine_completed_layers(
                    playbook,
                    results_by_step,
                )
            ],
            "missingEvidence": self.determine_missing_evidence(
                playbook,
                results_by_step,
            ),
            "nextBestActions": next_best_actions,
            "level1CanContinue": self.determine_level_one_can_continue(
                next_step,
                should_escalate,
            ),
            "level1BlockerReason": blocker_reason if should_escalate else "",
        }

    def _combined_ruled_out_causes(
        self,
        playbook: Playbook,
        checklist_results: list[ChecklistResult],
        assessment: EvidenceAssessment,
    ) -> list[dict[str, str]]:
        combined = self._ruled_out_causes(playbook, checklist_results)
        for item in assessment.ruled_out_causes:
            if any(existing["cause"] == item["cause"] for existing in combined):
                continue
            combined.append(item)
        return combined

    def _assessment_has_specific_direction(
        self,
        assessment: EvidenceAssessment,
    ) -> bool:
        if not assessment.suggested_cause:
            return False
        normalized = assessment.suggested_cause.lower()
        return not normalized.startswith(
            (
                "single-user ",
                "shared service, network, system, location, or workflow impact",
            )
        )

    def _placeholder_ticket_for_playbook(self, playbook: Playbook) -> TicketInput:
        return TicketInput.model_validate(
            {
                "title": playbook.subcategory,
                "userMessage": f"{playbook.subcategory} issue.",
                "affectedService": playbook.subcategory,
                "deviceType": "Unknown",
                "location": "unknown",
                "affectedUsers": "unknown",
                "agentSelectedUrgency": "medium",
                "businessImpact": "Not provided yet.",
            }
        )

    def _next_progressive_step(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
        failed_step: PlaybookStep | None = None,
    ) -> PlaybookStep | None:
        if failed_step is not None:
            return failed_step

        for layer in COMMON_LAYER_ORDER:
            for step in playbook.checklist_steps:
                if step.layer != layer:
                    continue
                if self._step_is_unresolved(step, results_by_step.get(step.id)):
                    return step
        return None

    def _step_is_unresolved(
        self,
        step: PlaybookStep,
        result: ChecklistResult | None,
    ) -> bool:
        if self._step_result_is_missing(result):
            return True
        return result is not None and result.result not in step.pass_results

    def _step_result_is_missing(self, result: ChecklistResult | None) -> bool:
        return result is None or result.result in {
            ChecklistResultValue.NOT_TESTED,
            ChecklistResultValue.USER_UNSURE,
        }

    def _step_result_passes(
        self,
        step: PlaybookStep,
        result: ChecklistResult | None,
    ) -> bool:
        if self._step_result_is_missing(result):
            return False
        return result.result in step.pass_results

    def _first_failed_step(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
    ) -> tuple[PlaybookStep | None, ChecklistResult | None]:
        for layer in COMMON_LAYER_ORDER:
            for step in playbook.checklist_steps:
                if step.layer != layer:
                    continue
                result = results_by_step.get(step.id)
                if result is None:
                    continue
                if result.result in step.failure_results:
                    return step, result
        return None, None

    def _next_unresolved_step(
        self,
        playbook: Playbook,
        results_by_step: dict[str, ChecklistResult],
    ) -> PlaybookStep | None:
        for layer in COMMON_LAYER_ORDER:
            for step in playbook.checklist_steps:
                if step.layer != layer:
                    continue
                result = results_by_step.get(step.id)
                if result is None or result.result not in step.pass_results:
                    return step
        return None

    def _ruled_out_causes(
        self,
        playbook: Playbook,
        checklist_results: list[ChecklistResult],
    ) -> list[dict[str, str]]:
        step_by_id = {step.id: step for step in playbook.checklist_steps}
        ruled_out_causes = []
        for result in checklist_results:
            step = step_by_id.get(result.step_id)
            cause = None
            if step is not None and result.result in step.pass_results:
                cause = step.ruled_out_cause
            if cause is None and result.result == ChecklistResultValue.WORKS:
                cause = GLOBAL_RULED_OUT_CAUSES.get(result.step_id)
            if cause is None:
                continue
            ruled_out_causes.append(
                {
                    "cause": cause,
                    "reason": result.evidence
                    or "The check was recorded as passing.",
                }
            )
        return ruled_out_causes

    def _has_vpn_authentication_evidence(
        self,
        ticket: TicketInput,
        results: dict[str, ChecklistResult],
    ) -> bool:
        ticket_text = self._ticket_text(ticket)
        return (
            self._result_affirms(results.get("vpn-password-change"))
            or self._result_affirms(results.get("vpn-saved-credentials"))
            or self._result_fails(results.get("vpn-mfa-behavior"))
            or (
                "authentication failed" in ticket_text
                and self._result_passes(results.get("vpn-confirm-internet"))
            )
        )

    def _vpn_authentication_layer_complete(
        self,
        results: dict[str, ChecklistResult],
    ) -> bool:
        return (
            self._result_denies(results.get("vpn-password-change"))
            and self._result_denies(results.get("vpn-saved-credentials"))
            and self._result_passes(results.get("vpn-mfa-behavior"))
        )

    def _has_vpn_client_evidence(
        self,
        results: dict[str, ChecklistResult],
    ) -> bool:
        return (
            self._result_fails(results.get("vpn-client-opens"))
            or self._result_fails(results.get("vpn-profile-selected"))
            or self._result_fails(results.get("vpn-client-error"))
        )

    def _vpn_client_layer_complete(
        self,
        results: dict[str, ChecklistResult],
    ) -> bool:
        return (
            self._result_passes(results.get("vpn-client-opens"))
            and self._result_passes(results.get("vpn-profile-selected"))
            and self._result_passes(results.get("vpn-client-error"))
        )

    def _result_fails(self, result: ChecklistResult | None) -> bool:
        if result is None:
            return False
        return result.result in {
            ChecklistResultValue.DOES_NOT_WORK,
            ChecklistResultValue.NO,
        }

    def _result_affirms(self, result: ChecklistResult | None) -> bool:
        if result is None:
            return False
        return result.result in {
            ChecklistResultValue.YES,
            ChecklistResultValue.NEEDS_ESCALATION,
        }

    def _result_passes(self, result: ChecklistResult | None) -> bool:
        if result is None:
            return False
        return result.result in {
            ChecklistResultValue.WORKS,
            ChecklistResultValue.YES,
        }

    def _result_denies(self, result: ChecklistResult | None) -> bool:
        if result is None:
            return False
        return result.result == ChecklistResultValue.NO

    def _summary(self, ticket: TicketInput) -> str:
        env = ticket.environment_context
        env_text = ""
        if env is not None:
            env_text = (
                f" Environment context: OS={env.operating_system.value}, "
                f"account platform={env.account_platform.value}, "
                f"application platform={env.application_platform.value}."
            )
        return (
            f"{ticket.title}. User reports: {ticket.user_message} "
            f"Affected service: {ticket.affected_service}.{env_text}"
        )

    def _priority(self, ticket: TicketInput) -> Priority:
        impact = self._impact(ticket)
        urgency = ticket.agent_selected_urgency
        if impact == Impact.UNKNOWN or urgency == Urgency.UNKNOWN:
            return Priority.UNKNOWN

        matrix = {
            Impact.SINGLE_USER: {
                Urgency.LOW: Priority.P4,
                Urgency.MEDIUM: Priority.P3,
                Urgency.HIGH: Priority.P3,
                Urgency.CRITICAL: Priority.P2,
            },
            Impact.MULTIPLE_USERS: {
                Urgency.LOW: Priority.P3,
                Urgency.MEDIUM: Priority.P3,
                Urgency.HIGH: Priority.P2,
                Urgency.CRITICAL: Priority.P1,
            },
            Impact.DEPARTMENT: {
                Urgency.LOW: Priority.P3,
                Urgency.MEDIUM: Priority.P2,
                Urgency.HIGH: Priority.P2,
                Urgency.CRITICAL: Priority.P1,
            },
            Impact.ORGANIZATION: {
                Urgency.LOW: Priority.P2,
                Urgency.MEDIUM: Priority.P2,
                Urgency.HIGH: Priority.P1,
                Urgency.CRITICAL: Priority.P1,
            },
        }
        return matrix[impact][urgency]

    def _impact(self, ticket: TicketInput) -> Impact:
        return {
            AffectedUsers.SINGLE_USER: Impact.SINGLE_USER,
            AffectedUsers.MULTIPLE_USERS: Impact.MULTIPLE_USERS,
            AffectedUsers.DEPARTMENT: Impact.DEPARTMENT,
            AffectedUsers.ORGANIZATION: Impact.ORGANIZATION,
            AffectedUsers.UNKNOWN: Impact.UNKNOWN,
        }[ticket.affected_users]

    def _ticket_text(self, ticket: TicketInput) -> str:
        return " ".join(
            [
                ticket.title,
                ticket.user_message,
                ticket.affected_service,
                ticket.error_message,
                ticket.recent_change,
                ticket.business_impact,
            ]
        ).lower()

    def _raw_ticket_text(self, ticket: TicketInput) -> str:
        return " ".join(
            [
                ticket.title,
                ticket.user_message,
                ticket.affected_service,
                ticket.error_message,
                ticket.recent_change,
                ticket.business_impact,
            ]
        )

    def _looks_like_application_location_workflow(self, text: str) -> bool:
        return (
            any(term in text for term in APP_LOCATION_WORKFLOW_ACTION_TERMS)
            and any(term in text for term in APP_LOCATION_WORKFLOW_APP_TERMS)
            and any(term in text for term in APP_LOCATION_WORKFLOW_LOCATION_TERMS)
        )

    def _application_location_workflow_draft(
        self,
        ticket: TicketInput,
    ) -> SimpleNamespace:
        ticket_text = self._ticket_text(ticket)
        signals = [
            "application_workflow_failed",
            "location_based_verification",
            "time_attendance_or_clock_in_workflow",
            "exact_error_unknown",
            "possible_location_permission_issue",
            "possible_gps_or_location_services_issue",
            "possible_app_session_or_cache_issue",
            "possible_network_issue",
            "possible_account_or_profile_issue",
            "possible_service_or_feature_issue",
        ]
        if any(
            phrase in ticket_text
            for phrase in (
                "right location",
                "correct location",
                "at the location",
                "at the job site",
                "on site",
                "onsite",
            )
        ):
            signals.append("user_claims_correct_location")

        return SimpleNamespace(
            app_or_service=self._extract_app_or_service(ticket),
            user_action=self._extract_location_workflow_action(ticket_text),
            diagnostic_signals=signals,
        )

    def _extract_app_or_service(self, ticket: TicketInput) -> str:
        raw_text = self._raw_ticket_text(ticket)
        patterns = (
            r"\bthrough\s+(?:my\s+|the\s+)?([A-Z][A-Za-z0-9_-]*(?:\s+(?:app|portal))?)\b",
            r"\b((?:staff|attendance|roster|delivery)\s+app)\b",
            r"\b([A-Za-z][A-Za-z0-9_-]*\s+portal)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, raw_text, flags=re.IGNORECASE)
            if match:
                return " ".join(match.group(1).split())
        return "the app"

    def _extract_location_workflow_action(self, ticket_text: str) -> str:
        normalized = ticket_text.replace("-", " ")
        for action in ("clock in", "punch in", "check in"):
            if action in normalized:
                return action
        if "attendance" in normalized:
            return "complete the attendance action"
        return "complete the action"

    def _application_platform(self, ticket: TicketInput) -> ApplicationPlatform:
        if ticket.environment_context is None:
            return ApplicationPlatform.UNKNOWN
        return ticket.environment_context.application_platform

    def _account_platform(self, ticket: TicketInput) -> AccountPlatform:
        if ticket.environment_context is None:
            return AccountPlatform.UNKNOWN
        return ticket.environment_context.account_platform

    def _operating_system(self, ticket: TicketInput) -> OperatingSystem:
        if ticket.environment_context is None:
            return OperatingSystem.UNKNOWN
        return ticket.environment_context.operating_system

    def _teams_os_permission_step(self, ticket: TicketInput) -> str:
        operating_system = self._operating_system(ticket)
        if operating_system == OperatingSystem.MACOS:
            return "Check macOS microphone permission for Teams."
        if operating_system == OperatingSystem.WINDOWS:
            return "Check Windows microphone privacy setting and selected input device."
        return "Check operating system microphone permission for Teams."

    def _format_playbook_text(self, text: str, ticket: TicketInput) -> str:
        return text.format(
            account_platform=self._account_platform(ticket).value,
            operating_system=self._operating_system(ticket).value,
            teams_os_permission_step=self._teams_os_permission_step(ticket),
        )

    def _evidence_summary(
        self,
        checklist_results: list[ChecklistResult],
    ) -> list[str]:
        if not checklist_results:
            return ["No checklist evidence recorded yet."]
        return [
            f"{result.step_id}: {result.result.value}"
            + (f" - {result.evidence}" if result.evidence else "")
            for result in checklist_results
        ]

    def _safety_notes(self) -> list[str]:
        return [
            (
                "This mock provider does not check real logs, accounts, devices, "
                "routers, PBX systems, Microsoft 365, Entra ID, Active Directory, "
                "Intune, Jamf, ISP systems, VPN systems, printers, or external systems."
            ),
            (
                "Ask the user to confirm evidence, check the relevant admin portal "
                "only if you have access, or escalate to the responsible team."
            ),
        ]
