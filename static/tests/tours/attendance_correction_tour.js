/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.attendance_correction (Attendances > Correction Requests): a teacher's request to amend
// a check-in/check-out, approved/rejected by a head of studies or academic admin - the
// approval step is the daily-use, admin-facing half of the flow and had zero browser
// coverage. This tour opens a seeded pending request and clicks Accept, verifying both the
// statusbar transition and that the underlying hr.attendance record was actually corrected.
registry.category("web_tour.tours").add("ems_attendance_correction_accept", {
    test: true,
    url: "/odoo/action-ems.action_attendance_correction_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Correction requests list loaded",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Attendance Correction Tour Teacher')",
            content: "Open the seeded pending request",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status button[data-value='pending'].o_arrow_button_current",
            content: "State starts as Pending",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='decision_note'] textarea",
            content: "Add a decision note",
            run: "edit Tour: accepted",
        },
        {
            // The arch's <header> tag compiles to a <div class="o_form_statusbar">, not a
            // literal <header> element (see form_compiler.js's compileHeader) - a
            // ".o_form_view header ..." selector silently never matches.
            trigger: ".o_form_statusbar button[name='action_accept']",
            content: "Accept the correction",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status button[data-value='accepted'].o_arrow_button_current",
            content: "State transitioned to Accepted",
        },
    ],
});

// ems.attendance_correction search view: the list defaults to showing only Pending
// requests (action context search_default_pending), matching the same pattern already
// used by ems.student.document — an approver reviewing this list should not have to
// wade through already-decided requests by default. This tour seeds one request per
// state and confirms only the pending one shows by default, that removing the default
// filter reveals all three, and that the Accepted filter can be used on its own to see
// only accepted requests.
registry.category("web_tour.tours").add("ems_attendance_correction_pending_filter", {
    test: true,
    url: "/odoo/action-ems.action_attendance_correction_tree",
    steps: () => [
        {
            trigger: ".o_searchview_facet:contains('Pending')",
            content: "Pending filter applied by default",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Filter Tour Teacher Pending')",
            content: "The pending request is shown by default",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td:contains('Filter Tour Teacher Accepted')))",
            content: "The accepted request is hidden under the default Pending filter",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td:contains('Filter Tour Teacher Rejected')))",
            content: "The rejected request is hidden under the default Pending filter",
        },
        {
            trigger: ".o_searchview_facet:contains('Pending') .o_facet_remove",
            content: "Remove the default Pending filter",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Filter Tour Teacher Accepted')",
            content: "All requests are shown once the default filter is removed",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Filter Tour Teacher Rejected')",
            content: "The rejected request is also shown",
        },
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search dropdown",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .o_menu_item:contains('Accepted')",
            content: "Enable the Accepted filter",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Filter Tour Teacher Accepted')",
            content: "Only the accepted request is shown",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td:contains('Filter Tour Teacher Pending')))",
            content: "The pending request is hidden while only the Accepted filter is active",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td:contains('Filter Tour Teacher Rejected')))",
            content: "The rejected request is hidden while only the Accepted filter is active",
        },
    ],
});
