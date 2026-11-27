/** @odoo-module **/

import { onWillDestroy } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { useService } from "@web/core/utils/hooks";

/**
 * Form view factory for wizards whose buttons run for a long time.
 *
 * Odoo alone greys the buttons out and shows its small "Loading" pill, which gives the
 * operator no way of telling a long run from a frozen screen — during the first full
 * course transition rehearsal, both the grade import (minutes per file) and the session
 * creation repeatedly looked hung. `ui.block()` is the overlay that already exists for
 * this; nobody was calling it.
 *
 * There is no live counter on purpose. These actions run in a SINGLE transaction, which
 * is what guarantees that a failure half-way leaves the database untouched; bus
 * notifications written inside it are invisible until it commits, so a progress bar would
 * need either to split the run into several transactions (losing that guarantee) or a
 * separate database cursor. The overlay states what is about to happen instead, which is
 * information the operator already has.
 *
 * @param {Object} messages - button name → (recordData) => string shown in the overlay.
 *                            A button absent from the map is left alone.
 */
export function blockingActionFormView(messages) {
    class BlockingActionFormController extends FormController {
        setup() {
            super.setup();
            this.ui = useService("ui");
            this.uiBlocked = false;
            // When the button returns an action that closes this wizard's dialog (e.g. back to the
            // sessions' list), the dialog is destroyed before afterExecuteActionButton runs, and
            // Odoo's protected action service then never resolves for it: the overlay would stay
            // forever (issue #878). Unblock when the wizard goes away.
            onWillDestroy(() => this._unblockUi());
        }

        _unblockUi() {
            if (this.uiBlocked) {
                this.ui.unblock();
                this.uiBlocked = false;
            }
        }

        async beforeExecuteActionButton(clickParams) {
            // Block only once the wizard has saved: a required field left empty stops the save
            // (the fields turn red) and Odoo then never calls afterExecuteActionButton, so a block
            // put before it stayed on screen as if the action were running (issue #878).
            const proceed = await super.beforeExecuteActionButton(clickParams);
            const buildMessage = messages[clickParams.name];
            if (proceed !== false && buildMessage) {
                this.ui.block({ message: buildMessage(this.model.root.data) });
                this.uiBlocked = true;
            }
            return proceed;
        }

        async afterExecuteActionButton(clickParams) {
            // useViewButtons calls this even when the action raised (it catches, calls the
            // hook, then re-throws), so a failed run cannot leave the UI blocked.
            this._unblockUi();
            return super.afterExecuteActionButton(clickParams);
        }
    }
    return { ...formView, Controller: BlockingActionFormController };
}

/**
 * Newlines only render because our CSS puts white-space: pre-line on the BlockUI message,
 * which escapes HTML. Shared so every overlay in the module reads the same way.
 */
export function overlayLines(...lines) {
    return lines.filter((line) => line !== null && line !== undefined).join("\n");
}
