/** @odoo-module **/

import { Component } from "@odoo/owl";

// Issue #645: one internal arrangement plan the guard duty board detected (see
// ems.course._get_arrangement_plans): "Proposal N:" and, indented below it, its steps one per
// line, each with its checkbox on the left - moved lessons, swaps and notices to the families -
// and under a step, the entry/exit times it changes. The planner may keep only some steps (all of
// them except the notice, say), but never one without those it needs: a move into the gap another
// one leaves, a notice freeing the group from a lesson a move left free. Ticking a step ticks
// what it needs and unticking one unticks what needs it (see toggledPlanSelection); the server
// checks it again (ems.absence_cover.board_apply_plan).
export class GuardArrangementPlan extends Component {
    static template = "ems.GuardArrangementPlan";
    static props = {
        plan: Object,
        selection: Array,
        onToggle: Function,
        disabled: { type: Boolean, optional: true },
        slots: { type: Object, optional: true },
    };
}

// Every step checked: what the board proposes as a whole.
export function fullPlanSelection(plan) {
    return plan.steps.map(() => true);
}

export function toggledPlanSelection(plan, selection, index, checked) {
    const result = [...selection];
    const visit = (current) => {
        if (result[current] === checked) {
            return;
        }
        result[current] = checked;
        if (checked) {
            plan.steps[current].depends.forEach(visit);
        } else {
            plan.steps.forEach((step, other) => step.depends.includes(current) && visit(other));
        }
    };
    result[index] = !checked;
    visit(index);
    return result;
}

// What the server needs to apply the checked steps, in the plan's own order.
export function selectedPlanSteps(plan, selection) {
    return plan.steps.filter((_step, index) => selection[index]).map((step) => step.payload);
}
