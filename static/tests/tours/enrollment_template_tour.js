/** @odoo-module **/

import { registry } from "@web/core/registry";

// sale.order.template's "Enrollment Templates" screen (Academic Management > Enrollment
// Configuration): a heavily xpath-customized quotation-template form (EMS study/level
// linkage, several native fields hidden) had zero browser coverage. A plain create-CRUD
// smoke test - ems_study_id is required.
registry.category("web_tour.tours").add("ems_enrollment_template_crud", {
    test: true,
    url: "/odoo/action-ems.action_ems_enrollment_template",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Enrollment templates list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new enrollment template",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in the name",
            run: "edit Tour Enrollment Template",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_study_id'] input",
            content: "Search for the seeded study (required)",
            run: "edit Test Study (Enrollment Template Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Study (Enrollment Template Tour)')",
            content: "Select it from the dropdown",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
        {
            trigger: ".o_breadcrumb:contains('Tour Enrollment Template')",
            content: "The enrollment template was created and saved",
        },
    ],
});
