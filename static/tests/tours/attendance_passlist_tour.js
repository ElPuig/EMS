/** @odoo-module **/

import { registry } from "@web/core/registry";

// The single most-used screen in EMS: the daily roll-call ("Current"/pass-list) client
// action teachers open every class period to actually take attendance. Its strike-issuing
// flow already had tour coverage (strike_tour.js), but the core action - marking a student's
// attendance status - and starting a brand-new session from a planned (not-yet-created)
// schedule slot had never been driven in a real browser, despite being the single most
// repeated daily interaction in the whole module. Status buttons only expose their
// *translated* name via the title attribute (no stable data-status-id in the DOM) - clicking
// by column position (td:nth-child(3), the 2nd status column) instead of by label text keeps
// this tour correct regardless of the logged-in session's UI language. Deliberately not the
// 1st status column (nth-child(2)): that one is "Attended", the default a freshly
// auto-populated line already has, so clicking it wouldn't prove a real change happened. The
// Python side verifies against whichever status actually sits at that same sequence position
// (see test_attendance_passlist_tour.py).
registry.category("web_tour.tours").add("ems_attendance_take", {
    test: true,
    url: "/odoo/action-ems.action_attendance_passlist",
    steps: () => [
        {
            trigger: ".ems-av-root",
            content: "Roll-call view loaded",
        },
        {
            trigger: ".ems-av-mode-wrap select",
            content: "Switch to Manual mode so the seeded schedule isn't hidden by the current-slot filter",
            run: "select manual",
        },
        {
            trigger: ".ems-av-session-wrap select",
            content: "Select the seeded planned schedule",
            run: function () {
                const select = document.querySelector(".ems-av-session-wrap select");
                const option = [...select.options].find((o) => o.textContent.includes("Take Tour"));
                select.value = option.value;
                select.dispatchEvent(new Event("change"));
            },
        },
        {
            trigger: ".ems-av-planned-card",
            content: "The 'not started yet' card renders for the planned schedule",
        },
        {
            trigger: ".ems-av-start-btn",
            content: "Start the session",
            run: "click",
        },
        {
            trigger: ".ems-av-td-student .ems-av-name:contains('Attendance Take Tour Student 1')",
            content: "The session was created and auto-populated with the enrolled students",
        },
        {
            trigger:
                ".ems-av-line:has(.ems-av-name:contains('Attendance Take Tour Student 1')) .ems-av-td-status:nth-child(3) .ems-av-status-btn",
            content: "Mark student 1's attendance status (the core daily action)",
            run: "click",
        },
        {
            trigger:
                ".ems-av-line:has(.ems-av-name:contains('Attendance Take Tour Student 1')) .ems-av-td-status:nth-child(3) .ems-av-status-btn--active",
            content: "The status button is now shown active",
        },
        {
            trigger:
                ".ems-av-line:has(.ems-av-name:contains('Attendance Take Tour Student 2')) .ems-av-notes-btn",
            content: "Open the notes dialog for student 2",
            run: "click",
        },
        {
            trigger: ".ems-av-notes-dialog[open]",
            content: "Notes dialog opens",
        },
        {
            trigger: ".ems-av-notes-textarea",
            content: "Type a note",
            run: "edit Tour note for student 2",
        },
        {
            trigger: ".ems-av-notes-save-btn",
            content: "Save the note",
            run: "click",
        },
        {
            trigger:
                ".ems-av-line:has(.ems-av-name:contains('Attendance Take Tour Student 2')) .ems-av-notes-preview:contains('Tour note for student 2')",
            content: "The note is now shown in the row's preview",
        },
    ],
});
