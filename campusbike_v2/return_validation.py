"""Validate return identifiers before binding untrusted JSON to SQLite."""

def validate_return_identifiers(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object.')
    # Missing values retain the route's existing missing/stale assignment errors.
    for key in ('ride_id', 'station_id'):
        if key in data and (type(data[key]) is not int or not 1 <= data[key] <= 9223372036854775807):
            raise ValueError(f'{key} must be a positive integer.')
    if 'slot_number' in data and (not isinstance(data['slot_number'], str) or not 1 <= len(data['slot_number']) <= 100):
        raise ValueError('slot_number must be a non-empty dock label.')
