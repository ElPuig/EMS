/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

// The issue-#682 review: a staff member applies to an Erasmus+ call, and follows their mobility,
// from the Erasmus+ app's "My participation"; this entry takes them there from anywhere. Only shown
// to whoever has a staff call to apply to or an application (session_info's 'ems_erasmus_staff',
// models/erasmus/ir_http.py). Never the portal: it is for students and families (the 2026-11-04 review).
function emsErasmusItem(env) {
    return {
        type: "item",
        id: "ems_erasmus",
        description: _t("Erasmus+"),
        show: () => Boolean(session.ems_erasmus_staff),
        callback: () => env.services.action.doAction("ems.action_erasmus_staff_calls"),
        sequence: 15,
    };
}

registry.category("user_menuitems").add("ems_erasmus", emsErasmusItem);
