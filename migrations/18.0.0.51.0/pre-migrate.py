# -*- coding: utf-8 -*-
import logging

from odoo.addons.ems.models.attendance.student_walkout import ONE_PER_DAY_INDEX, live_duplicates

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _report_duplicate_walkout_proposals(cr)


def _report_duplicate_walkout_proposals(cr):
    """Issue #827: the model's init() builds a unique index for one live student walkout proposal per
    group and day. Two managers proposing the same day at the same moment could already have made two:
    list them so they can be cancelled by hand (init() skips the index meanwhile, so the upgrade goes
    on, and builds it on the next upgrade once they are gone). Raw SQL: nothing new is touched. A clean
    install has none."""
    duplicates = live_duplicates(cr)
    for group_id, walkout_date, walkout_ids in duplicates:
        _logger.warning("Migration #827: group %s has %s live student walkout proposals for %s (ids %s); cancel "
                        "all but one so that %s can be built.", group_id, len(walkout_ids), walkout_date,
                        walkout_ids, ONE_PER_DAY_INDEX)
    _logger.info("Migration #827: %s group(s) and day(s) with duplicate live student walkout proposals.",
                 len(duplicates))
