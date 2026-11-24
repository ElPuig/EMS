# Changes

## ASP job position declared on the department (issue #815):

- Departments of the ASP area now have a Job Position; every ASP member takes it, and it is hidden on the employee form, where it only repeated the department. It keeps granting its security group.
- The departments list shows the Manager that applies, also when it is shared with the parent department.

# Internal changes

## Existing installations get the department's job position:

- A migration (18.0.0.51.1) sets each ASP department's job position when all its members already share one; departments with several different ones are logged and left for an administrator.

# Related with

- Closes #815
