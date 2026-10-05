/** @odoo-module **/

import { registry } from "@web/core/registry";

// The entire portal frontend (controllers/portal_*.py, reached via @http.route, not
// ir.actions/menuitems - a different reachability mechanism than the rest of EMS) had zero
// tour coverage: every one of the tours elsewhere in this module targets the backend (/odoo)
// UI only. These 5 render-only smoke tours cover every page-rendering portal route, proving
// each one actually renders for a real portal (student) user rather than 500ing.
registry.category("web_tour.tours").add("ems_portal_enrollment_render", {
    test: true,
    url: "/my/gestion-matriculas",
    steps: () => [
        {
            trigger: "#enrollment_content",
            content: "The enrollment page rendered (shared id between the draft and confirmed templates)",
        },
    ],
});

registry.category("web_tour.tours").add("ems_portal_documentation_render", {
    test: true,
    url: "/my/documentacion",
    steps: () => [
        { trigger: "#documentation_content", content: "The documentation page rendered" },
    ],
});

registry.category("web_tour.tours").add("ems_portal_comms_render", {
    test: true,
    url: "/my/comunicaciones",
    steps: () => [
        { trigger: "#communications_content", content: "The communications page rendered" },
    ],
});

registry.category("web_tour.tours").add("ems_portal_account_render", {
    test: true,
    url: "/my/account",
    steps: () => [
        {
            // Structural, not text-based: this dev DB's real portal users default to Catalan
            // (confirmed empirically - the English "read-only"/etc. text never matches), so a
            // translated-text trigger is not language-independent. The lock icon is only
            // rendered by EMS's own readonly override (portal_account_readonly.xml), never by
            // the stock editable form it replaces.
            trigger: ".o_portal_details .fa-lock",
            content: "The read-only account page rendered (EMS overrides the stock editable one for portal users)",
        },
    ],
});

registry.category("web_tour.tours").add("ems_portal_under_construction_render", {
    test: true,
    url: "/my/calificaciones",
    steps: () => [
        {
            // Structural, not text-based - see the account tour above for why.
            trigger: "h1.display-5.fw-bold",
            content: "The placeholder page rendered (/my/asistencia now shows the student's schedule instead)",
        },
    ],
});

// The mid-year authorizations of issue #443: a student whose enrollment is already confirmed
// still has to be able to answer an authorization sent during the course. That page
// (portal_enrollment_confirmed) showed no authorizations at all before this, so this tour
// guards the case the whole feature exists for.
//
// Structural selectors only, no text: this file's portal user is created without an explicit
// 'lang' and a fresh res.users does not reliably default to en_US on every box (see CLAUDE.md,
// "Tour tests and language").
registry.category("web_tour.tours").add("ems_portal_confirmed_authorizations", {
    test: true,
    url: "/my/gestion-matriculas",
    steps: () => [
        {
            trigger: "#enrollment_content",
            content: "The confirmed enrollment page rendered",
        },
        {
            trigger: "#portal_authorizations",
            content: "The authorizations block is there even though the enrollment is closed",
        },
        {
            trigger: "#portal_authorizations .ems-auth-answer",
            content: "Open the response modal of the authorization sent during the course",
            run: "click",
        },
        {
            trigger: ".modal.show form[data-auth-form] button[value='yes']",
            content: "The response form rendered inside the modal",
        },
    ],
});

// Issue #491: a confirmed enrollment whose first installment is already paid shows one row per
// installment with its own state, and the payment notification in the page's own communications
// block. Structural selectors only, same reason as the tour above.
registry.category("web_tour.tours").add("ems_portal_payment_status", {
    test: true,
    url: "/my/gestion-matriculas",
    steps: () => [
        {
            trigger: "#enrollment_content",
            content: "The confirmed enrollment page rendered",
        },
        {
            trigger: ".ems-payment-schedule [data-installment-state='paid']",
            content: "The settled installment is marked as paid",
        },
        {
            trigger: ".ems-payment-schedule [data-installment-state='pending']",
            content: "The one still due is marked as pending",
        },
        {
            trigger: "#portal_enrollment_messages",
            content: "The payment notification reached the enrollment page's communications block",
        },
    ],
});

// The same notification, on the Communications page of the portal menu.
registry.category("web_tour.tours").add("ems_portal_payment_status_comms", {
    test: true,
    url: "/my/comunicaciones",
    steps: () => [
        {
            trigger: "#communications_content .ems-bubble-center",
            content: "The payment notification is listed among the communications",
        },
    ],
});

// Issue #491: an enrollment confirmed from the backend has no payment plan and no payment method,
// but its invoice is real - its schedule must show all the same, and the "payment information not
// specified" placeholder (the credit-card icon) must not.
registry.category("web_tour.tours").add("ems_portal_payment_status_without_plan", {
    test: true,
    url: "/my/gestion-matriculas",
    steps: () => [
        {
            trigger: "#portal_enrollment_payment .ems-payment-schedule [data-installment-state='paid']",
            content: "The paid installment shows even with no payment plan on the enrollment",
        },
        {
            trigger: "#portal_enrollment_payment:not(:has(.fa-credit-card))",
            content: "The 'payment information not specified' placeholder is gone",
        },
    ],
});
