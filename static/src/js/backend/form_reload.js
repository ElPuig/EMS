/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillDestroy } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);     
        this.busService = useService("bus_service");
               
        this.myReloadListener = (payload, {id: notifyID}) => {
            const { model, record_id } = payload;
             
            // Main model (parent)
            if (this.props.resModel === model && this.model.root.resId == record_id) {
                this.model.root.load();
                return;
            }
            
            // For the children (if any)
            const fields = this.model.root.fields || {};            
            for (const fieldName in this.model.root.data) {
                const fieldDef = fields[fieldName];
                const fieldData = this.model.root.data[fieldName];
                
                if (!fieldDef || fieldDef.relation !== model || !fieldData) {
                    continue;
                }

                // One2many or Many2many child
                if (Array.isArray(fieldData.records)) {
                    const childRecord = fieldData.records.find(r => r.resId == record_id);
                    if (childRecord) {
                        if (typeof childRecord.load === "function") {
                            childRecord.load().catch(() => {}); // also update any open modal; ignore errors if record was deleted
                        }
                        this.model.root.load();
                        return;
                    }
                }
                // Many2one child
                else if (typeof fieldData.load === "function" && fieldData.resId == record_id) {
                    fieldData.load().catch(() => {}); // also update any open modal; ignore errors if record was deleted
                    this.model.root.load();
                    return;
                }
            }
        };

        this.busService.subscribe("reload_request", this.myReloadListener);
        onWillDestroy(() => {
            if (typeof this.busService.unsubscribe === "function") {
                this.busService.unsubscribe("reload_request", this.myReloadListener);
            }
        });
    }
});