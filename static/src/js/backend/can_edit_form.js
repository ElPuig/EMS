/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

// Whoever may only read the record (an attendee, a department colleague) gets it as plain
// reading, not fields that the save would then refuse. Decided per record, on every load, since
// the pager moves between records this user may and may not write. The model provides can_edit
// (ems.quality.can.edit).
export class EmsCanEditFormController extends FormController {
    get modelParams() {
        const params = super.modelParams;
        params.hooks.onRootLoaded = () => {
            const record = this.model.root;
            const mode = record.isNew || record.data.can_edit ? "edit" : "readonly";
            if (this.canEdit && record.config.mode !== mode) {
                record._switchMode(mode);
            }
        };
        return params;
    }
}

registry.category("views").add("ems_can_edit_form", { ...formView, Controller: EmsCanEditFormController });
