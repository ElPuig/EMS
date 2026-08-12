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
