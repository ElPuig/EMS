/** @odoo-module **/

import { registry } from "@web/core/registry";
import { htmlField } from "@html_editor/fields/html_field";
import { EmsHtmlBlockField } from "./text_blocks_field";

// Odoo's own rich text field with its code view always on hand, for a text whose HTML is prepared
// elsewhere and pasted as is (issue #774: the Erasmus+ information card, with the Bootstrap classes
// the portal already ships). Pasting rendered HTML into the editor drops the classes; the code
// view keeps them. Odoo's `codeview` option only shows that button in developer mode, which the
// Erasmus team should not need, so this widget turns it on for everyone who can edit the field.
// The toolbar is the fixed one of EmsHtmlBlockField: the button is in sight without first
// selecting some text.
export const emsHtmlCodeviewField = {
    ...htmlField,
    component: EmsHtmlBlockField,
    extractProps(fieldInfo, dynamicInfo) {
        return { ...htmlField.extractProps(fieldInfo, dynamicInfo), codeview: true };
    },
};

registry.category("fields").add("ems_html_codeview", emsHtmlCodeviewField);
