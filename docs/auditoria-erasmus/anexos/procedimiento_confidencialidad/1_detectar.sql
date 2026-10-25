-- Read-only. Erasmus+ documents that hold health, inclusion or bank data and are NOT marked confidential.
-- Run as: sudo -u postgres psql -d <db> -f 1_detectar.sql   (no row = nothing to fix)
-- Matches the default names in Catalan, Spanish and English; review any document renamed by hand.
SELECT 'call document' AS kind, d.id, COALESCE(d.call_id::text, 'group ' || d.group_mobility_id) AS owner,
       d.stage, d.confidential, d.file_category, d.name
  FROM ems_erasmus_call_document d
 WHERE COALESCE(d.confidential, FALSE) = FALSE
   AND d.name ~* '(sanit|health|salud|inclusi|bancari|bank|iban)'
UNION ALL
SELECT 'document line', l.id, COALESCE(l.application_id::text, 'group ' || l.group_mobility_id), l.stage,
       l.confidential, l.file_category, d.name
  FROM ems_erasmus_application_document l
  JOIN ems_erasmus_call_document d ON d.id = l.call_document_id
 WHERE COALESCE(d.confidential, FALSE) <> COALESCE(l.confidential, FALSE)
 ORDER BY 1, 2;
