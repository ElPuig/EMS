# -*- coding: utf-8 -*-
import logging
import os
import shutil
import subprocess
import tempfile

from odoo import api, models
from odoo.tools.image import ImageProcess

_logger = logging.getLogger(__name__)

PDF_MIMETYPE = 'application/pdf'
IMAGE_MIMETYPES = ('image/jpeg', 'image/png')
# 150 dpi: sharp on screen and in print, and the profile that shrinks scans the most without making
# a handwritten signature illegible.
GHOSTSCRIPT_ARGS = ['-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.5', '-dPDFSETTINGS=/ebook',
                    '-dDetectDuplicateImages=true', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dSAFER']
GHOSTSCRIPT_TIMEOUT = 120
# The same limit as Odoo's own (base.image_autoresize_max_px, 1920x1920), which resizes an image when
# it is stored but neither re-encodes one that already fits nor drops its EXIF metadata.
IMAGE_MAX_SIDE = 1920
IMAGE_QUALITY = 85
# A result must save at least 10 %: a smaller gain is not worth replacing the user's file.
MAX_RESULT_RATIO = 0.9


class EmsFileCompression(models.AbstractModel):
    """Shrinks a PDF (Ghostscript) or a JPEG/PNG image (Pillow, through Odoo's ImageProcess).
    Pure functions on bytes: they return the smaller content, or False when the file must stay as
    it is (not worth it, signed, encrypted, unreadable, engine missing or failing)."""
    _name = 'ems.file_compression'
    _description = 'File compression'

    @api.model
    def compress(self, raw, mimetype):
        if mimetype == PDF_MIMETYPE:
            result = self._compress_pdf(raw)
        elif mimetype in IMAGE_MIMETYPES:
            result = self._compress_image(raw)
        else:
            return False
        return result if result and len(result) <= len(raw) * MAX_RESULT_RATIO else False

    @api.model
    def compressible_mimetypes(self):
        """The types this installation can compress: PDF only when Ghostscript is installed."""
        return list(IMAGE_MIMETYPES) + ([PDF_MIMETYPE] if shutil.which('gs') else [])

    @api.model
    def _compress_pdf(self, raw):
        # A digital signature covers the exact bytes of the file (/ByteRange): rewriting the PDF
        # would invalidate it. An encrypted one cannot be rewritten at all.
        if b'/ByteRange' in raw or b'/Encrypt' in raw:
            return False
        gs = shutil.which('gs')
        if not gs:
            return False
        try:
            with tempfile.TemporaryDirectory(prefix='ems_compress_') as folder:
                source, target = os.path.join(folder, 'in.pdf'), os.path.join(folder, 'out.pdf')
                with open(source, 'wb') as file:
                    file.write(raw)
                subprocess.run([gs, *GHOSTSCRIPT_ARGS, f'-sOutputFile={target}', source],
                               check=True, capture_output=True, timeout=GHOSTSCRIPT_TIMEOUT)
                with open(target, 'rb') as file:
                    result = file.read()
                pages = self._pdf_pages(source)
                if not pages or pages != self._pdf_pages(target):
                    return False
            return result
        except Exception as error:  # a broken PDF, a timeout, gs failing: the original stays
            _logger.warning("PDF not compressed: %s", error)
            return False

    @api.model
    def _pdf_pages(self, path):
        """Number of pages, read by poppler's pdfinfo (already a dependency, issue #585), which also
        reads the PDF files with a damaged xref table that PyPDF2 refuses (6 % of the centre's)."""
        output = subprocess.run(['pdfinfo', path], capture_output=True, text=True, timeout=30).stdout
        return int(next((line.split()[1] for line in output.splitlines() if line.startswith('Pages:')), 0))

    @api.model
    def to_jpeg(self, image):
        """The upright, resized JPEG of an ImageProcess (what a photo or a scan is stored as).
        Re-encoding drops the EXIF metadata, which in a phone photo carries the GPS position."""
        image.resize(IMAGE_MAX_SIDE, IMAGE_MAX_SIDE)
        return image.image_quality(quality=IMAGE_QUALITY, output_format='JPEG')

    @api.model
    def _compress_image(self, raw):
        try:
            image = ImageProcess(raw)
            if not image.image:
                return False
            # A PNG with transparency stays PNG (resized only); anything else is a photo or a scan.
            if 'A' in image.image.getbands() or 'transparency' in image.image.info:
                image.resize(IMAGE_MAX_SIDE, IMAGE_MAX_SIDE)
                return image.image_quality(quality=0, output_format='PNG')
            return self.to_jpeg(image)
        except Exception as error:
            _logger.warning("Image not compressed: %s", error)
            return False
