/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.teaching's own CRUD screen is secondary — the model is normally kept in sync from
// the schedule (sync_from_schedule(), see the dev doc) rather than hand-edited. This tour
// only confirms the list and the (three Many2one selectors) form actually render without
// crashing, which a clean upgrade and passing TransactionCase tests don't prove.
registry.category("web_tour.tours").add("ems_teaching_form_renders", {
    test: true,
    url: "/odoo/action-ems.action_teaching_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Teaching list view loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Click New",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='teacher_id']",
            content: "teacher_id selector rendered",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='subject_id']",
            content: "subject_id selector rendered",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_id']",
            content: "group_id selector rendered",
        },
        {
            trigger: ".o_form_view .o_form_button_cancel, .o_breadcrumb a",
            content: "Discard the empty form",
            run: "click",
        },
        {
            trigger: ".o_list_view",
            content: "Back in list",
        },
    ],
});
