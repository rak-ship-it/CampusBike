import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from return_validation import validate_return_identifiers

class ReturnValidationTests(unittest.TestCase):
    def test_rejects_non_objects(self):
        for value in (None, [], 1, 'ride'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_return_identifiers(value)

    def test_rejects_unbindable_or_ambiguous_ids(self):
        for field in ('ride_id', 'station_id'):
            for value in ([], {}, True, False, 1.0, '1', 0, -1, 2**63, None):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_return_identifiers({field:value})

    def test_dock_label_and_valid_ids(self):
        validate_return_identifiers({'ride_id':1,'station_id':2,'slot_number':'SLOT-01'})
        validate_return_identifiers({})
        for value in ([], {}, 1, True, '', 'x'*101, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_return_identifiers({'slot_number':value})
