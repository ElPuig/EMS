# What's new:
## Uploaded PDF files and images are compressed automatically:
- Every PDF and JPG/PNG uploaded to EMS (strike calls, justifications, student documents, portal uploads...) is stored as uploaded and replaced in the background by a lighter copy when that saves at least 10 %. Scans shrink by about 90 %.
- PDF files with a digital signature, encrypted ones, generated documents and files under 300 KB (setting `ems.compress_min_kb`) are never touched. Images are also straightened and stripped of their EXIF metadata, and a PNG without transparency is stored as JPG.
- Files uploaded before this version are not changed.

# Internal changes:
## Ghostscript added as a system dependency:
- `apt-requirements.txt` now lists `ghostscript`, installed by `install.sh`, `upgrade.sh` (so every deploy) and the CI. Without it PDF files are left uncompressed and only images are processed.
- New `ems.file_compression` service (shared by the `ir.attachment` hook and tested on its own) and `queue_job` job `_ems_compress`.
