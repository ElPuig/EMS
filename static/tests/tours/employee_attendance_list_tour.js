/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #543 - the staff's own attendance list (Employee Attendances > Attendance). A plain
// employee only ever sees their own attendance, so the list opens flat and a row is one click away
// from its "Request Correction" button; from Department Chief up, who see several employees, it
// keeps opening grouped. Structural selectors only (no labels): the two users' language is not
// part of what is being checked. Seed data comes from TestEmployeeAttendanceListTour.
registry.category("web_tour.tours").add("ems_employee_attendance_list_employee", {
    test: true,
    url: "/odoo/action-hr_attendance.hr_attendance_action",
    steps: () => [
        {
            trigger: ".o_list_view:not(:has(.o_group_header)) .o_data_row",
            content: "The employee's own attendance, as a flat list: no group to unfold first",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell",
            content: "Open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_statusbar button.btn-secondary",
            content: "Its form offers to request a correction",
        },
    ],
});

registry.category("web_tour.tours").add("ems_employee_attendance_list_chief", {
    test: true,
    url: "/odoo/action-hr_attendance.hr_attendance_action",
    steps: () => [
        {
            trigger: ".o_list_view .o_group_header",
            content: "A Department Chief sees several employees: the list opens grouped",
        },
        {
            trigger: ".o_searchview .o_searchview_facet",
            content: "With its default group-bys on",
        },
    ],
});
