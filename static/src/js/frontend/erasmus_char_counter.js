/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * The issue-#682 review: the staff mobility plan's sections (1,500 characters at most each) show
 * how many characters are written. The number and the maximum only: the words around them are in
 * the QWeb template (portal_erasmus_application), so they are translated there.
 */
publicWidget.registry.EmsErasmusCharCounter = publicWidget.Widget.extend({
    selector: ".o_ems_erasmus_staff_form",
    events: {
        "input textarea[maxlength]": "_update",
    },

    start() {
        for (const textarea of this.el.querySelectorAll("textarea[maxlength]")) {
            this._show(textarea);
        }
        return this._super(...arguments);
    },

    _update(event) {
        this._show(event.target);
    },

    _show(textarea) {
        const counter = this.el.querySelector(`.o_ems_erasmus_char_count[data-for='${textarea.name}']`);
        if (counter) {
            counter.textContent = `${textarea.value.length} / ${textarea.maxLength}`;
        }
    },
});
