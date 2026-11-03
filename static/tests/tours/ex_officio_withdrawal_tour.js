/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #726, phase 1: a tutor opens an ex officio withdrawal case file by hand for one of their
// students, starts the procedure and finds it in the list (see test_ex_officio_withdrawal_tour.py).
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_tutor", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_button_add",
            content: "Open a new case file from the list",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            content: "Pick the student",
            run: "edit EOW Tour Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('EOW Tour Student')",
            content: "Select them",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='first_absence_date'] input",
            content: "First day of absence",
            run: "edit 12/17/2041",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='tutor_id']",
            content: "Leave the date field",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved .oe_title:contains('BO-')",
            content: "Saved with its registration number",
        },
        ...clickAction("action_start", "Start the procedure"),
        {
            trigger: ".o_form_view .o_field_widget[name='step_ids'] .o_data_row:nth-child(4):contains('Withdrawal')",
            content: "The post-compulsory circuit's four steps are there",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='step_ids'] .o_data_row:first-child:contains('01/08/2042')",
            content: "The tutor's step is due on the fifth school day, after the break",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb .breadcrumb-item a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('EOW Tour Student'):contains('In progress')",
            content: "The case file is listed, in progress",
        },
    ],
});
