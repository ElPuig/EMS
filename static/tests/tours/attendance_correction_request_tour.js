/** @odoo-module **/

import { registry } from "@web/core/registry";

// The native hr.attendance form's EMS additions (the "Request Correction" statusbar button and
// the "Corrections" stat button, views/attendance/attendance_correction/hr_attendance_form.xml)
// had zero coverage - no EMS tour ever opens the native check-in/check-out form at all, so
// attendance_correction_tour.js's own "accept an existing request" flow never exercised how a
// request is actually created in the first place.
registry.category("web_tour.tours").add("ems_attendance_correction_request", {
    test: true,
    url: "/odoo/action-hr_attendance.hr_attendance_action",
    steps: () => [
        { trigger: ".o_list_view", content: "Employee Attendances list loaded" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded employee",
            run: "edit Attendance Correction Request Tour Employee",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        {
            trigger: ".o_searchview_facet:contains('Attendance Correction Request Tour Employee')",
            content: "The search facet is applied",
        },
        // The native view's own default context groups by month then employee - drop it so
        // the seeded row is flat, same pattern as applicant_tour.js/no_destination_tour.js.
        {
            trigger: ".o_searchview_facet:contains('Date') .o_facet_remove",
            content: "Remove the default 'Date: Month > Employee' grouping facet",
            run: "click",
        },
        {
            // Odoo binds the row-open click handler to a data cell, not the bare <tr>.
            trigger: ".o_list_view .o_data_row .o_data_cell",
            content: "Open the seeded attendance",
            run: "click",
        },
        {
            trigger: ".o_form_statusbar button:contains('Request Correction')",
            content: "Open the correction request dialog",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='reason'] textarea",
            content: "Fill in the reason",
            run: "edit Tour: forgot to check out on time",
        },
        {
            // No <footer> in view_attendance_correction_form.xml - the dialog uses the
            // standard top-bar save icon, not dialog-footer buttons.
            trigger: ".modal .o_form_button_save",
            content: "Save the correction request",
            run: "click",
        },
        {
            trigger: ".o_form_view .oe_stat_button:contains('Corrections')",
            content: "Back on the attendance form - the 'Corrections' stat button now shows the new request",
        },
    ],
});

// Issue #479: while the teacher is still clocked in (no check-out yet) AND still within their
// expected working hours for that day, the correction dialog must hide requested_check_out
// entirely - only the check-in can be requested, since they haven't left yet.
registry.category("web_tour.tours").add("ems_attendance_correction_request_open_within_schedule", {
    test: true,
    url: "/odoo/action-hr_attendance.hr_attendance_action",
    steps: () => [
        { trigger: ".o_list_view", content: "Employee Attendances list loaded" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded employee",
            run: "edit Attendance Correction Open Schedule Tour Employee",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        {
            trigger: ".o_searchview_facet:contains('Attendance Correction Open Schedule Tour Employee')",
            content: "The search facet is applied",
        },
        {
            trigger: ".o_searchview_facet:contains('Date') .o_facet_remove",
            content: "Remove the default 'Date: Month > Employee' grouping facet",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell",
            content: "Open the seeded open attendance",
            run: "click",
        },
        {
            trigger: ".o_form_statusbar button:contains('Request Correction')",
            content: "Open the correction request dialog",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='requested_check_in']",
            content: "Only the check-in field is shown - the schedule hasn't ended yet",
            run: () => {
                if (document.querySelector(".modal .o_field_widget[name='requested_check_out']")) {
                    throw new Error("requested_check_out should be hidden while still within the working schedule");
                }
            },
        },
        {
            trigger: ".modal .o_field_widget[name='reason'] textarea",
            content: "Fill in the reason",
            run: "edit Tour: still within today's schedule",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Save the correction request",
            run: "click",
        },
        {
            trigger: ".o_form_view .oe_stat_button:contains('Corrections')",
            content: "Back on the attendance form - the 'Corrections' stat button now shows the new request",
        },
    ],
});
