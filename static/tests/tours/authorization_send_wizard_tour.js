/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #443's backend side: the follow-up list of every authorization requested, and the
// assistant that sends new ones to students during the course.
//
// Driven by a secretary account, not admin: sending authorizations is a secretary /
// academic admin / head of studies job, and a tour logged in as admin would prove nothing
// about whether the menus, the action and the record rules actually line up for the people
// who use this.
registry.category("web_tour.tours").add("ems_authorization_list", {
    test: true,
    url: "/odoo/action-ems.action_ems_authorizations",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The authorizations follow-up list rendered",
        },
        {
            trigger: ".o_list_view .o_data_row:first .o_data_cell",
            content: "Open one authorization - its form view is the second declared view_mode",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='partner_id']",
            content: "The form rendered, anchored on the student rather than on an enrollment",
        },
    ],
});

registry.category("web_tour.tours").add("ems_authorization_send_wizard", {
    test: true,
    url: "/odoo/action-ems.action_ems_authorization_send",
    steps: () => [
        {
            trigger: ".o_dialog .o_form_view",
            content: "The send assistant opened",
        },
        {
            trigger: ".o_dialog div[name='target'] input[data-value='students']",
            content: "Target the students picked by hand rather than a whole scope",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='student_ids'] input",
            content: "Pick the student",
            run: "edit Tour Send Wizard Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(Tour Send Wizard Student)",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='template_ids'] input",
            content: "Pick the authorization to send",
            run: "edit Tour Send Wizard Authorization",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(Tour Send Wizard Authorization)",
            run: "click",
        },
        {
            trigger: ".o_dialog button[name='action_apply']",
            content: "Send it",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_dialog))",
            content: "The assistant closed itself after sending (act_window_close)",
        },
    ],
});
