/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #800: the Head of Studies opens a closed student walkout vote (list, then form) and
// justifies the walkout day for the students who join (test_student_walkout_tour.py).
registry.category("web_tour.tours").add("ems_student_walkout", {
    test: true,
    url: "/odoo/action-ems.action_student_walkout",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('WLT') .o_field_badge:contains('Closed')",
            content: "The closed call is listed, waiting to be justified",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_yes_count']:contains('1')",
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
            trigger: ".o_list_view .o_data_row:contains('WLT') .o_field_badge:contains('Justified')",
            content: "The call is justified",
        },
    ],
});
