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
        {
            trigger: ".ems-av-strike-btn.ems-av-strike-btn--has-strikes:contains('1')",
            content: "Strike button now shows a count of 1 and is highlighted",
        },
        {
            trigger: ".ems-av-strike-btn",
            content: "Click the strike button again for a second strike",
            run: "click",
        },
        {
            trigger: ".ems-av-strike-kicked-out-checkbox",
            content: "Mark this second strike as a class kick-out",
            run: "click",
        },
        {
            trigger: ".ems-av-strike-notes-textarea",
            content: "Add distinguishing notes so this strike can be found later in the list",
            run: "edit Kicked out of class for disruption",
        },
        {
            trigger: ".ems-av-strike-send-btn",
            content: "Send the second strike",
            run: "click",
        },
        {
            trigger: ".ems-av-strike-btn.ems-av-strike-btn--has-strikes:contains('2')",
            content: "Strike button now shows a count of 2",
        },
    ],
});

// Second leg of the flow: confirm the strike created above shows up in the
// Convivencia list (verified in the list view, not by re-reading the dialog's
// local state, per this repo's tour-testing conventions), and that the
// "Kicked out of class" flag set in the dialog is visible on the record's own
// Coexistence form.
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
        {
            trigger: ".o_list_view .o_data_row td[name='notes']:contains('Kicked out of class for disruption')",
            content: "Open the kicked-out strike's own form",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='kicked_out'] input:checked",
            content: "The 'Kicked out of class' checkbox is shown, checked, on the Coexistence strike form",
        },
    ],
});

// Third leg: the two strikes issued above must also be visible from the session's own
// entry in Attendance > History — this used to show nothing at all for the student row.
registry.category("web_tour.tours").add("ems_strike_session_history", {
    test: true,
    url: "/odoo/action-ems.action_attendance_session_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Attendance session history list loaded",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='group_ids']:contains('Strike Tour Group')",
            content: "Open the seeded session",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='attendance_session_line_ids'] .o_data_row td[name='student_id']:contains('Strike Tour Student')",
            content: "Student row loaded in the session's Statuses list",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='attendance_session_line_ids'] .o_data_row td[name='strike_count']:contains('2')",
            content: "The two strikes issued during this session are now visible in the Statuses list",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='attendance_session_line_ids'] .o_data_row button[name='action_view_strikes']",
            content: "Click through to the full strike details for this student",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Strike Tour Student')",
            content: "The strike-details list opened by the button shows the strikes for this student",
        },
    ],
});
