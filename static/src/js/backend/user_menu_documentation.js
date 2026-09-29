/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";

// Replaces Odoo's own user-menu "Documentation" entry (web/static/src/webclient/user_menu/
// user_menu_items.js), which opens Odoo's developer documentation, with EMS's user manuals in
// the user's own language - English for any language without its own docs tree.
const EMS_DOCS_URL = "https://docs.ems.elpuig.xeill.net";
const EMS_DOCS_LANGUAGES = ["ca", "es", "en"];

function emsDocumentationItem() {
    const language = user.lang.split("-")[0];
    const documentationURL = `${EMS_DOCS_URL}/${EMS_DOCS_LANGUAGES.includes(language) ? language : "en"}/`;
    return {
        type: "item",
        id: "documentation",
        description: _t("Documentation"),
        href: documentationURL,
        callback: () => {
            browser.open(documentationURL, "_blank");
        },
        sequence: 10,
    };
}

registry.category("user_menuitems").add("documentation", emsDocumentationItem, { force: true });
