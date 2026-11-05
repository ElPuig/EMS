/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #764 - pocket money of a group mobility's participants. Records are seeded by
// tests/test_erasmus_pocket_money.py; the selectors are structural (field names, classes), so the
// language doesn't matter.

// The mobility technician checks each participant's pocket money and requests the payments.
registry.category("web_tour.tours").add("ems_erasmus_pocket_money_team", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook a[name='expenses']",
            content: "Open the Collective expenses tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_participant_ids'] .o_data_row td[name='invoice_share']:contains('700')",
            content: "Each participant's share of the collective invoices",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_participant_ids'] .o_data_row td[name='pocket_amount']:contains('500')",
            content: "A student's pocket money is the rest of their grant",
        },
        ...clickAction("action_request_pocket_money", "Request the pocket money"),
        {
            trigger: ".o_form_view .o_field_widget[name='grant_participant_ids'] .o_data_row td[name='pocket_requested']:contains('500')",
            content: "The payments are requested",
        },
    ],
});

// The Secretary pays every pocket money payment of the group with one transfer.
registry.category("web_tour.tours").add("ems_erasmus_pocket_money_secretary", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='group_mobility_id']",
            content: "The payments say which group mobility they belong to",
        },
        {
            trigger: ".o_list_view thead .o_list_record_selector input",
            content: "Select every payment to make",
            run: "click",
        },
        {
            trigger: ".o_control_panel button[name='action_register_transfer']",
            content: "Register one transfer for all of them",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='payment_ids'] .o_data_row:nth-child(10)",
            content: "The transfer lists the ten payments",
        },
        {
            trigger: ".modal-footer button[name='action_confirm']",
            content: "Mark them as paid",
            run: "click",
        },
        {
            trigger: ".o_view_nocontent",
            content: "Nothing left to pay",
        },
    ],
});

// The leader teacher reads the group's grants and pocket money (never the bank accounts).
registry.category("web_tour.tours").add("ems_erasmus_pocket_money_leader", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook a[name='expenses']",
            content: "Open the Collective expenses tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_participant_ids'] .o_data_row td[name='pocket_amount']:contains('500')",
            content: "The leader sees each participant's pocket money",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='invoice_ids'] .o_data_row td[name='amount']:contains('7,000')",
            content: "and the group's collective invoices",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_participant_ids']:not(:has(th[data-name='bank_account']))",
            content: "but no bank account",
        },
    ],
});
