# Changes

## Erasmus+ group mobilities: ranking by a score:

- Each enrolment has a score (`score`, stored): the record average (manual included) +1 for fewer opportunities accredited by the Erasmus team, -0.5 per conduct warning this course (at most -1.5), as art. 16 of the students' rules says. It follows the team's later checks (an accreditation, an average entered by hand).
- The ranking orders by the score; a tie is the same score and accreditation, then the coordinator's draw, which now keeps the score tied on.
- The selection tab, the participants' spreadsheet and the published lists (portal and PDF, header "Score") show it next to the average. The leader teacher sees the score but never its breakdown.
- The default selection criteria text explains the new rule (ca/es/en).
- A mobility already ranked before the upgrade keeps its ranking by the average (`rank_by_score` False, set by the migration where `ranking_date` was set): no recomputation.
