/** @odoo-module **/

import { registry } from "@web/core/registry";

// Fills the gaps left by attendance_passlist_tour.js/attendance_status_tour.js (which
// already cover: starting a session from a planned slot, marking a status, adding notes) and
// strike_tour.js (strike issuing + History's strike_count column). Never driven in a real
// browser before this pass: same-day continuation (double period) auto-copy + its banner,
// sorting the roll-call table, and deleting a session. Fixtures are seeded in Python (see
// tests/test_attendance_session_tour.py) - same reasoning as the other passlist tours for why
// a full curriculum isn't built via the UI here.
//
// Status buttons only expose their *translated* name via the title attribute (no stable
// data-status-id in the DOM) - same gotcha attendance_passlist_tour.js already documents.
// Clicking by column position (nth-child) instead of by label text keeps this tour correct
// regardless of the logged-in session's UI language. Column 3 is "Delayed" (by `sequence`,
// right after "Attended" in column 2) - deliberately not column 2, since that's the default
// every freshly auto-populated line already has, so clicking it wouldn't prove a real change.
registry.category("web_tour.tours").add("ems_attendance_session_continuation", {
    test: true,
    url: "/odoo/action-ems.action_attendance_passlist",
    steps: () => [
        { trigger: ".ems-av-root", content: "Roll-call view loaded" },
        {
            trigger: ".ems-av-mode-wrap select",
            content: "Switch to Manual mode so the seeded slots aren't hidden by the current-slot filter",
            run: "select manual",
        },
        {
            trigger: ".ems-av-session-wrap select",
            content: "Select the first period's planned slot (08:00 - 09:00)",
            run: function () {
                const select = document.querySelector(".ems-av-session-wrap select");
                const option = [...select.options].find(
                    (o) => o.textContent.includes("Attendance Session Guard Tour") && o.textContent.includes("08:00 - 09:00")
                );
                select.value = option.value;
                select.dispatchEvent(new Event("change"));
            },
        },
        {
            trigger: ".ems-av-planned-card",
            content: "The 'not started yet' card renders for the first period",
        },
        {
            trigger: ".ems-av-start-btn",
            content: "Start the first period's session",
            run: "click",
        },
        {
            trigger: ".ems-av-name:contains('Zoe Aguilar')",
            content: "Both seeded students are loaded",
        },
        {
            trigger: ".ems-av-line:has(.ems-av-name:contains('Zoe Aguilar')) .ems-av-td-status:nth-child(3) .ems-av-status-btn",
            content: "Mark Zoe Aguilar's 2nd status option (Delayed)",
            run: "click",
        },
        {
            trigger: ".ems-av-line:has(.ems-av-name:contains('Zoe Aguilar')) .ems-av-td-status:nth-child(3) .ems-av-status-btn--active",
            content: "Delayed is now the active status for Zoe Aguilar",
        },
        {
            trigger: ".ems-av-sort-wrap select",
            content: "Sort by first name ascending",
            run: "select name:asc",
        },
        {
            trigger: ".ems-av-table tbody tr:first-child .ems-av-name:contains('Ana Bosch')",
            content: "Ana Bosch (first name comes before Zoe alphabetically) now sorts first",
        },
        {
            trigger: ".ems-av-sort-wrap select",
            content: "Sort by last name ascending",
            run: "select lastname:asc",
        },
        {
            trigger: ".ems-av-table tbody tr:first-child .ems-av-name:contains('Zoe Aguilar')",
            content: "Zoe Aguilar (last name Aguilar comes before Bosch) now sorts first - proves the sort actually re-ran",
        },
        {
            trigger: ".ems-av-session-wrap select",
            content: "Select the second, back-to-back period's planned slot (09:00 - 10:00)",
            run: function () {
                const select = document.querySelector(".ems-av-session-wrap select");
                const option = [...select.options].find(
                    (o) => o.textContent.includes("Attendance Session Guard Tour") && o.textContent.includes("09:00 - 10:00")
                );
                select.value = option.value;
                select.dispatchEvent(new Event("change"));
            },
        },
        {
            trigger: ".ems-av-start-btn",
            content: "Start the second period's session",
            run: "click",
        },
        {
            trigger: ".ems-av-continuation-banner",
            content: "The continuation banner is shown, since this is the same subject's next period today",
        },
        {
            trigger: ".ems-av-line:has(.ems-av-name:contains('Zoe Aguilar')) .ems-av-td-status:nth-child(2) .ems-av-status-btn--active",
            content: "Zoe Aguilar's Delayed status from period 1 was carried forward as Attended (1st status column, active again)",
        },
        {
            trigger: ".ems-av-continuation-close",
            content: "Dismiss the continuation banner",
            run: "click",
        },
        {
            trigger: ".ems-av-delete-btn",
            content: "Delete this (second period) session",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm the deletion",
            run: "click",
        },
        {
            trigger: ".ems-av-root",
            content: "Back on the roll-call view - auto-selection falls back to the first period's still-existing session",
        },
        {
            trigger: ".ems-av-session-wrap select",
            content: "Re-select the second period to confirm it's back to being an un-started planned slot",
            run: function () {
                const select = document.querySelector(".ems-av-session-wrap select");
                const option = [...select.options].find(
                    (o) => o.textContent.includes("Attendance Session Guard Tour") && o.textContent.includes("09:00 - 10:00")
                );
                select.value = option.value;
                select.dispatchEvent(new Event("change"));
            },
        },
        {
            trigger: ".ems-av-planned-hint",
            content: "The second period is back to being an un-started planned slot",
        },
    ],
});

// Guard mode: cover another teacher's not-yet-started slot (the colleague never logs in -
// only their hr.employee/schedule need to exist), mark its student through
// write_guard_session_line (a different RPC than the plain orm.write a normal session uses),
// and confirm the Delete session button - only meaningful for the slot's own teacher - isn't
// offered here.
registry.category("web_tour.tours").add("ems_attendance_session_guard", {
    test: true,
    url: "/odoo/action-ems.action_attendance_passlist",
    steps: () => [
        { trigger: ".ems-av-root", content: "Roll-call view loaded" },
        {
            trigger: ".ems-av-mode-wrap select",
            content: "Switch to Guard mode",
            run: "select guard",
        },
        {
            trigger: ".ems-av-session-wrap select",
            content: "Select the other teacher's not-yet-started slot",
            run: function () {
                const select = document.querySelector(".ems-av-session-wrap select");
                const option = [...select.options].find((o) => o.textContent.includes("Attendance Session Guard Tour"));
                select.value = option.value;
                select.dispatchEvent(new Event("change"));
            },
        },
        {
            trigger: ".ems-av-start-btn",
            content: "Start the guard-covered session",
            run: "click",
        },
        {
            trigger: ".ems-av-name:contains('Zoe Aguilar')",
            content: "The other teacher's student is loaded",
        },
        {
            trigger: ".ems-av-line:has(.ems-av-name:contains('Zoe Aguilar')) .ems-av-td-status:nth-child(3) .ems-av-status-btn",
            content: "Mark the student's 2nd status option (Delayed) while covering (goes through write_guard_session_line)",
            run: "click",
        },
        {
            trigger: ".ems-av-line:has(.ems-av-name:contains('Zoe Aguilar')) .ems-av-td-status:nth-child(3) .ems-av-status-btn--active",
            content: "Delayed is now the active status, confirming the guard write actually persisted",
        },
        {
            trigger: ".ems-av-table",
            content: "No delete button is offered while covering someone else's session",
            run: function () {
                if (document.querySelector(".ems-av-delete-btn")) {
                    throw new Error("Delete session button should not be present in Guard mode");
                }
            },
        },
    ],
});
