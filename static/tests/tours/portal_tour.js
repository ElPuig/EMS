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
    url: "/my/asistencia",
    steps: () => [
        {
            // Structural, not text-based - see the account tour above for why.
            trigger: "h1.display-5.fw-bold",
            content: "The placeholder page rendered (shared by /my/asistencia and /my/calificaciones)",
        },
    ],
});
