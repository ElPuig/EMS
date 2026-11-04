/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #726: a tutor opens an ex officio withdrawal case file by hand for one of their students
// (only theirs are offered), starts the procedure and finds the steps in the history and the case
// file in the list (see test_ex_officio_withdrawal_tour.py).
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
            content: "Look for the students",
            run: "edit EOW Tour",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu:not(:has(.o-autocomplete--dropdown-item:contains('EOW Tour Other Student'))) .o-autocomplete--dropdown-item:contains('EOW Tour Student')",
            content: "Only the tutor's own student is offered; select them",
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
            trigger: ".o_form_view .o_field_widget[name='history_html'] tbody tr:nth-child(4):contains('Withdrawal')",
            content: "The history lists the post-compulsory circuit's four steps",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='history_html'] tbody tr:first-child:contains('01/08/2042')",
            content: "The tutor's step is due on the fifth school day, after the break",
        },
        {
            trigger: ".o_form_view div[name='current_step']:contains('Contact with the family') .o_field_widget[name='current_check_ids'] .o_data_row",
            content: "The tutor gets their step's block, with what to confirm",
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

// Issue #726: the tutor requests it from the student's form (Actions) and lands on a new case
// file for that student.
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_request", {
    test: true,
    steps: () => [
        ...clickAction("action_request_ex_officio_withdrawal", "Request ex officio withdrawal"),
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            content: "A new case file for the student (the name is the input's value, not its text)",
            run() {
                if (!this.anchor.value.includes("EOW Tour Student")) {
                    throw new Error(`Expected the student to be filled in, got "${this.anchor.value}"`);
                }
            },
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
    ],
});

// Issue #726: the Secretariat does its warning step - confirms the email and the eNotum, each
// with its day - and the case file moves on to Direction (see test_ex_officio_withdrawal_tour.py).
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_secretariat_step", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view div[name='current_step']:contains('Ex officio withdrawal warning')",
            content: "The Secretariat gets its step's instructions",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(1) .o_data_cell[name='done']",
            content: "Confirm the email (one click enters the row and ticks it)",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(1) .o_data_cell[name='done'] input:checked",
            content: "The email is ticked",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(2) .o_data_cell[name='done']",
            content: "Confirm the eNotum",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(2) .o_data_cell[name='done'] input:checked",
            content: "The eNotum is ticked",
        },
        ...clickAction("action_accept_step", "Accept and continue"),
        {
            trigger: ".o_form_view .o_field_widget[name='history_html'] tbody tr:nth-child(2):contains('EOW Step Tour Secretary')",
            content: "The history shows the step signed by the secretary",
        },
        {
            trigger: ".o_form_view .o_statusbar_status .o_arrow_button_current:contains('Pending Direction')",
            content: "The case file waits for Direction",
        },
        {
            trigger: ".o_form_view .alert-info:contains('Direction')",
            content: "The secretary now sees whose turn it is",
        },
    ],
});
