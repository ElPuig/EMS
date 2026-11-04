/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #727: snoozing tasks in My Activities (the to-do tray's "View all activities"). A row's
// bell opens a popover with 1/3/7 days; the header's "Snooze" offers the same for the selected
// tasks in a dialog. The action only shows what is due today or overdue, so a snoozed task
// leaves the list; the Python side checks the new due dates. Found by structure (widget class,
// data-days, button name), not by label, so the tour works in any language.
registry.category("web_tour.tours").add("ems_activity_snooze", {
    url: "/odoo/action-mail.mail_activity_action_my",
    steps: () => [
        {
            trigger: ".o_data_row:contains('Snooze tour task A') .o_ems_activity_snooze",
            content: "Open task A's snooze popover",
            run: "click",
        },
        {
            trigger: ".o_popover .o_ems_snooze_choice[data-days='3']",
            content: "Snooze it by three days",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('Snooze tour task A')))",
            content: "Task A left the list of what is due",
        },
        {
            trigger: ".o_data_row:contains('Snooze tour task B') .o_list_record_selector input",
            content: "Select task B",
            run: "click",
        },
        {
            trigger: ".o_data_row:contains('Snooze tour task C') .o_list_record_selector input",
            content: "Select task C",
            run: "click",
        },
        {
            trigger: ".o_control_panel_actions button[name='action_ems_snooze_dialog'], .o_list_buttons button[name='action_ems_snooze_dialog']",
            content: "Snooze the selected tasks",
            run: "click",
        },
        {
            trigger: ".modal .o_ems_snooze_dialog .o_ems_snooze_choice[data-days='1']",
            content: "By one day",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('Snooze tour task B'))):not(:has(.o_data_row:contains('Snooze tour task C')))",
            content: "Both left the list",
        },
        {
            trigger: ".o_data_row:contains('Snooze tour task D') button[name='action_done']",
            content: "Done is still on the row",
        },
        {
            trigger: ".o_switch_view.o_kanban",
            content: "Switch to the kanban view",
            run: "click",
        },
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('Snooze tour task D')",
            content: "The kanban view renders",
        },
    ],
});
