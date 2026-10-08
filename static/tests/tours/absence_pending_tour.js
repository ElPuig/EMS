/** @odoo-module **/

import { registry } from "@web/core/registry";

// Expected absences (issue #509), as the Department Chief who enters them on a teacher of
// their department's behalf (issue #604): the list and the form have to render for that
// role, not only for an officer, and a new entry has to land on the list as pending.
registry.category("web_tour.tours").add("ems_absence_pending", {
    test: true,
    url: "/odoo/action-ems.action_absence_pending",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The list of expected absences loads",
        },
        {
            trigger: ".o_list_button_add",
            content: "Announce a new one",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='date_from'] input",
            content: "The form opens with the dates prefilled",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='employee_id'] input",
            content: "Search for the teacher, who is in this chief's department",
            run: "edit Tour Pending Teacher",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Pending Teacher')",
            content: "Select them",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Saved",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='state'] .o_arrow_button_current[data-value='pending']",
            content: "It stays pending until the teacher requests it",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb .breadcrumb-item a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Pending Teacher') td[name='state'] .badge",
            content: "The new entry is listed as pending",
        },
    ],
});
