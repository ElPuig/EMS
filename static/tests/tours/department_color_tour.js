/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke-tests hr.department's custom_color widget on its own list+form (ems.action_department_tree).
// See docs/en/developers/shared/color_widget.md.
registry.category("web_tour.tours").add("ems_department_color_smoke", {
    test: true,
    url: "/odoo/action-ems.action_department_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Departments list view loaded",
        },
        {
            trigger: ".o_list_view .o_data_row:first-child .o_field_color",
            content: "Color swatch rendered in the list",
        },
        {
            trigger: ".o_list_view .o_data_row:first-child td[name='name']",
            content: "Open the first department",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='custom_color'] .o_field_color",
            content: "Color swatch rendered on the form",
        },
    ],
});

// Smoke-tests the SECONDARY kanban view (hr.hr_department_kanban_action) — reachable only
// through a different action than ems.action_department_tree above (not from any EMS menu at
// all), which is exactly the kind of view a per-model tour convention easily misses. It embeds
// custom_color inside the card's "..." config menu (view_department_kanban's override of
// hr.hr_department_view_kanban), which only renders once that menu is opened.
registry.category("web_tour.tours").add("ems_department_kanban_color_smoke", {
    test: true,
    url: "/odoo/action-hr.hr_department_kanban_action",
    steps: () => [
        {
            trigger: ".o_kanban_view",
            content: "Departments kanban view loaded",
        },
        {
            // The toggle is CSS "visibility: hidden" until the card is hovered
            // (kanban_controller.scss), which a headless tour never simulates - ":not(:visible)"
            // is the tour engine's own documented way to target a deliberately CSS-hidden
            // element (see the "TIP" in a failed run's error message).
            trigger: ".o_kanban_record:first-child .o_dropdown_kanban button:not(:visible)",
            content: "Open the first card's config menu",
            run: "click",
        },
        {
            trigger: ".ems_color_swatch .o_field_color",
            content: "Color swatch rendered inside the card's config menu",
        },
    ],
});
