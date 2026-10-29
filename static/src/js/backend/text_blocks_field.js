/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { HtmlField, htmlField } from "@html_editor/fields/html_field";

// Odoo's own rich text field, with its toolbar fixed above the text instead of popping up on a
// selection: whoever takes the minute should see bold, lists and tables without knowing the trick.
export class EmsHtmlBlockField extends HtmlField {
    static template = "ems.HtmlBlockField";
}

// A one2many shown as a column of blocks, one per line: its title and, underneath, a text of its
// own with the full editor. It is how a minute is written while the meeting goes on: a list would
// squeeze each text into a table cell, and a dialog per line would put two clicks between every
// item and what is said about it.
//
// Each line's fields are Odoo's own field components (the rich text field, the char field) fed with
// the line's record, so the editor and the way changes reach the form's save are Odoo's, not ours.
// They are used directly rather than through <Field>: that one makes every field of a one2many line
// read-only unless the line is the single one "being edited", as rows of a list are, and here every
// block is open for writing at once. The embedded <list> in the arch only declares the lines' fields.
//
// Options: title_field (default 'name'), body_field, filter_field (a boolean of the line: only the
// lines where it is set get a block), title_editable, can_add, can_delete, numbered.
export class EmsTextBlocksField extends Component {
    static template = "ems.TextBlocksField";
    static components = { CharField, EmsHtmlBlockField };
    static props = {
        ...standardFieldProps,
        titleField: { type: String },
        bodyField: { type: String },
        filterField: { type: String, optional: true },
        titleEditable: { type: Boolean, optional: true },
        canAdd: { type: Boolean, optional: true },
        canDelete: { type: Boolean, optional: true },
        numbered: { type: Boolean, optional: true },
        subFieldNodes: { type: Object, optional: true },
    };

    get list() {
        return this.props.record.data[this.props.name];
    }

    get lines() {
        const filterField = this.props.filterField;
        return this.list.records.filter((line) => !filterField || line.data[filterField]);
    }

    get addLabel() {
        return _t("Add an item");
    }

    get deleteLabel() {
        return _t("Remove this item");
    }

    /** The arch's own description of a line's field, so it gets what it declares there. */
    fieldInfo(fieldName) {
        return Object.values(this.props.subFieldNodes || {}).find((node) => node.name === fieldName) || {};
    }

    get titlePlaceholder() {
        return (this.fieldInfo(this.props.titleField).attrs || {}).placeholder;
    }

    /** What the rich text field takes from its node (placeholder, editor options), as a form would give it. */
    get bodyProps() {
        const info = this.fieldInfo(this.props.bodyField);
        return htmlField.extractProps(
            { attrs: info.attrs || {}, options: info.options || {} },
            { readonly: this.props.readonly }
        );
    }

    async add() {
        await this.list.addNewRecord({ position: "bottom" });
    }

    remove(line) {
        this.list.delete(line);
    }
}

export const emsTextBlocksField = {
    component: EmsTextBlocksField,
    supportedTypes: ["one2many"],
    useSubView: true,
    extractProps: ({ options, views }) => ({
        titleField: options.title_field || "name",
        bodyField: options.body_field,
        filterField: options.filter_field,
        titleEditable: Boolean(options.title_editable),
        canAdd: Boolean(options.can_add),
        canDelete: Boolean(options.can_delete),
        numbered: Boolean(options.numbered),
        subFieldNodes: (views && views.list && views.list.fieldNodes) || {},
    }),
};

registry.category("fields").add("ems_text_blocks", emsTextBlocksField);
