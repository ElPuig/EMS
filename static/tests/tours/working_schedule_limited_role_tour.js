/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #846: a role that can't read what the Schedule tab loads doesn't get the tab, and the form
// that holds it still opens. An access error loading the form fails the tour through the console.
const noScheduleTabStep = {
    trigger: ".o_form_view .o_notebook:not(:has(.nav-link[name='schedule']))",
    content: "The form is open, without a Schedule tab",
};

registry.category("web_tour.tours").add("ems_working_schedule_limited_role_profile", {
    test: true,
    steps: () => [
        {
            trigger: ".o_user_menu button",
            content: "Open the user menu",
            run: "click",
        },
        {
            trigger: ".dropdown-item:contains('My Profile')",
            content: "Open My Profile",
            run: "click",
        },
        {
            trigger: ".o_form_view:contains('Limited Role Tour User')",
            content: "My Profile loaded for the logged-in user",
        },
        noScheduleTabStep,
    ],
});

registry.category("web_tour.tours").add("ems_working_schedule_limited_role_form", {
    test: true,
    steps: () => [
        {
            trigger: ".o_kanban_view .o_kanban_record",
            content: "The teachers' kanban loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row",
            content: "The teachers' list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the tour's own teacher",
            run: "edit Limited Role Form User",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_searchview_facet",
            content: "Search applied",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Limited Role Form User')",
            content: "Open the teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view:contains('Limited Role Form User')",
            content: "The employee form loaded",
        },
        noScheduleTabStep,
    ],
});
