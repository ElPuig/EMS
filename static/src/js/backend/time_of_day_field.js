/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FloatTimeField, floatTimeField } from "@web/views/fields/float_time/float_time_field";
import { InvalidNumberError, parseFloatTime } from "@web/views/fields/parsers";
import { useInputField } from "@web/views/fields/input_field_hook";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";

// Hours and minutes split by a separator other than ":" ("13.04", "13,04" from the numeric
// keypad, "13h04"), or written together ("1304", "930").
const SEPARATED = /^(\d{1,2})\s*[.,hH']\s*(\d{1,2})$/;
const TOGETHER = /^(\d{1,2})(\d{2})$/;

/**
 * A time of the day typed by hand (issue #735). Odoo's float_time reads anything without ":" as
 * decimal hours, made for durations: "13.04" became 13:02, "13,04" (the keypad's decimal key in
 * Catalan and Spanish) 13:00 and "1304" 1304 hours. Here every way of writing hours and minutes
 * means hours and minutes, and the result must fall within a day.
 */
export function parseTimeOfDay(value) {
    const text = value.trim();
    const match = text.match(SEPARATED) || text.match(TOGETHER);
    const hours = match ? parseInt(match[1], 10) + parseInt(match[2], 10) / 60 : parseFloatTime(text);
    if ((match && parseInt(match[2], 10) > 59) || !(hours >= 0 && hours <= 24)) {
        throw new InvalidNumberError(`"${value}" is not a time of the day`);
    }
    return hours;
}

export class TimeOfDayField extends FloatTimeField {
    // float_time's own setup, with this parser: calling it too would hook the input twice.
    setup() {
        this.inputFloatTimeRef = useInputField({
            getValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: parseTimeOfDay,
        });
        useNumpadDecimal();
    }
}

registry.category("fields").add("ems_time_of_day", { ...floatTimeField, component: TimeOfDayField });
