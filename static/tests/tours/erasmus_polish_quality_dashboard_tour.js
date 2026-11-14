/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #793 - the quality panel opens on the current course, with the columns Indicator, Value,
// Target, Met (a coloured badge) and Answers, and the diffusion actions row.
// Seeded by tests/test_erasmus_polish_quality_dashboard.py (TestErasmusQualityDashboardTour).
registry.category("web_tour.tours").add("ems_erasmus_polish_quality_dashboard", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='course_id'] input:value('2093-2094')",
            content: "The current course, already chosen",
        },
        {
            trigger: ".o_ems_erasmus_quality_table thead tr:has(th:nth-child(5):last-child)",
            content: "Five columns: no median",
        },
        {
            trigger: ".o_ems_erasmus_quality_table td:contains('Diffusion actions') ~ td:contains('≥ 10') ~ td .badge.text-bg-danger",
            content: "The diffusion actions, below their target, in red",
        },
    ],
});
