/** @odoo-module **/

const { DateTime } = luxon;

// How far the browser's clock is from the server's. A computer with a wrong clock must never
// decide what "now" or "today" is (a teacher once got the wrong roll-call slot preselected that
// way) - see docs/en/developers/shared/timezones.md.
let offsetMs = 0;

export async function syncServerClock(orm) {
    const sentAt = Date.now();
    const serverMs = await orm.call("ems.datetime_utils", "get_server_epoch_ms", []);
    offsetMs = serverMs - (sentAt + Date.now()) / 2;
}

// The server's "now", in the company's timezone (luxon's default zone, see
// company_timezone_service.js).
export function serverNow() {
    return DateTime.fromMillis(Date.now() + offsetMs);
}
