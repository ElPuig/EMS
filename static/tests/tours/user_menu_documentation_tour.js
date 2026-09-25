/** @odoo-module **/

import { registry } from "@web/core/registry";

// The user menu's "Documentation" entry must lead to EMS's own user manuals, in the logged-in
// user's language, not to Odoo's developer documentation (issue #516). The link is only
// asserted, never clicked - it opens an external site in a new tab.
const documentationTourSteps = (expectedUrl) => [
    {
        trigger: ".o_user_menu button",
        content: "Open the user menu",
        run: "click",
    },
    {
        trigger: `.dropdown-item[data-menu='documentation'][href='${expectedUrl}']`,
        content: `Documentation points at ${expectedUrl}`,
    },
];

registry.category("web_tour.tours").add("ems_user_menu_documentation_ca_tour", {
    steps: () => documentationTourSteps("https://docs.ems.elpuig.xeill.net/ca/"),
});

registry.category("web_tour.tours").add("ems_user_menu_documentation_en_fallback_tour", {
    steps: () => documentationTourSteps("https://docs.ems.elpuig.xeill.net/en/"),
});
