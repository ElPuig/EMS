/** @odoo-module **/

import { registry } from "@web/core/registry";

// The teacher issues a strike from the roll-call view (button left of the notes
// pencil), accepting the default reason with no typing, then it's verified in the
// Convivencia list. Session/line data is seeded in Python before the tour starts
// (see tests/test_strike_tour.py) — building a real scheduled session from scratch
// via the UI would need a whole curriculum setup, out of scope for this smoke tour.
registry.category("web_tour.tours").add("ems_strike_issue", {
    test: true,
    url: "/odoo/action-ems.action_attendance_passlist",
    steps: () => [
        {
            trigger: ".ems-av-root",
            content: "Roll-call view loaded",
        },
        {
            trigger: ".ems-av-mode-wrap select",
            content: "Switch to Manual mode so the seeded session isn't hidden by the current-slot filter",
            run: "select manual",
        },
        {
            trigger: ".ems-av-session-wrap select",
            content: "Select the seeded session",
            run: function () {
                const select = document.querySelector(".ems-av-session-wrap select");
                const option = [...select.options].find((o) => o.textContent.includes("Strike Tour"));
                select.value = option.value;
                select.dispatchEvent(new Event("change"));
            },
        },
        {
            trigger: ".ems-av-td-student .ems-av-name:contains('Strike Tour Student')",
            content: "Student row loaded",
        },
        {
            trigger: ".ems-av-strike-btn",
            content: "Click the strike button",
            run: "click",
        },
        {
            trigger: ".ems-av-strike-dialog[open]",
            content: "Strike dialog opens",
        },
        {
            trigger: ".ems-av-strike-reason-select",
            content: "Default reason is preselected",
        },
        {
            trigger: ".ems-av-strike-send-btn",
            content: "Send the strike with no extra notes",
            run: "click",
        },
    ],
});

// Second leg of the flow: confirm the strike created above shows up in the
// Convivencia list (verified in the list view, not by re-reading the dialog's
// local state, per this repo's tour-testing conventions).
registry.category("web_tour.tours").add("ems_strike_consult", {
    test: true,
    url: "/odoo/action-ems.action_strike_list",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Convivencia strikes list loaded",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Strike Tour Student')",
            content: "The issued strike is listed for the student",
        },
    ],
});
