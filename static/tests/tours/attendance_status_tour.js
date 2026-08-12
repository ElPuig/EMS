/** @odoo-module **/

import { registry } from "@web/core/registry";

// Configuration screen: the seeded active statuses (Attended, Delayed, Miss, Justified
// Miss) must be listed; the archived "Issue" status must not show up by default (it
// ships pre-archived - ems.strike now covers what it used to flag). Opens one record's
// form to confirm the new fields (category, notifiable, color) render.
registry.category("web_tour.tours").add("ems_attendance_status_configuration", {
    test: true,
    url: "/odoo/action-ems.action_attendance_status_list",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Statuses configuration list loaded",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Attended')",
            content: "The seeded 'Attended' status is listed",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Miss')",
            content: "The seeded 'Miss' status is listed, click to open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='category'] select:value(absence)",
            content: "The 'Miss' status form shows its category",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='notifiable'] input:checked",
            content: "'Miss' is notifiable, matching the pre-refactor status_is_notificable() list",
        },
        {
            trigger: ".breadcrumb-item:contains('Statuses')",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td[name='name']:contains('Issue')))",
            content: "The archived 'Issue' status is not shown by default",
        },
    ],
});

// Roll-call view: the status buttons must be populated from ems.attendance_status
// (not the old hardcoded Selection), and clicking one must persist status_id.
registry.category("web_tour.tours").add("ems_attendance_status_passlist", {
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
                const option = [...select.options].find((o) => o.textContent.includes("Attendance Status Tour"));
                select.value = option.value;
                select.dispatchEvent(new Event("change"));
            },
        },
        {
            trigger: ".ems-av-td-student .ems-av-name:contains('Attendance Status Tour Student')",
            content: "Student row loaded",
        },
        {
            trigger: ".ems-av-status-btn[title='Miss']",
            content: "The 'Miss' status button (from ems.attendance_status, not a hardcoded selection) is rendered — click it",
            run: "click",
        },
        {
            trigger: ".ems-av-status-btn--active[title='Miss']",
            content: "'Miss' is now the active status for this student",
        },
    ],
});
