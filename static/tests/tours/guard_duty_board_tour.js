/** @odoo-module **/

import { registry } from "@web/core/registry";

// Opens the centre-wide guard duty board (Employee Attendances > Guard duty schedule),
// confirms it defaults to today's own weekday tab and the shift matching the current time (not
// always Monday/Morning), then switches over to the Monday/Morning fixture data deliberately to
// exercise weekday tabs and the morning/afternoon shift dropdown, confirms a seeded teaching
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
            // Regression check for a real request (2026-09-01, developer feedback: "cuando entro
            // en la sección... por defecto tendría que estar viendo el que toca") - mirrors
            // getDefaultDayAndShift() in guard_duty_board.js exactly, computed independently here
            // against the browser's own real clock (whatever day/time the test actually runs at),
            // not a fixed expectation - the board must match, not just happen to default to Monday.
            trigger: ".o_guard_board_tabs .nav-link.active",
            content: "The board defaults to today's own weekday tab, not always Monday",
            run: () => {
                const now = new Date();
                const jsDay = now.getDay();
                const expectedIndex = jsDay >= 1 && jsDay <= 5 ? jsDay - 1 : 0;
                const dayLabels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
                const activeLink = document.querySelector(".o_guard_board_tabs .nav-link.active");
                const activeLabel = activeLink && activeLink.textContent.trim();
                if (activeLabel !== dayLabels[expectedIndex]) {
                    throw new Error(`Expected the default active day to be '${dayLabels[expectedIndex]}' (today), got '${activeLabel}'`);
                }
            },
        },
        {
            trigger: ".o_guard_board_shift_select",
            content: "The board defaults to the shift matching the current time (afternoon from 15:00)",
            run: () => {
                const now = new Date();
                const expectedShift = now.getHours() >= 15 ? "afternoon" : "morning";
                const select = document.querySelector(".o_guard_board_shift_select");
                if (select.value !== expectedShift) {
                    throw new Error(`Expected the default shift to be '${expectedShift}' (current hour ${now.getHours()}), got '${select.value}'`);
                }
            },
        },
        {
            // The rest of this tour exercises fixed Monday/Morning fixture data (seeded by
            // TestGuardDutyBoardTour), regardless of which day/shift the smart default above
            // actually landed on today.
            trigger: ".o_guard_board_tabs .nav-link:contains('Monday')",
            content: "Switch to Monday to exercise the seeded fixture data",
            run: "click",
        },
        {
            trigger: ".o_guard_board_shift_select",
            content: "Switch to Morning",
            run: "selectByLabel Morning",
        },
        {
            trigger: ".o_guard_board_tabs .nav-link.active:contains('Monday')",
            content: "Monday/Morning is now active",
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
