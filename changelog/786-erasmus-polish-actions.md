# Changes

## Erasmus+ actions at the right moment, asking for their data (issue #786):
- Mobility: "Cancel the mobility" opens a dialog asking for the reason, instead of failing unless it had been written in a tab first; the Cancellation tab is gone and the reason shows at the top of the form once cancelled.
- Mobility: "Set the agreed destination" opens a dialog asking for the country, city, host entity and dates, instead of failing without a country. Students only: staff propose their activity and the Direction validates it, so it is no longer offered on a staff mobility.
- Staff call: "Send plans to the panel" is only offered while scoring (closed and before the provisional resolution), and refused afterwards with a clear message.
- Resolution: "Print the published list" in its Actions dropdown (the same PDF the applicants download); the list keeps it in its Print menu.
- Checked and kept as they are: every Erasmus+ form already had its buttons in Actions (expense included); "New" in Resolutions is how a resolution is created from its call; the participants spreadsheet adds what Odoo's export cannot (only those who accepted, the fixed format, bank and family data, each download logged, team only).

## The next step stays in view (issue #786, pending the agreed exception to "every action in Actions"):
- On the teacher's application ("Fill in the form" while nothing is answered, then "Submit", "Accept the place") and mobility ("Send the activity proposal"), and on a proposal waiting for validation ("Validate the proposal"), the next step is a highlighted button next to the Actions dropdown; everything else, renouncing included, stays in Actions. The notice no longer sends the teacher to "Actions > Fill in the form".
- The Actions dropdown supports it for any form through an opt-in class on the button; forms without it are unchanged.
