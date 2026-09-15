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
            // The recipient preview is what tells the sender who is about to be emailed. It
            // silently rendered empty until the manual screenshots showed it up, so it is
            // asserted here rather than trusted.
            trigger: ".o_dialog div[name='line_ids'] .o_data_row td:contains(Tour Send Wizard Student)",
            content: "The preview lists the student who is about to be notified",
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

// A tutor (issue #443 testing): the Responses menu entry shows their own students' answers
// only, and the send assistant offers their own groups only, without studies or levels.
registry.category("web_tour.tours").add("ems_authorization_tutor_follow_up", {
    test: true,
    url: "/odoo/action-ems.action_ems_authorizations_follow_up",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Send Wizard Student')",
            content: "The tutor's own student is listed",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('Tour Other Student')))",
            content: "A student of a group they do not tutor is not",
        },
    ],
});

registry.category("web_tour.tours").add("ems_authorization_tutor_send", {
    test: true,
    url: "/odoo/action-ems.action_ems_authorization_send",
    steps: () => [
        {
            trigger: ".o_dialog .o_form_view div[name='group_ids']",
            content: "The send assistant opened, on groups",
        },
        {
            // .modal-content and not .o_dialog: the latter is a wrapper with no box of its own,
            // and a tour trigger has to be visible.
            trigger: ".o_dialog .modal-content:not(:has(div[name='ems_study_ids'])):not(:has(div[name='ems_level_ids']))",
            content: "No studies or levels to pick for a tutor",
        },
        {
            trigger: ".o_dialog div[name='template_ids'] input",
            content: "Pick the authorization from the catalogue",
            run: "edit Tour Send Wizard Authorization",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(Tour Send Wizard Authorization)",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='group_ids'] input",
            content: "Pick their own group",
            run: "edit TAWTS",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(TAWTS)",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='line_ids'] .o_data_row td:contains(Tour Send Wizard Student)",
            content: "The preview lists the tutor's student",
        },
        {
            trigger: ".o_dialog button[name='action_apply']",
            content: "Send it",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_dialog))",
            content: "The assistant closed itself after sending",
        },
    ],
});
