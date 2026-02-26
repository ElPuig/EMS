/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onWillDestroy } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.busService = useService("bus_service");

        // Escuchamos los mensajes del bus
        const onMessage = (payload) => {
            for (const { type, payload: message } of payload) {
                if (type === "update_request") {
                    // Si el mensaje es para el registro que tenemos abierto en pantalla...
                    if (this.model.root.resId === message.record_id) {
                        // ... ¡Recargamos la vista!
                        this.model.root.load();
                    }
                }
            }
        };

        // Suscribirse al iniciar y desuscribirse al destruir el componente
        this.busService.addEventListener("notification", onMessage);
        
        onWillDestroy(() => {
            this.busService.removeEventListener("notification", onMessage);
        });
    }
});