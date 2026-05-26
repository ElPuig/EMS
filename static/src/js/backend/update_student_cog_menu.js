/** @odoo-module **/
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

let _studentActionId = null;

export class UpdateStudentCogMenu extends Component {
    static template = "cog_menu.UpdateStudentCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    async onClickCogMenu() {
        this.action.doAction({
            name: "Update students from CSV",
            type: "ir.actions.act_window",
            res_model: "ems.student_update_wizard",
            res_id: false,
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
        });
    }
}

export const UpdateStudentCogMenuItem = {
    Component: UpdateStudentCogMenu,
    groupNumber: 20,
    isDisplayed: (env) => {
        const { actionType, actionId, viewType } = env.config;
        if (actionType !== "ir.actions.act_window" || !actionId || viewType === "form") {
            return false;
        }
        if (_studentActionId === null) {
            try {
                const menu = env.services.menu.getAll().find((m) => m.xmlid === "ems.menu_students");
                _studentActionId = menu ? menu.actionID : false;
            } catch {
                _studentActionId = false;
            }
        }
        return actionId === _studentActionId;
    },
};

cogMenuRegistry.add("update-student-cog-menu", UpdateStudentCogMenuItem, { sequence: 11 });
