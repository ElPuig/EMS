/** @odoo-module **/

import { registry } from "@web/core/registry";

// The "Providers" filtered res.partner screen (Educational Community > Providers) had zero
// browser coverage - a plain create-CRUD smoke test, same pattern as family_tour.js.
registry.category("web_tour.tours").add("ems_provider_crud", {
    test: true,
    url: "/odoo/action-ems.action_provider_kanban",
    steps: () => [
        { trigger: ".o_control_panel", content: "Providers kanban loaded" },
        { trigger: ".o_switch_view.o_list", content: "Switch to list view", run: "click" },
        { trigger: ".o_list_view", content: "List view rendered" },
        { trigger: ".o_list_button_add", content: "Create a new provider", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='firstname'] input",
            content: "Fill in the first name",
            run: "edit Tour",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='lastname'] input",
            content: "Fill in the last name",
            run: "edit Provider Contact",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_button_save:not(:visible)", content: "Save completed" },
        {
            trigger: ".o_breadcrumb:contains('Tour Provider Contact')",
            content: "The provider contact was created and saved",
        },
    ],
});
