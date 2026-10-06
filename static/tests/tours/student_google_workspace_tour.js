/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Covers the two-stage leaving lifecycle (#388) as it is rendered on the student form
// (views/community/contact/form.xml): the scheduled-deactivation banner with its
// "Cancel scheduled deactivation" button, and - once the account is suspended - the
// scheduled-deletion banner with its confirm-guarded "Delete Google account" button.
// Both are driven by date fields rather than google_ws_state, so an arch/modifier
// mistake here would never show up in the state tests; only a real render catches it.
// The students are archived (that is what opens the grace period) but still show up in
// this list: ems.action_student_kanban deliberately runs with active_test disabled, so
// withdrawn/graduated students remain reachable from their own menu.
registry.category("web_tour.tours").add("ems_student_google_workspace_lifecycle", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Students loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        // --- stage 1: deactivation scheduled, nothing changed in Google yet ---
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 GW Student Scheduled')",
            content: "Open the student whose deactivation is scheduled",
            run: "click",
        },
        {
            trigger: ".alert-warning:contains('scheduled to be deactivated')",
            content: "The grace-period banner shows the pending deactivation",
        },
        {
            trigger: ".o_form_view:not(:has(.alert-danger))",
            content: "No deletion is scheduled yet: the account is still active",
        },
        ...clickAction("action_cancel_scheduled_deactivation", "Call off the scheduled deactivation"),
        {
            trigger: ".o_form_view:not(:has(.alert-warning:contains('scheduled to be deactivated')))",
            content: "The banner is gone: the account is kept",
        },
        ...checkActions(
            { offered: ["action_suspend_google_account"], notOffered: ["action_cancel_scheduled_deactivation"] },
            "Nothing left to call off: only the active account's own actions are offered",
        ),
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        // --- stage 2: suspended, deletion scheduled --------------------------
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 GW Student Suspended')",
            content: "Open the suspended student",
            run: "click",
        },
        {
            trigger: ".alert-danger:contains('deleted for good')",
            content: "The deletion banner warns the account is about to be deleted",
        },
        ...clickAction("action_delete_google_account", "Delete the account for good"),
        {
            trigger: ".modal-body:contains('cannot be recovered')",
            content: "The irreversible action asks for confirmation first",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm the deletion",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.alert-danger))",
            content: "The deletion banner is gone: the account is deleted",
        },
        ...checkActions(
            { offered: ["action_portal_access_bulk"], notOffered: ["action_delete_google_account"] },
            "The deletion is done: nothing left to delete",
        ),
    ],
});

// Issue #478: the TAC team resets a student's Google password from the form's Actions
// dropdown (and is offered the suspend entry next to it). Opened by
// URL on the seeded student (see test_student_google_workspace_tour.py).
registry.category("web_tour.tours").add("ems_student_google_password_reset", {
    test: true,
    steps: () => [
        ...checkActions(
            { offered: ["action_suspend_google_account", "action_reset_google_password"] },
            "The TAC team can also suspend the account",
        ),
        ...clickAction("action_reset_google_password", "Click 'Reset Google password'"),
        {
            trigger: ".modal .modal-footer .btn-primary",
            content: "Confirm the reset",
            run: "click",
        },
        {
            trigger: ".o-mail-Message:contains('password reset')",
            content: "The chatter records the reset",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='secretary']",
            content: "Open the Secretary tab, home of the documentation section",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='document_ids'] .o_data_row:contains('Cancelled') ~ .o_data_row:contains('Approved'), .o_field_widget[name='document_ids'] .o_data_row:contains('Approved') ~ .o_data_row:contains('Cancelled')",
            content: "The new credentials are listed next to the cancelled old ones",
        },
    ],
});

// Issue #490: a tutor resets the Google password of one of their own students, with none of the
// account-lifecycle buttons the secretary and the TAC team get, and reads the fresh credentials
// from the Documentation tab. Opened by URL on the seeded student (see
// test_student_google_workspace_tour.py).
registry.category("web_tour.tours").add("ems_student_google_password_reset_tutor", {
    test: true,
    steps: () => [
        ...checkActions(
            { offered: ["action_reset_google_password"], notOffered: ["action_suspend_google_account"] },
            "The tutor is not offered the account lifecycle buttons",
        ),
        ...clickAction("action_reset_google_password", "Click 'Reset Google password'"),
        {
            trigger: ".modal .modal-footer .btn-primary",
            content: "Confirm the reset",
            run: "click",
        },
        {
            trigger: ".o-mail-Message:contains('password reset')",
            content: "The chatter records the reset",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='secretary']",
            content: "Open the Secretary tab, home of the documentation section",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='document_ids'] .o_data_row:contains('Cancelled') ~ .o_data_row:contains('Approved'), .o_field_widget[name='document_ids'] .o_data_row:contains('Approved') ~ .o_data_row:contains('Cancelled')",
            content: "The tutor reads the new credentials next to the cancelled old ones",
        },
    ],
});

// Issue #513: a tutor creates the Google account of one of their own students who has none yet.
// Since #582 the button queues the same job as the automatic creation, so it disappears as soon as
// it is pressed and stays hidden until the job is over: a second press can't create a second
// account. Opened by URL on the seeded student (see test_student_google_workspace_tour.py), which
// then runs the queued job and checks the account.
registry.category("web_tour.tours").add("ems_student_google_account_create_tutor", {
    test: true,
    steps: () => [
        ...checkActions(
            { offered: ["action_create_google_account"], notOffered: ["action_reset_google_password"] },
            "No account yet: nothing to reset",
        ),
        ...clickAction("action_create_google_account", "Click 'Create Google account'"),
        {
            trigger: ".o_notification",
            content: "The tutor is told the account is being created",
        },
        ...checkActions(
            {
                offered: ["action_authorization_send_bulk"],
                notOffered: ["action_create_google_account", "action_reset_google_password"],
            },
            "The creation is queued: the button is gone until it is over",
        ),
    ],
});
