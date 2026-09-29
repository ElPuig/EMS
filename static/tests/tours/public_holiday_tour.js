/** @odoo-module **/

import { registry } from "@web/core/registry";

// Absences > Configuration > Public Holidays: the "Working Hours" column is hidden (a public
// holiday always applies to every schedule, see models/employees/public_holiday.py) and a
// holiday can still be added from the editable list.
registry.category("web_tour.tours").add("ems_public_holiday", {
    url: "/odoo/action-hr_holidays.open_view_public_holiday",
    steps: () => [
        {
            trigger: ".o_list_view .o_list_table:not(:has(th[data-name='calendar_id']))",
            content: "Public holidays list loaded, without the Working Hours column",
        },
        {
            trigger: ".o_list_button_add",
            content: "Add a public holiday",
            run: "click",
        },
        {
            trigger: ".o_selected_row .o_field_widget[name='name'] input",
            content: "Name it",
            run: "edit Tour Public Holiday",
        },
        {
            trigger: ".o_list_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_data_row:not(.o_selected_row) td:contains('Tour Public Holiday')",
            content: "The holiday is saved",
        },
    ],
});
