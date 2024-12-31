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
 }
 
 registry.category("views").add("studentpopup_expand_button", {
    ...formView,
    Controller: StudentPopupFormController,    
 });
