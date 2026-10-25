"""Explicit, reusable grouping rules; the DEV rule remains the default."""
DEV_DESCRIPTION = 'dev_description'
PROD_MODEL_RESPONSIBLE = 'prod_model_responsible'
FIELDS = ('numero_parte', 'descripcion', 'modelo', 'responsable')


def report_group_key(record, rule=DEV_DESCRIPTION):
    if rule == DEV_DESCRIPTION:
        fields = ('numero_parte', 'descripcion')
    elif rule == PROD_MODEL_RESPONSIBLE:
        fields = ('numero_parte', 'modelo', 'responsable')
    else:
        raise ValueError(f'Unknown report grouping rule: {rule}')
    return tuple((record.get(field) or '').strip().upper() for field in fields)
