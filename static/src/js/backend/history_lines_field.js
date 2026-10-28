/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

// A student's academic history in one list (issue #672): its lines (ems.student.history_line) are a
// read-only view joining the courses of the history and the previous curriculum records. Clicking a
// line opens the record behind it, not the line itself, and reloads the form when it is closed, in
// case it was corrected (a grade review, a previous curriculum record edited).
export class HistoryLinesField extends X2ManyField {
    setup() {
        super.setup();
        this.action = useService("action");
    }

    async openRecord(record) {
        await this.action.doActionButton({
            type: "object",
            name: "action_open_record",
            resModel: record.resModel,
            resId: record.resId,
            onClose: () => this.props.record.load(),
        });
    }
}

registry.category("fields").add("ems_history_lines", {
    ...x2ManyField,
    component: HistoryLinesField,
});
