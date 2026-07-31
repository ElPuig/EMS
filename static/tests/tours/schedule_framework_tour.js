/** @odoo-module **/

import { registry } from "@web/core/registry";

// resource.calendar's "Schedule Frameworks" screen (Community > Configuration > Schedules):
// the EMS-added is_framework/level_id fields (views/community/working_schedules/form.xml)
// had zero browser coverage - "Working Schedules" (the sibling, is_framework=False, action)
// already gets exercised indirectly via working_schedules_import_wizard_tour.js's cog menu,
// but never the record's own form. This tour opens a seeded framework and edits level_id.
registry.category("web_tour.tours").add("ems_schedule_framework_edit", {
    test: true,
    url: "/odoo/action-ems.action_schedule_frameworks_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Schedule frameworks list loaded",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Schedule Framework')",
            content: "Open the seeded framework",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='level_id'] input",
            content: "The EMS-added level_id field renders - pick a level",
            run: "edit Test Level (Schedule Framework Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Level (Schedule Framework Tour)')",
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
    ],
});
