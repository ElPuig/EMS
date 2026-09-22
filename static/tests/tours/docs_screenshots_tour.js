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

// Teachers' "Disable profile picture" manual: "My Profile" has no stable action URL of its own
// (hr.res_users_action_my resolves its res_id dynamically, per logged-in user, only when reached
// through the real user-menu click - see static/tests/tours/user_profile_tour.js's own NOTE) -
// navigating straight to it opens a blank "New" form instead. The capture opens the plain
// backend ('/odoo') itself; this tour does the whole "open My Profile, go to Preferences" walk a
// real user would do.
//
// Text triggers below are in CATALAN ("El meu perfil"/"Preferències"), not English, deliberately
// - unlike user_profile_tour.js (a real regression tour, forced to en_US via create_role_user()'s
// own default), this docs-screenshot capture logs in as the shared 'doc_shot_teacher' fixture
// (lang='ca_ES' - see TestDocsScreenshotsTeachers.setUpClass), the same fixture every other
// capture in that file relies on to get a Catalan-rendered screenshot "for free". Confirmed via
// hr/i18n/ca.po and web/i18n/ca.po: "My Profile" -> "El meu perfil", "Preferences" ->
// "Preferències". See CLAUDE.md's "Tour tests and language" - the fix for an account that is
// genuinely, deliberately NOT en_US is to match its real rendered text, not to force English.
registry.category("web_tour.tours").add("ems_doc_shot_photo_visibility", {
    test: true,
    steps: () => [
        {
            trigger: ".o_user_menu button",
            content: "Open the user menu",
            run: "click",
        },
        {
            trigger: ".dropdown-item:contains('El meu perfil')",
            content: "Open My Profile",
            run: "click",
        },
        {
            // The real record's own name, not just ".o_form_view" - see user_profile_tour.js's
            // own NOTE on why a blank "New" form would otherwise pass this check too. The form's
            // header shows the res.users' own 'name' ("Professor Exemple", set on
            // create_role_user()), NOT the linked hr.employee's "0000 "-prefixed one (a separate
            // field, only used for the employee's own sort order elsewhere) - confirmed via the
            // tour's own auto-saved failure screenshot after first trying the "0000 " variant.
            trigger: ".o_form_view:contains('Professor Exemple')",
            content: "My Profile loaded for the real logged-in user, not a blank new record",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Preferències')",
            content: "Open the Preferences tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='image_disabled']",
            content: "\"Disable profile picture\" is visible",
        },
    ],
});

// Teachers' "Your Weekly Schedule" manual: same "My Profile has no stable action URL" problem as
// the photo-visibility tour above, and the same Catalan-text reasoning (doc_shot_teacher is
// lang='ca_ES') - see that tour's own NOTE. Unlike Preferences, Schedule is the FIRST/default tab
// (see static/tests/tours/user_profile_tour.js's own tabOrderSteps(), true for every account
// regardless of role) - no tab click needed here at all.
registry.category("web_tour.tours").add("ems_doc_shot_working_schedule", {
    test: true,
    steps: () => [
        {
            trigger: ".o_user_menu button",
            content: "Open the user menu",
            run: "click",
        },
        {
            trigger: ".dropdown-item:contains('El meu perfil')",
            content: "Open My Profile",
            run: "click",
        },
        {
            trigger: ".o_form_view:contains('Professor Exemple')",
            content: "My Profile loaded for the real logged-in user, not a blank new record",
        },
        {
            trigger: ".o_field_widget[name='schedule_attendance_ids'] .o_schedule_grid_entry",
            content: "The teacher's own schedule grid, with at least one block on it",
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
