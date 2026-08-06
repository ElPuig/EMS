/** @odoo-module **/

import { registry } from "@web/core/registry";
import { selectionField, SelectionField } from "@web/views/fields/selection/selection_field";

// 'resolution's own 'co_teaching' ("Confirm") option only makes sense for a
// 'co_teaching_eligible' conflict line (see 'ems.working_schedules_import_wizard.
// conflict_mixin') - showing it for e.g. a genuine "Room conflict" is actively confusing, even
// though picking it there already raised server-side via '_resolution_is_valid' (developer
// feedback 2026-08-06). Odoo's Selection field has no declarative, per-record way to vary its own
// options within the same list (the options list is defined once per field, not per row), so this
// narrow widget override is the one genuinely necessary bit of custom JS here - it only ever hides
// 'co_teaching', nothing else; every other option stays available for every kind, unchanged.
export class EmsConflictResolutionField extends SelectionField {
    get options() {
        const options = super.options;
        if (this.props.record.data.kind === "co_teaching_eligible") {
            return options;
        }
        return options.filter((option) => option[0] !== "co_teaching");
    }
}

export const emsConflictResolutionField = {
    ...selectionField,
    component: EmsConflictResolutionField,
};

registry.category("fields").add("ems_conflict_resolution", emsConflictResolutionField);
