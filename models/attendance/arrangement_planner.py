# -*- coding: utf-8 -*-

from collections import defaultdict

from ..shared.schedule_report_mixin import HOUR_EPSILON
from .absence_coverage import overlaps


def schedule_shift(periods, removed, added):
    """How a teacher's working day - from their first period to their last, lessons, guards and any
    other duty alike (`periods`) - changes if they stop teaching the `removed` periods and teach the
    `added` ones instead: `[(kind, old, new)]`, `kind` being 'entry' or 'exit', empty when neither
    moves. None when the day would get longer: coming in earlier is only possible leaving earlier
    too, and leaving later coming in later (developer decision, 2026-10-10)."""
    if not periods:
        return None
    before = (min(start for start, _stop in periods), max(stop for _start, stop in periods))
    kept = [period for period in periods if not any(overlaps(*period, *gone) for gone in removed)] + list(added)
    after = (min(start for start, _stop in kept), max(stop for _start, stop in kept))
    if after[1] - after[0] > before[1] - before[0] + HOUR_EPSILON:
        return None
    return [(kind, old, new) for kind, old, new in (('entry', before[0], after[0]), ('exit', before[1], after[1]))
            if abs(old - new) > HOUR_EPSILON]


class ArrangementPlanner:
    """Finds the internal arrangements (issue #645) that leave a set of groups' day with as few
    lessons lost and as few hours without class inside the centre as possible: sequences of moved
    lessons, each teacher filling the gap the previous one left, until the last gap reaches the
    start or the end of the day (or a break) and is solved by telling the families.

    Works on the groups linked that day by shared lessons (moving a shared lesson changes every one
    of them), on plain data the board already read once: no query, so it can explore many
    combinations. Everything about the timetable that needs the ORM comes in as data or as the
    `free` callable; the change rules (what a late entry, an early leave or a longer break is)
    are the board's own, through `course`.

    - `blocks`: `{group id: [{'hour_from', 'hour_to', 'teachers', 'away', 'filled'}]}`, each group's
      day block by block (see ems.course._get_group_day_blocks): its teachers' ids, those away or
      whose lesson went elsewhere, and whether somebody already covers it.
    - `breaks`: `{group id: [(hour_from, hour_to)]}`, its level's breaks that day.
    - `communicated`: `{group id: {side: change}}`, what the families were already told per side.
    - `teachers`: `{teacher id: {'lessons': [((hour_from, hour_to), frozenset(group ids))],
      'periods': [(hour_from, hour_to)], 'vacated': [(hour_from, hour_to)]}}`: their lessons with
      these groups, every period of their day, and their lessons another arrangement already moved.
    - `free(teacher id, hour_from, hour_to)`: whether they can be with a group then.
    - `swaps`: the lesson swaps the timetable allows (see ems.course._get_arrangement_options),
      as steps: they combine with moves like any other step.

    A step is a hashable tuple: `('move', teacher id, lesson, target, group ids)` or
    `('swap', teacher id, lesson, target, group ids, absent teacher id)`, periods as
    `(hour_from, hour_to)`."""

    MAX_MOVES = 4
    BEAM = 30

    def __init__(self, course, blocks, breaks, communicated, now_hour, teachers, free, swaps=()):
        self.course = course
        self.blocks = blocks
        self.breaks = breaks
        self.communicated = communicated
        self.now_hour = now_hour
        self.teachers = teachers
        self.free = free
        self.swaps = list(swaps)

    # The state a sequence of steps leaves the groups' day in.

    def simulate(self, steps):
        day = {group_id: [dict(block, away=set(block['away'])) for block in blocks]
               for group_id, blocks in self.blocks.items()}
        for step in steps:
            kind, teacher_id, lesson, target, group_ids = step[:5]
            for group_id in group_ids:
                for block in day[group_id]:
                    if overlaps(block['hour_from'], block['hour_to'], *target):
                        block['filled'] = True
                    if overlaps(block['hour_from'], block['hour_to'], *lesson):
                        block['away'].add(teacher_id)
                        if kind == 'swap':
                            block['filled'] = True  # the absent teacher teaches it instead
        for group_id, blocks in day.items():
            for block in blocks:
                block['empty'] = bool(block['teachers']) and block['teachers'] <= block['away'] and not block['filled']
                block['taught'] = (block['teachers'] - block['away']) | {
                    step[1] for step in steps if group_id in step[4] and overlaps(block['hour_from'], block['hour_to'], *step[3])
                } | {step[5] for step in steps if step[0] == 'swap' and group_id in step[4]
                     and overlaps(block['hour_from'], block['hour_to'], *step[2])}
        return day

    def _is_past(self, change, blocks):
        return self.now_hour is not None and self.course._change_start(change, blocks) <= self.now_hour

    def _side_options(self, group_id, blocks):
        """`{side: (options, communicated)}` of one group's simulated day: the changes still to come
        it allows, from the smallest to the largest, and what the families were told on that side."""
        allowed = self.course._allowed_absence_changes(blocks, self.breaks.get(group_id, ()))
        return {side: ([option for option in options if not self._is_past(option, blocks)],
                       self.communicated.get(group_id, {}).get(side))
                for side, options in allowed.items()}

    def _evaluate(self, steps):
        """`(score, notices)`. The notices are the largest change each side allows that nobody was
        told yet, `(group id, side, change)`. The score, lower is better:
        1. lessons the students lose;
        2. of those, the hours they spend in the centre without class: with a guard, or in a
           longer break - coming in later or leaving earlier is what avoids them;
        3. of those, the ones that need a guard;
        4. notices to the families;
        5. teachers who move a lesson;
        6. runs of a teacher's lessons with a group cut in two (two hours in a row of the same
           subject are better kept together);
        7. changes to somebody's entry or exit time."""
        day = self.simulate(steps)
        lost = idle = guards = 0
        notices = []
        for group_id, blocks in day.items():
            windows = []
            for side, (options, communicated) in self._side_options(group_id, blocks).items():
                if communicated:
                    # A change already told (and still valid, or past) frees its lessons; a stale
                    # one is the correction box's business, not a plan's.
                    if self._is_past(communicated, blocks) or any(
                            self.course._same_change(communicated, option) for option in options):
                        windows.append(communicated)
                    continue
                if options:
                    notices.append((group_id, side, options[-1]))
                    windows.append(options[-1])
            for block in blocks:
                if block['empty']:
                    lost += 1
                    freeing = [window for window in windows
                               if self.course._change_window_contains(window, block['hour_from'], block['hour_to'])]
                    if not freeing:
                        guards += 1
                    if all(window[0] == 'long_break' for window in freeing):
                        idle += 1
        shifts = self._shifts(steps)
        moves = len({step[1] for step in steps})
        return (lost, idle, guards, len(notices), moves, self._runs(day),
                sum(len(changes) for changes in shifts.values())), notices

    @staticmethod
    def _runs(day):
        """How many runs of consecutive lessons each teacher has with each group, in all."""
        runs = 0
        for blocks in day.values():
            previous = set()
            for block in blocks:
                runs += len(block['taught'] - previous)
                previous = block['taught']
        return runs

    def _shifts(self, steps):
        """`{teacher id: [(kind, old, new)]}` for every teacher the steps move; None for a teacher
        whose day they would lengthen."""
        removed, added = defaultdict(list), defaultdict(list)
        for step in steps:
            removed[step[1]].append(step[2])
            added[step[1]].append(step[3])
            if step[0] == 'swap':
                # The absent teacher teaches the other lesson instead of their own.
                removed[step[5]].append(step[3])
                added[step[5]].append(step[2])
        return {teacher_id: schedule_shift(self.teachers[teacher_id]['periods'], removed[teacher_id], added[teacher_id])
                for teacher_id in removed}

    # The steps possible from a state.

    def _keeps_days(self, steps, step):
        shifts = self._shifts([*steps, step])
        return all(shifts.get(teacher_id) is not None for teacher_id in (step[1], *step[5:]))

    def _steps(self, steps, day):
        holes = defaultdict(set)
        for group_id, blocks in day.items():
            for block in blocks:
                if block['empty']:
                    holes[(block['hour_from'], block['hour_to'])].add(group_id)
        # Where each teacher already is because of a step: in the gap they fill, and in a swap the
        # absent teacher at the other lesson.
        taken = [(step[1], step[3]) for step in steps] + [(step[5], step[2]) for step in steps if step[0] == 'swap']
        vacated = {(step[1], step[2]) for step in steps}
        for step in self.swaps:
            _kind, teacher_id, lesson, target, group_ids, absent_id = step
            if step not in steps and target in holes and group_ids <= holes[target] and (teacher_id, lesson) not in vacated \
                    and not any(other in (teacher_id, absent_id) and overlaps(*period, *(target if other == teacher_id else lesson))
                                for other, period in taken) \
                    and self._keeps_days(steps, step):
                yield step
        for target, group_ids in sorted(holes.items()):
            for teacher_id in sorted(self.teachers):
                teacher = self.teachers[teacher_id]
                if any(other == teacher_id and overlaps(*period, *target) for other, period in taken) \
                        or not self.free(teacher_id, *target):
                    continue
                for lesson, lesson_groups in teacher['lessons']:
                    # Every group of the lesson must have the gap: a shared lesson moves for all
                    # of them, and none may end up with a lesson where it already had one.
                    if overlaps(*lesson, *target) or not lesson_groups <= group_ids or (teacher_id, lesson) in vacated \
                            or any(overlaps(*lesson, *other) for other in teacher['vacated']):
                        continue
                    step = ('move', teacher_id, lesson, target, lesson_groups)
                    if self._keeps_days(steps, step):
                        yield step

    # Search.

    def plans(self, limit=3):
        """The best plans, `[{'steps', 'notices', 'score', 'depends', 'notice_depends', 'shifts'}]`:
        a beam search over moves and swaps (at most MAX_MOVES steps). Only those no
        worse than leaving the day as it is in lessons lost, hours without class, guards and notices,
        and none that merely adds steps to another one that does as well."""
        base, _notices = self._evaluate(())
        candidates = {}
        frontier, seen = [()], {frozenset()}
        for _depth in range(self.MAX_MOVES):
            expanded = []
            for steps in frontier:
                day = self.simulate(steps)
                for step in self._steps(steps, day):
                    new = (*steps, step)
                    key = frozenset(new)
                    if key in seen:
                        continue
                    seen.add(key)
                    score, notices = self._evaluate(new)
                    expanded.append((score, new, notices))
            expanded.sort(key=lambda item: item[0])
            candidates.update({frozenset(steps): (score, steps, notices) for score, steps, notices in expanded})
            frontier = [steps for _score, steps, _notices in expanded[:self.BEAM]]
            if not frontier:
                break
        kept = [(score, steps, notices) for score, steps, notices in candidates.values() if score[:4] <= base[:4]]
        kept = [(score, steps, notices) for score, steps, notices in kept if not any(
            frozenset(other) < frozenset(steps) and other_score[:4] <= score[:4]
            for other_score, other, _other_notices in kept)]
        kept.sort(key=lambda item: (item[0], [(step[0] != 'swap', step[3], step[1]) for step in item[1]]))
        # Two ways to the very same day (a swap seen from each of its two absences) are one plan.
        unique, seen_days = [], set()
        for score, steps, notices in kept:
            day = self.simulate(steps)
            signature = (frozenset((group_id, index, frozenset(block['taught'])) for group_id, blocks in day.items()
                                   for index, block in enumerate(blocks)), tuple(sorted(notices)))
            if signature not in seen_days:
                seen_days.add(signature)
                unique.append((score, steps, notices))
        return [self._plan(score, steps, notices) for score, steps, notices in unique[:limit]]

    def _plan(self, score, steps, notices):
        """One plan with its steps' dependencies: a move into a gap another step left needs that
        step, and a notice needs the moves whose lessons left free are part of what it frees."""
        created = []
        depends = []
        for index, step in enumerate(steps):
            depends.append(sorted({other for other, (group_id, period) in created
                                   if group_id in step[4] and overlaps(*period, *step[3])}))
            if step[0] == 'move':
                created += [(index, (group_id, step[2])) for group_id in step[4]]
        notice_depends = [sorted({other for other, (group_id, period) in created if group_id == notice_group
                                  and self.course._change_window_contains(change, *period)})
                          for notice_group, _side, change in notices]
        return {'steps': list(steps), 'notices': notices, 'score': score, 'depends': depends,
                'notice_depends': notice_depends, 'shifts': self._shifts(steps)}

    def check(self, steps, notices):
        """Whether `steps` (in order) and `notices` (`(group id, change)`) can be applied as they are
        now: each move into a gap still there, with a teacher still free, nobody's day longer; each
        notice one of the changes the resulting day allows, on a side the families were not told
        about yet. Returns the error, or None."""
        applied = ()
        for step in steps:
            if step not in set(self._steps(applied, self.simulate(applied))):
                return 'step'
            applied = (*applied, step)
        day = self.simulate(applied)
        for group_id, change in notices:
            sides = self._side_options(group_id, day.get(group_id, []))
            if not any(not communicated and any(self.course._same_change(change, option) for option in options)
                       for options, communicated in sides.values()):
                return 'notice'
        return None
