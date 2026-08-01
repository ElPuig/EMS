/** @odoo-module **/

import { registry } from "@web/core/registry";

// Renders the shared 'ems_archived_reason_ribbon' field widget (also used on res.partner,
// see withdrawal_tour.js) on hr.employee's form AND kanban card - both were plain, non-reason-
// aware ribbons before this. The employee is seeded already archived with a departure reason
// set (see TestEmployeeArchivedReasonTour), so this tour only proves the VIEW renders the
// widget correctly in both places, not the archiving flow itself (covered by backend tests in
// test_departure_reason.py / test_employee_display_fields.py).
registry.category("web_tour.tours").add("ems_employee_archived_reason_indicator", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Teachers loaded",
        },
        // The Teachers action has no active_test:False in its context (unlike Students'), so
        // an archived teacher is hidden by default - reveal it via the native "Archived" filter
        // (hr.view_employee_filter's own "inactive" filter, inherited by
        // views/community/employee/search.xml).
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search dropdown",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .o_menu_item:contains('Archived')",
            content: "Enable the 'Archived' filter",
            run: "click",
        },
        {
            trigger:
                ".o_kanban_view .o_kanban_record:contains('Tour Retired Teacher') .ribbon span:contains('Retired')",
            content: "The 'Retired' ribbon shows on the archived teacher's kanban card",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_data_row .o_data_cell:contains('Tour Retired Teacher')",
            content: "Open the retired teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .ribbon span:contains('Retired')",
            content: "The same ribbon shows on the form",
        },
    ],
});
