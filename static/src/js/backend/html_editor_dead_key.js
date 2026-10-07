/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { InlineCodePlugin } from "@html_editor/main/inline_code";

// Catalan's grave accent (à, è, ò) is typed with a dead key: the keyboard opens a composition
// holding a bare "`" and waits for the next letter. Odoo's inline-code plugin turns `text` into
// code and reacts to every "`" it sees, the composing one included: it moves the selection and
// records a history step, and the browser cancels the composition, so the accent never reaches
// the letter (found in Firefox, the centre's browser, and Chrome alike - "no puc escriure
// l'accent obert"). A "`" still being composed is not a backtick yet: let the composition finish.
// A plain backtick (dead key + space) arrives once composed and still makes inline code.
patch(InlineCodePlugin.prototype, {
    onInput(ev) {
        if (ev.isComposing) {
            return;
        }
        return super.onInput(ev);
    },
});
