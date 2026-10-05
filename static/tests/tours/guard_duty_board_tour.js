/** @odoo-module **/

import { registry } from "@web/core/registry";

const { DateTime } = luxon;

// Opens the centre-wide guard duty board (Employee Attendances > Guard duty schedule),
// confirms it defaults to today's own weekday tab and the shift matching the current time (not
// always Monday/Morning), then switches over to the Monday/Morning fixture data deliberately to
// exercise weekday tabs and the morning/afternoon shift dropdown, confirms a seeded teaching
// slot (group/teacher/room) and a seeded guard-duty slot both render on Monday morning, and a
// DIFFERENT teacher shows up once the shift dropdown is switched to afternoon (proving the
// dropdown actually re-fetches, not just keeps showing whatever was already loaded), exercises
// the level filter (issue #390), the absence information on both the timetable and "Guard duty
// table" tabs (with the week navigation clearing it once the absence's own week is left), then
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
            // against the real clock in the company's timezone (luxon's default zone, see
            // company_timezone_service.js), as the board itself does - never the browser's own
            // timezone, which is UTC on CI - not a fixed expectation: the board must match, not
            // just happen to default to Monday.
            trigger: ".o_guard_board_tabs .nav-link.active",
            content: "The board defaults to today's own weekday tab, not always Monday",
            run: () => {
                const now = DateTime.now();
                const expectedIndex = now.weekday <= 5 ? now.weekday - 1 : 0;
                const dayLabels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
                const activeLink = document.querySelector(".o_guard_board_tabs .nav-link.active");
                // The tab holds two spans now - the weekday name and the day of the month it
                // stands for in the shown week - so read the name, not the whole textContent.
                const activeLabel = activeLink && activeLink.querySelector("span").textContent.trim();
                if (activeLabel !== dayLabels[expectedIndex]) {
                    throw new Error(`Expected the default active day to be '${dayLabels[expectedIndex]}' (today), got '${activeLabel}'`);
                }
            },
        },
        {
            trigger: ".o_guard_board_shift_select",
            content: "The board defaults to the shift matching the current time (afternoon from 15:00)",
            run: () => {
                const now = DateTime.now();
                const expectedShift = now.hour >= 15 ? "afternoon" : "morning";
                const select = document.querySelector(".o_guard_board_shift_select");
                if (select.value !== expectedShift) {
                    throw new Error(`Expected the default shift to be '${expectedShift}' (current hour ${now.hour}), got '${select.value}'`);
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
            // 'is_wc' (2026-09-11, developer request): a 'Guard (WC)' duty gets a "(WC)" suffix
            // next to the teacher's own name, right in the guard badge - a plain 'Guard' duty
            // must NOT get it, even though both are on duty in the exact same period.
            trigger: ".o_guard_board_guard_badge:contains('Tour Guard Board WC Guard') .o_guard_board_guard_wc_tag",
            content: "The WC guard's own badge carries the '(WC)' tag",
        },
        {
            trigger: ".o_guard_board_guard_badge:contains('Tour Guard Board Guard'):not(:has(.o_guard_board_guard_wc_tag))",
            content: "The plain guard's badge does NOT carry the '(WC)' tag",
        },
        {
            // 'is_break' (2026-09-11, developer request): a guard whose own period is break time
            // for some level, with no real class in it, gets its row visually marked - the
            // "Break" text label (translates to "Patio"/"Pati" in es_ES/ca_ES - this tour's own
            // teacher runs in en_US, see create_role_user()'s own 'lang', so it stays "Break"
            // here) plus the row's own left-border accent, both under "All levels" (no level
            // filter needed any more, see get_guard_duty_board_lines' own docstring).
            trigger: ".o_guard_board_guard_badge:contains('Tour Guard Board Patio Guard')",
            content: "The patio guard shows up in the Guard duty column",
        },
        {
            trigger: ".o_guard_board_table tr.o_guard_board_row_break:has(.o_guard_board_guard_badge:contains('Tour Guard Board Patio Guard'))",
            content: "That guard's own row is marked as a break/'Patio' row",
        },
        {
            trigger: ".o_guard_board_table tr.o_guard_board_row_break .o_guard_board_break_label:contains('Break')",
            content: "The row carries the (translatable) 'Break' text label",
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
            // Level filter (issue #390): a checkbox dropdown, not a native multi-<select> (see
            // guard_duty_board.js's own reasoning) - opening it and checking the seeded level
            // narrows the board down to that level's own group/teacher, and back to "All levels"
            // once unchecked. TestGuardDutyBoardTour seeds a SECOND level (group2/level2_teacher)
            // specifically so this can assert real exclusion, not just that the dropdown opens.
            // 'data-bs-auto-close="outside"' (guard_duty_board.xml) keeps the dropdown open across
            // several checkbox clicks in a row, so it never needs re-opening between them.
            trigger: ".o_guard_board_level_toggle",
            content: "Open the level filter dropdown",
            run: "click",
        },
        {
            trigger: ".o_guard_board_level_item:contains('Tour Guard Board Level 1') input[type='checkbox']",
            content: "Check the seeded level (level 1) to narrow the board down to it",
            run: "click",
        },
        {
            trigger: ".o_guard_board_table td:contains('Tour Guard Board Teacher')",
            content: "Level 1's own teacher still shows once level 1 is checked",
        },
        {
            trigger: ".o_guard_board_table:not(:has(td:contains('Tour Guard Board Level 2 Teacher')))",
            content: "Level 2's teacher is NOT shown while only level 1 is checked",
        },
        {
            trigger: ".o_guard_board_level_item:contains('Tour Guard Board Level 1') input[type='checkbox']",
            content: "Uncheck level 1 to go back to 'All levels'",
            run: "click",
        },
        {
            trigger: ".o_guard_board_table td:contains('Tour Guard Board Level 2 Teacher')",
            content: "Back on 'All levels', level 2's teacher shows again too",
        },
        {
            // The board now stands for a real week, not just a weekday: absences happen on
            // dates. The date input must agree with whichever weekday tab is active.
            trigger: ".o_guard_board_date_input",
            content: "The date input matches the active weekday tab",
            run: () => {
                const value = document.querySelector(".o_guard_board_date_input").value;
                const picked = new Date(value + "T00:00:00");
                if (picked.getDay() !== 1) {
                    throw new Error(`Expected the Monday tab's date to be a Monday, got ${value}`);
                }
            },
        },
        {
            trigger: ".o_guard_board_table .o_guard_board_absent:contains('Tour Guard Board Teacher')",
            content: "The teacher with an approved absence is marked in their own cell",
        },
        {
            trigger: ".o_guard_board_guard_badge:contains('Tour Guard Board Guard'):not(.o_guard_board_absent)",
            content: "The guard on duty, who is not away, is not marked",
        },
        {
            trigger: ".o_guard_board_view_tabs .nav-link:contains('Absences table')",
            content: "Switch to the absences table",
            run: "click",
        },
        {
            trigger: ".o_guard_board_duty_table",
            content: "The table renders",
        },
        {
            // Regression check for a real complaint (developer feedback, 2026-09-08: "queda
            // demasiado disperso en la pantalla"). With only three columns, Bootstrap's own
            // `.table { width: 100% }` spread them across the whole window; the table now sizes
            // to its own fixed <col> widths and is centred instead (see guard_duty_board.css).
            trigger: ".o_guard_board_duty_table",
            content: "The guard duty table keeps its own width and stays centred",
            run: () => {
                const table = document.querySelector(".o_guard_board_duty_table");
                const wrap = table.closest(".o_guard_board_table_wrap");
                const tableBox = table.getBoundingClientRect();
                const wrapBox = wrap.getBoundingClientRect();
                if (tableBox.width >= wrapBox.width) {
                    throw new Error(`The table should be narrower than the page, got table=${tableBox.width} wrap=${wrapBox.width}`);
                }
                // Only meaningful when there is spare room to centre it in; a narrow window
                // legitimately leaves none.
                const left = tableBox.left - wrapBox.left;
                const right = wrapBox.right - tableBox.right;
                if (Math.abs(left - right) > 2) {
                    throw new Error(`The table is not centred: ${left}px on the left, ${right}px on the right`);
                }
                // Each absence stays on one line (developer feedback, 2026-09-08). Measured
                // against its own line-height rather than a hardcoded pixel height, so a theme
                // or font change cannot quietly turn this into a false pass.
                for (const row of document.querySelectorAll(".o_guard_board_absence_row")) {
                    const lineHeight = parseFloat(getComputedStyle(row).lineHeight) || 16;
                    const lines = Math.round((row.getBoundingClientRect().height - 4) / lineHeight);
                    if (lines > 1) {
                        throw new Error(`An absence row wrapped onto ${lines} lines: "${row.textContent.trim()}"`);
                    }
                }
            },
        },
        {
            trigger: ".o_guard_board_absence_cell .o_guard_board_absent:contains('Tour Guard Board Teacher')",
            content: "The absent teacher heads their own row in the Absences column",
        },
        {
            trigger: ".o_guard_board_absence_class:contains('Tour Guard Board Space')",
            content: "The row says which class has to be covered, room included",
        },
        {
            trigger: ".o_guard_board_duty_table .o_guard_board_guard_badge:contains('Tour Guard Board Guard')",
            content: "The same row lists who is on guard duty to cover it",
        },
        {
            // Moving off this week must clear the absence: it belongs to one date, not to every
            // Monday - the surest proof the board is really re-fetching per date.
            trigger: ".o_guard_board_toolbar .o_guard_board_week_nav button:last-child",
            content: "Move to next week",
            run: "click",
        },
        {
            trigger: ".o_guard_board_duty_table:not(:has(.o_guard_board_absent))",
            content: "Next week has no absence, so nobody is marked",
        },
        {
            trigger: ".o_guard_board_week_nav button:first-child",
            content: "Back to the week the absence is in",
            run: "click",
        },
        {
            trigger: ".o_guard_board_absence_cell .o_guard_board_absent:contains('Tour Guard Board Teacher')",
            content: "The absence is back",
        },
        {
            trigger: ".o_guard_board_view_tabs .nav-link:contains('Guard duty schedule')",
            content: "Back to the timetable tab",
            run: "click",
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
