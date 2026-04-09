# Migration Notes

## v18.0.0.6.0 — Partner categories sync

After deploying this version, run the following command **once** to assign the correct partner category (`Student`, `Family`, `Provider`) to all existing contacts based on their `contact_type`:

```bash
sudo -u odoo odoo shell -d ems -c /etc/odoo/odoo.conf --no-http << 'EOF'
cat_student = env.ref('ems.partner_category_student')
cat_family = env.ref('ems.partner_category_family')
cat_provider = env.ref('ems.partner_category_provider')
all_managed = cat_student | cat_family | cat_provider
category_map = {'student': cat_student, 'family': cat_family, 'provider': cat_provider}
partners = env['res.partner'].search([('contact_type', 'in', ['student', 'family', 'provider'])])
for p in partners:
    cat = category_map.get(p.contact_type)
    if cat:
        p.category_id = (p.category_id - all_managed) | cat
env.cr.commit()
print(f"Synced {len(partners)} partners")
EOF
```

This is only needed for existing data. New partners will get their category assigned automatically on create/write.
