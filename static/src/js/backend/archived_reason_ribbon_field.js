/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";

// Default color when no per-record color is set (departure_reason_id.color left empty on
// e.g. "Fired", or a student's archived_reason_color deliberately False for "Expelled") -
// matches the plain "Archived" ribbon's usual look elsewhere in the app (Bootstrap's own
// --bs-danger red).
const DEFAULT_COLOR = "#dc3545";

// Shared by ems.group (Archived), res.partner (Alumni/Withdrawal/Expelled) and hr.employee
// (whatever hr.departure.reason is set) - reuses web.Ribbon's own DOM structure/CSS classes
// (.ribbon/.ribbon-top-right, loaded globally by the web module) so it renders identically to
// the native ribbon, but its text AND color both come from the field(s) it is bound to instead
// of a static XML attribute - web.Ribbon's own "title" is read once at view-compile time and
// can't follow a record's live value (see web/static/src/views/widgets/ribbon/ribbon.js).
export class ArchivedReasonRibbonField extends Component {
    static template = "ems.ArchivedReasonRibbonField";
    static props = { ...standardFieldProps, colorField: { type: String, optional: true } };

    get text() {
        return this.props.record.data[this.props.name];
    }

    get colorHex() {
        const colorField = this.props.colorField;
        return (colorField && this.props.record.data[colorField]) || DEFAULT_COLOR;
    }
}

export const archivedReasonRibbonField = {
    component: ArchivedReasonRibbonField,
    supportedOptions: [
        {
            label: _t("Color field"),
            name: "color_field",
            type: "field",
            availableTypes: ["char"],
        },
    ],
    extractProps: ({ options }) => ({
        colorField: options.color_field,
    }),
    // Ensures the color field is fetched even though it's never declared as its own <field/>
    // in the view - same mechanism already used by role_color_tags_field.js's "color_field"
    // option, avoids the "must separately declare every field a kanban template touches" trap
    // hit earlier in this same view family (hr.employee's kanban badge work).
    relatedFields: ({ options }) => {
        const relatedFields = [];
        if (options.color_field) {
            relatedFields.push({ name: options.color_field, type: "char", readonly: false });
        }
        return relatedFields;
    },
};

registry.category("fields").add("ems_archived_reason_ribbon", archivedReasonRibbonField);
