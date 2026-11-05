/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_erasmus_send_to_sign", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_mobility",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "Open the mobility",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row:has(td[name='name']:contains('Grant agreement')) button[name='action_send_to_sign']",
            content: "Send the filled-in grant agreement to sign",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='signer_ids'] .o_data_row",
            content: "The signature request lists who signs it, ready to check and send",
        },
    ],
});
