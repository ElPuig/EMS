/** @odoo-module **/

import { registry } from "@web/core/registry";

// Covers the space (classroom) form's own "Schedule" tab (views/community/space/form.xml) - the
// read-only aggregation widget (schedule_grid_readonly_field.js, widget="readonly_schedule_grid")
// reused as-is from the group's/student's own Schedule tab, this time backed by
// ems.space.schedule_attendance_ids. A clean TransactionCase/PDF-render test only proves the
// Python side works - this is what actually catches a client-side (OWL template/widget) crash,
// per CLAUDE.md's DTON "T" step.
registry.category("web_tour.tours").add("ems_space_schedule_tab", {
    test: true,
    url: "/odoo/action-ems.action_space_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Spaces list view loaded",
        },
        {
            // No free-text search step here (unlike the student tour): ems.space's search view
            // declares 'work_location_id' as its first field, so typing plain text and pressing
            // Enter matches that facet ("Location: ...") instead of a name search, and finds
            // nothing (confirmed empirically 2026-09-16 via the tour's own failure screenshot -
            // see CLAUDE.md's "Tour tests and language" section on always checking that
            // screenshot). The full Spaces list is small enough (well under one page) that the
            // test fixture's own row is already visible without searching for it.
            trigger: ".o_list_view .o_data_row td:contains('Tour Schedule Space')",
            content: "Open the test space",
            run: "click",
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
            trigger: ".o_form_view .o_field_widget[name='schedule_attendance_ids'] .o_schedule_grid_entry",
            content: "The space's own booked entry renders as a real block in the grid",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='schedule_attendance_ids'] .o_schedule_grid_toolbar button:contains('PDF')",
            content: "The PDF export button is available",
        },
    ],
});
