import pytest

from larcutils.common import Null

from coursework import canvas

def test_map_answer_keys():
    assert canvas.quiz.map_answer_keys({'comments': ''}) == {
        'answer_comments': ''
    }
    assert canvas.quiz.map_answer_keys({'match_left': ''}) == {
        'answer_match_left': ''
    }
    assert canvas.quiz.map_answer_keys({'ml': ''}) == {
        'answer_match_left': ''
    }
    assert canvas.quiz.map_answer_keys({'match_right': ''}) == {
        'answer_match_right': ''
    }
    assert canvas.quiz.map_answer_keys({'mr': ''}) == {
        'answer_match_right': ''
    }
    assert canvas.quiz.map_answer_keys({'incorrect': ''}) == {
        'matching_answer_incorrect_matches': ''
    }
    assert canvas.quiz.map_answer_keys({'weight': ''}) == {
        'answer_weight': ''
    }
    assert canvas.quiz.map_answer_keys({'w': ''}) == {
        'answer_weight': ''
    }
    assert canvas.quiz.map_answer_keys({'html': ''}) == {
        'answer_html': ''
    }
    assert canvas.quiz.map_answer_keys({'h': ''}) == {
        'answer_html': ''
    }
    assert canvas.quiz.map_answer_keys({'text': ''}) == {
        'answer_text': ''
    }
    assert canvas.quiz.map_answer_keys({'t': ''}) == {
        'answer_text': ''
    }

def test_no_text_or_html():
    assert not canvas.quiz.process_answer(None, None, {})

# def test_get_quizzes(quizzes):
#     assert len(quizzes) == 12
