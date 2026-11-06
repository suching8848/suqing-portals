"""Keep one canonical Steam item identity per independent project.

This module performs local validation only; it never queries or mutates Steam.
"""
import json
import re
from pathlib import Path

ID_FIELDS = ('publishedfileid', 'workshop_item_id', 'workshop_id')

def normalize_item_id(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValueError('Workshop item ID must be a positive decimal integer')
    text = str(value)
    if not re.fullmatch(r'[1-9][0-9]{0,19}', text) or int(text) >= 2**64:
        raise ValueError('Workshop item ID must be a positive uint64 decimal integer')
    return text

def item_ids(record):
    return {value for key in ID_FIELDS if (value := normalize_item_id(record.get(key))) is not None}

def resolve_workshop_item(publishing, mod_id, metadata=None):
    """Missing identity means a new private draft; an assigned item is reused.

    Reject foreign app/project identities and stale conflicting metadata rather
    than silently dropping an ID and allowing a duplicate Workshop creation.
    """
    path = Path(publishing) / 'workshop-item.json'
    metadata_ids = item_ids(metadata or {})
    if len(metadata_ids) > 1:
        raise ValueError('Conflicting Workshop IDs in publication metadata')
    if not path.exists():
        if metadata_ids:
            raise ValueError('Assigned metadata requires publishing/workshop-item.json')
        return None
    record = json.loads(path.read_text(encoding='utf-8-sig'))
    if record.get('app_id') != 108600:
        raise ValueError('Workshop identity belongs to another Steam app')
    if record.get('mod_id') != mod_id:
        raise ValueError('Workshop identity belongs to another Mod ID')
    if 'mod_ids' in record and record['mod_ids'] != [mod_id]:
        raise ValueError('Workshop identity must bind exactly this one main Mod ID')
    canonical_ids = item_ids(record)
    if len(canonical_ids) != 1:
        raise ValueError('Canonical identity needs exactly one consistent assigned Workshop ID')
    item_id = next(iter(canonical_ids))
    if metadata_ids and metadata_ids != canonical_ids:
        raise ValueError('Publication metadata conflicts with canonical Workshop identity')
    return item_id

def native_item_id_lines(item_id):
    item_id = normalize_item_id(item_id)
    return [] if item_id is None else ['id=' + item_id]
