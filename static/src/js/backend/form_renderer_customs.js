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
        var model = self.props.record.model.config.resModel;
        var id = self.props.record.model.config.resId;

        owl.onMounted(async function(){
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

        if(model === 'res.partner'){
            function annotateRows() {
                const records = self.props.record.data.relation_all_ids?.records || [];
                document.querySelectorAll('.relation_all_list .o_data_row').forEach((row, i) => {
                    if(records[i]) row.dataset.relationId = records[i].resId;
                });
            }
            owl.onMounted(annotateRows);
            owl.onPatched(annotateRows);

            const clickHandler = async function(event) {
                const row = event.target.closest('.relation_all_list .o_data_row');
                if(!row) return;
                if(event.target.closest('button')) return;
                event.stopPropagation();

                annotateRows();
                const relationId = parseInt(row.dataset.relationId);
                if(!relationId) return;

                const result = await self.orm.read('res.partner.relation.all', [relationId], ['other_partner_id']);
                if(!result || !result[0] || !result[0].other_partner_id) return;

                self.action.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'res.partner',
                    res_id: result[0].other_partner_id[0],
                    views: [[false, "form"]],
                    target: 'current'
                });
            };
            document.addEventListener('click', clickHandler, true);
            owl.onWillUnmount(function() {
                document.removeEventListener('click', clickHandler, true);
            });
        }     
    }       
});