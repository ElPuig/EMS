[Català](../../ca/admin/uploaded-files-compression.md) | [Castellano](../../es/admin/uploaded-files-compression.md) | [English](uploaded-files-compression.md)

---

# Automatic compression of uploaded files

EMS shrinks the PDF files and the images (JPG, PNG) that are uploaded to it, so that scans and phone photos do not fill the server. It happens by itself, in the background, a few seconds after the upload: nobody has to do anything.

**Role required:** none (automatic). The setting below is for the Administrator.

---

## What happens

- The file is stored as it was uploaded and can be opened straight away. Within seconds to a minute, EMS replaces it with a lighter copy if that saves at least 10 %. The original is **not** kept.
- PDF files are re-saved at screen quality (150 dpi): they stay perfectly readable and printable, but the pictures inside them weigh much less.
- Images are turned upright, reduced to at most 1920 pixels on the long side and saved as JPG with the same sharpness to the eye. A PNG without transparency becomes a JPG (its name ends in `.jpg`). The photo's hidden data (such as the place where a phone took it) is removed.

## What is never changed

- PDF files with a **digital signature**, and protected (encrypted) PDF files: changing them would invalidate the signature.
- Files smaller than 300 KB, and any file whose compressed version is not at least 10 % smaller.
- The documents EMS generates itself (approved quality records, reports) and the Erasmus+ templates.

> The compression was introduced in version 18.0.0.51.0. Files uploaded before it are not changed.

## Setting

In **Settings → Technical → System Parameters**, the parameter `ems.compress_min_kb` (default `300`) is the minimum size in KB for a file to be compressed.

If the server has no Ghostscript installed, PDF files are left as uploaded and only the images are compressed.
