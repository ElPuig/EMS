/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #879: the student claims a grade from the portal. Structural selectors only.
registry.category("web_tour.tours").add("ems_grade_claim_portal", {
    test: true,
    url: "/my/calificaciones",
    steps: () => [
        {
            trigger: ".o_ems_grade_claim_form select[name='item']:has(option)",
            content: "The graded outcome can be claimed",
        },
        {
            trigger: ".o_ems_grade_claim_form textarea[name='reason']",
            content: "Explain what does not match",
            run: "edit My second project is missing from RA1",
        },
        {
            trigger: ".o_ems_grade_claim_form button[type='submit']",
            content: "Send the claim",
            run: "click",
        },
        {
            trigger: ".o_ems_portal_grade_claims .alert-success",
            content: "Sent to the teacher",
        },
        {
            trigger: ".o_ems_grade_claims_table tbody tr .badge.text-bg-info",
            content: "Listed as pending",
        },
    ],
});

// Issue #879: the teacher answers it from Grades > Grade claims (list, then form).
registry.category("web_tour.tours").add("ems_grade_claim_answer", {
    test: true,
    url: "/odoo/action-ems.action_grade_claim",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Claim Student')",
            content: "Open the pending claim",
            run: "click",
        },
        ...clickAction("action_accept", "Accept it"),
        {
            trigger: ".modal .o_field_widget[name='new_score'] input",
            content: "The corrected grade",
            run: "edit 6",
        },
        {
            trigger: ".modal button[name='action_confirm']",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='accepted'].o_arrow_button_current",
            content: "The claim is accepted",
        },
    ],
});
