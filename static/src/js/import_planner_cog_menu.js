/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

export class ImportPlannerCogMenu extends Component {
    static template = "cog_menu.ImportPlannerCogMenu";
    static components = { DropdownItem };
    static props = {};
    
    async setup() {
        this.action = useService("action");
        this.orm = useService("orm");                           
    };

    async onClickCogMenu() {
        // Include your action for the menu here...
        //https://www.odoo.com/ca_ES/forum/ajuda-1/unable-to-display-cogmenuitem-only-in-specific-views-276153
        //https://www.odoo.com/ca_ES/forum/ajuda-1/call-a-python-method-from-owl-javascript-v16-236218
        //let data = this.orm.call("resource.calendar", "action_import_planner_data", [ ]);
        //this.orm.call("resource.calendar", "action_import_planner_data", [[]]);
        this.action.doAction({
            name: "Import: planner data",
            type: "ir.actions.act_window",
            res_model: "ims.working_schedules_import_wizard",
            res_id: false,
            views: [[false, "form"]],   
            view_mode: "form",
            target: "new",
        });  
    };
}

export const ImportPlannerCogMenuItem = {
    Component: ImportPlannerCogMenu,
    groupNumber: 20,
    isDisplayed: ({ config }) => {  
        const { actionType, actionId, viewType, actionName } = config;            
        return actionType === "ir.actions.act_window" && actionId && viewType !=="form" && actionName === "Working Schedules";
    },
};

cogMenuRegistry.add("import-planner-cog-menu", ImportPlannerCogMenuItem, { sequence: 10 });