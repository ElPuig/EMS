/** @odoo-module **/

import { registry } from "@web/core/registry";

// A teacher reserves a free space (issue #475): the reservation list's New button opens the
// wizard, which lists by itself the spaces that are free for the day, start and end typed (never
// the one a reservation already holds); Reserve books the chosen one.
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
            trigger: ".modal .o_field_widget[name='free_space_ids'] .o_data_row td:contains('Tour Free Space')",
            content: "The free space is offered without searching",
            run() {
                if ([...document.querySelectorAll(".modal .o_field_widget[name='free_space_ids'] .o_data_row")]
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
            trigger: ".modal .o_field_widget[name='free_space_ids'] .o_data_row:contains('Tour Free Space') input.o_ems_radio_row",
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
            content: "Choose the space: its week appears by itself",
            run: "edit 000 Tour Busy",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Busy Space')",
            content: "Pick it",
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

// The free spaces follow what is typed: a space held at 10:00 appears once the hours move past its
// reservation (09:30-12:30), the choice stays while its space is still free, and goes when the hours
// stop making sense (the end before the start).
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
            trigger: ".modal .o_field_widget[name='free_space_ids'] .o_data_row:contains('Tour Spare Space') td[name='display_name']",
            content: "Choose a space by clicking its row",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='free_space_ids'] .o_data_row.table-active:contains('Tour Spare Space') input.o_ems_radio_row:checked",
            content: "The row is highlighted and its radio button checked",
        },
        {
            trigger: ".modal-footer button[name='action_reserve']:not(.disabled)",
            content: "Reserve is available",
        },
        {
            trigger: ".modal .o_field_widget[name='end_time'] input",
            content: "Change the end",
            run: "edit 14:00 && press Tab",
        },
        {
            trigger: ".modal .o_field_widget[name='start_time'] input",
            content: "Change the start, past the reservation of the busy space",
            run: "edit 13:00 && press Tab",
        },
        {
            trigger: ".modal .o_field_widget[name='free_space_ids'] .o_data_row td:contains('Tour Busy Space')",
            content: "The list follows by itself: the busy space is free from 13:00",
        },
        {
            trigger: ".modal .o_field_widget[name='free_space_ids'] .o_data_row.table-active:contains('Tour Spare Space') input.o_ems_radio_row:checked",
            content: "The chosen space is still free, so it stays chosen",
        },
        {
            trigger: ".modal .o_field_widget[name='end_time'] input",
            content: "An end before the start",
            run: "edit 12:00 && press Tab",
        },
        {
            trigger: ".modal .alert-warning",
            content: "The wizard says the end must be after the start",
            run() {
                if (document.querySelector(".modal .o_field_widget[name='free_space_ids'] .o_data_row")) {
                    throw new Error("No space can be offered for an end before the start");
                }
            },
        },
        {
            trigger: ".modal .o_field_widget[name='end_time'] input",
            content: "A valid end again",
            run: "edit 14:00 && press Tab",
        },
        {
            trigger: ".modal .o_field_widget[name='free_space_ids'] .o_data_row input.o_ems_radio_row",
            content: "The results are back with nothing chosen",
            run() {
                if (document.querySelector(".modal input.o_ems_radio_row:checked")) {
                    throw new Error("The choice must be dropped when its space stopped being offered");
                }
            },
        },
        {
            trigger: ".modal-footer button.disabled[name='action_reserve']",
            content: "Reserve is disabled again",
        },
        {
            trigger: ".modal-header .btn-close",
            content: "Close the wizard without reserving",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The wizard is closed",
        },
    ],
});

// The current time is a dotted red line in today's column; what is above it is the past and cannot be chosen.
registry.category("web_tour.tours").add("ems_space_reservation_now_line", {
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
            run: "edit 000 Tour Free",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Free Space')",
            content: "Pick it",
            run: "click",
        },
        {
            trigger: ".modal .o_ems_week_grid_column .o_ems_week_grid_now",
            content: "The current time is marked in today's column",
        },
        {
            trigger: ".modal .o_ems_week_grid_column .o_ems_week_grid_elapsed",
            content: "What is above it is shaded",
            run() {
                const column = document.querySelector(".modal .o_ems_week_grid_column:has(.o_ems_week_grid_now)");
                const rect = column.getBoundingClientRect();
                const at = (y) => ({ bubbles: true, button: 0, clientX: rect.left + 10, clientY: rect.top + y });
                // 9:00 is before the current time (12:00): clicking there chooses nothing.
                column.dispatchEvent(new MouseEvent("mousedown", at(40)));
                document.dispatchEvent(new MouseEvent("mouseup", at(40)));
            },
        },
        {
            trigger: ".modal .o_ems_week_grid_column .o_ems_week_grid_now",
            content: "Nothing was chosen in the past",
            async run() {
                await new Promise((resolve) => setTimeout(resolve, 300));
                if (document.querySelector(".modal .o_ems_week_grid_chosen")) {
                    throw new Error("A time that has gone by must not be chosen");
                }
                const column = document.querySelector(".modal .o_ems_week_grid_column:has(.o_ems_week_grid_now)");
                const rect = column.getBoundingClientRect();
                const at = (y) => ({ bubbles: true, button: 0, clientX: rect.left + 10, clientY: rect.top + y });
                // 14:00 is after it: that is free.
                column.dispatchEvent(new MouseEvent("mousedown", at(40 * 6)));
                document.dispatchEvent(new MouseEvent("mouseup", at(40 * 6)));
            },
        },
        {
            trigger: ".modal .o_ems_week_grid_chosen",
            content: "A time after the current one can be chosen",
        },
        {
            trigger: ".modal .o_field_widget[name='space_start'] input",
            content: "Type by hand a start that has gone by (09:00, it is 12:00)",
            run: "edit 09:00 && press Tab",
        },
        {
            trigger: ".modal:not(:has(.o_form_view)) .modal-footer .btn-primary",
            content: "The wizard says a reservation cannot start in the past (a dialog): close it",
            run: "click",
        },
        {
            trigger: ".modal-footer button.disabled[name='action_reserve']",
            content: "The day is cleared: nothing is chosen and Reserve is disabled",
            run() {
                if (document.querySelector(".modal .o_ems_week_grid_chosen")) {
                    throw new Error("A time typed in the past must not stay chosen");
                }
            },
        },
    ],
});
