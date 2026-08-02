"""grading extension tests — tf / standard / error_case question types."""

from __future__ import annotations

from deeptutor.learning.grading import grade_answer


def test_grade_tf_true():
    assert grade_answer("对", "对", question_type="tf")
    assert grade_answer("正确", "正确", question_type="tf")


def test_grade_tf_false():
    assert not grade_answer("对", "错", question_type="tf")


def test_grade_standard_valid_box():
    expected = '{"required_fields":["x","y","w","h","label"]}'
    answer = '{"x":10,"y":10,"w":100,"h":100,"label":"car"}'
    assert grade_answer(answer, expected, question_type="standard")


def test_grade_standard_missing_field():
    expected = '{"required_fields":["x","y","w","h","label"]}'
    answer = '{"x":10,"y":10,"w":100,"h":100}'  # missing label
    assert not grade_answer(answer, expected, question_type="standard")


def test_grade_error_case():
    expected = '{"errors":[1,3]}'
    answer = "[1,3]"
    assert grade_answer(answer, expected, question_type="error_case")


def test_grade_error_case_partial():
    expected = '{"errors":[1,3]}'
    answer = "[1]"
    assert not grade_answer(answer, expected, question_type="error_case")


def test_grade_standard_non_dict_expected_fails_closed():
    answer = '{"x":10,"y":10,"w":100,"h":100,"label":"car"}'
    assert not grade_answer(answer, "[1,2,3]", question_type="standard")


def test_grade_error_case_non_dict_expected_fails_closed():
    assert not grade_answer("[1,3]", "null", question_type="error_case")


def test_grade_tf_unrecognized_input_fails_closed():
    assert not grade_answer("maybe", "maybe", question_type="tf")
