/** @odoo-module **/

import { registry } from "@web/core/registry";

// Not a regression test: tests/test_docs_screenshots.py runs these to put a screen into the state
// a manual shows, then photographs it. Driving it through a real tour rather than setting input
// values from a script matters - Odoo's own `edit` action types the way a person does, and a
// value merely assigned from JavaScript was lost again right after the group was picked.
//
// No `url`: the capture opens the screen itself and starts the tour where it already is. The
// authorization comes preloaded, so no autocomplete dropdown other than the group's is ever
// opened - one left open covers the form and lists whatever the database holds.
registry.category("web_tour.tours").add("ems_doc_shot_tutor_send", {
    test: true,
    steps: () => [
        {
            trigger: ".o_dialog div[name='group_ids'] input",
            content: "Type the tutor's own group",
            run: "edit DAM1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(DAM1A)",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='line_ids'] .o_data_row td:contains(Marina Exemple)",
            content: "The preview lists the group's students",
        },
    ],
});

// Tutors' justification manual: a new justification with its student and period filled in, so
// the day's affected sessions (the tutor's own and a colleague's) are listed. The capture opens
// the empty form itself; the dates are typed in ca_ES format, as a Catalan tutor would.
registry.category("web_tour.tours").add("ems_doc_shot_tutor_justification", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view div[name='student_id'] input",
            content: "Type one of the tutor's students",
            run: "edit Marina",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(Marina Exemple)",
            run: "click",
        },
        {
            trigger: ".o_form_view div[name='start_date'] input[data-field='start_date']",
            content: "Start of the period",
            run: "edit 02/03/2026 07:00:00",
        },
        {
            trigger: ".o_form_view div[name='start_date'] input[data-field='end_date']",
            content: "End of the period",
            run: "edit 02/03/2026 13:00:00",
        },
        {
            trigger: ".o_notebook .nav-item:first-child .nav-link",
            content: "Leave the date picker, back on the affected sessions",
            run: "click",
        },
        {
            trigger: ".o_form_view div[name='attendance_session_line_ids'] .o_data_row:nth-child(2)",
            content: "Both of the day's sessions are listed",
        },
    ],
});

// Tutors' Google credentials manual: every student of the list selected and the Actions menu
// open on "Download Google credentials". The capture opens the (fixture-only) list itself.
registry.category("web_tour.tours").add("ems_doc_shot_tutor_google_credentials", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view thead .o_list_record_selector input",
            content: "Select every student of the list",
            run: "click",
        },
        {
            trigger: ".o_cp_action_menus button:has(.fa-cog)",
            content: "Open the Actions menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains(Google)",
            content: "The download action is listed",
        },
    ],
});
