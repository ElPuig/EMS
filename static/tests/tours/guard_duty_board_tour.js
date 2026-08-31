/** @odoo-module **/

import { registry } from "@web/core/registry";

// Opens the centre-wide guard duty board (Employee Attendances > Guard duty schedule),
// switches weekday tabs and the morning/afternoon shift dropdown, confirms a seeded teaching
// slot (group/teacher/room) and a seeded guard-duty slot both render on Monday morning, and a
// DIFFERENT teacher shows up once the shift dropdown is switched to afternoon (proving the
// dropdown actually re-fetches, not just keeps showing whatever was already loaded), then
// exercises the per-day "Download PDF" button. Seed data comes from
// TestGuardDutyBoardTour.test_guard_duty_board_tour (tests/test_guard_duty_board_tour.py).
registry.category("web_tour.tours").add("ems_guard_duty_board", {
    test: true,
    url: "/odoo/action-ems.action_guard_duty_board",
    steps: () => [
        {
            trigger: ".o_guard_board_title",
            content: "Guard duty board loaded",
        },
        {
            trigger: ".o_guard_board_tabs .nav-link:contains('Monday')",
            content: "Monday tab is the default",
        },
        {
            trigger: ".o_guard_board_shift_select",
            content: "Morning is the default shift",
            run: () => {
                const select = document.querySelector(".o_guard_board_shift_select");
                if (select.value !== "morning") {
                    throw new Error(`Expected the default shift to be 'morning', got '${select.value}'`);
                }
            },
        },
        {
            trigger: ".o_guard_board_table td:contains('Tour Guard Board Teacher')",
            content: "The seeded teacher shows up in their group's column, Monday morning",
        },
        {
            trigger: ".o_guard_board_table td:contains('Tour Guard Board Space')",
            content: "The seeded room shows up in the same cell",
        },
        {
            trigger: ".o_guard_board_guard_badge:contains('Tour Guard Board Guard')",
            content: "The seeded guard-duty teacher shows up in the Guard duty column, not a group cell",
        },
        {
            trigger: ".o_guard_board_table:not(:has(td:contains('Tour Guard Board Afternoon Teacher')))",
            content: "The afternoon-only teacher is NOT shown while morning is selected",
        },
        {
            trigger: ".o_guard_board_shift_select",
            content: "Switch the shift dropdown to Afternoon",
            run: "selectByLabel Afternoon",
        },
        {
            trigger: ".o_guard_board_table td:contains('Tour Guard Board Afternoon Teacher')",
            content: "Switching to Afternoon re-fetches and shows the afternoon-only teacher",
        },
        {
            trigger: ".o_guard_board_table:not(:has(td:contains('Tour Guard Board Teacher')))",
            content: "The morning teaching cell is gone now that Afternoon is selected",
        },
        {
            trigger: ".o_guard_board_shift_select",
            content: "Switch back to Morning",
            run: "selectByLabel Morning",
        },
        {
            trigger: ".o_guard_board_table td:contains('Tour Guard Board Teacher')",
            content: "Back on Morning, the seeded teaching slot renders again",
        },
        {
            // Regression check for a real bug (2026-08-31): an earlier table-layout:auto + min/
            // max-width CSS approach left the scroll container's measured scrollWidth short of
            // the table's true rendered width, so dragging the scrollbar all the way right never
            // actually revealed the last column. table-layout:fixed + an explicit <colgroup> (see
            // guard_duty_board.css) fixed it - confirmed here by scrolling to the reported max and
            // checking the last header cell is then fully inside the wrapper's visible bounds.
            trigger: ".o_guard_board_table_wrap",
            content: "Scrolling the board all the way right reveals the last (Guard duty) column",
            run: () => {
                const wrap = document.querySelector(".o_guard_board_table_wrap");
                wrap.scrollLeft = wrap.scrollWidth;
                const lastHeader = wrap.querySelector("thead th:last-child").getBoundingClientRect();
                const wrapBounds = wrap.getBoundingClientRect();
                if (lastHeader.right > wrapBounds.right + 1) {
                    throw new Error(`Guard duty column not fully visible after scrolling to the end: header right=${lastHeader.right}, wrap right=${wrapBounds.right}`);
                }
            },
        },
        {
            // Regression check for a real bug (2026-08-31): the page's root had no explicit
            // height, so a table taller than the viewport simply got clipped by Odoo's own
            // action container with no scrollbar at all (neither axis). Giving .o_guard_board
            // height:100%/flex-column, with only .o_guard_board_content scrolling vertically
            // (see guard_duty_board.css), fixed it - confirmed here the same way as the
            // horizontal check above.
            trigger: ".o_guard_board_content",
            content: "Scrolling the page down reaches the bottom of a tall table",
            run: () => {
                const content = document.querySelector(".o_guard_board_content");
                content.scrollTop = content.scrollHeight;
                const maxPossible = content.scrollHeight - content.clientHeight;
                if (maxPossible > 0 && Math.abs(content.scrollTop - maxPossible) > 1) {
                    throw new Error(`Vertical scroll did not reach the end: scrollTop=${content.scrollTop}, max=${maxPossible}`);
                }
            },
        },
        {
            trigger: ".o_guard_board_tabs .nav-link:contains('Tuesday')",
            content: "Switch to the Tuesday tab",
            run: "click",
        },
        {
            trigger: ".o_guard_board_tabs .nav-link.active:contains('Tuesday')",
            content: "Tuesday tab is now active",
        },
        {
            trigger: ".o_guard_board_tabs .nav-link:contains('Monday')",
            content: "Switch back to Monday",
            run: "click",
        },
        {
            trigger: ".o_guard_board_table td:contains('Tour Guard Board Teacher')",
            content: "Back on Monday, the seeded teaching slot renders again",
        },
        {
            trigger: ".o_guard_board_toolbar button:contains('PDF')",
            content: "Download this day's PDF",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_error_dialog))",
            content: "No client-side error after printing",
        },
    ],
});
