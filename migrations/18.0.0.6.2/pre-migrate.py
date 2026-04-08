import logging

_logger = logging.getLogger(__name__)
def migrate(cr, version):    
    module = 'ems'
    old_id = 'ems.level_cfpb'
    new_id = 'ems.level_cfgb'

    _logger.info(f"Renaming external_id from '{old_id}' to '{new_id}'.")
    cr.execute("UPDATE ir_model_data SET name = %s WHERE module = %s AND name = %s", (new_id, module, old_id))

    field_rename = [('ems_level', 'acronym', 'CFPB', 'CFGB')]
    for table, column, old_value, new_value in field_rename:
        _logger.info(f"Migration: Renaming field '{table}.{column}' from '{old_value}' to '{new_value}'.")
        cr.execute("UPDATE %s SET %s='%s' WHERE %s='%s'" % (table,column,new_value,column,old_value))