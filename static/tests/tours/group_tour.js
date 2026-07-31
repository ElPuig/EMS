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
