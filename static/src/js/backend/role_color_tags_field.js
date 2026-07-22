/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Many2ManyTagsField, many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { HexColorTagsList } from "./hex_color_tags_list";

const DEFAULT_TAG_COLOR = "#A2A2A2";

// Relative luminance (WCAG) of the tag's own hex background decides whether its text is
// rendered in light or dark ink, so any freely-picked color (from the "color" widget on
// ems.role) stays readable instead of relying on a fixed, pre-vetted palette.
function contrastTextColor(hex) {
    const match = /^#([0-9A-Fa-f]{6})$/.exec(hex || "");
    if (!match) {
        return "#1F1F1F";
    }
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(match[1].substr(i, 2), 16) / 255);
    const toLinear = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    const luminance = 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
    return luminance > 0.45 ? "#1F1F1F" : "#FFFFFF";
}

export class RoleColorTagsField extends Many2ManyTagsField {
    static components = { ...Many2ManyTagsField.components, TagsList: HexColorTagsList };

    getTagProps(record) {
        const props = super.getTagProps(record);
        const bgColor = record.data[this.props.colorField] || DEFAULT_TAG_COLOR;
        props.bgColor = bgColor;
        props.textColor = contrastTextColor(bgColor);
        return props;
    }
}

export const roleColorTagsField = {
    ...many2ManyTagsField,
    component: RoleColorTagsField,
    supportedOptions: many2ManyTagsField.supportedOptions.map((option) =>
        option.name === "color_field" ? { ...option, availableTypes: ["char"] } : option
    ),
    relatedFields: ({ options }) => {
        const relatedFields = [{ name: "display_name", type: "char" }];
        if (options.color_field) {
            relatedFields.push({ name: options.color_field, type: "char", readonly: false });
        }
        return relatedFields;
    },
};

registry.category("fields").add("role_color_tags", roleColorTagsField);
