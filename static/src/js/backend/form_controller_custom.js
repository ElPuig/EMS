/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { useService } from "@web/core/utils/hooks";
import { registry } from '@web/core/registry';

export class StudentPopupFormController extends FormController {
    setup() {
        this.action = useService("action");
        super.setup();

        var self = this;
        owl.onMounted(function(){
            const items = document.getElementsByClassName("o_expand_button");
            if(items.length > 0){
                items[0].onclick = function() {
                    self.action.doAction({
                        type: 'ir.actions.act_window',
                        res_model: 'res.partner',    //self.props.record.model.config.resModel
                        res_id: self.props.resId,
                        views: [[false, "form"]],
                        target: 'current', //with 'new' the form opens as a modal window.
                   });
                };
            }
        });
    }

    getStaticActionMenuItems() {
        // Archiving a student already opens the withdrawal wizard (see toggle_active
        // on res.partner), which has its own "this withdraws immediately" confirmation
        // — skip Odoo's generic "are you sure you want to archive?" dialog so the wizard
        // opens directly, same as hr.employee's departure wizard (EmployeeFormController).
        const menuItems = super.getStaticActionMenuItems();
        if (this.model.root.data.contact_type === 'student') {
            menuItems.archive.callback = () => this.model.root.archive();
        }
        return menuItems;
    }
 }
 
 registry.category("views").add("studentpopup_expand_button", {
    ...formView,
    Controller: StudentPopupFormController,    
 });
