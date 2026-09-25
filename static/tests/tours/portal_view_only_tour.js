/** @odoo-module **/

import { registry } from "@web/core/registry";

// Whoever only consults (res.partner._ems_portal_is_view_only) - a minor on his own portal
// account, or a family looking at its adult child who authorized sharing with it: the home cards and the header menu leave out Enrollment, Convalidations and Documentation,
// and the consulting pages still open from them. Structural selectors only (hrefs, ids), so
// the tour does not depend on the account's language.
const MANAGING = ["/my/gestion-matriculas", "/my/convalidaciones", "/my/documentacion"]
    .map((href) => `a[href='${href}']`)
    .join(", ");

registry.category("web_tour.tours").add("ems_portal_view_only", {
    test: true,
    url: "/my/home",
    steps: () => [
        {
            trigger: ".o_portal_index_card a[href='/my/asistencia']",
            content: "The home shows the consulting cards",
        },
        {
            trigger: `body:not(:has(${MANAGING}))`,
            content: "Neither the home cards nor the header menu offer the managing pages",
        },
        {
            trigger: ".o_portal_index_card a[href='/my/asistencia']",
            content: "Open the schedule from its card",
            run: "click",
        },
        {
            trigger: "#schedule_content",
            content: "The schedule page rendered",
        },
        {
            trigger: ".ems-custom-navbar a[href='/my/comunicaciones']",
            content: "Open the communications from the header menu",
            run: "click",
        },
        {
            trigger: "#communications_content",
            content: "The communications page rendered",
        },
    ],
});
