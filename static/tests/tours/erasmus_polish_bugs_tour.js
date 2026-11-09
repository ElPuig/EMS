/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #777 - bugs found in the review of 46.0. Records seeded by
// tests/test_erasmus_polish_bugs_tour.py; structural selectors only.

const HOST = "Test Polish Host GmbH";
const PROJECT = "2099-1-ES01-KA121-VET-000777777";

// 13.3: the Erasmus team fills in a host entity's address, website and OID.
registry.category("web_tour.tours").add("ems_erasmus_host_entity_details", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_host_entity",
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row td[name='complete_name']:contains('${HOST}'), .o_list_view .o_data_row td[name='name']:contains('${HOST}')`,
            content: "The host entity is listed",
        },
        {
            trigger: ".o_control_panel .o_switch_view.o_kanban",
            content: "Switch to the cards",
            run: "click",
        },
        {
            trigger: `.o_kanban_view .o_kanban_record:contains('${HOST}')`,
            content: "Open the host entity",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='street'] input",
            content: "Its address is in sight",
            run: "edit Hauptstrasse 1",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='city'] input",
            content: "Its city",
            run: "edit Reutlingen",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='website'] input",
            content: "Its website",
            run: "edit https://host.example.com",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='erasmus_oid'] input",
            content: "Its Erasmus+ OID",
            run: "edit E10150031",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});

// 10.2: a year is shown as 2099, never with a thousands separator (economic panel and project).
registry.category("web_tour.tours").add("ems_erasmus_project_year", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_economy_panel",
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row:contains('${PROJECT}') td[name='call_year']:contains('2099')`,
            content: "The panel's list shows the year as is",
        },
        {
            trigger: ".o_control_panel .o_switch_view.o_pivot",
            content: "Switch to the comparison by call",
            run: "click",
        },
        {
            trigger: ".o_pivot th:contains('2099')",
            content: "The comparison by call shows the year as is",
        },
        {
            trigger: ".o_control_panel .o_switch_view.o_list",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: `.o_list_view .o_data_row:contains('${PROJECT}') td[name='name']`,
            content: "Open the project",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='call_year']:contains('2099')",
            content: "The project's form shows the year as is",
        },
    ],
});

// 13.8: the organisational support rates show the year as is.
registry.category("web_tour.tours").add("ems_erasmus_support_rate_year", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_support_rate",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='call_year']:contains('2099')",
            content: "The rates show the year as is",
        },
    ],
});
