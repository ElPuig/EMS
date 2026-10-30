/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issues #701-#704 - Erasmus+ group mobilities. Records are seeded by
// tests/test_erasmus_group_mobility_tour.py; the selectors are structural (field and page names,
// classes) or fixture names, so the language doesn't matter.

const MOBILITY = "Test SMX2 morning";

function openMyMobility() {
    return [
        {
            trigger: `.o_kanban_view .o_kanban_record:contains('${MOBILITY}')`,
            content: "Open the group mobility from its card",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook",
            content: "The mobility's panel is open",
        },
    ];
}

// The leader teacher reviews the ranking of their mobility and sends the proposal.
registry.category("web_tour.tours").add("ems_erasmus_group_leader", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_my_group_mobility",
    steps: () => [
        ...openMyMobility(),
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='selection']",
            content: "Open the Selection tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='registration_ids'] .o_data_row:nth-child(10)",
            content: "The ten enrolments are ranked",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='stay']",
            content: "Open the Programme and stay tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='log_ids']",
            content: "The follow-up is there",
        },
        ...checkActions({ offered: ["action_submit_proposal"], notOffered: ["action_approve_selection", "action_open_enrolment"] },
            "The leader sends the proposal, never approves it"),
        ...clickAction("action_submit_proposal", "Send the proposal to the coordinator"),
        {
            trigger: ".o_form_view .o_statusbar_status button.o_arrow_button_current[data-value='validation']",
            content: "The proposal waits for the coordinator",
        },
    ],
});

// An accompanying teacher never sees the enrolments, and writes the follow-up of the stay.
registry.category("web_tour.tours").add("ems_erasmus_group_companion", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_my_group_mobility",
    steps: () => [
        ...openMyMobility(),
        {
            trigger: ".o_form_view .o_notebook:not(:has(a.nav-link[name='selection'])):not(:has(a.nav-link[name='enrolment']))",
            content: "No enrolments nor ranking for an accompanying teacher",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='stay']",
            content: "Open the Programme and stay tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='log_ids'] .o_field_x2many_list_row_add a",
            content: "Add a follow-up entry",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='name'] input",
            content: "Summary",
            run: "edit Everybody arrived",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Save the entry",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='log_ids'] .o_data_row:contains('Everybody arrived')",
            content: "The entry is in the follow-up",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save the mobility",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});

// The Erasmus coordinator follows every group mobility (kanban and list) and approves a selection.
registry.category("web_tour.tours").add("ems_erasmus_group_coordinator", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_group_mobility",
    steps: () => [
        {
            trigger: `.o_kanban_view .o_kanban_record:contains('${MOBILITY}')`,
            content: "The mobility's card in the overview",
        },
        {
            trigger: ".o_control_panel .o_switch_view.o_list",
            content: "Switch to the list",
            run: "click",
        },
        {
            trigger: `.o_list_view .o_data_row:contains('${MOBILITY}') td[name='name']`,
            content: "Open the mobility from the list",
            run: "click",
        },
        ...checkActions({ offered: ["action_publish_provisional", "action_return_proposal"],
            notOffered: ["action_approve_selection"] },
            "The coordinator publishes the provisional list first, or sends the proposal back"),
        ...clickAction("action_publish_provisional", "Publish the provisional list"),
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='selection']",
            content: "Open the Selection tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='resolution_ids'] .o_data_row",
            content: "The provisional list is published",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button.o_arrow_button_current[data-value='validation']",
            content: "The selection waits for the claims deadline",
        },
    ],
});

// Once the claims deadline has passed, the coordinator approves the selection.
registry.category("web_tour.tours").add("ems_erasmus_group_coordinator_approve", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_group_mobility",
    steps: () => [
        {
            trigger: `.o_kanban_view .o_kanban_record:contains('${MOBILITY}')`,
            content: "Open the mobility from its card",
            run: "click",
        },
        ...clickAction("action_approve_selection", "Approve and publish the selection"),
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button.o_arrow_button_current[data-value='preparation']",
            content: "The selection is published and the files open",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='participants']",
            content: "Open the Participants tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='participant_ids'] .o_data_row:nth-child(10)",
            content: "Eight students and two teachers",
        },
    ],
});
