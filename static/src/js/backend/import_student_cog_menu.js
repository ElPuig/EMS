/** @odoo-module **/
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

let _studentActionId = null;

export class ImportStudentCogMenu extends Component {
    static template = "cog_menu.ImportStudentCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    async onClickCogMenu() {
        this.action.doAction({
            name: "Import from Esfera",
            type: "ir.actions.act_window",
            res_model: "ems.student_import_wizard",
            res_id: false,
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
        });
    }
}

export const ImportStudentCogMenuItem = {
    Component: ImportStudentCogMenu,
    groupNumber: 20,
    isDisplayed: async (env) => {
        const { actionType, actionId, viewType } = env.config;
        if (actionType !== "ir.actions.act_window" || !actionId || viewType === "form") {
            return false;
        }
        if (_studentActionId === null) {
            try {
                const result = await env.services.orm.call(
                    "ir.model.data",
                    "check_object_reference",
                    ["ems", "action_student_kanban"]
                );
                _studentActionId = result[1];
            } catch {
                _studentActionId = false;
            }
        }
        return actionId === _studentActionId;
    },
};

cogMenuRegistry.add("import-student-cog-menu", ImportStudentCogMenuItem, { sequence: 10 });
