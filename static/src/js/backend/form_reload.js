/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillDestroy } from "@odoo/owl";

// When a child's reload_request fires we reload the child in-place (so any open modal for that
// record — which holds a JS reference to the same object — also updates). We deliberately avoid
// reloading the full parent here: that would replace fieldData.records with brand-new objects,
// breaking the modal's reference on every subsequent save.
// Instead we register a parent-reload callback keyed by "model:id" and fire it once, from
// onWillDestroy, when the child's FormController (i.e. the modal) is eventually closed.
const _pendingParentReload = new Map(); // "model:id" → () => void

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
                            // Reload child in-place so the open modal also updates.
                            // On failure (e.g. deleted record) fall back to a full parent reload.
                            childRecord.load().catch(() => { this.model.root.load(); });

                            // Schedule a full parent reload for when the modal closes.
                            _pendingParentReload.set(`${model}:${record_id}`, () => {
                                try { this.model.root.load(); } catch(e) {}
                            });
                        } else {
                            this.model.root.load();
                        }
                        return;
                    }
                }
                // Many2one child
                else if (typeof fieldData.load === "function" && fieldData.resId == record_id) {
                    fieldData.load().catch(() => { this.model.root.load(); });
                    return;
                }
            }
        };

        this.busService.subscribe("reload_request", this.myReloadListener);
        onWillDestroy(() => {
            // Fire the pending parent-reload callback (if any) when this form is closed.
            const key = `${this.props.resModel}:${this.model.root?.resId}`;
            const cb = _pendingParentReload.get(key);
            if (cb) {
                _pendingParentReload.delete(key);
                cb();
            }

            if (typeof this.busService.unsubscribe === "function") {
                this.busService.unsubscribe("reload_request", this.myReloadListener);
            }
        });
    }
});
