/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FileModel } from "@web/core/file_viewer/file_model";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import {
    Many2ManyBinaryField,
    many2ManyBinaryField,
} from "@web/views/fields/many2many_binary/many2many_binary_field";

// A record's own files (models inheriting ems.attachment_mixin): the stock upload widget - one
// click, several files, each named after its file, no list of existing files to pick from - with
// three matching actions on every file: preview in Odoo's own file viewer (the chatter's, only for
// what it can show: PDF, images, text, video), download and delete. Removing a file deletes it on
// save (ems.attachment_mixin.write()).
export class EmsAttachmentsField extends Many2ManyBinaryField {
    static template = "ems.AttachmentsField";

    setup() {
        super.setup();
        this.fileViewer = useFileViewer();
    }

    get files() {
        return this.props.record.data[this.props.name].records.map((record) =>
            Object.assign(new FileModel(), {
                id: record.resId,
                name: record.data.name,
                mimetype: record.data.mimetype,
                checksum: record.data.checksum,
            })
        );
    }

    onFilePreview(file) {
        // The viewer finds the file in the list by identity, and 'files' builds new objects.
        const files = this.files;
        this.fileViewer.open(files.find((candidate) => candidate.id === file.id), files);
    }
}

export const emsAttachmentsField = {
    ...many2ManyBinaryField,
    component: EmsAttachmentsField,
    relatedFields: [...many2ManyBinaryField.relatedFields, { name: "checksum", type: "char" }],
};

registry.category("fields").add("ems_attachments", emsAttachmentsField);
