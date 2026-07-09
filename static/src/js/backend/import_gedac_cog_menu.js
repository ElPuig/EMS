/** @odoo-module **/
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

let _applicantActionId = null;

export class ImportGedacCogMenu extends Component {
    static template = "cog_menu.ImportGedacCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    async onClickCogMenu() {
        this.action.doAction({
            name: "Import from GEDAC",
            type: "ir.actions.act_window",
            res_model: "ems.applicant_import_wizard",
            res_id: false,
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
        });
    }
}

export const ImportGedacCogMenuItem = {
    Component: ImportGedacCogMenu,
    groupNumber: 20,
    isDisplayed: (env) => {
        const { actionType, actionId, viewType } = env.config;
        if (actionType !== "ir.actions.act_window" || !actionId || viewType === "form") {
            return false;
        }
        // Show only on the Preinscription (applicants) list, not on other
        // res.partner lists — scoped by matching the applicants menu action.
        if (_applicantActionId === null) {
            try {
                const menu = env.services.menu.getAll().find((m) => m.xmlid === "ems.menu_ems_applicants");
                _applicantActionId = menu ? menu.actionID : false;
            } catch {
                _applicantActionId = false;
            }
        }
        return actionId === _applicantActionId;
    },
};

cogMenuRegistry.add("import-gedac-cog-menu", ImportGedacCogMenuItem, { sequence: 10 });
