/** @odoo-module **/

import { registry } from "@web/core/registry";

// hr.work.location (Work locations): plain native Odoo model exposed through EMS's own menu,
// no EMS-specific fields or view customization. Had zero browser coverage. A plain
// create-CRUD smoke test.
registry.category("web_tour.tours").add("ems_work_location_crud", {
    test: true,
    url: "/odoo/action-ems.action_work_location_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Work locations list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new work location",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in the name",
            run: "edit Tour Work Location",
        },
        {
            // Work Address is required - pick the company's own address (always exists).
            trigger: ".o_form_view .o_field_widget[name='address_id'] input",
            content: "Search for the company's own address",
            run: "edit INS Puig Castellar",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('INS Puig Castellar')",
            content: "Select it from the dropdown",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb:contains('Tour Work Location')",
            content: "The work location was created and saved",
        },
    ],
});
