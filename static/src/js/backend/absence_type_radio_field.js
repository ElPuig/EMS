/** @odoo-module **/

import { registry } from "@web/core/registry";
import { RadioField, radioField } from "@web/views/fields/radio/radio_field";

// Every absence type is named after the original Google form's own option text, and several of
// them are a whole legal sentence. The part before the colon is the type's real name - the one
// that shows in lists, in the calendar and in emails - so it is set in bold here to give the
// reader something to scan, with the declaration they are accepting left readable after it.
export class EmsAbsenceTypeRadioField extends RadioField {
    static template = "ems.AbsenceTypeRadioField";

    labelParts(label) {
        const index = (label || "").indexOf(":");
        return index === -1 ? [label, ""] : [label.slice(0, index), label.slice(index)];
    }
}

export const emsAbsenceTypeRadioField = {
    ...radioField,
    component: EmsAbsenceTypeRadioField,
};

registry.category("fields").add("ems_absence_type_radio", emsAbsenceTypeRadioField);
