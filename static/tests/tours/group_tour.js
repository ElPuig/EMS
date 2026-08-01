/** @odoo-module **/

import { registry } from "@web/core/registry";

// Two halves: (1) open an existing, real 'main' group and click through every tab
// (Students/Enrolled/Schedule/Notes) to confirm none of them crash on render — a real
// group with real enrollments/schedule data exercises this far more realistically than a
// freshly created empty one, and a full 'main' group create() would need several
// interdependent Many2one selections (level → filtered study → tutor) that add fragility
// for little extra coverage over what test_group.py's TransactionCase tests already prove.
// (2) full CRUD on a 'reinforcement' group instead, which only ever needs a plain Name —
// no Many2one selection at all — covering the create/save/delete path safely.
registry.category("web_tour.tours").add("ems_group_form_tabs_and_reinforcement_crud", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Groups list view loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the DAM1A group",
            run: "edit DAM1A",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('DAM1A')",
            content: "Open the DAM1A group",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Students')",
            content: "Open the Students tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='main_student_ids']",
            content: "Students tab rendered without crashing",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Enrolled')",
            content: "Open the Enrolled tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='enrollment_view_ids']",
            content: "Enrolled tab (side-effecting compute) rendered without crashing",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='schedule_attendance_ids']",
            content: "Schedule tab rendered without crashing",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Notes')",
            content: "Open the Notes tab",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to the list — done reviewing the real group, no changes made",
            run: "click",
        },
        // --- Reinforcement group: full CRUD, no Many2one selection needed ---
        {
            trigger: ".o_list_button_add",
            content: "Click New",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_type'] label:contains('Reinforcement')",
            content: "Switch to Reinforcement",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Reinforcement Group",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        // The reinforcement-type "Students" page (reinforcement_student_ids) is a SEPARATE
        // <page> from the main-type one already checked above (same tab label, different
        // visibility condition) - never rendered by any tour before.
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Students')",
            content: "Open the reinforcement group's own Students tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='reinforcement_student_ids']",
            content: "The reinforcement Students tab rendered without crashing",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Navigate back to the list",
            run: "click",
        },
        {
            trigger: ".o_searchview .o_facet_remove",
            content: "Remove the DAM1A search filter",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Reinforcement Group')",
            content: "New reinforcement group confirmed in list",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_cp_action_menus button",
            content: "Open action menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains('Delete')",
            content: "Click Delete",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm deletion",
            run: "click",
        },
        {
            trigger: ".o_list_view, .o_breadcrumb a",
            content: "Back in list after deletion (navigating there explicitly if needed)",
            run: () => {
                document.querySelector(".o_breadcrumb a")?.click();
            },
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td:contains('Tour Reinforcement Group')))",
            content: "Reinforcement group deleted — no longer in list",
        },
    ],
});

// Exercises the RedirectWarning-based duplicate-name guard added to ems.group's create()/write()
// (models/contacts/group.py::_raise_if_archived_duplicate): creating a group whose name matches
// an already-ARCHIVED group must not silently create a duplicate - it should offer to reactivate
// the archived one instead. Two archived reinforcement groups are seeded via the ORM in
// TestGroupTour.test_group_reactivate_archived_duplicate_tour; this tour proves both outcomes of
// the dialog actually work in the browser: accepting reactivates and navigates there, cancelling
// leaves everything untouched (no duplicate, original still archived).
registry.category("web_tour.tours").add("ems_group_reactivate_archived_duplicate", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Groups list loaded",
        },
        // --- Accept path: click "Reactivate" ---
        {
            trigger: ".o_list_button_add",
            content: "Click New",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_type'] label:contains('Reinforcement')",
            content: "Switch to Reinforcement",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Type the archived group's exact name",
            run: "edit Tour Archived Reinforcement Reactivate",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save - this should collide with the archived group of the same name",
            run: "click",
        },
        {
            // A Save failing from a form view is shown by Odoo's generic "Oh snap!"
            // FormErrorDialog (web.FormErrorDialog), not the plain RedirectWarningDialog used
            // for other error entry points - our custom "Reactivate" label ends up on its own
            // btn-secondary button (redirectBtnLabel), alongside the dialog's own built-in
            // "Stay here"/"Discard changes" buttons.
            trigger: ".modal .btn-secondary:contains('Reactivate')",
            content: "The error dialog offers our custom 'Reactivate' action",
        },
        {
            trigger: ".modal .btn-secondary:contains('Reactivate')",
            content: "Accept - reactivate it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_breadcrumb:contains('Tour Archived Reinforcement Reactivate')",
            content: "Landed on the (now reactivated) group's own form",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger:
                ".o_list_view .o_data_row td:contains('Tour Archived Reinforcement Reactivate')",
            content: "The reactivated group shows up in the plain (non-archived) list - proof it is active again, not just navigated to while still archived",
        },
        // --- Cancel path: close the dialog instead ---
        {
            trigger: ".o_list_button_add",
            content: "Click New again",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_type'] label:contains('Reinforcement')",
            content: "Switch to Reinforcement",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Type the OTHER archived group's exact name",
            run: "edit Tour Archived Reinforcement Cancel",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save - collides with the second archived group",
            run: "click",
        },
        {
            // "Discard changes" both closes the dialog and discards the still-unsaved new-group
            // form in one action - nothing should have been created.
            trigger: ".modal .btn-secondary:contains('Discard changes')",
            content: "Decline - discard instead of reactivating",
            run: "click",
        },
        {
            // Whether "Discard changes" lands back on the list directly or leaves the (now
            // reset) new-record form in place depends on internal FormController behaviour not
            // worth pinning down here - explicitly getting back to the list either way.
            trigger: ".o_list_view, .o_breadcrumb a",
            content: "Back in the list (navigating there explicitly if needed)",
            run: () => {
                document.querySelector(".o_breadcrumb a")?.click();
            },
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the second archived group's name",
            run: "edit Tour Archived Reinforcement Cancel",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            // Proves the whole point of this cancel path: no duplicate was created. Whether
            // exactly one archived record with this name still exists is already asserted at
            // the ORM level by test_group.py's own regression tests - no need to also drive the
            // search Filters menu here just to re-check the same invariant less precisely.
            trigger:
                ".o_list_view:not(:has(.o_data_row td:contains('Tour Archived Reinforcement Cancel')))",
            content: "Not in the plain list - no duplicate was created, and the archived one still isn't shown",
        },
    ],
});
