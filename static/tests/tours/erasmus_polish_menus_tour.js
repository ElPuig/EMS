/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #789 (12.6) - from the quality panel to the low scores still without an improvement action.
// Seeded by tests/test_erasmus_polish_menus.py (TestErasmusPolishMenusTour).
registry.category("web_tour.tours").add("ems_erasmus_polish_menus_low_scores", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook button[name='action_open_low_scores']:contains('without an improvement action')",
            content: "The low scores, under the indicators",
            run: "click",
        },
        {
            trigger: ".o_searchview_facet:contains('Without an improvement action')",
            content: "Those without an action, filtered",
        },
        {
            trigger: ".o_list_view .o_data_row",
            content: "The low score",
        },
    ],
});
