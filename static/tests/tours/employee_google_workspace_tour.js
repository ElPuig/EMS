/** @odoo-module **/

import { registry } from "@web/core/registry";

// Covers google_ws_state on the employee form header (views/community/employee/form.xml):
// exactly one Google Workspace / EMS user button must be visible per state, never two at
// once — the original bug report this consolidation fixes (Create + Suspend both showing
// for a teacher whose account was adopted from pre-integration/migrated data).
registry.category("web_tour.tours").add("ems_employee_google_workspace_state", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Teachers loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        // --- state 'none': only "Create Google account" ---------------------
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('GW Tour None')",
            content: "Open the 'none' state teacher",
            run: "click",
        },
        {
            trigger:
                ".o_statusbar_buttons:has(button[name='action_create_google_account'])"
                + ":not(:has(button[name='action_create_ems_user']))"
                + ":not(:has(button[name='action_suspend_google_account']))"
                + ":not(:has(button[name='action_reactivate_google_account']))",
            content: "Only 'Create Google account' is visible",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        // --- state 'pending_user': only "Create EMS User" --------------------
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('GW Tour Pending')",
            content: "Open the 'pending_user' state teacher",
            run: "click",
        },
        {
            trigger:
                ".o_statusbar_buttons:has(button[name='action_create_ems_user'])"
                + ":not(:has(button[name='action_create_google_account']))"
                + ":not(:has(button[name='action_suspend_google_account']))"
                + ":not(:has(button[name='action_reactivate_google_account']))",
            content: "Only 'Create EMS User' is visible — Suspend is NOT offered "
                + "before the account is adopted (the bug this consolidation fixes)",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        // --- state 'active': only "Suspend Google account" -------------------
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('GW Tour Active')",
            content: "Open the 'active' state teacher",
            run: "click",
        },
        {
            trigger:
                ".o_statusbar_buttons:has(button[name='action_suspend_google_account'])"
                + ":not(:has(button[name='action_create_google_account']))"
                + ":not(:has(button[name='action_create_ems_user']))"
                + ":not(:has(button[name='action_reactivate_google_account']))",
            content: "Only 'Suspend Google account' is visible",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        // --- state 'suspended': only "Reactivate Google account" -------------
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('GW Tour Suspended')",
            content: "Open the 'suspended' state teacher",
            run: "click",
        },
        {
            trigger:
                ".o_statusbar_buttons:has(button[name='action_reactivate_google_account'])"
                + ":not(:has(button[name='action_create_google_account']))"
                + ":not(:has(button[name='action_create_ems_user']))"
                + ":not(:has(button[name='action_suspend_google_account']))",
            content: "Only 'Reactivate Google account' is visible",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        // --- pending identification: "Mark as identified" clears it manually -
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('GW Tour Pending Identification')",
            content: "Open the pending-identification teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .ribbon:contains('Pending identification')",
            content: "The pending-identification ribbon shows",
        },
        {
            // Regression check for #378: schedule_import_code (only visible while
            // pending) used to be inserted INSIDE the title/avatar flex row, pushing
            // the avatar off its normal top-right slot onto its own line below the
            // title/buttons - only reproducible while genuinely pending, since that
            // field is invisible (no layout footprint at all) otherwise. This selector
            // only matches when the avatar is still the title's immediate next sibling
            // in the row, i.e. nothing else got inserted between them.
            trigger: ".row.justify-content-between > .oe_title + .o_employee_avatar",
            content: "The avatar sits right next to the title, not pushed onto its own line",
        },
        {
            trigger: "button[name='action_mark_as_identified']",
            content: "Click 'Mark as identified'",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm the action in the dialog",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.ribbon:contains('Pending identification')))"
                + ":not(:has(button[name='action_mark_as_identified']))",
            content: "The ribbon and the button are both gone: no longer pending",
        },
    ],
});
