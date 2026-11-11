/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #813: the Director chooses a day in the dialog and the figures open as a pivot (one row
// per period, one column per staff type and contract type), whose figures open the names.
registry.category("web_tour.tours").add("ems_staff_strike_report", {
    test: true,
    url: "/odoo/action-ems.action_staff_strike_report",
    steps: () => [
        {
            trigger: ".modal .o_field_widget[name='date'] input",
            content: "The dialog opens on a day",
        },
        {
            trigger: ".modal .modal-footer .btn-primary",
            content: "Show the figures",
            run: "click",
        },
        {
            trigger: ".o_pivot_view .o_pivot td.o_pivot_cell_value",
            content: "The pivot renders the periods and the figures",
        },
        {
            trigger: ".o_pivot_view .o_pivot th.o_pivot_header_cell_closed:contains('08:00-09:00')",
            content: "The first period of the fixture is a row",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to the list of names",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('0000 TSSR Tour Striker')",
            content: "The teacher who never checked in is on the list",
        },
    ],
});
