/** @odoo-module **/

// What a teacher types in a grade cell, shared by the session's grade matrix and the tutors' view.
// A number from 0 to 10 (rounded, comma or dot), empty to clear it, and a trailing "*" or "p" to
// mark a learning outcome's grade as provisional (issue #314), e.g. "6*" or "6p".
const PROVISIONAL_SUFFIX = /\s*[*pP]$/;

// {score, is_scored, is_provisional} for the typed text, or null when it is not a grade.
// `allowProvisional` false drops the mark (the session does not allow provisional grades).
export function parseGradeInput(raw, allowProvisional = true) {
    let value = (raw || "").trim().replace(",", ".");
    const provisional = PROVISIONAL_SUFFIX.test(value);
    value = value.replace(PROVISIONAL_SUFFIX, "");
    if (value === "") {
        return provisional ? null : { score: 0, is_scored: false, is_provisional: false };
    }
    const parsed = Math.round(parseFloat(value));
    if (Number.isNaN(parsed)) {
        return null;
    }
    return {
        score: Math.max(0, Math.min(10, parsed)),
        is_scored: true,
        is_provisional: provisional && allowProvisional,
    };
}

// The text a cell shows (and starts editing with): "6", "6*" when provisional, "" when empty.
export function formatGradeInput(score, isScored, isProvisional) {
    if (!isScored) {
        return "";
    }
    return isProvisional ? `${score}*` : String(score);
}
