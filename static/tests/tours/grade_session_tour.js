/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke test: the bulk-creation wizard (the admin entry point) opens with its main
// fields. Grade sessions are no longer created one by one from the list; a full
// creation flow would require seeded study/group/enrolment data, so the numeric
// calculation and the wizard logic are covered by the backend TransactionCase tests.
registry.category("web_tour.tours").add("ems_grade_session_ui", {
    test: true,
    url: "/odoo/action-ems.action_grade_session_wizard",
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='mode']",
            content: "Wizard loaded — mode field present",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='study_ids']",
            content: "Study selector present (default mode)",
        },
        {
            // Not asked any more (issue #354): computed and shown read-only.
            trigger: ".o_form_view .o_field_widget[name='round'].o_readonly_modifier",
            content: "Round field present, read-only",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='claim_date_from'].o_required_modifier",
            content: "Claims period present and required (issue #878)",
        },
        {
            trigger: ".modal-footer button[name='action_create_sessions'], .o_form_view button[name='action_create_sessions']",
            content: "Create without the required fields",
            run: "click",
        },
        {
            // The save stops on the empty fields: the "creating" overlay must not appear (issue #878).
            trigger: ".o_form_view .o_field_widget[name='claim_date_from'].o_field_invalid",
            content: "Claims dates flagged, no blocking overlay",
            run() {
                if (document.querySelector(".o_blockUI")) {
                    throw new Error("The creation overlay is shown although nothing is being created.");
                }
            },
        },
    ],
});
