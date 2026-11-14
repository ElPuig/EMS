/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #786 - the actions at the right moment, asking for their data. Records seeded by
// tests/test_erasmus_polish_actions_tour.py; structural selectors (field and button names).

// 5.15, 8.11: the reason in a dialog, shown on the form once cancelled (no Cancellation tab).
registry.category("web_tour.tours").add("ems_erasmus_actions_cancel", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view:not(:has(.o_notebook a[name='cancellation']))",
            content: "No Cancellation tab",
        },
        ...clickAction("action_open_cancel_wizard", "Cancel the mobility"),
        {
            trigger: ".modal .o_field_widget[name='reason'] textarea",
            content: "The dialog asks for the reason",
            run: "edit Tour reason: travel documents not handed in",
        },
        {
            trigger: ".modal footer button[name='action_confirm']",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-secondary:contains('Tour reason')",
            content: "The reason, on the cancelled mobility",
        },
    ],
});

// 5.16: the agreed destination in a dialog.
registry.category("web_tour.tours").add("ems_erasmus_actions_destination", {
    test: true,
    steps: () => [
        ...clickAction("action_open_destination_wizard", "Set the agreed destination"),
        {
            trigger: ".modal .o_field_widget[name='country_id'] input",
            content: "The country",
            run: "edit Ireland",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('Ireland')",
            content: "Ireland",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='city'] input",
            content: "The city",
            run: "edit Tour City",
        },
        {
            trigger: ".modal footer button[name='action_confirm']",
            content: "Set it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='preparing'].o_arrow_button_current",
            content: "The mobility is in preparation",
        },
    ],
});
