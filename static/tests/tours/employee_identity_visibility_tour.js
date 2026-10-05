/** @odoo-module **/

import { registry } from "@web/core/registry";

// The identity document and social security number live in the teacher form's "Private
// Information" tab. The backend test (tests/test_employee_identity_visibility.py) proves who
// may read and write them; only a browser proves the tab actually renders them for each role.

const privateTab = ".o_notebook_headers a[name='personal_information']";

// A Department Chief has no hr.group_hr_user, yet gets the tab, read-only, on a teacher of
// their own department - and no tab at all on another department's teacher.
registry.category("web_tour.tours").add("ems_employee_identity_visibility", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('0000 IDV Own Teacher')",
            content: "Teachers kanban renders for the Department Chief",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 IDV Own Teacher')",
            content: "Open a teacher of the chief's own department",
            run: "click",
        },
        {
            trigger: privateTab,
            content: "Open the Private Information tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='scoped_identification_id']:contains('11111111H')",
            content: "The identity document is shown",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='scoped_ssnid']:contains('081234567890')",
            content: "The social security number is shown",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='scoped_identification_id'] input))",
            content: "Read-only: no input to type in",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='private_street']))",
            content: "The rest of the private information stays hidden",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 IDV Other Teacher')",
            content: "Open a teacher of another department",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb .active:contains('0000 IDV Other Teacher')",
            content: "The other teacher's form is loaded",
        },
        {
            trigger: `.o_form_view:not(:has(${privateTab}))`,
            content: "No Private Information tab on another department's teacher",
        },
    ],
});

// The secretariat edits the identity data of any staff member, ASP included.
registry.category("web_tour.tours").add("ems_employee_identity_secretary_edit", {
    test: true,
    url: "/odoo/action-ems.action_asp_kanban",
    steps: () => [
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('0000 IDV ASP')",
            content: "ASP kanban renders for the secretariat",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 IDV ASP')",
            content: "Open the ASP",
            run: "click",
        },
        {
            trigger: privateTab,
            content: "Open the Private Information tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='identification_id'] input",
            content: "Type the identity document",
            run: "edit 44444444A",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ssnid'] input",
            content: "Type the social security number",
            run: "edit 080000000002",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "The edit was accepted",
        },
    ],
});
