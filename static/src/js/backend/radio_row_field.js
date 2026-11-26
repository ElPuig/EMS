/** @odoo-module **/

import { Component, useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// A radio button in a list row: it chooses that row among the rows of the list, and so does a
// click anywhere on the row (the chosen row is highlighted). The choice is kept in a many2one of
// the form the list belongs to (options: {"chosen_field": "<its name>"}), so the form's own
// buttons can read it (a "Reserve" button enabled only once a row is chosen, in the space
// reservation wizard, issue #475). The field that hosts the widget only gives it a column; a row
// where the field is invisible has no widget and cannot be chosen.
export class EmsRadioRowField extends Component {
    static template = "ems.RadioRowField";
    static props = { ...standardFieldProps, chosenField: { type: String } };

    setup() {
        this.radio = useRef("radio");
        useEffect(
            (chosen) => {
                const row = this.radio.el && this.radio.el.closest(".o_data_row");
                if (!row) {
                    return;
                }
                const choose = () => this.onChange();
                row.classList.add("cursor-pointer");
                row.classList.toggle("table-active", chosen);
                row.addEventListener("click", choose);
                return () => {
                    row.classList.remove("cursor-pointer", "table-active");
                    row.removeEventListener("click", choose);
                };
            },
            () => [this.chosen]
        );
    }

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
