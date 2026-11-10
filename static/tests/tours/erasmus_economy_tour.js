/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #762 - the economic panel. Seeded by tests/test_erasmus_economy.py (TestErasmusEconomyTour):
// the Secretary opens the panel in both view modes, a project's Economy tab, and registers an
// expense from the Expenses menu. Structural selectors and fixture names only.
registry.category("web_tour.tours").add("ems_erasmus_economy_tour", {
    url: "/odoo/action-ems.action_erasmus_economy_panel",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('2019-1-ES01-KA131-HED-000000762')",
            content: "The project is on the panel",
        },
        {
            trigger: ".o_list_view .o_data_row:has(td[name='name']:contains('KA131-HED-000000762')) td[name='available_amount']:contains('4,925')",
            content: "Its available budget is the grant minus the registered expense",
        },
        {
            trigger: ".o_switch_view.o_pivot",
            content: "The comparison by call",
            run: "click",
        },
        {
            trigger: ".o_pivot_view .o_pivot",
            content: "The comparison renders",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('KA131-HED-000000762')",
            content: "Open the project",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link.active:contains('Economy'), .o_form_view .o_notebook .nav-item:first-child .nav-link.active",
            content: "The Economy tab is the first one",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='expense_ids'] .o_data_row td[name='concept']:contains('Merchandising')",
            content: "The project's expense is listed",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='economy_warnings']",
            content: "It warns about the expense without a receipt",
        },
        {
            trigger: ".o_main_navbar",
            content: "Go to the expenses",
            run() {
                window.location.href = "/odoo/action-ems.action_erasmus_expense";
            },
        },
        {
            trigger: ".o_control_panel .o_list_button_add",
            content: "New expense",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='project_id'] input",
            content: "Project",
            run: "edit KA131-HED-000000762",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('2019-HED')",
            content: "Pick the project",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='concept'] input",
            content: "Concept",
            run: "edit Tour dissemination service",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='amount'] input",
            content: "Amount",
            run: "edit 120",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save the expense",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});
