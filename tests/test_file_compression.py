# -*- coding: utf-8 -*-
import base64
import io
import random
import shutil
import unittest
from unittest.mock import patch

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.pdf import PdfReader


def _photo(width, height, fmt='JPEG', mode='RGB', **save_args):
    """A noisy picture, which does not shrink by itself (like a real photo or scan)."""
    channels = [Image.effect_noise((width, height), 60) for _channel in range(3)]
    image = Image.merge('RGB', channels).convert(mode)
    stream = io.BytesIO()
    image.save(stream, fmt, **save_args)
    return stream.getvalue()


def _scanned_pdf(pages=2):
    """A PDF whose pages are big losslessly stored pictures, as a scan is."""
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(595, 842))
    picture = Image.open(io.BytesIO(_photo(1400, 1900, 'PNG')))
    for _page in range(pages):
        pdf.drawImage(ImageReader(picture), 0, 0, 595, 842)
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


@tagged('post_install', '-at_install')
class TestFileCompression(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compression = cls.env['ems.file_compression']
        cls.scan = _scanned_pdf()

    def _attachment(self, raw, mimetype, name='file', **vals):
        created = self.env['ir.attachment'].with_context(ems_no_compress=True).create(
            dict({'name': name, 'raw': raw, 'mimetype': mimetype}, **vals))
        return self.env['ir.attachment'].browse(created.id)  # back in the normal context

    def _jobs(self, attachment):
        return self.env['queue.job'].sudo().search([('identity_key', '=', f"ems_compress_{attachment.id}")])

    # ---- the engines ----

    @unittest.skipUnless(shutil.which('gs'), "Ghostscript is not installed")
    def test_scanned_pdf_shrinks_and_keeps_its_pages(self):
        result = self.compression.compress(self.scan, 'application/pdf')
        self.assertTrue(result)
        self.assertLess(len(result), len(self.scan) * 0.9)
        self.assertEqual(len(PdfReader(io.BytesIO(result)).pages), 2)

    def test_signed_and_encrypted_pdfs_are_left_alone(self):
        for marker in (b'/ByteRange [0 10 20 30]', b'/Encrypt 5 0 R'):
            with self.subTest(marker=marker):
                self.assertFalse(self.compression.compress(self.scan + marker, 'application/pdf'))

    def test_broken_pdf_or_failing_engine_keeps_the_original(self):
        self.assertFalse(self.compression.compress(b'%PDF-1.4 not really', 'application/pdf'))
        with patch('odoo.addons.ems.models.shared.file_compression.subprocess.run', side_effect=OSError('boom')):
            self.assertFalse(self.compression.compress(self.scan, 'application/pdf'))

    def test_missing_ghostscript_is_not_an_error(self):
        with patch('odoo.addons.ems.models.shared.file_compression.shutil.which', return_value=None):
            self.assertFalse(self.compression.compress(self.scan, 'application/pdf'))
            self.assertEqual(self.compression.compressible_mimetypes(), ['image/jpeg', 'image/png'])

    def test_big_jpeg_is_resized_upright_and_loses_its_metadata(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # rotated: displayed with its right side down
        exif[0x010F] = 'Phone maker'
        raw = _photo(3000, 2000, 'JPEG', quality=98, exif=exif)
        result = self.compression.compress(raw, 'image/jpeg')
        self.assertTrue(result)
        image = Image.open(io.BytesIO(result))
        self.assertEqual(image.size, (1280, 1920))  # 1920 px long side, turned upright
        self.assertFalse(image.getexif())

    def test_png_becomes_jpeg_unless_it_has_transparency(self):
        opaque = self.compression.compress(_photo(1900, 1200, 'PNG'), 'image/png')
        self.assertEqual(Image.open(io.BytesIO(opaque)).format, 'JPEG')
        see_through = self.compression.compress(_photo(4000, 3000, 'PNG', mode='RGBA'), 'image/png')
        self.assertEqual(Image.open(io.BytesIO(see_through)).format, 'PNG')

    def test_a_result_that_saves_little_is_discarded(self):
        small = _photo(300, 200, 'JPEG', quality=60)
        self.assertFalse(self.compression.compress(small, 'image/jpeg'))

    def test_other_types_are_ignored(self):
        self.assertFalse(self.compression.compress(b'a,b\n1,2\n' * 100000, 'text/csv'))

    # ---- what an upload queues ----

    def test_upload_queues_a_job_and_stores_the_file_as_uploaded(self):
        attachment = self.env['ir.attachment'].create(
            {'name': 'scan.png', 'raw': _photo(1900, 1200, 'PNG'), 'mimetype': 'image/png'})
        self.assertEqual(attachment.mimetype, 'image/png')  # still as uploaded
        self.assertEqual(len(self._jobs(attachment)), 1)

    def test_excluded_or_small_files_queue_nothing(self):
        big, small = _photo(1900, 1200, 'PNG'), _photo(100, 100, 'PNG')
        cases = {
            'small': dict(raw=small, mimetype='image/png'),
            'system view': dict(raw=big, mimetype='image/png', res_model='ir.ui.view', res_id=1),
            'derived image': dict(raw=big, mimetype='image/png', res_model='res.partner', res_field='image_512', res_id=1),
            'template': dict(raw=big, mimetype='image/png', res_model='ems.erasmus.call', res_field='template_file', res_id=1),
            'csv': dict(raw=b'a,b\n1,2\n' * 100000, mimetype='text/csv'),
        }
        for label, vals in cases.items():
            with self.subTest(label):
                attachment = self.env['ir.attachment'].create(dict(vals, name=label))
                self.assertFalse(self._jobs(attachment))

    def test_rewriting_the_content_queues_again_but_the_job_itself_does_not(self):
        attachment = self._attachment(_photo(100, 100, 'PNG'), 'image/png', 'a.png')
        attachment.write({'raw': _photo(1900, 1200, 'PNG')})
        self.assertEqual(len(self._jobs(attachment)), 1)

    # ---- what the job does ----

    def test_job_replaces_the_file_and_renames_a_png_stored_as_jpeg(self):
        attachment = self._attachment(_photo(1900, 1200, 'PNG'), 'image/png', 'scan.png')
        size_before = attachment.file_size
        self.assertTrue(attachment._ems_compress())
        self.assertLess(attachment.file_size, size_before * 0.9)
        self.assertEqual((attachment.mimetype, attachment.name), ('image/jpeg', 'scan.jpg'))
        self.assertFalse(self._jobs(attachment))  # the replacement queued nothing

    @unittest.skipUnless(shutil.which('gs'), "Ghostscript is not installed")
    def test_job_compresses_a_pdf_and_keeps_its_name(self):
        attachment = self._attachment(self.scan, 'application/pdf', 'scan.pdf')
        self.assertTrue(attachment._ems_compress())
        self.assertEqual((attachment.mimetype, attachment.name), ('application/pdf', 'scan.pdf'))

    def test_job_leaves_the_file_when_nothing_is_gained(self):
        raw = _photo(300, 200, 'JPEG', quality=60)
        attachment = self._attachment(raw, 'image/jpeg', 'small.jpg')
        self.assertFalse(attachment._ems_compress())
        self.assertEqual(attachment.raw, raw)

    def test_threshold_is_a_setting(self):
        attachment = self._attachment(_photo(700, 500, 'PNG'), 'image/png', 'a.png')
        self.assertTrue(attachment._ems_compression_candidates())
        self.env['ir.config_parameter'].sudo().set_param('ems.compress_min_kb', str(attachment.file_size // 1024 + 100))
        self.assertFalse(attachment._ems_compression_candidates())

    def test_files_stored_before_are_queued_once_and_only_when_worth_it(self):
        big, small = _photo(1900, 1200, 'PNG'), _photo(100, 100, 'PNG')
        worth = self._attachment(big, 'image/png', 'old.png')
        template = self._attachment(big, 'image/png', 'tpl.png', res_model='ems.erasmus.call', res_field='template_file', res_id=1)
        tiny = self._attachment(small, 'image/png', 'tiny.png')
        queued = self.env['ir.attachment']._ems_queue_existing_compression()
        self.assertGreaterEqual(queued, 1)
        self.assertEqual(len(self._jobs(worth)), 1)
        self.assertFalse(self._jobs(template) | self._jobs(tiny))
        self.assertEqual(self._jobs(worth).priority, 20)
        self.env['ir.attachment']._ems_queue_existing_compression()
        self.assertEqual(len(self._jobs(worth)), 1)  # not queued twice

    def test_files_loaded_from_data_are_never_queued(self):
        """The official curricula come back from the CSV on every upgrade (install_mode)."""
        loaded = self.env['ir.attachment'].with_context(install_mode=True).create(
            {'name': 'curriculum.png', 'raw': _photo(1900, 1200, 'PNG'), 'mimetype': 'image/png'})
        self.assertFalse(self._jobs(loaded))
        self.env['ir.model.data'].create({'module': 'ems', 'name': 'test_shipped_attachment', 'model': 'ir.attachment', 'res_id': loaded.id})
        self.env['ir.attachment']._ems_queue_existing_compression()
        self.assertFalse(self._jobs(loaded))
