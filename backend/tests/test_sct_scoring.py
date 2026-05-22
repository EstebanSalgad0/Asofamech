from app.routers.sct import calculate_sct_attempt_score, is_sct_answer_correct
from app.schemas import SCTAnswerItem


def test_sct_scoring_requires_exact_answer():
    assert is_sct_answer_correct(2, 2)
    assert is_sct_answer_correct(0, 0)
    assert not is_sct_answer_correct(2, 1)
    assert not is_sct_answer_correct(0, -1)


def test_calculate_sct_attempt_score_uses_exact_answers():
    items = [
        {"id": 1, "correct_answer": 2},
        {"id": 2, "correct_answer": 0},
        {"id": 3, "correct_answer": -2},
    ]
    answers = [
        SCTAnswerItem(item_id=1, selected_answer=2),
        SCTAnswerItem(item_id=2, selected_answer=-1),
        SCTAnswerItem(item_id=3, selected_answer=0),
    ]

    correct_count, total, score = calculate_sct_attempt_score(items, answers)

    assert correct_count == 1
    assert total == 3
    assert score == 0.3333
