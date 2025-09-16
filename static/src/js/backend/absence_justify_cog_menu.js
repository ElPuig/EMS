/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

debugger;
const cogMenuRegistry = registry.category("cogMenu");

export class AbsenceJustifyCogMenu extends Component {
    static template = "cog_menu.AbsenceJustifyCogMenu";
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
        this.action.doAction({
            name: "Bulk absence justification",
            type: "ir.actions.act_window",
            res_model: "ems.absence_bulk_justification_wizard",
            res_id: false,
            views: [[false, "form"]],   
            view_mode: "form",
            target: "new",
        });  
    };
}

export const AbsenceJustifyCogMenuItem = {
    Component: AbsenceJustifyCogMenu,
    groupNumber: 20,
    isDisplayed: ({ config }) => { 
        debugger; 
        const { actionType, actionId, viewType, actionName } = config;            
        return actionType === "ir.actions.act_window" && actionId && viewType !=="form" && actionName === "Attendance session";
    },
};

cogMenuRegistry.add("absence-justify-cog-menu", AbsenceJustifyCogMenuItem, { sequence: 1 });