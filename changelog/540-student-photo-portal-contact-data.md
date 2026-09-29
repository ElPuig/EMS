# What's new

## Student photo in the portal contact details review (#540, follow-up to #507):

- Students and families can send the student's photo from the same portal page where they review
  their contact details (/my/dades-contacte). It is optional: a missing photo is never listed as
  missing data nor blocks sending.
- The photo goes through the same review as every other change: the tutor, the secretariat or the
  head of studies sees the photo on file and the proposed one side by side in the request's list of
  changes (bigger on hover, and side by side at a large size when the change is opened), and it is
  only written to the student when the request is approved.
- The photo picked opens in an editor with a portrait frame: it can be moved, zoomed and rotated
  (e.g. to frame the face of a full-length photo), and the result is previewed next to the photo
  on file before sending. Only the framed photo is sent.
- Only JPG and PNG images up to 10 MB are accepted, checked on the file's real content. The photo
  is turned upright, resized to at most 1920 px and re-encoded as JPEG, which drops its EXIF
  metadata (a phone photo carries the GPS position where it was taken).
- A photo already sent is kept when the form comes back with errors or is sent again while it
  waits for review, so the family does not have to pick it again.
- Family and tutor manuals (Catalan, Spanish, English) explain how to send and review the photo,
  with screenshots on an invented student drawn as an illustration.

# Fixes

## Contact details page for an account with no student:

- /my/dades-contacte failed with a server error for a portal account with no student to review
  (e.g. an account not linked to any student); it now shows the "no contact details to review"
  notice.
