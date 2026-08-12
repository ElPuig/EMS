/** @odoo-module **/

import { registry } from "@web/core/registry";

// Regression coverage for the 'derivedBreaks'/'summary' staleness bug (schedule_grid_field.js,
// found 2026-08-11): the widget only loaded these two in 'onWillStart' (mount-only), so paging
// from one teacher's form to a DIFFERENT one via the pager - which the form view does WITHOUT
// remounting this component, an Odoo web client optimization - left the PREVIOUSLY viewed
// teacher's own derived break still showing on the newly navigated-to teacher, until an actual
// full page reload. Fixed via 'useRecordObserver' (reloads on every record change, not just on
// mount). Two fixture teachers, alphabetically adjacent and the only two matching the search
// below, so the pager's "next" reliably goes from A to B: Teacher A works only in the afternoon
// (real entries with a gap exactly matching the framework's own afternoon break), Teacher B only
// in the morning (same, for the morning break) - after paging from A to B, B's own morning break
// must show, and A's afternoon break must NOT still be showing.
registry.category("web_tour.tours").add("ems_working_schedule_stale_breaks", {
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
        {
            trigger: ".o_searchview_input",
            content: "Search for the two fixture teachers by their shared name prefix",
            run: "edit Stale Breaks Tour Teacher",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Stale Breaks Tour Teacher A')",
            content: "Open Teacher A",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('16:00-16:15')",
            content: "Teacher A shows their own afternoon break",
        },
        {
            trigger: ".o_pager_next",
            content: "Page to the next record (Teacher B) - the widget component is NOT remounted for this",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb:contains('Stale Breaks Tour Teacher B')",
            content: "Confirm the form actually navigated to Teacher B",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('09:00-09:15')",
            content: "Teacher B shows their own morning break",
        },
        {
            trigger: ".o_schedule_grid_grid:not(:has(.o_schedule_grid_entry:contains('16:00-16:15')))",
            content: "Teacher A's afternoon break must NOT still be showing on Teacher B's calendar - the exact regression this tour exists to catch",
        },
    ],
});
