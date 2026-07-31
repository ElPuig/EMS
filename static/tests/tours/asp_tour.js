/** @odoo-module **/

import { registry } from "@web/core/registry";

// "ASP" (action_asp_kanban, hr.employee filtered to employee_type='asp') and "Roles (for ASP)"
// (action_asp_role_tree, ems.role) are secondary actions on already-tested models (the
// Teachers kanban and Teachers roles list respectively share the exact same view
// architecture) - never opened themselves though, so their own domain/context is unverified.
registry.category("web_tour.tours").add("ems_asp_crud", {
    test: true,
    url: "/odoo/action-ems.action_asp_kanban",
    steps: () => [
        { trigger: ".o_control_panel", content: "ASP kanban loaded" },
        { trigger: ".o_switch_view.o_list", content: "Switch to list view", run: "click" },
        { trigger: ".o_list_view", content: "List view rendered" },
        { trigger: ".o_list_button_add", content: "Create a new ASP employee", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in the name",
            run: "edit ASP Tour Employee",
        },
        {
            // private_email is required for a new asp/teacher employee (EMS's own override,
            // see views/community/employee/form.xml - needed for the Google account recovery
            // address), but lives on the "Private Information" tab, not the default one.
            trigger: ".o_notebook .nav-link:contains('Private Information')",
            content: "Open the Private Information tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='private_email'] input",
            content: "Fill in the private email",
            run: "edit asp.tour.employee@example.com",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_button_save:not(:visible)", content: "Save completed" },
    ],
});

registry.category("web_tour.tours").add("ems_asp_role_crud", {
    test: true,
    url: "/odoo/action-ems.action_asp_role_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "ASP roles list loaded" },
        { trigger: ".o_list_button_add", content: "Create a new ASP role", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in the name",
            run: "edit ASP Tour Role",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_button_save:not(:visible)", content: "Save completed" },
    ],
});
