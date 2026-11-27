/** @odoo-module **/

import { registry } from "@web/core/registry";
import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";

/**
 * A selection dropdown offering only some of its values, which depend on the record (issue #878:
 * an evaluation session moves only to the previous or the next state). A selection field's options
 * are the same for every record; the record gives its own, comma-separated, in the field named by
 * the `allowed_field` option. An empty value offers them all. The current value is always kept,
 * so the field can still display it.
 */
export class SelectionAllowedField extends SelectionField {
    static props = { ...SelectionField.props, allowedField: { type: String } };

    get options() {
        const allowed = (this.props.record.data[this.props.allowedField] || "").split(",").filter(Boolean);
        const options = super.options;
        if (!allowed.length) {
            return options;
        }
        const current = this.props.record.data[this.props.name];
        return options.filter(([value]) => value === current || allowed.includes(value));
    }
}

registry.category("fields").add("ems_selection_allowed", {
    ...selectionField,
    component: SelectionAllowedField,
    supportedTypes: ["selection"],
    fieldDependencies: ({ options }) => [{ name: options.allowed_field, type: "char" }],
    extractProps: (fieldInfo, dynamicInfo) => ({
        ...selectionField.extractProps(fieldInfo, dynamicInfo),
        allowedField: fieldInfo.options.allowed_field,
    }),
});
