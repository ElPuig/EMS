/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction, noActions } from "./actions_dropdown_helpers";

// A notice drafted by a Department Chief can be sent by the Head of Studies above them, and only
// read by a Head of Studies of another branch (issue #636). Seed data comes from
// TestNoticeHierarchyTour (tests/test_notice_hierarchy_tour.py).
function openChiefDraft() {
    return [
        {
            // "Show only mine" is on by default: the draft is someone else's.
            trigger: ".o_searchview .o_facet_remove",
            content: "Clear the default filter",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Hierarchy tour draft')",
            content: "Open the chief's draft",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='subject'] input",
            content: "The draft is open",
        },
    ];
}

registry.category("web_tour.tours").add("ems_notice_hierarchy_send", {
    test: true,
    url: "/odoo/action-ems.action_communication_list",
    steps: () => [
        ...openChiefDraft(),
        ...clickAction("action_send", "Send it"),
        {
            trigger: ".o_statusbar_status button[data-value='scheduled'].o_arrow_button_current",
            content: "The notice is now Scheduled",
        },
    ],
});

registry.category("web_tour.tours").add("ems_notice_hierarchy_read_only", {
    test: true,
    url: "/odoo/action-ems.action_communication_list",
    steps: () => [
        ...openChiefDraft(),
        noActions("Another branch's Head of Studies gets no action on it"),
    ],
});
