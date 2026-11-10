/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

const ROW = ".o_list_view .o_data_row:contains('WLT')";

// Issue #800 (test_student_walkout_tour.py): two calls of the same group, on different walkout days.
// The group's tutor aborts the one being voted, with a reason, after reading which reasons are
// lawful; the Head of Studies validates the closed one, which justifies the students who join.
registry.category("web_tour.tours").add("ems_student_walkout_abort", {
    test: true,
    url: "/odoo/action-ems.action_student_walkout",
    steps: () => [
        {
            trigger: `${ROW} .o_field_badge:contains('Voting')`,
            content: "Open the call being voted",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('tutor watches over the call')",
            content: "The form says the tutor watches over the call",
        },
        ...clickAction("action_open_reject_wizard", "Abort it"),
        {
            trigger: ".modal .alert-warning:contains('LODE')",
            content: "The wizard explains which reasons are lawful",
        },
        {
            trigger: ".modal .o_field_widget[name='reason_id'] input",
            content: "Pick a reason",
            run: "edit Other reasons",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Other reasons')",
            content: "Other reasons",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='details'] textarea",
            content: "Other reasons need details",
            run: "edit A dockers' strike",
        },
        {
            trigger: ".modal button[name='action_reject']:visible",
            content: "Abort the call",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='rejection_details']:contains('dockers')",
            content: "The call is aborted, with its reason",
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item:first-child a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: `${ROW} .o_field_badge:contains('Closed')`,
            content: "The closed call is listed too",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_yes_count']:contains('2')",
            content: "The form shows the anonymous group vote, with nothing left for the tutor to do",
        },
    ],
});

registry.category("web_tour.tours").add("ems_student_walkout_validate", {
    test: true,
    url: "/odoo/action-ems.action_student_walkout",
    steps: () => [
        {
            trigger: `${ROW} .o_field_badge:contains('Closed')`,
            content: "Open the closed call, waiting to be validated",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='line_ids'] .o_data_row:contains('WLT Delegate')",
            content: "The form shows every student of the group",
        },
        ...clickAction("action_generate_justification", "Validate and justify"),
        {
            trigger: ".o_form_view .o_field_widget[name='student_ids']:contains('WLT Delegate')",
            content: "The justification of the walkout day opens, for the students who join",
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item:first-child a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: `${ROW} .o_field_badge:contains('Justified')`,
            content: "The call is validated",
        },
    ],
});
