/** @odoo-module **/

import { registry } from "@web/core/registry";

// A teacher reserves a free space (issue #475): the action's three views open (calendar, list,
// form) and the form only offers the spaces that are free for the span typed, never the one a
// reservation already holds.
registry.category("web_tour.tours").add("ems_space_reservation", {
    test: true,
    url: "/odoo/action-ems.action_space_reservation",
    steps: () => [
        {
            trigger: ".o_calendar_view",
            content: "The reservations open in the calendar",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Busy Space')",
            content: "The existing reservation is listed",
        },
        {
            trigger: ".o_list_button_add",
            content: "Reserve a space",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='space_id'] input",
            content: "Look for a space",
            run: "edit Tour",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Free Space')",
            content: "The free space is offered",
            run() {
                if ([...document.querySelectorAll(".o-autocomplete--dropdown-item")]
                        .some((item) => item.textContent.includes("Tour Busy Space"))) {
                    throw new Error("A space that is already reserved must not be offered");
                }
                document.querySelector(".o-autocomplete--dropdown-item:not(.o_m2o_dropdown_option)").click();
            },
        },
        {
            trigger: ".o_form_view .o_field_widget[name='reason'] input",
            content: "Say why",
            run: "edit Tour reason",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the reservation",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Reservation saved",
        },
        {
            trigger: ".o_back_button",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour reason')",
            content: "The new reservation is listed",
        },
    ],
});
