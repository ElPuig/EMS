/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

patch(ListRenderer.prototype, {
    setup() {        
        this.orm = useService("orm");
        this.action = useService("action");        
        super.setup();

        owl.onMounted(async () => {
            await this.autofocusForRadioCells();            
        });                  
    },  

    async getViewData(xml_id){
        const data = await this.orm.searchRead("ir.ui.view", [["xml_id", "=", xml_id]], ["id", "xml_id", "name"]);
        var view = data.filter(function(item){
            //TODO: the domain is not working in the orm searchRead method... WHY?
            return item.xml_id == xml_id;
        })[0];
        return view;
    },
       
    onClickCapture(record, ev){
        switch(record.resModel){
            case "ems.enrollment_view":
                ev.preventDefault();
                ev.stopPropagation();

                this.action.doAction({
                    name: "Open: Students",
                    type: "ir.actions.act_window",
                    res_model: "res.partner",
                    res_id: record.data.student_id[0],
                    views: [[this.getViewData("view_contact_form").name, "form"]],
                    view_mode: "form",
                    target: "new",
                });
            break;

            case "res.partner":
                if (ev.target.closest('.ems-tutor-enrollment-list')) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    if (record.data.ems_current_enrollment_id) {
                        this.action.doAction({
                            type: "ir.actions.act_window",
                            res_model: "sale.order",
                            res_id: record.data.ems_current_enrollment_id[0],
                            views: [[false, "form"]],
                            target: "current",
                        });
                    }
                }
            break;
        }
    },       

    async autofocusForRadioCells(){            
        var self = this;
        // TODO: should be reloaded on session change...

        // NOTE: This is fired by onMounted and all the DOM is ready and $(".o_field_cell.o_radio_cell").length != 0 BUT when saving, must be
        // fired again and $(".o_field_cell.o_radio_cell").length == 0 so, a timer is needed. 
        var intervalID = setInterval(function(){               
            const cells = document.getElementsByClassName("o_radio_cell");            
            if(cells.length != 0){
                clearInterval(intervalID);

                document.getElementsByClassName("o_form_button_save")[0].onclick = function(){
                    self.autofocusForRadioCells();
                };
                
                Array.from(document.getElementsByClassName("o_field_cell o_radio_cell")).forEach(function(element){
                    element.onmouseover = function(){
                        element.click();
                    };

                    element.onmouseout = function(){                        
                        document.getElementsByClassName("o_horizontal_separator")[0].click();
                    };
                });
            }           
        }, 100);                               
    },
});