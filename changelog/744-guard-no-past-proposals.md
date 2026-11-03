# Fixes

## Guard duty board proposals never touch a class that has already started:

- The arrangement proposals (moves, joins and swaps) could suggest bringing a later lesson to a free class already under way, or moving a lesson that was being taught or was already over: impossible to carry out. Now both the free class and the lesson brought to it must still be to come at the board's current time; a free class already under way is left to a guard (and still shows as such).
- The same check applies to the swaps offered for a single class and when one is applied, so a swap whose time has passed is refused.
