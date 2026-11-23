# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Issue #799: queues the compression of the PDF files and images stored before it existed.
    It only queues: every file is compressed later by a background job (queue_job), at low
    priority, so the upgrade itself takes seconds whatever the number of files. A clean install
    has no stored files, so it needs no equivalent in post_init_hook."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    queued = env['ir.attachment']._ems_queue_existing_compression()
    _logger.info("Compression of %s stored files queued (issue #799)", queued)
