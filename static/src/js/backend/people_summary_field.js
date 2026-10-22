/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// A many2many of people in a list cell: their names while they are few, and past that just how
// many they are, with every name in the tooltip and a click that opens the record they belong to.
// A whole department responsible for an agreement would otherwise make its row thirty lines tall.
//
// Options: limit (default 3), open_field (a many2one of the line) and open_model (its model).
export class EmsPeopleSummaryField extends Component {
    static template = "ems.PeopleSummaryField";
    static props = {
        ...standardFieldProps,
        limit: { type: Number, optional: true },
        openField: { type: String, optional: true },
        openModel: { type: String, optional: true },
    };

    setup() {
        this.action = useService("action");
    }

    get names() {
        return this.props.record.data[this.props.name].records.map((person) => person.data.display_name);
    }

    get isLong() {
        return this.names.length > (this.props.limit || 3);
    }

    get countLabel() {
        return _t("%s people", this.names.length);
    }

    get tooltip() {
        return this.names.join("\n");
    }

    open() {
        const target = this.props.openField && this.props.record.data[this.props.openField];
        if (target && this.props.openModel) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: this.props.openModel,
                res_id: target[0],
                views: [[false, "form"]],
                target: "new",
            });
        }
    }
}

export const emsPeopleSummaryField = {
    component: EmsPeopleSummaryField,
    supportedTypes: ["many2many"],
    relatedFields: [{ name: "display_name", type: "char" }],
    extractProps: ({ options }) => ({
        limit: options.limit,
        openField: options.open_field,
        openModel: options.open_model,
    }),
};

registry.category("fields").add("ems_people_summary", emsPeopleSummaryField);
