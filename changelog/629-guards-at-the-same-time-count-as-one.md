# Fixes:

## Guard cover count (groups covered at the same time count once):
- The number of covers shown next to each guard teacher on the guard duty board (and in the dialog to send a guard) counted one per group, so a guard sent to look after two groups put together in the same room at the same time got two. Covers of the same guard in the same room in the same period now count as a single one; groups in different rooms, and consecutive periods, still count separately (issue #629).
