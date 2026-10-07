/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #592: the secretariat undoes a withdrawal registered by mistake from the withdrawn
// (archived) student's own form. The student goes back to the group of their confirmed
// enrollment, so the "Withdrawal" ribbon goes away and the group is shown again.
registry.category("web_tour.tours").add("ems_undo_withdrawal", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .ribbon span:contains('Withdrawal')",
            content: "The withdrawn student's form shows the Withdrawal ribbon",
        },
        ...clickAction("action_undo_withdrawal", "Undo the withdrawal from the Actions dropdown"),
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_notification:contains('UWTS1A')",
            content: "The notification says which group the student is back in",
        },
        {
            trigger: ".o_form_view:has(.o_form_sheet):not(:has(.ribbon))",
            content: "The form reloaded as a student's: no Withdrawal ribbon",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            // The Group Data block only shows for contact_type 'student'; the group itself is an
            // editable input for the secretariat (OWL never syncs its value attribute), so its
            // value is asserted on the Python side.
            trigger: ".o_field_widget[name='main_group_id'] input",
            content: "The Studies tab shows the student's group data again",
        },
    ],
});
