/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component } from "@odoo/owl";

// Filing an absence has to be a deliberate act. Odoo saves a form on its own after a while,
// even one nobody typed into, so a teacher who merely opened the request screen to look at it
// would end up with a real absence on record. hr.leave refuses to save without 'ems_submitted',
// and this button is the only thing that sets it - which is why it has to set the field and
// save itself, rather than being a plain type="object" button: the web client would save the
// record *before* calling the method, and the record would not be saveable yet.
export class EmsAbsenceSubmitButton extends Component {
    static template = "ems.AbsenceSubmitButton";
    static props = { ...standardWidgetProps };

    setup() {
        this.dialog = useService("dialog");
    }

    // What is still missing, or "" when the request is ready to send. Doubles as the button's
    // tooltip, so a disabled button says why it is disabled instead of just not reacting.
    get blockingReason() {
        const data = this.props.record.data;
        if (!data.holiday_status_id) {
            return _t("Choose the type of absence.");
        }
        if (!data.ems_full_day && !(data.request_hour_to > data.request_hour_from)) {
            return _t("Give a start and an end time, with the end later than the start.");
        }
        if (!data.ems_responsible_declaration) {
            return _t("Accept the responsible declaration.");
        }
        return "";
    }

    get canSubmit() {
        return !this.blockingReason;
    }

    onClick() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Send the absence request"),
            body: _t(
                "Your absence request is about to be filed. Do you confirm that every detail is correct?"
            ),
            confirmLabel: _t("Send request"),
            confirm: async () => {
                await this.props.record.update({ ems_submitted: true });
                let saved = false;
                try {
                    saved = await this.props.record.save();
                } finally {
                    // Put the flag back if the record did not make it to the database, whether
                    // because a field was invalid or the server refused it. Leaving it set
                    // would hide this button - the only way to send - on a request that was
                    // never actually filed.
                    if (!saved) {
                        await this.props.record.update({ ems_submitted: false });
                    }
                }
            },
            cancel: () => {},
        });
    }
}

export const emsAbsenceSubmitButton = {
    component: EmsAbsenceSubmitButton,
    // The other fields the button reasons about are all on the form already; this one is not.
    fieldDependencies: [{ name: "ems_submitted", type: "boolean" }],
};

registry.category("view_widgets").add("ems_absence_submit", emsAbsenceSubmitButton);
