/** @odoo-module **/

import { registry } from "@web/core/registry";

// res.config.settings' "EMS Management" app tab (~20 fields: Google Workspace, LimeSurvey
// credentials, course/attendance/strike settings) had zero browser coverage - admin-only and
// rarely touched, but a crash here would have high blast radius. This tour switches to the
// EMS tab and edits one representative field per settings block, proving the whole tab
// renders and its fields are genuinely interactive in a real browser.
//
// Deliberately does NOT click Save: res.config.settings.execute() (see base/models/
// res_config.py) returns {'type': 'ir.actions.client', 'tag': 'reload'}, which forces a real
// browser navigation (router.pushState(..., {reload: true}), not an in-place SPA re-render.
// A tour step can't reliably observe anything after that: the reload destroys the very JS
// execution context the tour macro (and any of its polling) runs in, so a following step's
// trigger either races the navigation (matching the still-live, about-to-be-destroyed old DOM
// instantly, before the save round-trip actually finishes - confirmed via screenshot: Save/
// Discard still visible) or times out waiting on a signal (".o_form_button_save:not(:visible)")
// that turns out to never apply to this view in the first place (Settings keeps Save/Discard
// permanently visible, unlike a regular form's dirty-only indicator). The actual thing this
// gap cares about - do these EMS-added fields render and accept input without crashing - is
// fully covered by the edits below; verifying Odoo's own generic settings-save/reload
// mechanism is out of scope (it's core Odoo behavior, not EMS code).
registry.category("web_tour.tours").add("ems_settings_edit", {
    test: true,
    url: "/odoo/action-base_setup.action_general_configuration",
    steps: () => [
        {
            trigger: ".settings_tab",
            content: "Settings app list loaded",
        },
        {
            trigger: ".settings_tab a.tab[data-key='ems']",
            content: "Switch to the EMS Management tab",
            run: "click",
        },
        {
            trigger: ".app_settings_block[data-key='ems'] .o_field_widget[name='center_code'] input",
            content: "EMS settings rendered - edit the center code",
            run: "edit 08099999",
        },
        {
            trigger: ".app_settings_block[data-key='ems'] .o_field_widget[name='limesurvey_api'] input",
            content: "Edit the LimeSurvey API endpoint",
            run: "edit https://tour.limesurvey.example.com",
        },
        {
            trigger: ".app_settings_block[data-key='ems'] .o_field_widget[name='google_ws_enabled'] input[type='checkbox']",
            content: "Toggle Google Workspace enabled",
            run: "click",
        },
        {
            trigger: ".app_settings_block[data-key='ems'] .o_field_widget[name='google_ws_enabled'] input[type='checkbox']:checked",
            content: "The checkbox actually toggled (not just clicked)",
        },
        {
            // Discard (unlike Save) stays a normal in-place SPA action - res.config.settings.
            // cancel() just re-reads the record, no client-side "reload" action tag involved -
            // so it's the safe way to leave the tour with a clean (non-dirty) form.
            trigger: ".o_form_button_cancel",
            content: "Discard the edits - leaves the form clean without touching the risky save/reload path",
            run: "click",
        },
        {
            trigger: ".app_settings_block[data-key='ems'] .o_field_widget[name='google_ws_enabled'] input[type='checkbox']:not(:checked)",
            content: "Discarded - the checkbox is back to its original state",
        },
    ],
});
