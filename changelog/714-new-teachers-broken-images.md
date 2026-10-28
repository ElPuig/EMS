# Fixes

## New teachers' photo shown as "Binary file" (initials placeholder stored as text/plain):

- When a Head of Studies created a teacher's EMS account (Google Workspace integration), Odoo baked the user's initials placeholder as that Head of Studies, who can't write views, so the SVG was stored as text/plain and copied that way onto the teacher: both showed "Binary file" instead of the initials.
- Creating or linking a user to an employee now regenerates the placeholder as the superuser on the employee and the user (`_refresh_stale_avatar_placeholder()`), always generating it again instead of elevating the stored bytes, so no foreign SVG is ever served as an image.
- Migration 18.0.0.41.1 repairs the photos already broken: every employee or contact whose photo is an SVG stored as text/plain (or whose file is missing) gets a fresh placeholder (63 on the dev database).
