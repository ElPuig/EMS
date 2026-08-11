/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";

// Groups a conflict-line o2m (internal_conflict_line_ids/external_conflict_line_ids) into cards
// by 'kind', then into sub-sections by 'left_group_key' within each kind - developer feedback
// (2026-08-10) after resolving a large real batch by hand, one row at a time: "me iría bien que
// estuvieran agrupadas por tipo... y por 'left', y que cada grupo me permitiera escoger el
// resolution que se aplica al grupo entero." Each sub-section gets its own bulk-resolution
// dropdown - picking a value there writes it onto every row in that sub-section via
// 'record.update()' (the same client-side model every other field widget already uses, so a
// picked value is immediately visible without any extra RPC), then resets itself so it never
// looks like a bound field - every row's OWN resolution dropdown right below it stays fully
// editable afterward for a one-off override, exactly like the plain list this replaces.
//
// 'left_group_key' (teacher + subject, server-side '_entry_group_key') supersedes 'left_label'
// (teacher + subject + group + weekday + time) as the sub-section KEY, not just its display text -
// developer feedback the same day, after seeing the first version rendered for real: grouping by
// the full label produced one sub-section per row in practice, since two different conflicts
// almost never share the exact same group/weekday/time too, only rarely the same teacher+subject.
// The row itself keeps showing the FULL 'left_label'/'right_label' (never trimmed down to "just
// the diff") since the right side's own teacher/subject can genuinely differ from the left's
// (e.g. a plain room clash between two unrelated classes) - only the grouping key is coarser, not
// what a row displays.
//
// Also developer feedback (2026-08-10, after using the grouped view for real): plain "left"/
// "right" text with no label read as arbitrary - unlike the OLD list's own two dedicated columns
// (labeled "File"/"File" or "File"/"Database" as column HEADERS), a row here has no header of its
// own to carry that meaning. Fixed by never showing the bare words "left"/"right" in the UI at
// all: on "File conflicts" (internal - both sides are file entries, so there is no asymmetry
// worth naming) a row just joins the two full descriptions with "vs."; on "Existing schedule
// conflicts" (external - genuinely asymmetric) each side is explicitly prefixed "File:"/
// "Database:", reusing the exact words the old column headers already used.
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
        // A plain x2many o2m only materializes its FIRST page of records client-side
        // ('StaticList.records' is 'data.slice(offset, limit)' - see 'relational_model.js'/
        // 'static_list.js') even though 'list.count' already reflects the TRUE total. This widget
        // renders no pager of its own to reach anything past that first page (unlike the native
        // Odoo list it replaces), so it must load every record itself before ever showing "you're
        // done" - developer feedback (2026-08-10) after a fixed 'limit="1000"' on the arch just
        // moved the same silent-Continue-stuck bug to whatever number was picked: "si tuviéramos
        // más de 1000 conflictos estaríamos en las mismas... ¿no se puede paginar, o de alguna
        // otra forma?" Fixed properly instead: no arch-level limit at all - 'list.load({ limit:
        // list.count })' (the exact same public API Odoo's own pager calls on "next page", see
        // 'x2many_field.js's 'pagerProps.onUpdate') asks for however many records actually exist,
        // whatever that number is, so there is no cap left to outgrow.
        onWillStart(() => this._ensureAllRecordsLoaded());
    }

    async _ensureAllRecordsLoaded() {
        const list = this.props.record.data[this.props.name];
        if (list.records.length < list.count) {
            await list.load({ limit: list.count, offset: 0 });
        }
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
            filePrefix: _t("File"),
            databasePrefix: _t("Database"),
        };
    }

    // 'external_conflict_line_ids' is genuinely asymmetric (file entry vs. an already-active DB
    // session) - 'internal_conflict_line_ids' isn't (both sides are file entries), so only the
    // former gets explicit "File:"/"Database:" prefixes on each row (see the file's own top
    // comment for why plain, unlabeled "left"/"right" was dropped from the UI entirely).
    get isExternal() {
        return this.props.name === "external_conflict_line_ids";
    }

    rowText(record) {
        if (this.isExternal) {
            return `${this.labels.filePrefix}: ${record.data.left_label}   -   ${this.labels.databasePrefix}: ${record.data.right_label}`;
        }
        return `${record.data.left_label}   vs.   ${record.data.right_label}`;
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
    // 'left_group_key' value (teacher + subject, coarser than the full 'left_label' - see the
    // file's own top comment), in the order that value first appears - matches the developer's
    // own "agrupadas por tipo... y por left" request.
    get kindGroups() {
        const groups = [];
        for (const kind of Object.keys(this.kindLabels)) {
            const kindRecords = this.records.filter((record) => record.data.kind === kind);
            if (!kindRecords.length) {
                continue;
            }
            const subgroups = [];
            const byGroupKey = new Map();
            for (const record of kindRecords) {
                const groupKey = record.data.left_group_key;
                if (!byGroupKey.has(groupKey)) {
                    const subgroup = { groupKey, records: [] };
                    byGroupKey.set(groupKey, subgroup);
                    subgroups.push(subgroup);
                }
                byGroupKey.get(groupKey).records.push(record);
            }
            groups.push({ kind, label: this.kindLabels[kind], subgroups });
        }
        return groups;
    }

    // Found while empirically verifying this scales past a couple of rows (2026-08-10, developer
    // question: "si tuviéramos más de 1000 conflictos estaríamos en las mismas... ¿de alguna otra
    // forma?", tested with an 85-row tour fixture - safely past Odoo's own x2many page-size default
    // of 80): plain 'record.update({ resolution: value })' triggers a genuine server 'onchange' RPC
    // per call ('resolution' is a dependency of the wizard's own invisible 'continue_disabled'
    // field present in the same view, so Odoo's arch-level onchange-spec builder marks it needing a
    // round-trip on every edit, regardless of there being an explicit '@api.onchange') - firing that
    // sequentially for every record in a large sub-group made bulk-apply itself the new bottleneck
    // once the widget's own full-record-load fix stopped hiding rows past that count.
    //
    // Fix: 'Record._update()' (the private method the public 'update()' wraps) accepts
    // 'withoutOnchange'/'withoutParentUpdate' directly - the public wrapper only ever sets the
    // former, and only via a 'save' flag that ALSO force-saves the record early, not something this
    // deferred-write wizard wants. Both flags are needed, not just 'withoutOnchange' alone: a
    // nested record's own 'onUpdate' callback (wired up by 'StaticList._createRecordDatapoint', a
    // SEPARATE mechanism from the line's own field-level onchange) independently notifies the
    // PARENT (wizard) record's own onchange too unless told not to - confirmed by reading that
    // callback directly in 'static_list.js'. Skip both for every record but the last (still applies
    // + re-renders each row's own value locally, and still queues its own write command for the
    // eventual Continue/Import save - 'StaticList' pushes that command before the parent-
    // notification check, so nothing here is lost) - the one real RPC, on the final record, already
    // carries every already-applied sibling change along with it (an x2many sub-record's onchange
    // payload includes its own parent's current full pending state, not just this one row's own
    // delta - confirmed by reading 'Record._getOnchangeValues()'), so 'continue_disabled' still ends
    // up correctly recomputed from the FULL, final state in that single round-trip.
    //
    // A more aggressive follow-up (bypassing '_update()' entirely for non-final records via
    // 'Record._applyChanges()' plus manually replicating its 'dirty'/'_commands' bookkeeping, to
    // additionally batch the 84 local mutations into a single OWL render instead of 84) was tried
    // and REVERTED (2026-08-10) - it introduced a new, unexplained regression where the final
    // record's onchange RPC completed successfully (confirmed in server logs) but the client never
    // reflected the result, with no thrown error to explain why. Reaching that deep into private,
    // undocumented reactivity internals for a scenario this extreme (85 rows resolved in a single
    // click, far past anything a real EMS import is likely to produce) traded a correctness risk
    // for a speed gain in an edge case - not a good trade. This version is the one confirmed
    // correct: still real per-row local re-renders (bounded, not free), but no unexplained failures
    // across repeated runs. Wrapped in the model's own mutex (same serialization the public
    // 'update()' wrapper provides) since this bypasses it to reach these two options directly.
    async onBulkApply(subgroup, ev) {
        const value = ev.target.value;
        if (!value) {
            return;
        }
        const records = subgroup.records;
        await this.props.record.model.mutex.exec(async () => {
            for (const record of records.slice(0, -1)) {
                await record._update(
                    { resolution: value },
                    { withoutOnchange: true, withoutParentUpdate: true }
                );
            }
            const last = records[records.length - 1];
            if (last) {
                await last._update({ resolution: value });
            }
        });
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
