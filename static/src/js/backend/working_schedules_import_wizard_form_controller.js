/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const IMPORT_LOADING_MESSAGE = _t("Importing the schedule, please wait...");

export class EmsWorkingSchedulesImportWizardFormController extends FormController {
    setup() {
        super.setup();
        this.ui = useService("ui");
    }

    // Clicking "Import" (name="import_planner_data") implicitly saves this still-unsaved wizard
    // first - that save IS the actual create() override that parses the whole XML and writes the
    // schedule (reported 2026-08-01: looked hung, no feedback, same complaint as the file-upload
    // spinner added earlier in working_schedule_import_blocking_upload.js). The button's own
    // server method runs after the save and is trivial (just a 'soft_reload' client action), so
    // wrapping only the save call here - not afterExecuteActionButton - covers the slow part.
    // Unblocking in 'finally' also covers the save failing (e.g. a ValidationError from an
    // unresolved group/subject) - 'afterExecuteActionButton' would never run in that case, since
    // the framework's own onClickViewButton doesn't wrap 'beforeExecuteAction' in a try/catch.
    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name !== "import_planner_data") {
            return super.beforeExecuteActionButton(clickParams);
        }
        this.ui.block({ message: IMPORT_LOADING_MESSAGE });
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
