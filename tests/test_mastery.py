"""Unit tests for the pure EMA mastery scoring logic."""

from mastery_service.mastery import apply_attempt


def test_first_correct_initializes_at_20():
    assert apply_attempt(0, True) == 20


def test_first_incorrect_keeps_zero():
    assert apply_attempt(0, False) == 0


def test_consecutive_corrects_climb():
    score = 0
    for expected in [20, 36, 49, 59, 67, 74, 79, 83]:
        score = apply_attempt(score, True)
        assert score == expected


def test_many_corrects_converge_but_never_exceed_100():
    score = 0
    for _ in range(500):
        new = apply_attempt(score, True)
        assert new >= score
        score = new
        assert 0 <= score <= 100
    assert score >= 90


def test_many_incorrects_converge_but_never_below_0():
    score = 100
    for _ in range(500):
        new = apply_attempt(score, False)
        assert new <= score
        score = new
        assert 0 <= score <= 100
    assert score <= 10


def test_wrong_attempt_lowers_without_resetting():
    score = 67
    lowered = apply_attempt(score, False)
    assert 0 < lowered < score


def test_alternating_correct_wrong_stays_bounded():
    score = 50
    for i in range(100):
        score = apply_attempt(score, i % 2 == 0)
        assert 0 <= score <= 100