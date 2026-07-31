/** @odoo-module **/

import { registry } from "@web/core/registry";

// account.move.line's "Enrollment collections" screen (Accounting > Enrollment collections):
// a pure read-only report (create="0" edit="0" delete="0", list-only view_mode, grouped by
// due date) had zero browser coverage. A render smoke test - seeding a matching posted
// invoice would need substantial accounting fixture setup for a purely read-only screen, so
// this confirms the list (with its default group-by) loads without crashing regardless of
// whether any row currently matches the domain.
registry.category("web_tour.tours").add("ems_enrollment_collections_open", {
    test: true,
    url: "/odoo/action-ems.action_enrollment_collections",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Enrollment collections list rendered without crashing",
        },
    ],
});
