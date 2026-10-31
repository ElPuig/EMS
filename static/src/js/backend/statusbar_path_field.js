/** @odoo-module **/

import { registry } from "@web/core/registry";
import { StatusBarField, statusBarField } from "@web/views/fields/statusbar/statusbar_field";

/**
 * A status bar showing the steps a record really went through, ending in its current state, plus
 * the ones still ahead of it (issue #735). A plain status bar only takes a fixed list of steps
 * (statusbar_visible), the same for every record: a detected absence corrected straight from the
 * review and one corrected after a justification was asked for need different ones. The record
 * gives its own, comma-separated, in the field named by the `path_field` option.
 */
export class StatusBarPathField extends StatusBarField {
    static props = { ...StatusBarField.props, pathField: { type: String } };

    getAllItems() {
        const path = (this.props.record.data[this.props.pathField] || "").split(",");
        return super.getAllItems().filter((item) => item.isSelected || path.includes(item.value));
    }
}

registry.category("fields").add("ems_statusbar_path", {
    ...statusBarField,
    component: StatusBarPathField,
    supportedTypes: ["selection"],
    // The native status bar's look, which Odoo's styles hang on this class.
    additionalClasses: ["o_field_statusbar"],
    fieldDependencies: ({ options }) => [{ name: options.path_field, type: "char" }],
    extractProps: (fieldInfo, dynamicInfo) => ({
        ...statusBarField.extractProps(fieldInfo, dynamicInfo),
        visibleSelection: undefined,
        pathField: fieldInfo.options.path_field,
    }),
});
