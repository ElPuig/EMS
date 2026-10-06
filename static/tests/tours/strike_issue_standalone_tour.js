/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #402: a teacher issues a strike outside any attendance session (e.g. a student
// caught in the corridor), from the "New strike" button of Coexistence > Strikes, then
// checks it is listed. Driven by a plain teacher (see tests/test_strike_issue_standalone_tour.py).
registry.category("web_tour.tours").add("ems_strike_issue_standalone", {
    test: true,
    url: "/odoo/action-ems.action_strike_list",
    steps: () => [
        {
            trigger: ".o_list_view .o_list_button_add_strike",
            content: "Open the New strike dialog",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='teacher_id'].o_readonly_modifier:contains('Test Teacher User')",
            content: "The issuer is the logged-in teacher, read-only",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='student_id'] input",
            content: "Search for the student",
            run: "edit Strike Standalone Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Strike Standalone Student')",
            content: "Select the student",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='reason_id'] input",
            content: "The reason is required, so the dialog must preselect the default one",
            run: function () {
                if (!this.anchor.value) {
                    throw new Error("The default strike reason is not preselected");
                }
            },
        },
        {
            trigger: ".modal .o_field_widget[name='kicked_out'] input",
            content: "Mark it as kicked out",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='notes'] textarea",
            content: "Add the details",
            run: "edit Caught running in the corridor",
        },
        {
            trigger: ".modal footer button.o_strike_issue_send",
            content: "Send",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The dialog closes",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='notes']:contains('Caught running in the corridor')",
            content: "The new strike is listed without reloading the page",
        },
        {
            trigger: ".o_list_view .o_data_row:has(td[name='notes']:contains('Caught running in the corridor')) td[name='group_id']:contains('TSSG1A')",
            content: "Issue #570: it shows the student's main group, issued outside class",
        },
        // Issue #554: another strike for the same student a moment later is flagged as a
        // possible duplicate and only sent once confirmed.
        {
            trigger: ".o_list_view .o_list_button_add_strike",
            content: "Open the New strike dialog again",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view:not(:has(.o_strike_duplicate_warning))",
            content: "No warning before choosing the student",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='student_id'] input",
            content: "Search for the same student",
            run: "edit Strike Standalone Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Strike Standalone Student')",
            content: "Select the same student",
            run: "click",
        },
        {
            trigger: ".modal .o_strike_duplicate_warning:contains('Strike Standalone Student')",
            content: "The dialog warns of the strike just issued",
        },
        {
            trigger: ".modal .o_field_widget[name='notes'] textarea",
            content: "Add the details",
            run: "edit Threw a chair, a different incident",
        },
        {
            trigger: ".modal footer button.o_strike_issue_send",
            content: "Send",
            run: "click",
        },
        {
            trigger: ".modal:not(:has(.o_form_view)) .modal-footer .btn-primary",
            content: "It asks for confirmation: send it anyway",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "Both dialogs close",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='notes']:contains('Threw a chair, a different incident')",
            content: "The second strike is listed too",
        },
    ],
});

// Same dialog, reached from a student's own form: the "Strikes" button is shown even with no
// strike yet, and the list it opens presets that student, locked, in the "New strike" dialog.
registry.category("web_tour.tours").add("ems_strike_issue_from_student", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view button[name='action_view_strikes'] .o_stat_value:contains('0')",
            content: "The Strikes button is shown even before the student has any strike",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_list_button_add_strike",
            content: "Open the New strike dialog from this student's strikes",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='student_id'].o_readonly_modifier:contains('Strike From Student Student')",
            content: "The student is preset and read-only",
        },
        {
            trigger: ".modal .o_field_widget[name='teacher_id'].o_readonly_modifier:contains('Test Teacher User')",
            content: "The issuer is the logged-in teacher, read-only",
        },
        {
            trigger: ".modal .o_field_widget[name='notes'] textarea",
            content: "Add the details",
            run: "edit Insulted a classmate at the playground",
        },
        {
            trigger: ".modal footer button.o_strike_issue_send",
            content: "Send",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The dialog closes",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='notes']:contains('Insulted a classmate at the playground')",
            content: "The new strike is listed among this student's strikes",
        },
    ],
});
