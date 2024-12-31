/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { useService } from "@web/core/utils/hooks";

patch(FormRenderer.prototype, {
    setup() {        
        this.orm = useService("orm");
        this.action = useService("action");
        super.setup();

        var self = this;
        owl.onMounted(function(){
            var model = self.props.record.model.config.resModel;
            var id = self.props.record.model.config.resId;
            var allowed = ["ems.content", "ems.outcome", "ems.subject"]

            if(allowed.includes(model)){
                const items = document.getElementsByClassName("o_expand_button");            
                if(items.length > 0){                
                    items[0].onclick = function() { 
                        self.action.doAction({
                            type: 'ir.actions.act_window',
                            res_model: model,                
                            res_id: id,
                            views: [[false, "form"]],                               
                            target: 'current'
                        });
                    };                 
                }  
            }          
        });     
    }       
});