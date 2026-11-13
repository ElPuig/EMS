# Changes

## Generic minutes require their scope:

- The "Scope of the meeting" of a generic minute starts empty and must be chosen before saving (any of its values, "No particular scope" included); choosing a department, workgroup or group then requires that record.
- The same rule is checked on the server (`_check_scope_is_set`), so a minute created by code can't go without the scope its type asks for either. The code preview waits until the scope is chosen.
