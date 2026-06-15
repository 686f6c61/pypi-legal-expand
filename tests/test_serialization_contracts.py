"""
Contratos pequeños de serialización JSON-friendly.
"""

from enum import Enum

from legal_expand.types import Position, _to_plain


class _FixtureEnum(Enum):
    ACTIVE = 'active'


def test_to_plain_handles_dicts_sets_tuples_and_enums():
    value = {
        'position': Position(1, 4),
        'states': {_FixtureEnum.ACTIVE},
        7: ('x', Position(2, 3)),
    }

    plain = _to_plain(value)

    assert plain == {
        'position': {'start': 1, 'end': 4},
        'states': ['active'],
        '7': ['x', {'start': 2, 'end': 3}],
    }
