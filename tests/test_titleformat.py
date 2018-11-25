#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from euphonogenizer import titleformat
from euphonogenizer.common import unistr

import pytest

cs_01 = {
      "@" : "01. This.flac",
      "ALBUM" : "See What You Started by Continuing (Deluxe Edition)",
      "ARTIST" : "Collective Soul",
      "COMMENT" : "Van-38004-02 Vanguard Records",
      "DATE" : "2015",
      "DISCNUMBER" : "1",
      "GENRE" : "Rock",
      "REPLAYGAIN_ALBUM_GAIN" : "-11.65 dB",
      "REPLAYGAIN_ALBUM_PEAK" : "1.000000",
      "REPLAYGAIN_TRACK_GAIN" : "-12.10 dB",
      "REPLAYGAIN_TRACK_PEAK" : "1.000000",
      "TITLE" : "This",
      "TOTALDISCS" : "2",
      "TOTALTRACKS" : "11",
      "TRACKNUMBER" : "01"
}

fake_track = {
    "FAKEDASH" : "-",
}

window_title_integration_fmt = (
    "[%artist% - ]%title%["
      + " '['["
         + "#$num(%tracknumber%, 0)"
         + "$if(%totaltracks%,[ of $num(%totaltracks%, 0)])"
      + "]"
    + "] on %album%[ '('%date%')']["
      + "$ifgreater(%totaldiscs%,1, "
        + "$if("
              + "$strcmp(%discnumber%,A)"
              + "$strcmp(%discnumber%,B)"
              + "$strcmp(%discnumber%,C)"
              + "$strcmp(%discnumber%,D),"
          + "'{'Side %discnumber%'}',"
          + "'{'Disc %discnumber% of %totaldiscs%"
            + "$if2( - %set subtitle%,)'}'"
        + ")"
      + ",)"
    + "]"
    + "$if($or(%tracknumber%,%totaltracks%),']')"
)

window_title_integration_expected = (
    'Collective Soul - This'
    + ' [#1 of 11 on See What You Started by Continuing'
    + ' (Deluxe Edition) (2015) {Disc 1 of 2}]'
)

f = titleformat.TitleFormatter()
fdbg = titleformat.TitleFormatter(debug=True)

test_eval_cases = [
    # Variable resolution tests
    pytest.param(
      '%artist% - ', 'Collective Soul - ', True, cs_01,
      id='artist_variable_lookup'),
    pytest.param(
      '[%artist% - ]', 'Collective Soul - ', True, cs_01,
      id='artist_variable_lookup_cond'),
    # Arithmetic: $add()
    pytest.param('$add()!a$add()', '0!a0', False, {}, id='add_arity0'),
    pytest.param('$add(123)', '123', False, {}, id='add_arity1'),
    pytest.param('$add(-)', '0', False, {}, id='add_arity1_dash'),
    pytest.param('$add(0)', '0', False, {}, id='add_arity1_zero'),
    pytest.param('$add(-0)', '0', False, {}, id='add_arity1_negative_zero'),
    pytest.param('$add(007)', '7', False, {}, id='add_arity1_leading_zeroes'),
    pytest.param('$add(-007)', '-7', False, {},
      id='add_arity1_negative_leading_zeroes'),
    pytest.param('$add(12,34)', '46', False, {}, id='add_arity2'),
    pytest.param('$add(,)', '0', False, {}, id='add_arity2_blanks'),
    pytest.param('$add(1,2,3)', '6', False, {}, id='add_arity3'),
    pytest.param(
        '$add(  -1!a,-1- , -2 -9-  ,-3a bc  )', '-7', False, {},
        id='add_arity3_trailing_chars'),
    pytest.param('$add(1,2,3,4)', '10', False, {}, id='add_arity4'),
    pytest.param(
        '$add(  -1!a,-1- , -2 -9-  ,-3a bc  ,10-)', '3', False, {},
        id='add_arity4_trailing_chars'),
    pytest.param(
        '$add(1,$add(1,$add(1,$add(1))))', '4', False, {},
        id='add_arity2_nested_ones'),
    pytest.param(
        '$add(1,$add(2,$add(3,$add(4))))', '10', False, {},
        id='add_arity2_nested_positive_integers'),
    pytest.param(
        '$add(-1,$add(-2,$add(-3,$add(-4))))', '-10', False, {},
        id='add_arity2_nested_negative_integers'),
    pytest.param(
        # Foobar can't negate functions, so it will return the first value.
        '$add(-1,-$add(-2,-$add(-3)))', '-1', False, {},
        id='add_arity2_nested_negative_integers_negation'),
    pytest.param(
        # Same here, but it actually sums the first two.
        '$add(-2,-6,-$add(-2,-$add(-3)))', '-8', False, {},
        id='add_arity3_nested_negative_integers_negation1'),
    pytest.param(
        '$add(-3,-$add(-2,-$add(-3)),-4)', '-7', False, {},
        id='add_arity3_nested_negative_integers_negation2'),
    pytest.param(
        '$add($add($add(1,$add(5))),$add(2,$add(3,$add(4))))', '15', False, {},
        id='add_arity2_nested_branching_positive_integers'),
    # Arithmetic: $sub()
    pytest.param('$sub()!a$sub()', '!a', False, {}, id='sub_arity0'),
    pytest.param('$sub(123)', '123', False, {}, id='sub_arity1'),
    pytest.param('$sub(-)', '0', False, {}, id='sub_arity1_dash'),
    pytest.param('$sub(0)', '0', False, {}, id='sub_arity1_zero'),
    pytest.param('$sub(-0)', '0', False, {}, id='sub_arity1_negative_zero'),
    pytest.param('$sub(007)', '7', False, {}, id='sub_arity1_leading_zeroes'),
    pytest.param('$sub(-007)', '-7', False, {},
      id='sub_arity1_negative_leading_zeroes'),
    pytest.param('$sub(12,34)', '-22', False, {}, id='sub_arity2'),
    pytest.param('$sub(,)', '0', False, {}, id='sub_arity2_blanks'),
    pytest.param('$sub(1,2,3)', '-4', False, {}, id='sub_arity3'),
    pytest.param(
        '$sub(  -1!a,-1- , -2 -9-  ,-3a bc  )', '5', False, {},
        id='sub_arity3_trailing_chars'),
    pytest.param('$sub(1,2,3,4)', '-8', False, {}, id='sub_arity4'),
    pytest.param(
        '$sub(  -1!a,-1- , -2 -9-  ,-3a bc  ,10-)', '-5', False, {},
        id='sub_arity4_trailing_chars'),
    pytest.param(
        '$sub(1,$sub(1,$sub(1)))', '1', False, {},
        id='sub_arity2_nested_ones3'),
    pytest.param(
        '$sub(1,$sub(1,$sub(1,$sub(1))))', '0', False, {},
        id='sub_arity2_nested_ones4'),
    pytest.param(
        '$sub(1,$sub(2,$sub(3,$sub(4))))', '-2', False, {},
        id='sub_arity2_nested_positive_integers'),
    pytest.param(
        '$sub(-1,$sub(-2,$sub(-3,$sub(-4))))', '2', False, {},
        id='sub_arity2_nested_negative_integers'),
    pytest.param(
        # Foobar can't negate functions, so it will return the first value.
        '$sub(-1,-$sub(-2,-$sub(-3)))', '-1', False, {},
        id='sub_arity2_nested_negative_integers_negation'),
    pytest.param(
        # Same here, but it actually sums the first two.
        '$sub(-2,-6,-$sub(-2,-$sub(-3)))', '4', False, {},
        id='sub_arity3_nested_negative_integers_negation1'),
    pytest.param(
        '$sub(-3,-$sub(-2,-$sub(-3)),-4)', '1', False, {},
        id='sub_arity3_nested_negative_integers_negation2'),
    pytest.param(
        '$sub($sub($sub(1,$sub(5))),$sub(2,$sub(3,$sub(4))))', '-7', False, {},
        id='sub_arity2_nested_branching_positive_integers'),
    # Arithmetic: $mul()
    pytest.param('$mul()!a$mul()', '1!a1', False, {}, id='mul_arity0'),
    pytest.param('$mul(123)', '123', False, {}, id='mul_arity1'),
    pytest.param('$mul(-456)', '-456', False, {}, id='mul_arity1_negative'),
    pytest.param('$mul(-)', '0', False, {}, id='mul_arity1_dash'),
    pytest.param('$mul(0)', '0', False, {}, id='mul_arity1_zero'),
    pytest.param('$mul(-0)', '0', False, {}, id='mul_arity1_negative_zero'),
    pytest.param('$mul(70, 20)', '1400', False, {}, id='mul_arity2'),
    pytest.param('$mul(1000, 10)', '10000', False, {}, id='mul_arity2_10'),
    pytest.param('$mul(,)', '0', False, {}, id='mul_arity2_blanks'),
    pytest.param('$mul(-,)', '0', False, {}, id='mul_arity2_dash_blank'),
    pytest.param('$mul(,-)', '0', False, {}, id='mul_arity2_blank_dash'),
    pytest.param('$mul(-,-)', '0', False, {}, id='mul_arity2_dashes'),
    pytest.param(
        '$mul(-1,-)', '0', False, {},
        id='mul_arity2_negative_then_dash'),
    pytest.param('$mul(0, 123)', '0', False, {}, id='mul_arity2_zero'),
    pytest.param('$mul(1, 0)', '0', False, {}, id='mul_arity2_by_zero'),
    pytest.param('$mul(0, 0)', '0', False, {}, id='mul_arity2_zero_by_zero'),
    pytest.param(
        '$mul(-10, 3)', '-30', False, {},
        id='mul_arity2_negative_first'),
    pytest.param(
        '$mul(10, -3)', '-30', False, {},
        id='mul_arity2_negative_second'),
    pytest.param(
        '$mul(-10, -3)', '30', False, {},
        id='mul_arity2_negative_both'),
    pytest.param('$mul(128,2,2)', '512', False, {}, id='mul_arity3'),
    pytest.param('$mul(128,0,3)', '0', False, {}, id='mul_arity3_second_zero'),
    pytest.param('$mul(128,5,0)', '0', False, {}, id='mul_arity3_third_zero'),
    pytest.param(
        '$mul(6969,0,-0)', '0', False, {},
        id='mul_arity3_zero_and_negative_zero'),
    # Arithmetic: $div()
    pytest.param('$div()!a$div()', '!a', False, {}, id='div_arity0'),
    pytest.param('$div(123)', '123', False, {}, id='div_arity1'),
    pytest.param('$div(-456)', '-456', False, {}, id='div_arity1_negative'),
    pytest.param('$div(-)', '0', False, {}, id='div_arity1_dash'),
    pytest.param('$div(0)', '0', False, {}, id='div_arity1_zero'),
    pytest.param('$div(-0)', '0', False, {}, id='div_arity1_negative_zero'),
    pytest.param('$div(1000, 10)', '100', False, {}, id='div_arity2'),
    pytest.param('$div(,)', '0', False, {}, id='div_arity2_blanks'),
    pytest.param('$div(-,)', '0', False, {}, id='div_arity2_dash_blank'),
    pytest.param('$div(,-)', '0', False, {}, id='div_arity2_blank_dash'),
    pytest.param('$div(-,-)', '0', False, {}, id='div_arity2_dashes'),
    pytest.param(
        '$div(-1,-)', '-1', False, {},
        id='div_arity2_negative_then_dash'),
    pytest.param('$div(0, 123)', '0', False, {}, id='div_arity2_zero'),
    pytest.param('$div(1, 0)', '1', False, {}, id='div_arity2_by_zero'),
    pytest.param('$div(0, 0)', '0', False, {}, id='div_arity2_zero_by_zero'),
    pytest.param('$div(70, 20)', '3', False, {}, id='div_arity2_rounds_down'),
    pytest.param(
        '$div(-10, 3)', '-3', False, {},
        id='div_arity2_negative_first_rounds_down'),
    pytest.param(
        '$div(10, -3)', '-3', False, {},
        id='div_arity2_negative_second_rounds_down'),
    pytest.param(
        '$div(-10, -3)', '3', False, {},
        id='div_arity2_negative_both_rounds_down'),
    pytest.param('$div(128,2,2)', '32', False, {}, id='div_arity3'),
    pytest.param(
        '$div(128,0,3)', '42', False, {},
        id='div_arity3_skip_second_zero'),
    pytest.param(
        '$div(128,5,0)', '25', False, {},
        id='div_arity3_skip_third_zero_and_rounds_down'),
    pytest.param(
        '$div(6969,0,-0)', '6969', False, {},
        id='div_arity3_skip_all_zeroes'),
    # Arithmetic: $muldiv()
    # NOTE: This function is weird. Any valid call is True, according to Foobar.
    pytest.param('$muldiv()!a$muldiv()', '!a', False, {}, id='muldiv_arity0'),
    pytest.param('$muldiv(123)', '', False, {}, id='muldiv_arity1'),
    pytest.param('$muldiv(-456)', '', False, {}, id='muldiv_arity1_negative'),
    pytest.param('$muldiv(-)', '', False, {}, id='muldiv_arity1_dash'),
    pytest.param('$muldiv(0)', '', False, {}, id='muldiv_arity1_zero'),
    pytest.param(
        '$muldiv(-0)', '', False, {},
        id='muldiv_arity1_negative_zero'),
    pytest.param('$muldiv(1000, 10)', '', False, {}, id='muldiv_arity2'),
    pytest.param('$muldiv(,)', '', False, {}, id='muldiv_arity2_blanks'),
    pytest.param('$muldiv(-,)', '', False, {}, id='muldiv_arity2_dash_blank'),
    pytest.param('$muldiv(,-)', '', False, {}, id='muldiv_arity2_blank_dash'),
    pytest.param('$muldiv(-,-)', '', False, {}, id='muldiv_arity2_dashes'),
    pytest.param(
        '$muldiv(-1,-)', '', False, {},
        id='muldiv_arity2_negative_then_dash'),
    pytest.param('$muldiv(0, 123)', '', False, {}, id='muldiv_arity2_zero'),
    pytest.param('$muldiv(1, 0)', '', False, {}, id='muldiv_arity2_by_zero'),
    pytest.param(
        '$muldiv(0, 0)', '', False, {},
        id='muldiv_arity2_zero_by_zero'),
    pytest.param(
        '$muldiv(-10, 3)', '', False, {},
        id='muldiv_arity2_negative_first'),
    pytest.param(
        '$muldiv(10, -3)', '', False, {},
        id='muldiv_arity2_negative_second'),
    pytest.param(
        '$muldiv(-10, -3)', '', False, {},
        id='muldiv_arity2_negative_both'),
    pytest.param('$muldiv(128,2,2)', '128', True, {}, id='muldiv_arity3'),
    pytest.param('$muldiv(,,)', '-1', True, {}, id='muldiv_arity3_blanks'),
    pytest.param('$muldiv(-,-,-)', '-1', True, {}, id='muldiv_arity3_dashes'),
    pytest.param(
        '$muldiv(5,3,1)', '15', True, {},
        id='muldiv_arity3_rounds_down_div_by_1'),
    pytest.param(
        '$muldiv(-5,3,1)', '-15', True, {},
        id='muldiv_arity3_a_negative_div_by_1'),
    pytest.param(
        '$muldiv(5,-3,1)', '-15', True, {},
        id='muldiv_arity3_b_negative_div_by_1'),
    pytest.param(
        '$muldiv(-5,-3,1)', '15', True, {},
        id='muldiv_arity3_a_b_negative_div_by_1'),
    pytest.param(
        '$muldiv(5,3,2)', '7', True, {},
        id='muldiv_arity3_rounds_down_div_by_2'),
    pytest.param(
        '$muldiv(-5,3,2)', '-7', True, {},
        id='muldiv_arity3_a_negative_rounds_down_div_by_2'),
    pytest.param(
        '$muldiv(5,-3,2)', '-7', True, {},
        id='muldiv_arity3_b_negative_rounds_down_div_by_2'),
    pytest.param(
        '$muldiv(-5,-3,2)', '7', True, {},
        id='muldiv_arity3_a_b_negative_rounds_down_div_by_2'),
    pytest.param(
        '$muldiv(5,2,3)', '3', True, {},
        id='muldiv_arity3_rounds_down_div_by_3'),
    pytest.param(
        '$muldiv(-5,2,3)', '-3', True, {},
        id='muldiv_arity3_a_negative_rounds_down_div_by_3'),
    pytest.param(
        '$muldiv(5,-2,3)', '-3', True, {},
        id='muldiv_arity3_b_negative_rounds_down_div_by_3'),
    pytest.param(
        '$muldiv(-5,-2,3)', '3', True, {},
        id='muldiv_arity3_a_b_negative_rounds_down_div_by_3'),
    pytest.param(
        '$muldiv(5,7,8)', '4', True, {},
        id='muldiv_arity3_rounds_down'),
    pytest.param(
        '$muldiv(-5,7,8)', '-4', True, {},
        id='muldiv_arity3_a_negative_rounds_down'),
    pytest.param(
        '$muldiv(5,-7,8)', '-4', True, {},
        id='muldiv_arity3_b_negative_rounds_down'),
    pytest.param(
        '$muldiv(-5,-7,8)', '4', True, {},
        id='muldiv_arity3_a_b_negative_rounds_down'),
    pytest.param(
        '$muldiv(5,3,-1)', '-15', True, {},
        id='muldiv_arity3_rounds_down_div_by_negative_1'),
    pytest.param(
        '$muldiv(-5,3,-1)', '15', True, {},
        id='muldiv_arity3_a_negative_div_by_negative_1'),
    pytest.param(
        '$muldiv(5,-3,-1)', '15', True, {},
        id='muldiv_arity3_b_negative_div_by_negative_1'),
    pytest.param(
        '$muldiv(-5,-3,-1)', '-15', True, {},
        id='muldiv_arity3_a_b_negative_div_by_negative_1'),
    pytest.param(
        '$muldiv(5,3,-2)', '-7', True, {},
        id='muldiv_arity3_rounds_down_div_by_negative_2'),
    pytest.param(
        '$muldiv(-5,3,-2)', '7', True, {},
        id='muldiv_arity3_a_negative_rounds_down_div_by_negative_2'),
    pytest.param(
        '$muldiv(5,-3,-2)', '7', True, {},
        id='muldiv_arity3_b_negative_rounds_down_div_by_negative_2'),
    pytest.param(
        '$muldiv(-5,-3,-2)', '-7', True, {},
        id='muldiv_arity3_a_b_negative_rounds_down_div_by_negative_2'),
    pytest.param(
        '$muldiv(5,2,-3)', '-3', True, {},
        id='muldiv_arity3_rounds_down_div_by_negative_3'),
    pytest.param(
        '$muldiv(-5,2,-3)', '3', True, {},
        id='muldiv_arity3_a_negative_rounds_down_div_by_negative_3'),
    pytest.param(
        '$muldiv(5,-2,-3)', '3', True, {},
        id='muldiv_arity3_b_negative_rounds_down_div_by_negative_3'),
    pytest.param(
        '$muldiv(-5,-2,-3)', '-3', True, {},
        id='muldiv_arity3_a_b_negative_rounds_down_div_by_negative_3'),
    pytest.param(
        '$muldiv(5,7,-8)', '-4', True, {},
        id='muldiv_arity3_rounds_down_c_negative'),
    pytest.param(
        '$muldiv(-5,7,-8)', '4', True, {},
        id='muldiv_arity3_a_negative_rounds_down_c_negative'),
    pytest.param(
        '$muldiv(5,-7,-8)', '4', True, {},
        id='muldiv_arity3_b_negative_rounds_down_c_negative'),
    pytest.param(
        '$muldiv(-5,-7,-8)', '-4', True, {},
        id='muldiv_arity3_a_b_negative_rounds_down_c_negative'),
    pytest.param(
        '$muldiv(128,0,3)', '0', True, {},
        id='muldiv_arity3_multiply_by_zero'),
    pytest.param(
        # WTF. This is actual Foobar behavior. It's obviously a bug but... HOW?
        '$muldiv(128,5,0)', '-1', True, {},
        id='muldiv_arity3_divide_by_zero'),
    pytest.param(
        '$muldiv(6969,0,-0)', '-1', True, {},
        id='muldiv_arity3_multiply_and_divide_by_zero'),
    pytest.param('$muldiv(,,,)', '', False, {}, id='muldiv_arity4_blanks'),
    pytest.param('$muldiv(1,1,1,1)', '', False, {}, id='muldiv_arity4_ones'),
    pytest.param(
        '$muldiv(%artist%,%artist%,%artist%)', '-1', True,
        cs_01, id='muldiv_arity3_text_variable_lookup'),
    pytest.param(
        '$muldiv(%date%,%totaldiscs%,%totaltracks%)', '366', True,
        cs_01, id='muldiv_arity3_numeric_variable_lookup'),
    pytest.param(
        '$muldiv(%no%,%nope%,%still no%)', '-1', True,
        cs_01, id='muldiv_arity3_invalid_variable_lookup'),
    # Real-world use-cases; integration tests
    pytest.param(
        window_title_integration_fmt, window_title_integration_expected, True,
        cs_01, id='window_title_integration'),
]


# Add variable resolution tests
for fn in ('add', 'sub', 'mul', 'div'):
  for testarg in (
      'TOTALDISCS',
      'TRACKNUMBER',
      'ARTIST',
      'MISSING',
  ):
    # default, if it's not in the track
    expected = {
        'add': '0',
        'sub': '0',
        'mul': '0',
        'div': '0',
    }[fn]
    try:
      if testarg in cs_01:
        expected = unistr(int(cs_01[testarg]))
    except ValueError:
      pass

    test_eval_cases.append(pytest.param(
        '$%s(%%%s%%)' % (fn, testarg),
        expected,
        testarg in cs_01,
        cs_01,
        id='arity1_variable_resolution(%s, %s)' % (fn, testarg)))

  arity2_answer_key = {
      'add': lambda x, y: x + y,
      'sub': lambda x, y: x - y,
      'mul': lambda x, y: x * y,
      'div': lambda x, y: x // (1 if y == 0 else y),
  }

  for t1, t2 in (
      ('TOTALDISCS', 1),
      (3, 'TOTALDISCS'),
      ('TOTALDISCS', 'TOTALDISCS'),
      ('MISSING', 'TOTALDISCS'),
      ('TOTALDISCS', 'MISSING'),
      ('MISSING', 'MISSING'),
  ):
    first = t1 if type(t1) is int else '%' + t1 + '%'
    second = t2 if type(t2) is int else '%' + t2 + '%'
    val1 = t1 if type(t1) is int else int(cs_01[t1]) if t1 in cs_01 else 0
    val2 = t2 if type(t2) is int else int(cs_01[t2]) if t2 in cs_01 else 0
    test_eval_cases.append(pytest.param(
        '$%s(%s,%s)' % (fn, first, second),
        unistr(arity2_answer_key[fn](val1, val2)),
        t1 in cs_01 or t2 in cs_01,
        cs_01,
        id='arity2_variable_resolution(%s, %s, %s)' % (fn, t1, t2)))


class TestTitleFormatter:
  @pytest.mark.parametrize('compiled', [
    pytest.param(False, id='interpreted'),
    pytest.param(True, id='compiled'),
  ])
  @pytest.mark.parametrize('fmt,expected,expected_truth,track', test_eval_cases)
  def test_eval(self, fmt, expected, expected_truth, compiled, track):
    if compiled:
      print("[TEST] Compiling titleformat...")
      fn = fdbg.eval(None, fmt, compiling=True)
      print("[TEST] Calling resulting function...")
      result = fn(track)
    else:
      result = fdbg.eval(track, fmt)

    assert result.string_value == expected
    assert result.truth_value is expected_truth

    if compiled:
      fb = f.eval(None, fmt, compiling=True)
      quiet_result = fn(track)
    else:
      quiet_result = f.eval(track, fmt)

    assert quiet_result == result

