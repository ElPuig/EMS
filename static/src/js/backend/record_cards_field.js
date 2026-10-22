/** @odoo-module **/

import { Component } from "@odoo/owl";
import { makeContext } from "@web/core/context";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { Field } from "@web/views/fields/field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// <Field> makes every field of a one2many line read-only unless the line is the one "being
// edited", which is how the rows of a list work: one at a time. In a card every field of every
// line is open at once, so this one only follows the field's own readonly, as a form does.
export class EmsOpenField extends Field {
    get fieldComponentProps() {
        const props = super.fieldComponentProps;
        let readonly = this.props.readonly || false;
        if (this.props.fieldInfo) {
            readonly = readonly || evaluateBooleanExpr(this.props.fieldInfo.readonly, this.props.record.evalContextWithVirtualIds);
        }
        return { ...props, readonly };
    }
}

// A one2many shown as cards, one per line: a short header with the brief facts (a code, a date,
// who is responsible) and, underneath, the texts at full width. For lines whose point is what
// they say - an agreement, what a meeting said about it - a list gives the text one narrow
// column among many.
//
// The embedded <list> in the arch declares the lines' fields, each with the widget and attributes
// it would have in a list; the options say where each goes: header_fields, body_fields, can_add,
// can_delete.
export class EmsRecordCardsField extends Component {
    static template = "ems.RecordCardsField";
    static components = { EmsOpenField };
    static props = {
        ...standardFieldProps,
        headerFields: { type: Array },
        bodyFields: { type: Array },
        canAdd: { type: Boolean, optional: true },
        canDelete: { type: Boolean, optional: true },
        context: { type: Object, optional: true },
        subFieldNodes: { type: Object, optional: true },
    };

    get list() {
        return this.props.record.data[this.props.name];
    }

    get addLabel() {
        return _t("Add");
    }

    get deleteLabel() {
        return _t("Remove");
    }

    fieldInfo(fieldName) {
        return Object.values(this.props.subFieldNodes || {}).find((node) => node.name === fieldName);
    }

    label(fieldName) {
        const info = this.fieldInfo(fieldName);
        return (info && info.string) || this.list.fields[fieldName].string;
    }

    async add() {
        await this.list.addNewRecord({ position: "bottom", context: makeContext([this.props.context]) });
    }

    remove(line) {
        this.list.delete(line);
    }
}

export const emsRecordCardsField = {
    component: EmsRecordCardsField,
    supportedTypes: ["one2many"],
    useSubView: true,
    extractProps: ({ options, views }, dynamicInfo) => ({
        headerFields: options.header_fields || [],
        bodyFields: options.body_fields || [],
        canAdd: Boolean(options.can_add),
        canDelete: Boolean(options.can_delete),
        context: dynamicInfo.context,
        subFieldNodes: (views && views.list && views.list.fieldNodes) || {},
    }),
};

registry.category("fields").add("ems_record_cards", emsRecordCardsField);
