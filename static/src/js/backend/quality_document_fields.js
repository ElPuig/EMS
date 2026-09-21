/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { FormRenderer } from "@web/views/form/form_renderer";
import { formView } from "@web/views/form/form_view";

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

// Forms of the quality structure (js_class="ems_quality_form"): they always open on their first tab,
// the record's own document, whatever tab was open on the previous record. Odoo remembers the last
// tab per form (activeNotebookPages) and keeps the notebook mounted while paging, so the renderer is
// given no remembered tab and is remounted for every record.
export class QualityFormRenderer extends Component {
    static template = xml`<FormRenderer t-props="rendererProps" t-key="props.record.resId"/>`;
    static components = { FormRenderer };
    static props = ["*"];

    get rendererProps() {
        return { ...this.props, activeNotebookPages: {} };
    }
}

registry.category("views").add("ems_quality_form", {
    ...formView,
    Renderer: QualityFormRenderer,
});
