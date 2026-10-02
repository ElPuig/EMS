/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ACTIONS_TOGGLE, checkActions, closeActions, noActions, noArchiveInCog, openActions } from "@ems/../tests/tours/actions_dropdown_helpers";

// The student form's "Actions" dropdown (static/src/js/backend/actions_dropdown.js), run by a
// tutor on one of their own students with an active Google account (see
// test_actions_dropdown_tour.py): every action sits in the dropdown - never loose in the header -
// and each entry follows its own invisible/groups.
registry.category("web_tour.tours").add("ems_actions_dropdown_student", {
    test: true,
    steps: () => [
        {
            trigger: `${ACTIONS_TOGGLE}:contains('Actions')`,
            content: "The header shows the Actions dropdown",
        },
        {
            trigger: ".o_form_view .o_form_statusbar .o_statusbar_buttons"
                + ":not(:has(button:not(.o_ems_actions_toggle)))",
            content: "No action is left loose in the header",
        },
        ...checkActions(
            {
                offered: [
                    "action_reset_google_password",
                    "action_portal_access_bulk",
                    "action_authorization_send_bulk",
                    "action_contact_data_request_bulk",
                ],
                notOffered: [
                    // the account already exists
                    "action_create_google_account",
                    // account lifecycle: secretary/admin/TAC only
                    "action_suspend_google_account",
                    // no credentials PDF yet
                    "action_download_google_credentials",
                ],
            },
            "The tutor is offered what applies to this student, and nothing else",
        ),
        ...noArchiveInCog("Archiving a student is a withdrawal: the tutor is not offered it"),
    ],
});

// The same tutor on another group's student (no corporate email yet): portal access,
// authorizations and data requests would only open an assistant that drops the student, and the
// Google account isn't theirs to create - nothing applies, so no dropdown.
registry.category("web_tour.tours").add("ems_actions_dropdown_foreign_student", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_title:contains('Actions Dropdown Foreign')",
            content: "The other group's student form is loaded",
        },
        noActions("Not the tutor's student: no Actions dropdown"),
        ...noArchiveInCog("No Archive for someone else's student either"),
    ],
});

// The same tutor on a teacher's form: read-only access to employees, so no Archive either.
registry.category("web_tour.tours").add("ems_actions_dropdown_employee_no_archive", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_title:contains('Actions Dropdown Colleague')",
            content: "The teacher's form is loaded",
        },
        ...noArchiveInCog("The tutor can't archive a colleague: no Archive in the cog menu"),
    ],
});

// The same tutor on a family contact: no entry applies, so the dropdown is not rendered at all
// rather than opening onto an empty menu.
registry.category("web_tour.tours").add("ems_actions_dropdown_family", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_title:contains('Actions Dropdown Family')",
            content: "The family contact's form is loaded",
        },
        noActions("Nothing applies to a family contact: no Actions dropdown"),
    ],
});

// The employee form (views/community/employee/form.xml), as an administrator on a teacher with
// extra hours: EMS's own actions and the native "Deduct Extra Hours" (hr_holidays_attendance,
// moved in by view_employee_form_native_actions) share the one dropdown, with nothing loose in
// the header. The native entry is matched on its label: its name is an action id.
registry.category("web_tour.tours").add("ems_actions_dropdown_employee", {
    test: true,
    steps: () => [
        {
            trigger: `${ACTIONS_TOGGLE}:contains('Actions')`,
            content: "The employee form shows the Actions dropdown",
        },
        {
            trigger: ".o_form_view .o_form_statusbar .o_statusbar_buttons"
                + ":not(:has(button:not(.o_ems_actions_toggle)))",
            content: "No action is left loose in the header, native ones included",
        },
        openActions(),
        {
            trigger: ".o-dropdown--menu.o_ems_actions_menu"
                + ":has(button[name='action_create_google_account'])"
                + ":has(button:contains('Deduct Extra Hours'))",
            content: "The native 'Deduct Extra Hours' sits in the dropdown next to EMS's own entries",
        },
        closeActions(),
    ],
});
