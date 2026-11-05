/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #697 - Erasmus+ grants. Records are seeded by tests/test_erasmus_grant_tour.py; the
// selectors are structural (field names, classes) or fixture names, so the language doesn't matter.

// The Erasmus team uploads an invoice for both students, sets a grant and requests its first payment.
registry.category("web_tour.tours").add("ems_erasmus_grant_team", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_invoice",
    steps: () => [
        {
            trigger: ".o_control_panel .o_list_button_add",
            content: "New invoice",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Invoice number",
            run: "edit F-TOUR-1",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='amount'] input",
            content: "Amount",
            run: "edit 600",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='mobility_ids'] input",
            content: "Add the first student",
            run: "edit Erasmus Test Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Erasmus Test Student')",
            content: "Pick the first student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='mobility_ids'] input",
            content: "Add the second student",
            run: "edit Erasmus Second",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Erasmus Second')",
            content: "Pick the second student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save the invoice",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='provision_ids'] .o_data_row:nth-child(2) td[name='amount']:contains('300')",
            content: "The invoice is split between both students",
        },
        {
            trigger: ".o_main_navbar",
            content: "Go to the mobilities",
            run() {
                window.location.href = "/odoo/action-ems.action_erasmus_mobility";
            },
        },
        {
            // The mobilities' own list, not the invoice's shares still on screen while the page reloads.
            trigger: ".o_list_view:not(.o_field_x2many) .o_data_row td[name='rank']:contains('1')",
            content: "Open the first student's mobility",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='grant']",
            content: "Open the grant tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='provision_ids'] td[name='invoice_id']:contains('F-TOUR-1')",
            content: "The share of the invoice is a provision of services",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_amount'] input",
            content: "Set the grant",
            run: "edit 1250",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save the grant",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_net']:contains('950')",
            content: "The participant receives the grant minus the invoice's share",
        },
        ...clickAction("action_request_prefinancing", "Request the first payment"),
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='payment_ids'] .o_data_row td[name='amount']:contains('760')",
            content: "80 % of 950 goes to the Secretary",
        },
    ],
});

// The Secretary registers the transfer of the grant payment.
registry.category("web_tour.tours").add("ems_erasmus_grant_secretary", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_payment",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='bank_account']:contains('ES91 2100 0418 4502 0005 1332')",
            content: "The payment shows the participant's IBAN",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "Open the payment",
            run: "click",
        },
        ...clickAction("action_register_transfer", "Register the transfer"),
        {
            trigger: ".modal .o_field_widget[name='payment_ids'] .o_data_row",
            content: "The transfer lists the payment",
        },
        {
            trigger: ".modal-footer button[name='action_confirm']",
            content: "Mark it as paid",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button.o_arrow_button_current[data-value='paid']",
            content: "The payment is paid",
        },
    ],
});
