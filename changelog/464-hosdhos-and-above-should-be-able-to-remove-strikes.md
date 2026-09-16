# What's new:

## Head of Studies, Deputy Head of Studies, Director and Coexistence coordinators can now delete strikes:
- Previously only Administrators could delete a disciplinary strike (`ems.strike`). Added `rule_strike_head_of_studies` (`security/rules/coexistence.xml`) granting Head of Studies / Deputy Head of Studies / Director (`ems.group_head_of_studies`, also reached by `group_director`/`group_academic_admin` via implication) delete access to any strike centre-wide, plus a matching `access_ems_strike_head_of_studies` ACL row (`security/ir.model.access.csv`).
- Extended the existing `rule_strike_coexistence` rule and `access_ems_strike_coexistence` ACL row to also grant Coexistence coordinators (`ems.group_coexistence`/`group_coexistence_admin`) delete access to any strike centre-wide, matching their existing transversal read access.
- Corrected the Head of Studies user manual and the `ems.strike` developer documentation, which incorrectly stated Head of Studies/Deputy Head of Studies/Director only saw their own issued/tutee strikes — they already had centre-wide read access via `group_student_data_reader` (issue #448); the docs now describe this correctly alongside the new delete capability.

# Related with:
- Closes #464
