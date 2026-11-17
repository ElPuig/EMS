# What's new:
## Extending the joining of a student walkout proposal (delegates once, tutor chain any time):
- The delegate or sub-delegate of the group can extend the joining once from the portal, also after it has ended; the tutor, whoever is above them and the administrators can extend it any time and as often as needed from the Actions menu.
- Every extension lasts one phase (the existing phase setting, no new setting), or less when the notice before the walkout does not allow a whole one, and is only offered when the Head of Studies can still get the minute with the notice before the walkout.
- If the proposal had already closed, it reopens: the minute and the task are withdrawn, the Head of Studies is told in their daily summary and a new minute is sent when it closes again. Students and the tutor are told by email.

# Internal changes:
## Daily-summary notices to the Head of Studies:
- One helper (`_ems_notify_heads`) now builds the notice sent when a proposal is aborted or its joining is extended.

# Changes:
## Student walkout proposals that only fit with a shorter joining phase:
- A proposal for a day that does not leave room for both whole phases before the notice is now accepted when at least 5 minutes of the individual joining phase fit; the group vote and the notice stay whole.
- The delegate is warned on the proposal's page of how long the joining phase will last at most, and that it grows with the time gained if the group vote ends early, up to the usual phase.
- The form shows the earliest possible day, and the settings example shows it too.
