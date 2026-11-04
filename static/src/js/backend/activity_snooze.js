/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component } from "@odoo/owl";
import { serverNow } from "./server_clock";

// Snoozing a task (issue #727), in My Activities: a bell on each row opens a popover with 1, 3
// or 7 days, and the list header's "Snooze" offers the same for the selected tasks in a small
// dialog. The server moves the due date (mail.activity.action_ems_snooze, models/shared/
// mail_activity.py). See docs/en/developers/shared/daily_summary.md.
const SNOOZE_DAYS = [1, 3, 7];

// The three choices. With one task's `deadline`, each shows the date it would move to, by the
// server's rule: the later of today and the due date, plus the days. "Today" is the server's
// (serverNow), never the computer's clock.
export class EmsSnoozeChoices extends Component {
    static template = "ems.SnoozeChoices";
    static props = {
        onChoose: Function,
        deadline: { type: [Object, { value: false }], optional: true },
    };

    get choices() {
        const today = serverNow().startOf("day");
        const deadline = this.props.deadline && this.props.deadline.startOf("day");
        const from = deadline && deadline > today ? deadline : today;
        return SNOOZE_DAYS.map((days) => ({
            days,
            label: days === 1 ? _t("1 day") : _t("%s days", days),
            date: this.props.deadline ? from.plus({ days }).toFormat("ccc d/L") : "",
        }));
    }
}

class EmsSnoozePopover extends Component {
    static template = "ems.SnoozePopover";
    static components = { EmsSnoozeChoices };
    static props = { deadline: { optional: true }, onChoose: Function, close: Function };

    choose(days) {
        this.props.close();
        this.props.onChoose(days);
    }
}

// The row's bell.
export class EmsActivitySnooze extends Component {
    static template = "ems.ActivitySnooze";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.popover = usePopover(EmsSnoozePopover, { position: "bottom-end" });
    }

    get isActive() {
        return this.props.record.data.active !== false;
    }

    onClick(ev) {
        if (this.popover.isOpen) {
            this.popover.close();
            return;
        }
        this.popover.open(ev.currentTarget, {
            deadline: this.props.record.data.date_deadline,
            onChoose: (days) => this.snooze(days),
        });
    }

    async snooze(days) {
        const record = this.props.record;
        await this.orm.call("mail.activity", "action_ems_snooze", [[record.resId], days]);
        await record.model.load();
    }
}

registry.category("view_widgets").add("ems_activity_snooze", {
    component: EmsActivitySnooze,
    fieldDependencies: [
        { name: "date_deadline", type: "date" },
        { name: "active", type: "boolean" },
    ],
    listViewWidth: 32,
});

// The list header's "Snooze", for the selected tasks (mail.activity.action_ems_snooze_dialog).
export class EmsActivitySnoozeDialog extends Component {
    static template = "ems.ActivitySnoozeDialog";
    static components = { EmsSnoozeChoices };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    async snooze(days) {
        const ids = this.props.action.params.activity_ids;
        await this.orm.call("mail.activity", "action_ems_snooze", [ids, days]);
        await this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("actions").add("ems.activity_snooze_dialog", EmsActivitySnoozeDialog);
