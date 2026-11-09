/** @odoo-module **/

import { registry } from "@web/core/registry";
import { IntegerField, integerField } from "@web/views/fields/integer/integer_field";

// An integer whose 0 means "nothing here": no limit, no data, not known (issue #778). The cell or
// input stays empty, and in an input the view's placeholder says what that means. Odoo's integer
// widget always prints the 0 and has no option for it; hiding the value with `invisible` would also
// hide the input of an editable list's row. The stored value is untouched (an empty input is 0).
export class EmsBlankZeroField extends IntegerField {
    get formattedValue() {
        return this.value === 0 ? "" : super.formattedValue;
    }
}

registry.category("fields").add("ems_blank_zero", { ...integerField, component: EmsBlankZeroField });
