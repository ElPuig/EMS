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
            trigger: ".o_form_view .o_field_widget[name='round']",
            content: "Round field present",
        },
    ],
});
