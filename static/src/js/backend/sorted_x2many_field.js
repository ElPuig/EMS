/** @odoo-module **/

import { useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

// A list that keeps the order of its `default_order` when the form's onchange changes its rows. The
// web client adds the rows an onchange links at the end of the list, unsorted, so a computed list
// that follows what is typed (the free spaces of the reservation wizard, issue #475) would show the
// spaces that became free after the others, on the last page. The sort is the list's own (the one a column
// header click runs), so it follows `default_order` and loads the field to sort on when missing.
export class SortedX2ManyField extends X2ManyField {
    setup() {
        super.setup();
        let sorted = null; // the rows as last sorted: sorting them again would give the same
        useEffect(
            (rows) => {
                if (this.list.orderBy.length && rows !== sorted) {
                    this.list._sort().then(() => (sorted = this.list.currentIds.join(",")));
                }
            },
            () => [this.list.currentIds.join(",")]
        );
    }
}

registry.category("fields").add("ems_sorted_x2many", {
    ...x2ManyField,
    component: SortedX2ManyField,
});
