/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";

// Groups a conflict-line o2m (internal_conflict_line_ids/external_conflict_line_ids) into cards
// by 'kind', then into sub-sections by 'left_label' within each kind - developer feedback
// (2026-08-10) after resolving a large real batch by hand, one row at a time: "me iría bien que
// estuvieran agrupadas por tipo... y por 'left', y que cada grupo me permitiera escoger el
// resolution que se aplica al grupo entero." Each sub-section gets its own bulk-resolution
// dropdown - picking a value there writes it onto every row in that sub-section via
// 'record.update()' (the same client-side model every other field widget already uses, so a
// picked value is immediately visible without any extra RPC), then resets itself so it never
// looks like a bound field - every row's OWN resolution dropdown right below it stays fully
// editable afterward for a one-off override, exactly like the plain list this replaces.
//
// The grouping is entirely client-side (kind/left_label are already loaded, ordinary Char/
// Selection values) - no new server method, no extra round-trip. Left/right room pickers (only
// ever relevant once a row's own resolution is 'reassign_rooms') use Odoo's generic 'AutoComplete'
// component directly (the same one the standard Many2one field widget itself is built on) rather
// than the generic per-record 'Field' component: the latter's Many2one only renders as genuinely
// editable once 'record.isInEdition' is true, which a plain o2m load never sets for a row that
// isn't the single "currently edited" row of a real list (confirmed empirically - it rendered as
// inert text, not an editable input, in a real browser) - not worth chasing given every row here
// needs to be directly editable at once, never one-row-at-a-time list editing. 'AutoComplete' has
// no such "is this row in edition" dependency at all - it is a fully self-contained input, driven
// here by a plain 'ems.space' 'name_search' RPC and writing straight onto the record via
// 'record.update()', matching exactly the '[id, display_name]' shape Many2OneField's own
// 'updateRecord()' writes.
export class EmsGroupedConflictLinesField extends Component {
    static template = "ems.GroupedConflictLinesField";
    static props = { ...standardFieldProps };
    static components = { AutoComplete };

    setup() {
        this.orm = useService("orm");
    }

    async searchSpaces(request) {
        const results = await this.orm.call("ems.space", "name_search", [], {
            name: request,
            args: [],
            limit: 8,
        });
        return results.map(([id, label]) => ({ value: id, label }));
    }

    get spaceAutocompleteSources() {
        return [{ options: (request) => this.searchSpaces(request) }];
    }

    spaceDisplayName(record, fieldName) {
        const value = record.data[fieldName];
        return value ? value[1] : "";
    }

    onSpaceSelect(record, fieldName, option) {
        record.update({ [fieldName]: [option.value, option.label] });
    }

    get labels() {
        return {
            bulkPlaceholder: _t("— apply to all —"),
            spacePlaceholder: _t("Classroom…"),
        };
    }

    // Same 4 kinds as 'ems.working_schedules_import_wizard.conflict_mixin's own 'kind' Selection,
    // in the same fixed order - a card only ever appears for a kind actually present.
    get kindLabels() {
        return {
            co_teaching_eligible: _t("Co-teaching"),
            desdoble_eligible: _t("Split session"),
            plain_conflict: _t("Room conflict"),
            self_conflict: _t("Same teacher, different room"),
        };
    }

    // Mirrors '_resolution_is_valid's own 'allowed_by_kind' server-side (models/employees/
    // working_schedule.py) - kept in sync by hand, same as the pre-existing
    // 'ems_conflict_resolution' widget's own per-kind filtering this one supersedes for these two
    // fields (that widget still drives every OTHER x2many list in this codebase, unaffected).
    get allowedResolutionsByKind() {
        return {
            co_teaching_eligible: ["co_teaching", "prevail_left", "prevail_right"],
            desdoble_eligible: ["reassign_rooms", "prevail_left", "prevail_right"],
            plain_conflict: ["reassign_rooms", "prevail_left", "prevail_right"],
            self_conflict: ["prevail_left", "prevail_right"],
        };
    }

    get resolutionLabels() {
        return {
            co_teaching: _t("Confirm"),
            prevail_left: _t("Left prevails"),
            prevail_right: _t("Right prevails"),
            reassign_rooms: _t("Reassign rooms"),
        };
    }

    resolutionOptions(kind) {
        return (this.allowedResolutionsByKind[kind] || []).map((value) => ({
            value,
            label: this.resolutionLabels[value],
        }));
    }

    get records() {
        return this.props.record.data[this.props.name].records;
    }

    // One card per 'kind' present (fixed order below), each holding one sub-section per distinct
    // 'left_label' value, in the order that value first appears - matches the developer's own
    // "agrupadas por tipo... y por left" request exactly.
    get kindGroups() {
        const groups = [];
        for (const kind of Object.keys(this.kindLabels)) {
            const kindRecords = this.records.filter((record) => record.data.kind === kind);
            if (!kindRecords.length) {
                continue;
            }
            const subgroups = [];
            const byLeftLabel = new Map();
            for (const record of kindRecords) {
                const leftLabel = record.data.left_label;
                if (!byLeftLabel.has(leftLabel)) {
                    const subgroup = { leftLabel, records: [] };
                    byLeftLabel.set(leftLabel, subgroup);
                    subgroups.push(subgroup);
                }
                byLeftLabel.get(leftLabel).records.push(record);
            }
            groups.push({ kind, label: this.kindLabels[kind], subgroups });
        }
        return groups;
    }

    onBulkApply(subgroup, ev) {
        const value = ev.target.value;
        if (!value) {
            return;
        }
        for (const record of subgroup.records) {
            record.update({ resolution: value });
        }
        ev.target.value = "";
    }

    onRowResolutionChange(record, ev) {
        record.update({ resolution: ev.target.value });
    }
}

export const emsGroupedConflictLinesField = {
    component: EmsGroupedConflictLinesField,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("ems_grouped_conflict_lines", emsGroupedConflictLinesField);
