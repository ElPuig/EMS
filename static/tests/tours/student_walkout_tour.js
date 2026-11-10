/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

const ROW = ".o_list_view .o_data_row:contains('WLT')";

// Issue #800: the Head of Studies accepts a student walkout call, rejects another one with a
// reason, and justifies a closed vote (test_student_walkout_tour.py): three calls of the same
// group, on different walkout days.
registry.category("web_tour.tours").add("ems_student_walkout", {
    test: true,
    url: "/odoo/action-ems.action_student_walkout",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:first-child .o_field_badge:contains('Pending review')",
            content: "Open a call waiting for review",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('the group hears of it only once accepted')",
            content: "The form says the group does not know yet",
        },
        ...clickAction("action_accept", "Accept it"),
        {
            trigger: ".modal .modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button.o_arrow_button_current:contains('Voting')",
            content: "The group votes now",
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item:first-child a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: `${ROW} .o_field_badge:contains('Pending review')`,
            content: "Open the other call waiting for review",
            run: "click",
        },
        ...clickAction("action_open_reject_wizard", "Reject it"),
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
            trigger: ".modal button[name='action_reject']",
            content: "Reject",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='rejection_details']:contains('dockers')",
            content: "The call is rejected, with its reason",
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item:first-child a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: `${ROW} .o_field_badge:contains('Closed')`,
            content: "The closed call is listed, waiting to be justified",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_yes_count']:contains('3')",
            content: "The form shows the anonymous group vote",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='line_ids'] .o_data_row:contains('WLT Delegate')",
            content: "and every student of the group",
        },
        ...clickAction("action_generate_justification", "Generate the justification"),
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
            content: "The call is justified",
        },
    ],
});
