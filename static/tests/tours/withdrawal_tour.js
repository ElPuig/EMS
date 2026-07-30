/** @odoo-module **/

import { registry } from "@web/core/registry";

// Archiving via the generic "Archive" action (form cog-menu for a single record, list
// multi-selection for several) must open the withdrawal wizard — not archive silently.
// This IS the withdrawal flow now: there is no separate "Withdrawal" button anymore (see
// toggle_active on res.partner, models/contacts/contact.py), so this is the only UI entry
// point left to cover the wizard end-to-end in a real browser.
registry.category("web_tour.tours").add("ems_archive_action_single_opens_wizard", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Archive Action Tour Single')",
            content: "Open the seeded student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_cp_action_menus button",
            content: "Open the form's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains('Archive')",
            content: "Click Archive — the withdrawal wizard must open directly, with no generic "
                + "'are you sure?' dialog first (StudentPopupFormController.getStaticActionMenuItems)",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='exit_reason'] textarea",
            content: "The withdrawal wizard opens instead — fill in the exit reason",
            run: "edit Tour: archived via generic Archive action",
        },
        {
            trigger: ".modal-footer button[name='action_apply']",
            content: "Confirm the withdrawal",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm the 'immediately' warning dialog",
            run: "click",
        },
        {
            trigger: ".o_form_view .ribbon span:contains('Archived')",
            content: "Back on the student form — the Archived ribbon confirms active=False",
        },
    ],
});

registry.category("web_tour.tours").add("ems_archive_action_bulk_opens_wizard", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('Archive Action Tour Bulk A')) .o_list_record_selector",
            content: "Select the first seeded student",
            run: "click",
        },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('Archive Action Tour Bulk B')) .o_list_record_selector",
            content: "Select the second seeded student",
            run: "click",
        },
        {
            trigger: ".o_cp_action_menus button",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains('Archive')",
            content: "Click Archive — the withdrawal wizard must open directly, with no generic "
                + "'are you sure?' dialog first (StudentListController.getStaticActionMenuItems)",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='exit_reason'] textarea",
            content: "The withdrawal wizard opens for both students — fill in the reason",
            run: "edit Tour: bulk archived via generic Archive action",
        },
        {
            trigger: ".modal .o_data_row:contains('Archive Action Tour Bulk A')",
            content: "Both students are listed in the wizard",
        },
        {
            trigger: ".modal .o_data_row:contains('Archive Action Tour Bulk B')",
            content: "Both students are listed in the wizard",
        },
        {
            trigger: ".modal-footer button[name='action_apply']",
            content: "Confirm the withdrawal",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm the 'immediately' warning dialog",
            run: "click",
        },
        {
            trigger:
                ".o_list_view:not(:has(.o_data_cell:contains('Archive Action Tour Bulk A')))",
            content: "Both withdrawn students no longer show under the default Students filter",
        },
    ],
});

// The withdrawn (now archived) student from the single-record tour above still shows up
// under "Former students" — the one thing a TransactionCase can't catch:
// action_student_kanban's context needs active_test:False, or an archived alumni/withdrawal
// would silently vanish from every filter regardless of domain (see views/community/menu.xml).
registry.category("web_tour.tours").add("ems_archive_action_shows_in_list", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        // A single click on the facet's remove button reliably updates the search domain
        // (confirmed via the actual RPC payload) but can occasionally get lost — most
        // likely swallowed by a layout reflow while this 1000+-row list is still settling
        // its initial render — leaving the facet *chip* stuck showing "Students" even
        // though the click landed. Opening the dropdown while that stale chip is still
        // around then swaps out the toggler mid-click and the "Former students" menu item
        // never appears (TIMEOUT). A single defensive re-click on a fixed "body" trigger
        // wasn't reliable either (confirmed via a failing run + its screenshot: the chip
        // was still there), because it only fires once, at a fixed point in time, with no
        // guarantee the reflow has finished by then. Poll instead: keep clicking the
        // remove button, with a real delay between attempts, until it is actually gone.
        {
            trigger: ".o_searchview_facet .o_facet_remove",
            content: "Remove the default 'Students' filter, retrying the click until it actually takes",
            run: async () => {
                for (let attempt = 0; attempt < 20; attempt++) {
                    const removeBtn = document.querySelector(".o_searchview_facet .o_facet_remove");
                    if (!removeBtn) break;
                    removeBtn.click();
                    await new Promise((resolve) => setTimeout(resolve, 200));
                }
            },
        },
        {
            trigger: ".o_searchview_input_container:not(:has(.o_searchview_facet))",
            content: "Confirm the 'Students' filter is fully removed",
        },
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search dropdown",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .o_menu_item:contains('Former students')",
            content: "Enable the 'Former students' filter",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Archive Action Tour Single')",
            content: "The withdrawn (now archived) student still shows up under Former students",
        },
    ],
});
