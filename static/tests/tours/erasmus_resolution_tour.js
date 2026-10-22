/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #685 - Erasmus+ resolutions, place offers and claims. Every tour runs against records
// seeded by tests/test_erasmus_resolution_tour.py and uses structural selectors (field names,
// values, classes), so the logged-in user's language does not matter.

// The Erasmus team prepares the provisional resolution and publishes it.
registry.category("web_tour.tours").add("ems_erasmus_resolution_publish", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_resolution",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='kind']",
            content: "Open the draft resolution",
            run: "click",
        },
        ...clickAction("action_prepare", "Prepare the lines"),
        {
            trigger: ".o_form_view .o_field_widget[name='line_ids'] .o_data_row td[name='public_id']:contains('***4567**')",
            content: "The lines show the masked identity document",
        },
        ...clickAction("action_publish", "Publish"),
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm the publication",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='published'].o_arrow_button_current",
            content: "The resolution is published",
        },
    ],
});

// A selected student renounced: the team offers the free place to the next reserve.
registry.category("web_tour.tours").add("ems_erasmus_offer_place", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_call",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Test Erasmus Call')",
            content: "Open the call",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='resolutions']",
            content: "Open the resolutions tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='modality_ids'] td[name='next_reserve_id']:contains('Erasmus Second Student')",
            content: "EMS proposes the next reserve",
        },
        ...clickAction("action_offer_place", "Offer a free place"),
        {
            trigger: ".modal .o_field_widget[name='application_id']:contains('Erasmus Second Student')",
            content: "The wizard proposes the next reserve",
        },
        {
            trigger: ".modal .o_field_widget[name='deadline'] input",
            content: "Set the answer deadline",
            run: "edit 12/31/2099 10:00:00",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']",
            content: "Offer the place",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The wizard closes",
        },
    ],
});

// The team's list of place offers, and one of them.
registry.category("web_tour.tours").add("ems_erasmus_offers", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_offer",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The offer is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='deadline']",
            content: "The offer form opens",
        },
    ],
});

// The team answers a claim recorded against the provisional resolution.
registry.category("web_tour.tours").add("ems_erasmus_claims", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_claim",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The open claim is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='response'] textarea",
            content: "Write the response",
            run: "edit The score stands.",
        },
        ...clickAction("action_resolve", "Resolve the claim"),
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='resolved'].o_arrow_button_current",
            content: "The claim is resolved",
        },
    ],
});

// The selected student accepts the place from the portal.
registry.category("web_tour.tours").add("ems_erasmus_portal_accept", {
    test: true,
    steps: () => [
        {
            trigger: ".o_ems_erasmus_results .o_ems_erasmus_result_selected",
            content: "The result is shown",
        },
        {
            trigger: ".o_ems_erasmus_breakdown",
            content: "With the score breakdown",
        },
        {
            trigger: ".o_ems_erasmus_offer .o_ems_erasmus_accept",
            content: "Accept the place",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_ems_erasmus_answered",
            content: "The answer is recorded",
        },
        {
            trigger: ".o_ems_erasmus_accepted",
            content: "The place is accepted",
        },
        {
            trigger: ".o_ems_erasmus_list_link",
            content: "See the published list",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_ems_erasmus_resolution_table td:contains('***4567**')",
            content: "The list shows only four digits of the identity document",
        },
    ],
});
