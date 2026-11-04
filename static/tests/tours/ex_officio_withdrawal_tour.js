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

// Issue #726: the Secretariat does its warning step - sends the email to the family from its
// template (which ticks it) and confirms the eNotum - and the case file moves on to Direction (see
// test_ex_officio_withdrawal_tour.py).
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_secretariat_step", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view div[name='current_step']:contains('Ex officio withdrawal warning')",
            content: "The Secretariat gets its step's instructions",
        },
        {
            trigger: ".o_form_view div[name='current_step'] button[name='action_open_contact']:not(.d-none)",
            content: "Open the email to the family",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='body']:contains('EOW Tour Student')",
            content: "The template's text, with the student, ready to review",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']",
            content: "Send it",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(1) .o_data_cell[name='done'] input:checked",
            content: "Sending it ticked the email",
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

// Issue #726: the post-compulsory tutor says how the phone call went, right below the step's text.
// "I did not reach them" opens the call's day and its own notice to the family; sending it ticks the
// call and the email (neither by hand) and says when it went (see test_ex_officio_withdrawal_tour.py).
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_tutor_email", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view div[name='family_email'] button[name='action_open_contact']:contains('I did not reach them')",
            content: "The family was not reached",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='call_date'] input",
            content: "The day of the call, today by default and editable",
        },
        {
            trigger: ".modal .o_field_widget[name='body']:contains('EOW Tour Student')",
            content: "Its own text (in the family's language; which one, checked in Python), with no choice of another one",
        },
        {
            trigger: ".modal .modal-footer button[name='action_try_again']",
            content: "Trying again tomorrow is offered too",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']",
            content: "Send the notice",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view div[name='current_step'] > .text-success:contains('could not reach them by phone')",
            content: "When it went and which text",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(1) .o_data_cell[name='done'] input:checked:disabled",
            content: "The call is ticked, not by hand",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(2) .o_data_cell[name='done'] input:checked:disabled",
            content: "And so is the email",
        },
    ],
});

// Issue #726, phase 4: the Secretariat's last step. It ticks Esfera, SAGA and the eNotum, sends
// the email to the family, and only then "Process the withdrawal" (Actions) opens the withdrawal
// wizard as an ex officio withdrawal; applying it closes the case file (see
// test_ex_officio_withdrawal_tour.py).
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_process", {
    test: true,
    steps: () => [
        ...[1, 2, 3].map((row) => ({
            trigger: `.o_form_view .o_field_widget[name='current_check_ids'] .o_data_row:nth-child(${row}) .o_data_cell[name='done']`,
            content: `Tick action ${row} (one click enters the row and ticks it)`,
            run: "click",
        })),
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved div[name='family_email'] button[name='action_open_contact']",
            content: "Send the email to the family",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']",
            content: "Send it",
            run: "click",
        },
        ...clickAction("action_open_withdrawal_wizard", "Process the withdrawal"),
        {
            trigger: ".modal .o_field_widget[name='withdrawal_mode']:contains('Ex officio')",
            content: "The wizard is filled in as an ex officio withdrawal",
        },
        {
            trigger: ".modal .modal-footer button[name='action_apply']:not(.d-none)",
            content: "Withdraw",
            run: "click",
        },
        {
            trigger: ".modal:contains('This withdraws') .modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_statusbar_status .o_arrow_button_current:contains('Withdrawn')",
            content: "The case file is closed",
        },
    ],
});

// Issue #726, phase 4: Direction does not give the green light, it closes the case file saying
// why (see test_ex_officio_withdrawal_tour.py).
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_direction_close", {
    test: true,
    steps: () => [
        ...clickAction("action_open_close_wizard", "Close without a withdrawal"),
        {
            trigger: ".modal .o_field_widget[name='close_reason'] input[data-value='came_back']",
            content: "The student came back",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='note'] textarea",
            content: "Say why",
            run: "edit Back in class since Monday",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']:not(.d-none)",
            content: "Close it",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_statusbar_status .o_arrow_button_current:contains('Cancelled')",
            content: "Cancelled",
        },
    ],
});

// Phase 6: the roll-calls say the student came; the tutor checks it was a mistake and the case
// file can go on (structural selectors). Fixtures in tests/test_ex_officio_withdrawal_tour.py.
registry.category("web_tour.tours").add("ems_ex_officio_withdrawal_attendance_check", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view div[name='attendance_review'] .o_data_row",
            content: "The attendance to check, with its session",
        },
        {
            trigger: ".o_form_view div[name='attendance_review'] button[name='action_mark_absent']",
            content: "It was a mistake",
            run: "click",
        },
        { trigger: ".modal-footer .btn-primary", content: "Confirm", run: "click" },
        {
            trigger: ".o_form_view:not(:has(div[name='attendance_review']))",
            content: "Nothing left to check",
        },
    ],
});
