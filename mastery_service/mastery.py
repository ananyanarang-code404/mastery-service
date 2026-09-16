"""Pure mastery scoring logic — no DB or HTTP concerns."""

MASTERY_ALPHA = 0.2


def apply_attempt(current_score: int, is_correct: bool) -> int:
    """Exponential moving average: move the score partway toward the target
    this attempt suggests (100 = correct, 0 = incorrect), then round and
    clamp to 0-100.

    alpha=0.2 means each correct attempt closes a fifth of the remaining
    gap to 100; an incorrect attempt moves a fifth of the way toward 0.
    Recent attempts therefore weigh more than old ones, the score never
    saturates instantly, and one wrong answer lowers but does not reset.
    """
    target = 100 if is_correct else 0
    new_score = round(current_score + MASTERY_ALPHA * (target - current_score))
    return max(0, min(100, new_score))