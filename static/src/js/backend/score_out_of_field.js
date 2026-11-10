/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formatFloat } from "@web/views/fields/formatters";
import { FloatField, floatField } from "@web/views/fields/float/float_field";

// A computed score over its maximum, e.g. "36 / 40", with no needless decimals (issue #779). Odoo's
// float widget only prints the number. `options="{'max': 40}"`, or no option for a criterion that
// only takes points off; read-only: it is for scores, which are always computed.
export class EmsScoreOutOfField extends FloatField {
    static props = { ...FloatField.props, max: { type: Number, optional: true } };

    get formattedValue() {
        const score = formatFloat(this.value, { digits: this.props.digits, trailingZeros: false });
        return this.props.max === undefined
            ? score
            : `${score} / ${formatFloat(this.props.max, { trailingZeros: false })}`;
    }
}

registry.category("fields").add("ems_score_out_of", {
    ...floatField,
    component: EmsScoreOutOfField,
    extractProps: (fieldInfo, dynamicInfo) => ({
        ...floatField.extractProps(fieldInfo, dynamicInfo),
        max: fieldInfo.options.max,
    }),
});
