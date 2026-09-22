/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #470: a tutor deleting a family contact of their own student from the Contacts &
// Addresses tab hit an AccessError on res.partner.relation (only the Contact Creation group
// could delete relations). Opened by URL on the seeded student (see test_contact_tour.py).
registry.category("web_tour.tours").add("ems_contact_tutor_deletes_family_contact", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Contacts & Addresses')",
            content: "Open the Contacts & Addresses tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='relation_all_ids'] .o_data_row:has(td:contains('Tutor Tour Mother')) button[name='unlink']",
            content: "Delete the family contact with the trash button",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button:contains('Ok')",
            content: "Confirm the delete",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='relation_all_ids']:not(:has(td:contains('Tutor Tour Mother')))",
            content: "The family contact is gone from the list, without an access error",
        },
    ],
});
