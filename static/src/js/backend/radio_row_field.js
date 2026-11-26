/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// A radio button in a list row: it chooses that row among the rows of the list. The choice is kept
// in a many2one of the form the list belongs to (options: {"chosen_field": "<its name>"}), so the
// form's own buttons can read it (a "Reserve" button enabled only once a row is chosen, in the
// space reservation wizard, issue #475). The field that hosts the widget only gives it a column.
export class EmsRadioRowField extends Component {
    static template = "ems.RadioRowField";
    static props = { ...standardFieldProps, chosenField: { type: String } };

    get chosen() {
        const chosen = this.props.record.model.root.data[this.props.chosenField];
        // A many2one is a [id, display_name] pair in the relational model.
        return Boolean(chosen) && chosen[0] === this.props.record.resId;
    }

    onChange() {
        this.props.record.model.root.update({
            [this.props.chosenField]: [this.props.record.resId, String(this.props.record.resId)],
        });
    }
}

export const emsRadioRowField = {
    component: EmsRadioRowField,
    displayName: "Radio button of a row",
    supportedTypes: ["boolean"],
    extractProps: ({ options }) => ({ chosenField: options.chosen_field }),
};

registry.category("fields").add("ems_radio_row", emsRadioRowField);
