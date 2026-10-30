# Changes

## Auto check-out fallback notice goes to the employee only (issue #734):

- When the automatic check-out can't use the schedule (the employee checked in after the last hour their schedule expected that day) and closes the attendance one hour after check-in, the notice now goes only to the employee, no longer to the Head or Deputy Head of Studies, the area's attendance manager or the administrators (issue #648 had already left out the Department/Seminar Chief). Those approvers only get involved if the employee requests a correction.
- The notice is rewritten for the employee: it says, in their own time, when they checked in, the last hour their schedule expected that day and the check-out it set, and tells them to open the attendance and click "Request Correction". It now has Catalan and Spanish translations (it used to arrive in English).

## Non-teaching staff can request attendance corrections (issue #734):

- Requesting a correction of one's own check-ins was limited to teachers, but the non-teaching staff clock in too and now receive the notice above. The "own requests" access right and record rule now belong to everyone who reads their own attendance (the Secretary role included), still restricted to their own records; their requests are routed to their approver like a teacher's. Same xmlids, no migration needed.
- Teacher manual (ca/es/en): note explaining the auto check-out message and that non-teaching staff use the same steps; linked from the Secretary index. Developer docs updated.
