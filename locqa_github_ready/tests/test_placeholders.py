import pytest
from locqa.cli import safe_translation

@pytest.mark.parametrize('source,target', [
    ('Привет {name}', 'Сәлем, {name}'),
    ('{count} предметов', '{count} зат'),
    ('<g>{name}</g>: %s1 / %s2', '<g>{name}</g>: %s1 / %s2'),
])
def test_placeholders_and_tokens_preserved(source,target):
    safe_translation(source,target)

@pytest.mark.parametrize('source,target', [
    ('Привет {name}', 'Сәлем'),
    ('{count} предметов', '{n} зат'),
    ('Привет <nick>', 'Сәлем <name>'),
    ('<g>{name}</g>', '{name}'),
])
def test_unsafe_replacement_rejected(source,target):
    with pytest.raises(ValueError): safe_translation(source,target)
