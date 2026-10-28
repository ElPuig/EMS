/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #640: the family of a student without a birth date gives it when confirming the
// enrollment from the portal. The field is required; once filled in, the enrollment confirms.
registry.category("web_tour.tours").add("ems_portal_birth_date", {
    test: true,
    url: "/my/gestion-matriculas",
    steps: () => [
        {
            trigger: ".o_ems_portal_birth_date input[name='birth_date'][required]",
            content: "The page asks for the student's birth date, required",
        },
        {
            trigger: "label:contains('Birth date single payment')",
            content: "Pick the payment plan",
            run: "click",
        },
        {
            trigger: ".o_ems_portal_birth_date input[name='birth_date']",
            content: "Give the birth date (a native date input takes an ISO value)",
            run() {
                const input = document.querySelector(".o_ems_portal_birth_date input[name='birth_date']");
                input.value = "2011-02-03";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: "#ems-confirm-btn:not([disabled])",
            content: "Confirm the enrollment",
            run: "click",
        },
        {
            trigger: "#enrollment_content:not(:has(.o_ems_portal_birth_date))",
            content: "Back on the enrollment page, which no longer asks for it",
        },
    ],
});
