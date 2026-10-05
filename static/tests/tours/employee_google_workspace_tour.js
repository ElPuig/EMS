/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Covers google_ws_state on the employee form's Actions dropdown (views/community/employee/
// form.xml): exactly one Google Workspace / EMS user entry must be offered per state, never two at
// once — the original bug report this consolidation fixes (Create + Suspend both showing
// for a teacher whose account was adopted from pre-integration/migrated data).
// The single exception is "Re-link Google sign-in" (issue #420), a repair driven by its
// own google_signin_missing field that shows next to Suspend in the 'active' state.
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
        ...checkActions(
            {
                offered: ["action_create_google_account"],
                notOffered: ["action_create_ems_user", "action_suspend_google_account", "action_reactivate_google_account"],
            },
            "Only 'Create Google account' is visible",
        ),
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
        ...checkActions(
            {
                offered: ["action_create_ems_user"],
                notOffered: ["action_create_google_account", "action_suspend_google_account", "action_reactivate_google_account"],
            },
            "Only 'Create EMS User' is visible — Suspend is NOT offered "
                + "before the account is adopted (the bug this consolidation fixes)",
        ),
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
        ...checkActions(
            {
                offered: ["action_suspend_google_account"],
                notOffered: ["action_create_google_account", "action_create_ems_user", "action_relink_google_signin", "action_reactivate_google_account"],
            },
            "Only 'Suspend Google account' is visible: this user's Google "
                + "sign-in is linked, so no repair is offered",
        ),
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        // --- state 'active' with a broken sign-in link (issue #420) ----------
        // The repair button is deliberately NOT another exclusive state: the account
        // is genuinely active, only its OAuth link is gone, so Suspend must keep
        // showing next to it.
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('GW Tour Relink')",
            content: "Open the teacher whose user lost its OAuth data",
            run: "click",
        },
        ...checkActions(
            {
                offered: ["action_relink_google_signin", "action_suspend_google_account"],
                notOffered: ["action_create_google_account", "action_create_ems_user", "action_reactivate_google_account"],
            },
            "'Re-link Google sign-in' shows alongside Suspend",
        ),
        ...clickAction("action_relink_google_signin", "Repair the Google sign-in link"),
        ...checkActions(
            { offered: ["action_suspend_google_account"], notOffered: ["action_relink_google_signin"] },
            "The repair entry is gone once the link is back; Suspend stays",
        ),
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
        ...checkActions(
            {
                offered: ["action_reactivate_google_account"],
                notOffered: ["action_create_google_account", "action_create_ems_user", "action_suspend_google_account"],
            },
            "Only 'Reactivate Google account' is visible",
        ),
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        // --- grace period (#388): the scheduled-deactivation banner and its button
        // The employee is archived (that is what opens the grace period), so the list
        // has to be switched to archived records first.
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search dropdown",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .dropdown-item:contains('Archived')",
            content: "Filter on archived employees",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('GW Tour Scheduled')",
            content: "Open the teacher whose deactivation is scheduled",
            run: "click",
        },
        {
            trigger: ".alert-warning:contains('scheduled to be deactivated')",
            content: "The grace-period banner shows the pending deactivation",
        },
        ...clickAction("action_cancel_scheduled_deactivation", "Call off the scheduled deactivation"),
        {
            trigger: ".o_form_view:not(:has(.alert-warning:contains('scheduled to be deactivated')))",
            content: "The banner is gone: the account is kept",
        },
        ...checkActions(
            { offered: ["action_create_ems_user"], notOffered: ["action_cancel_scheduled_deactivation"] },
            "Nothing left to call off: only the account's own state entry is offered",
        ),
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list",
            run: "click",
        },
        {
            trigger: ".o_searchview .o_facet_remove",
            content: "Drop the archived filter again",
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
        ...clickAction("action_mark_as_identified", "Click 'Mark as identified'"),
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm the action in the dialog",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.ribbon:contains('Pending identification')))",
            content: "The ribbon is gone: no longer pending",
        },
        ...checkActions(
            { offered: ["action_create_google_account"], notOffered: ["action_mark_as_identified"] },
            "Nothing left to mark: the entry is gone too",
        ),
    ],
});
