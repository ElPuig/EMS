# Changes

## Erasmus+ actions at the right moment, asking for their data (issue #786):
- Mobility: "Cancel the mobility" opens a dialog asking for the reason, instead of failing unless it had been written in a tab first; the Cancellation tab is gone and the reason shows at the top of the form once cancelled.
- Mobility: "Set the agreed destination" opens a dialog asking for the country, city, host entity and dates, instead of failing without a country. Students only: staff propose their activity and the Direction validates it, so it is no longer offered on a staff mobility.
- Staff call: "Send plans to the panel" is only offered while scoring (closed and before the provisional resolution), and refused afterwards with a clear message.
- Resolution: "Print the published list" in its Actions dropdown (the same PDF the applicants download); the list keeps it in its Print menu.
- Checked and kept as they are: every Erasmus+ form already had its buttons in Actions (expense included); "New" in Resolutions is how a resolution is created from its call; the participants spreadsheet adds what Odoo's export cannot (only those who accepted, the fixed format, bank and family data, each download logged, team only).

## Erasmus+ actions only when they serve, and status bars (issue #786):
- Each form offers, in each state, only the actions that do something there; when only one is left it shows as a plain button, otherwise they stay in Actions (the visible next-step button was refused).
- Teacher's application: while it can be changed, "Fill in the form" is the one action (its dialog already has "Save and submit"); "Submit" alone only sends the corrections asked for.
- Mobility (team): closing only once the stay is over, cancelling until it ends, the record export from the preparation on, the final payment on return, notices of pending documents before leaving and on return.
- Renouncing a mobility (teacher, portal) only until the stay starts, refused by the server too; the portal's "Upload the documents" only when something can be uploaded; the interview call only on students' applications.
- Application status bar shows the way it really went (e.g. Draft, Submitted, Excluded), as a detected absence does; the teacher's view of a call shows its phase.

# Internal changes

## Erasmus+ tanda 6 close (issues #785, #786):
- User manuals (team, families, Head of Studies) describe the phases, the dialogs and the print entry in Catalan, Spanish and English, with a new screenshot of the mobility's phase bar.
- Permission audit of the touched buttons: printing the published list and sending the plans to the panel are now restricted to the Erasmus team and the administrators in the view too (the server already refused anyone else); 0 mismatches.
