/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// The 'Edit' button of the quality structure's forms (processes, procedures, documents): those
// forms open read-only, and pressing it turns the record's non-stored 'edit_mode' on, which is
// what every field's readonly="not edit_mode" follows. Saving or discarding reloads the record,
// and 'edit_mode' comes back False from the server, so the form is read-only again.
// The view hides it with invisible="edit_mode or not can_edit".
export class QualityEditModeButton extends Component {
    static template = "ems.QualityEditModeButton";
    static props = { ...standardFieldProps };

    onClick() {
        this.props.record.update({ [this.props.name]: true });
    }
}

registry.category("fields").add("ems_quality_edit_mode", {
    component: QualityEditModeButton,
    supportedTypes: ["boolean"],
});

// Shows a document inside the form, from the embeddable address EMS derives from its ordinary
// link (ems.quality.document.embed_url). Google decides what the frame shows, following the
// document's own sharing, so nothing is copied into EMS.
export class QualityDocumentPreview extends Component {
    static template = "ems.QualityDocumentPreview";
    static props = { ...standardFieldProps };

    get url() {
        return this.props.record.data[this.props.name];
    }
}

registry.category("fields").add("ems_quality_document_preview", {
    component: QualityDocumentPreview,
    supportedTypes: ["char"],
});
