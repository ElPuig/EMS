/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { browser } from "@web/core/browser/browser";

// The issue-#682 review: a staff member applies to an Erasmus+ call, and follows their mobility,
// on the portal's Erasmus+ page; this entry takes them there from the backend. Only shown to whoever
// has that page (session_info's 'ems_erasmus_portal', models/erasmus/ir_http.py).
function emsErasmusItem() {
    return {
        type: "item",
        id: "ems_erasmus",
        description: _t("Erasmus+"),
        href: "/my/erasmus",
        show: () => Boolean(session.ems_erasmus_portal),
        callback: () => {
            browser.location.href = "/my/erasmus";
        },
        sequence: 15,
    };
}

registry.category("user_menuitems").add("ems_erasmus", emsErasmusItem);
