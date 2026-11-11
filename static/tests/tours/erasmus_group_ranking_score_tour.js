/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #773. Records seeded by tests/test_erasmus_group_ranking_score_tour.py.

registry.category("web_tour.tours").add("ems_erasmus_group_ranking_score", {
    test: true,
    steps: () => [
        {
            trigger: ".o_kanban_record:contains('Test SMX2 morning'), .o_data_row:contains('Test SMX2 morning')",
            content: "Open the group mobility",
            run: "click",
        },
        {
            trigger: ".o_form_view a.nav-link[name='selection']",
            content: "The selection",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='registration_ids'] table:has(th[data-name='score']):not(:has(th[data-name='strike_count']))",
            content: "The score next to the average, never the conduct warnings",
        },
        {
            trigger: ".o_field_widget[name='registration_ids'] .o_data_row:first td[name='score']:contains('8.00')",
            content: "First, the student with fewer opportunities accredited (7.00 + 1)",
        },
    ],
});
