# Changes

## Erasmus+ status bars with the real phases (issue #785):
- Call: the bar goes Draft, Published, Scoring, Resolution, Offers, Finished instead of stopping at "Closed" while offers were still waiting for an answer. The phase follows the published resolutions and the pending offers; the call list shows it too and greys out only finished calls.
- Mobility: the bar goes Defining, Preparation, Mobility stay, Return home, Closed. The stay starts on the start date and the return the day after the end date, updated every hour by a scheduled job, so the lists, the kanban (now one column per phase) and the "Group by" use the same phases. The "Ready to leave" and "Return complete" checkboxes are gone from the list and the Record tab (they are still checked when closing the mobility). The teacher's own mobility, the project's mobility list and the student's portal show the same phase.
- Place offer: "No answer" is part of the status bar.
- Portal: on a phone, the eight-step bar of an application (which broke into two lines) is replaced by "Step N of 8" and the step's name.
