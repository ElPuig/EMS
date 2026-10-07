/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #575: a checked-in colleague's presence dot is green both on the Teachers kanban and on
// their own form, for a tutor (no HR rights). The form used to show it grey ("Out of working
// hours"): its state was computed with the viewer's rights, which can't read the last check-in.
// Seed data comes from TestEmployeePresenceTour (tests/test_employee_presence_tour.py).
registry.category("web_tour.tours").add("ems_employee_presence", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_kanban_record:contains('0000 Presence Colleague') .hr_presence.text-success",
            content: "The checked-in colleague is present (green) on the kanban",
        },
        {
            trigger: ".o_kanban_record:contains('0000 Presence Colleague')",
            content: "Open their form",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_employee_availability .hr_presence.text-success",
            content: "...and present (green) on the form too",
        },
    ],
});
