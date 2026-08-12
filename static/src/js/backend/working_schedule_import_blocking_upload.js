/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import {
    Many2ManyBinaryField,
    many2ManyBinaryField,
} from "@web/views/fields/many2many_binary/many2many_binary_field";

// The working-schedule import wizard's onchange (_onchange_attachment_ids in
// models/employees/working_schedule.py) parses the whole XML schedule server-side, slow enough -
// with zero visual feedback otherwise - that it looks like the wizard has hung (reported
// 2026-08-01: "parece que se haya colgado"). Odoo's own block-UI overlay
// (env.services.ui.block()/.unblock(), the same mechanism already used natively for long button
// actions) is reused here rather than a bespoke spinner - it already renders a spinner + a
// message, wrapped around exactly the RPC that's actually slow (the file-triggered onchange),
// not the whole form.
const LOADING_MESSAGE = _t("Reading and validating the schedule file, please wait...");

export class EmsBlockingMany2ManyBinaryField extends Many2ManyBinaryField {
    setup() {
        super.setup();
        this.ui = useService("ui");
    }

    async onFileUploaded(files) {
        this.ui.block({ message: LOADING_MESSAGE });
        try {
            return await super.onFileUploaded(files);
        } finally {
            this.ui.unblock();
        }
    }
}

export const emsBlockingMany2ManyBinaryField = {
    ...many2ManyBinaryField,
    component: EmsBlockingMany2ManyBinaryField,
};
registry.category("fields").add("ems_blocking_many2many_binary", emsBlockingMany2ManyBinaryField);
