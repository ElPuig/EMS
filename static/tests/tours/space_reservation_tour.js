/** @odoo-module **/

import { registry } from "@web/core/registry";

// A teacher reserves a free space (issue #475): the reservation list's New button opens the
// wizard, which lists the spaces that are free for the day, start and duration typed (never the
// one a reservation already holds); Reserve on a row books it.
registry.category("web_tour.tours").add("ems_space_reservation", {
    test: true,
    url: "/odoo/action-ems.action_space_reservation",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Busy Space')",
            content: "The existing reservation is listed",
        },
        {
            trigger: ".o_list_view .o_list_button_add, .o_list_view button:contains('New')",
            content: "New opens the reservation wizard",
            run: "click",
        },
        {
            trigger: ".modal button[name='action_search']",
            content: "Search the free spaces",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='line_ids'] .o_data_row td:contains('Tour Free Space')",
            content: "The free space is offered",
            run() {
                if ([...document.querySelectorAll(".modal .o_field_widget[name='line_ids'] .o_data_row")]
                        .some((row) => row.textContent.includes("Tour Busy Space"))) {
                    throw new Error("A space that is already reserved must not be offered");
                }
            },
        },
        {
            trigger: ".modal .o_field_widget[name='reason'] input",
            content: "Say why",
            run: "edit Tour reason",
        },
        {
            trigger: ".modal .o_field_widget[name='line_ids'] .o_data_row:contains('Tour Free Space') button[name='action_reserve']",
            content: "Reserve the free space",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved .o_field_widget[name='reason']:contains('Tour reason'), .o_form_view .o_form_saved .o_field_widget[name='reason'] input",
            content: "The reservation is saved and opened",
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
