# Fixes

## Student walkout minute (table borders and supporting document link):

- The minute's row labels were `<th>` cells, so the company's rounded table layout (`o_table_boxed-rounded`, "bubble" layout) curved the left corner of every row. They are now bold `<td>` cells, and each table is drawn as a single box with rounded outer corners.
- The supporting document's name is now a link to its download (`/web/content/<id>?download=true`, absolute URL). The minute only reaches staff (Head of Studies / Deputy Head of Studies), who can read the walkout's attachments once logged in.
