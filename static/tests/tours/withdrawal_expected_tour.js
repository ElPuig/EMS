/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "./actions_dropdown_helpers";

// Issue #644: a tutor marks a student's expected withdrawal from the student's Actions dropdown,
// sees the ribbon, the notice and the dashed classes on the Schedule tab, then reverts it.
// Fixtures in tests/test_withdrawal_expected_tour.py; the tutor renders in English.
registry.category("web_tour.tours").add("ems_withdrawal_expected_tutor", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_schedule_grid_entry:not(.o_schedule_grid_entry_not_expected)",
            content: "The student's schedule, with every class expected",
        },
        ...clickAction("action_withdrawal_expected_wizard", "Mark the expected withdrawal"),
        {
            trigger: ".modal .o_field_widget[name='note'] textarea",
            content: "Explain why",
            run: "edit The family is moving abroad.",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .ribbon:contains('Expected withdrawal')",
            content: "The form shows the Expected withdrawal ribbon",
        },
        {
            trigger: ".o_form_view .alert-warning:contains('The family is moving abroad.')",
            content: "...and the notice, with the note",
        },
        {
            trigger: ".o_form_view .o_schedule_grid_entry.o_schedule_grid_entry_not_expected",
            content: "The classes are drawn as not required to attend",
        },
        {
            trigger: ".o_form_view .o_schedule_grid_not_expected_legend",
            content: "...with the legend explaining why",
        },
        ...clickAction("action_revert_withdrawal_expected", "Revert it"),
        { trigger: ".modal-footer .btn-primary", content: "Confirm", run: "click" },
        {
            trigger: ".o_form_view:not(:has(.ribbon)):not(:has(.o_schedule_grid_not_expected_legend))",
            content: "No ribbon and no dashed classes any more",
        },
    ],
});

// The teacher's roll-call lists the student greyed out, with the reason (structural selectors).
registry.category("web_tour.tours").add("ems_withdrawal_expected_roll_call", {
    test: true,
    url: "/odoo/action-ems.action_attendance_passlist",
    steps: () => [
        { trigger: ".ems-av-root", content: "Roll-call view loaded" },
        {
            trigger: ".ems-av-mode-wrap select",
            content: "Manual mode, so the seeded slot isn't hidden by the current-slot filter",
            run: "select manual",
        },
        {
            trigger: ".ems-av-session-wrap select:has(option:contains('Withdrawal Expected Tour'))",
            content: "Select the seeded slot",
            run() {
                const option = [...this.anchor.options].find((o) => o.textContent.includes("Withdrawal Expected Tour"));
                this.anchor.value = option.value;
                this.anchor.dispatchEvent(new Event("change"));
            },
        },
        { trigger: ".ems-av-start-btn", content: "Start the session", run: "click" },
        {
            trigger: ".ems-av-line--removed:has(.ems-av-name:contains('Leaving Student')) .ems-av-removed-reason",
            content: "The student is off the roll-call, with the reason",
        },
        {
            trigger: ".ems-av-line:not(.ems-av-line--removed) .ems-av-name:contains('Staying Student')",
            content: "Their classmate is on it",
        },
    ],
});
