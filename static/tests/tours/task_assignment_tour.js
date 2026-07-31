/** @odoo-module **/

import { registry } from "@web/core/registry";

// mail.activity.type's "Task Assignment" screen (Academic Management > Configuration): an
// editable="bottom" list letting admins assign who gets EMS's auto-created activities, had
// zero browser coverage. Edits the many2many_tags cell of a real seeded row (data/main/
// mail.activity.type.csv) inline.
registry.category("web_tour.tours").add("ems_task_assignment_edit", {
    test: true,
    url: "/odoo/action-ems.action_task_assignment",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td:contains('Review enrollment comment')",
            content: "Task assignment list loaded with the seeded activity type",
        },
        {
            trigger:
                ".o_data_row:has(td:contains('Review enrollment comment')) .o_field_widget[name='ems_assignee_ids']",
            content: "Click into the assignees cell to edit it",
            run: "click",
        },
        {
            trigger:
                ".o_selected_row .o_field_widget[name='ems_assignee_ids'] input",
            content: "Search for the admin user",
            run: "edit Administrator",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Administrator')",
            content: "Select it from the dropdown",
            run: "click",
        },
        {
            trigger: ".o_list_button_save",
            content: "Save the inline edit",
            run: "click",
        },
        {
            trigger:
                ".o_data_row:has(td:contains('Review enrollment comment')) .o_field_widget[name='ems_assignee_ids'] .o_tag:contains('Administrator')",
            content: "The assignee was saved",
        },
    ],
});
