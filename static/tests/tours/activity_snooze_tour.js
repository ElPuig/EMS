/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #727: "Snooze 1d" and "Snooze 3d" next to Odoo's own "Snooze 7d" in My Activities (the
// to-do tray's "View all activities"). The action only shows what is due today or overdue, so a
// snoozed task leaves the list; the Python side checks its new due date. Buttons are found by
// their method name, not their label, so the tour works in any language.
registry.category("web_tour.tours").add("ems_activity_snooze", {
    url: "/odoo/action-mail.mail_activity_action_my",
    steps: () => [
        {
            trigger: ".o_data_row:contains('Snooze tour task A') button[name='action_ems_snooze_1d']",
            content: "Snooze task A by one day",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('Snooze tour task A')))",
            content: "Task A left the list of what is due",
        },
        {
            trigger: ".o_data_row:contains('Snooze tour task B') button[name='action_ems_snooze_3d']",
            content: "Snooze task B by three days",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('Snooze tour task B')))",
            content: "Task B left the list of what is due",
        },
        {
            trigger: ".o_data_row:contains('Snooze tour task C') button[name='action_snooze']",
            content: "Odoo's own Snooze 7d is still there",
        },
        {
            trigger: ".o_switch_view.o_kanban",
            content: "Switch to the kanban view",
            run: "click",
        },
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('Snooze tour task C')",
            content: "The kanban view renders",
        },
    ],
});
