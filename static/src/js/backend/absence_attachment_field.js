/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import {
    Many2ManyBinaryField,
    many2ManyBinaryField,
} from "@web/views/fields/many2many_binary/many2many_binary_field";

// The stock attachment widget drops a file the moment its "x" is clicked, with no confirmation
// and no undo. On an absence that file is the justification for the absence itself - often the
// only copy of a medical certificate the employee handed in - and the people most likely to
// click it (the absence manager and Direction) are reviewing dozens of requests in a row.
// Same widget in every respect, one confirmation dialog in front of the removal.
export class EmsConfirmedAttachmentField extends Many2ManyBinaryField {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    async onFileRemove(deleteId) {
        const file = this.props.record.data[this.props.name].records.find(
            (record) => record.resId === deleteId
        );
        this.dialog.add(ConfirmationDialog, {
            title: _t("Remove the supporting document"),
            body: _t(
                "\"%s\" will be removed from this absence. This cannot be undone.",
                file ? file.data.name : ""
            ),
            confirmLabel: _t("Remove"),
            confirm: () => super.onFileRemove(deleteId),
            cancel: () => {},
        });
    }
}

export const emsConfirmedAttachmentField = {
    ...many2ManyBinaryField,
    component: EmsConfirmedAttachmentField,
};

registry.category("fields").add("ems_attachment_confirm", emsConfirmedAttachmentField);
