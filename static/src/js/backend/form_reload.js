/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onWillDestroy } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);        
        this.busService = useService("bus_service");

        this.busService.subscribe("reload_request", (payload, {id: notifyID}) => {
            console.log("-> onMessage")
             const {record_id: record_id, message: message} = payload;
             if (this.model.root.resId === record_id) {
                this.model.root.load();
            }
        });

        this.busService.start();
    }
});