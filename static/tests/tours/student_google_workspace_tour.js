/** @odoo-module **/

import { registry } from "@web/core/registry";

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
        {
            trigger: "button[name='action_cancel_scheduled_deactivation']",
            content: "Call off the scheduled deactivation",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.alert-warning:contains('scheduled to be deactivated')))"
                + ":not(:has(button[name='action_cancel_scheduled_deactivation']))",
            content: "Banner and button are both gone: the account is kept",
        },
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
        {
            trigger: "button[name='action_delete_google_account']",
            content: "Delete the account for good",
            run: "click",
        },
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
            trigger: ".o_form_view:not(:has(.alert-danger))"
                + ":not(:has(button[name='action_delete_google_account']))",
            content: "Deletion banner and button are gone: the account is deleted",
        },
    ],
});

// Issue #478: the TAC team resets a student's Google password from the form header (and is
// offered the suspend button next to it). Opened by
// URL on the seeded student (see test_student_google_workspace_tour.py).
registry.category("web_tour.tours").add("ems_student_google_password_reset", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_form_statusbar button[name='action_suspend_google_account']",
            content: "The TAC team can also suspend the account",
        },
        {
            trigger: ".o_form_view .o_form_statusbar button[name='action_reset_google_password']",
            content: "Click 'Reset Google password'",
            run: "click",
        },
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
            trigger: ".o_form_view .o_notebook .nav-link[name='documentation']",
            content: "Open the Documentation tab",
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
        {
            trigger: ".o_form_view .o_form_statusbar:not(:has(button[name='action_suspend_google_account']))",
            content: "The tutor is not offered the account lifecycle buttons",
        },
        {
            trigger: ".o_form_view .o_form_statusbar button[name='action_reset_google_password']",
            content: "Click 'Reset Google password'",
            run: "click",
        },
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
            trigger: ".o_form_view .o_notebook .nav-link[name='documentation']",
            content: "Open the Documentation tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='document_ids'] .o_data_row:contains('Cancelled') ~ .o_data_row:contains('Approved'), .o_field_widget[name='document_ids'] .o_data_row:contains('Approved') ~ .o_data_row:contains('Cancelled')",
            content: "The tutor reads the new credentials next to the cancelled old ones",
        },
    ],
});

// Issue #513: a tutor creates the Google account of one of their own students who has none yet,
// and is then offered the password reset on the same form. Opened by URL on the seeded student
// (see test_student_google_workspace_tour.py).
registry.category("web_tour.tours").add("ems_student_google_account_create_tutor", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_form_statusbar:not(:has(button[name='action_reset_google_password']))",
            content: "No account yet: nothing to reset",
        },
        {
            trigger: ".o_form_view .o_form_statusbar button[name='action_create_google_account']",
            content: "Click 'Create Google account'",
            run: "click",
        },
        {
            trigger: ".o-mail-Message:contains('account created')",
            content: "The chatter records the new account",
        },
        {
            trigger: ".o_form_view .o_form_statusbar:not(:has(button[name='action_create_google_account']))"
                + " button[name='action_reset_google_password']",
            content: "The account is active: the tutor can now reset its password",
        },
    ],
});
