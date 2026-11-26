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
            trigger: ".modal-footer button.disabled[name='action_reserve']",
            content: "Reserve is not available until a space is chosen",
        },
        {
            trigger: ".modal .o_field_widget[name='line_ids'] .o_data_row:contains('Tour Free Space') input.o_ems_radio_row",
            content: "Choose the free space",
            run: "click",
        },
        {
            trigger: ".modal-footer button[name='action_reserve']:not(.disabled)",
            content: "Reserve the chosen space",
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

// By space: the week of a space as a grid, with what holds it; a click on a free time chooses it.
registry.category("web_tour.tours").add("ems_space_reservation_by_space", {
    test: true,
    url: "/odoo/action-ems.action_space_reservation",
    steps: () => [
        {
            trigger: ".o_list_view .o_list_button_add, .o_list_view button:contains('New')",
            content: "New opens the reservation wizard",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='mode'] .o_radio_item:contains('when it is free') input",
            content: "Search by space",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='space_id'] input",
            content: "Choose the space",
            run: "edit 000 Tour Busy",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Busy Space')",
            content: "Pick it",
            run: "click",
        },
        {
            trigger: ".modal button[name='action_search']:contains('Show the occupation')",
            content: "Show its occupation",
            run: "click",
        },
        {
            trigger: ".modal .o_ems_week_grid .o_ems_week_grid_reservation",
            content: "The reservation that holds the space is drawn on the grid",
        },
        {
            trigger: ".modal-footer button.disabled[name='action_reserve']",
            content: "Reserve is not available until a time is chosen",
        },
        {
            trigger: ".modal .o_ems_week_next",
            content: "Next week (every day of it is free)",
            run: "click",
        },
        {
            trigger: ".modal .o_ems_week_grid_column:not(.o_ems_week_grid_past)[data-date]",
            content: "Click a free time",
            run: "click",
        },
        {
            trigger: ".modal .o_ems_week_grid_chosen",
            content: "The chosen time is drawn on the grid",
        },
        {
            trigger: ".modal .o_ems_week_grid_column:not(.o_ems_week_grid_past)[data-date]",
            content: "Drag over a free time of two hours",
            run() {
                const column = document.querySelector(".modal .o_ems_week_grid_column:not(.o_ems_week_grid_past)[data-date]");
                const rect = column.getBoundingClientRect();
                const at = (y) => ({ bubbles: true, button: 0, clientX: rect.left + 10, clientY: rect.top + y });
                column.dispatchEvent(new MouseEvent("mousedown", at(40 * 6)));
                document.dispatchEvent(new MouseEvent("mousemove", at(40 * 8)));
                document.dispatchEvent(new MouseEvent("mouseup", at(40 * 8)));
            },
        },
        {
            trigger: ".modal .o_ems_week_grid_chosen[style*='height: 80px']",
            content: "The dragged two hours are chosen",
        },
        {
            trigger: ".modal-footer button[name='action_reserve']:not(.disabled)",
            content: "Reserve the chosen time",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "The reservation is saved and opened",
        },
    ],
});

// Choosing a result and then changing the hour and searching again drops the choice (no error).
registry.category("web_tour.tours").add("ems_space_reservation_search_again", {
    test: true,
    url: "/odoo/action-ems.action_space_reservation",
    steps: () => [
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
            trigger: ".modal .o_field_widget[name='line_ids'] .o_data_row td[name='space_id']",
            content: "Choose a space by clicking its row",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='line_ids'] .o_data_row.table-active input.o_ems_radio_row",
            content: "The row is highlighted and its radio button checked",
            run() {
                if (!document.querySelector(".modal input.o_ems_radio_row:checked")) {
                    throw new Error("Clicking the row must check its radio button");
                }
            },
        },
        {
            trigger: ".modal-footer button[name='action_reserve']:not(.disabled)",
            content: "Reserve is available",
        },
        {
            trigger: ".modal .o_field_widget[name='start_time'] input",
            content: "Change the hour",
            run: "edit 09:00",
        },
        {
            trigger: ".modal button[name='action_search']",
            content: "Search again",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='line_ids'] .o_data_row input.o_ems_radio_row",
            content: "The results are back with nothing chosen",
            run() {
                if (document.querySelector(".modal input.o_ems_radio_row:checked")) {
                    throw new Error("The choice must be dropped when the search changes");
                }
            },
        },
        {
            trigger: ".modal-footer button.disabled[name='action_reserve']",
            content: "Reserve is disabled again",
        },
    ],
});
