/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const IMPORT_LOADING_MESSAGE = _t("Importing the schedule, please wait...");
const CONTINUE_LOADING_MESSAGE = _t("Processing, please wait...");
// Clicking either button implicitly saves this wizard first (creating the still-unsaved record
// on the very first click) - since 2026-08-05's multi-step redesign, the slow part moved: leaving
// the intro screen ("Continue") is what now parses the whole XML (see
// 'ems.working_schedules_import_wizard._continue_from_intro'), while every later step's own
// "Continue"/"Import" server method is comparatively cheap. Both are still wrapped the same way,
// since a slow save is possible either way and the spinner is cheap insurance either way.
const BLOCKED_BUTTON_MESSAGES = {
    'action_continue': CONTINUE_LOADING_MESSAGE,
    'import_planner_data': IMPORT_LOADING_MESSAGE,
};

export class EmsWorkingSchedulesImportWizardFormController extends FormController {
    setup() {
        super.setup();
        this.ui = useService("ui");
    }

    // The button's own server method runs after the save and is comparatively cheap (a
    // self-reopening action, or a 'soft_reload' client action), so wrapping only the save call
    // here - not afterExecuteActionButton - covers the slow part (reported 2026-08-01: looked
    // hung, no feedback, same complaint as the file-upload spinner added earlier in
    // working_schedule_import_blocking_upload.js). Unblocking in 'finally' also covers the save
    // failing (e.g. a ValidationError from an unresolved group/subject) -
    // 'afterExecuteActionButton' would never run in that case, since the framework's own
    // onClickViewButton doesn't wrap 'beforeExecuteAction' in a try/catch.
    async beforeExecuteActionButton(clickParams) {
        const message = BLOCKED_BUTTON_MESSAGES[clickParams.name];
        if (!message) {
            return super.beforeExecuteActionButton(clickParams);
        }
        this.ui.block({ message });
        try {
            return await super.beforeExecuteActionButton(clickParams);
        } finally {
            this.ui.unblock();
        }
    }
}

registry.category("views").add("ems_working_schedules_import_wizard_form", {
    ...formView,
    Controller: EmsWorkingSchedulesImportWizardFormController,
});
