"""The answer record keeps question and answer with no identifier, and the
background check replaces or drops only the sentences it was told about."""
import json
import os

from backend.assistant import background_check, record


def test_record_writes_one_json_line_without_identifiers(tmp_path, monkeypatch):
    monkeypatch.setenv('TESSERAE_ASSISTANT_RECORD', str(tmp_path))
    assert record.record('guide', 'What can you do?', 'Two things.', model_used=True,
                         background={'checked': False})
    files = list(tmp_path.glob('*.jsonl'))
    assert len(files) == 1
    row = json.loads(files[0].read_text(encoding='utf-8').splitlines()[0])
    assert row['kind'] == 'guide' and row['question'] == 'What can you do?'
    assert row['answer'] == 'Two things.' and row['model_used'] is True
    for forbidden in ('ip', 'remote_addr', 'session', 'user', 'cookie'):
        assert forbidden not in row


def test_record_can_be_turned_off(tmp_path, monkeypatch):
    monkeypatch.setenv('TESSERAE_ASSISTANT_RECORD', '0')
    assert record.record('guide', 'q', 'a') is False
    assert not list(tmp_path.glob('*'))


def test_apply_replaces_a_flagged_sentence_and_drops_when_asked():
    answer = ('Dracontius was a Latin poet active in the sixth century. He wrote the Romulea. '
              'His Orestes retells the murder of Agamemnon in 974 lines.')
    text, applied = background_check.apply(answer, [
        {'sentence': 'Dracontius was a Latin poet active in the sixth century.',
         'claim': 'sixth century', 'revised': 'Dracontius was a Latin poet of late antiquity.'},
        {'sentence': 'His Orestes retells the murder of Agamemnon in 974 lines.',
         'claim': 'contents of Orestes', 'revised': ''}])
    assert text == 'Dracontius was a Latin poet of late antiquity. He wrote the Romulea.'
    assert [a['dropped'] for a in applied] == [False, True]


def test_apply_refuses_a_revision_that_adds_a_digit_or_grows_too_much():
    answer = ('He died in the fifth century. He wrote hymns that the site holds in two '
              'collections, and a two-text comparison with Prudentius is the place to start.')
    text, applied = background_check.apply(answer, [
        {'sentence': 'He died in the fifth century.', 'claim': 'date',
         'revised': 'He died in 484.'}])
    assert text.startswith('He wrote hymns') and applied[0]['dropped'] is True


def test_apply_leaves_the_answer_alone_rather_than_gut_it():
    answer = 'Only sentence, with a date of 1200.'
    text, applied = background_check.apply(answer, [
        {'sentence': 'Only sentence, with a date of 1200.', 'claim': 'date', 'revised': ''}])
    assert text == answer and applied == []


def test_review_uses_the_model_and_returns_a_verdict(monkeypatch):
    monkeypatch.setenv('TESSERAE_ASSISTANT_BACKGROUND_CHECK', '1')
    monkeypatch.setattr(background_check.model, 'complete', lambda *a, **k: json.dumps({
        'unsupported': [{'sentence': 'He lived in the ninth century.', 'claim': 'ninth century',
                         'revised': 'He lived in the early Middle Ages.'}]}))
    text, verdict = background_check.review(
        'He lived in the ninth century. The site holds his Carmina.', 'WHAT THIS SITE HOLDS BY X:\n- Carmina')
    assert text == 'He lived in the early Middle Ages. The site holds his Carmina.'
    assert verdict['checked'] and verdict['flagged'] == 1 and len(verdict['revised']) == 1


def test_review_is_off_when_disabled(monkeypatch):
    monkeypatch.setenv('TESSERAE_ASSISTANT_BACKGROUND_CHECK', '0')
    called = []
    monkeypatch.setattr(background_check.model, 'complete', lambda *a, **k: called.append(1) or '{}')
    text, verdict = background_check.review('Anything.', 'material')
    assert text == 'Anything.' and verdict == {'checked': False} and not called


def test_worth_checking_fires_on_background_or_dates_not_on_line_numbers():
    assert background_check.worth_checking('As background, Lucan wrote under Nero.')
    assert background_check.worth_checking('Statius wrote in the first century AD.')
    assert not background_check.worth_checking('Aeneid 1.150 and Lucan 1.8 share furor.')
