/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

const { IANAZone, Settings } = luxon;

// EMS works in the company's timezone only (session_info's 'ems_tz', models/shared/ir_http.py),
// never the browser's - see docs/en/developers/shared/timezones.md:
// - luxon's "default" zone is what every date/time the web client shows or reads from an input
//   goes through; left alone it is the browser's, so a computer with a wrong timezone would show
//   and save times shifted.
// - the 'tz' cookie is what the server reads as the browser's timezone: Odoo gives it to a user on
//   their first login (res.users._login) and formats some labels with it (e.g. hr.attendance's
//   display name). The frontend layout only fills it in when missing, so overwriting it here wins.
export const companyTimezoneService = {
    start() {
        if (session.ems_tz && IANAZone.isValidZone(session.ems_tz)) {
            Settings.defaultZone = session.ems_tz;
            document.cookie = `tz=${session.ems_tz}; path=/; SameSite=Lax`;
        }
    },
};

registry.category("services").add("ems_company_timezone", companyTimezoneService);
