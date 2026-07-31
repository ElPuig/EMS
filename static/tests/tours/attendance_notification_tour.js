/** @odoo-module **/

import { registry } from "@web/core/registry";

// queue.job filtered to attendance-issue jobs (Attendance > Configuration > Sessions >
// Notifications): a pure monitoring screen (jobs are only ever created automatically via
// with_delay(), never by hand) had zero browser coverage. A render smoke test: open the
// seeded job and confirm its form renders.
registry.category("web_tour.tours").add("ems_attendance_notification_open", {
    test: true,
    url: "/odoo/action-ems.action_attendance_notification_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Attendance notifications list loaded",
        },
        {
            // Odoo's list view binds the row-open click handler to a data cell, not the
            // <tr> itself - clicking the bare row does nothing.
            trigger: ".o_list_view .o_data_row td[name='name']",
            content: "Open the seeded notification job",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='state']",
            content: "The job form rendered without crashing",
        },
    ],
});
