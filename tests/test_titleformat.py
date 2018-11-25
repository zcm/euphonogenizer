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
    pytest.param('$mul(128,2,2)', '512', False, {}, id='mul_arity3'),
    pytest.param('$mul(128,0,3)', '0', False, {}, id='mul_arity3_second_zero'),
    pytest.param('$mul(128,5,0)', '0', False, {}, id='mul_arity3_third_zero'),
    pytest.param(
        '$mul(6969,0,-0)', '0', False, {},
        id='mul_arity3_zero_and_negative_zero'),
    # Arithmetic: $div()
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
    # Arithmetic: $greater()
    pytest.param('$greater()', '', False, {}, id='greater_arity0'),
    pytest.param('$greater(0)', '', False, {}, id='greater_arity1_zero'),
    pytest.param('$greater(-)', '', False, {}, id='greater_arity1_dash'),
    pytest.param('$greater(,)', '', False, {}, id='greater_arity2_blanks'),
    pytest.param('$greater(0,)', '', False, {}, id='greater_arity2_zero_blank'),
    pytest.param('$greater(,0)', '', False, {}, id='greater_arity2_blank_zero'),
    pytest.param('$greater(,-0)', '', False, {}, id='greater_arity2_neg_zero'),
    pytest.param('$greater(1,)', '', True, {}, id='greater_arity2_one_blank'),
    pytest.param('$greater(,1)', '', False, {}, id='greater_arity2_blank_one'),
    pytest.param('$greater(2,1)', '', True, {}, id='greater_arity2'),
    pytest.param('$greater(2,t)', '', True, {}, id='greater_arity2_text'),
    pytest.param('$greater(,,)', '', False, {}, id='greater_arity3_blanks'),
    pytest.param('$greater(2,,)', '', False, {}, id='greater_arity3_two_blank'),
    pytest.param('$greater(2,1,)', '', False, {}, id='greater_arity3_blank'),
    pytest.param('$greater(2,1,0)', '', False, {}, id='greater_arity3'),
    pytest.param('$greater(,-1)', '', True, {}, id='greater_arity2_negative'),
    pytest.param(
        '$greater(-1,-2)', '', True, {},
        id='greater_arity2_both_negative'),
    pytest.param(
        '$greater(%totaltracks%,-1)', '', True, cs_01,
        id='greater_arity2_variable_resolution_first'),
    pytest.param(
        '$greater(-1,%totaltracks%)', '', False, cs_01,
        id='greater_arity2_variable_resolution_second'),
    pytest.param(
        '$greater(%totaltracks%,%totaltracks%)', '', False, cs_01,
        id='greater_arity2_variable_resolution_both'),
    pytest.param(
        '$greater($add(%totaltracks%,1),%totaltracks%)', '', True, cs_01,
        id='greater_arity2_variable_resolution_both_add_first'),
    pytest.param(
        '$greater(%totaltracks%,$add(%totaltracks%,1))', '', False, cs_01,
        id='greater_arity2_variable_resolution_both_add_second'),
    pytest.param(
        '$greater($add(1,%totaltracks%),$add(%totaltracks%,1))', '', False,
        cs_01, id='greater_arity2_variable_resolution_both_add_both'),
    # Arithmetic: $max() and $min -- the rest are autogenerated
    pytest.param('$max()', '', False, {}, id='max_arity0'),
    pytest.param('$min()', '', False, {}, id='max_arity0'),
    # Real-world use-cases; integration tests
    pytest.param(
        window_title_integration_fmt, window_title_integration_expected, True,
        cs_01, id='window_title_integration'),
]


expected_arity0 = {
    'add': '0',
    'sub': '',
    'mul': '1',
    'div': '',
}


def div_logic(x, y):
  if x * y < 0:
    return x * -1 // (1 if y == 0 else y) * -1
  return x // (1 if y == 0 else y)

arity2_answer_key = {
    'add': lambda x, y: x + y,
    'sub': lambda x, y: x - y,
    'mul': lambda x, y: x * y,
    'div': div_logic,
}


# Generate arithmetic tests
for fn in ('add', 'sub', 'mul', 'div'):
  # Arity 0 tests
  expected = expected_arity0[fn]
  test_eval_cases.append(pytest.param(
      '$%s()!a$%s()' % (fn, fn),
      '%s!a%s' % (expected, expected),
      False, {}, id="arithmetic:arity0<$%s() = '%s'>" % (fn, expected)))

  # Arity 1 tests
  for testarg in (
      '123', '-456', '-', '0', '-0', '007', '-007',
      '%TOTALDISCS%', '%TRACKNUMBER%', '%ARTIST%', '%MISSING%',
  ):
    testarg_stripped = testarg.strip('%')
    # default, if it's not in the track
    expected = '0'
    try:
      expected = unistr(int(testarg))
    except ValueError:
      try:
        if testarg_stripped in cs_01:
          expected = unistr(int(cs_01[testarg_stripped]))
      except ValueError:
        pass

    fmt = '$%s(%s)' % (fn, testarg)
    test_eval_cases.append(pytest.param(
        fmt, expected, testarg_stripped in cs_01, cs_01,
        id='arithmetic:arity1<%s = %s>' % (fmt, expected)))

  # Arity 2 tests
  for t1, t2 in (
      (12, 34),
      (70, 20),
      (1000, 10),
      (10, 3),
      (-10, 3),
      (10, -3),
      (-10, -3),
      (123, 0),
      (0, 123),
      (0, 0),
      (0, 10),
      (10, 0),
      (100, 0),
      (0, 100),
      (1, 1),
      (1, 10),
      (10, 1),
      (1, 100),
      (100, 1),
      (-1, 1),
      (1, -1),
      (-1, -1),
      (-1, 100),
      (1, -100),
      (-100, -1),
      (-1, 0),
      (0, -1),
      (0, '-0'),
      ('-0', 0),
      ('-0', '-0'),
      (1, '-0'),
      ('-0', 1),
      ('', ''),
      ('-', ''),
      ('', '-'),
      ('-', '-'),
      (-1,'-'),
      ('%TOTALDISCS%', 1),
      (3, '%TOTALDISCS%'),
      ('%TOTALDISCS%', '%TOTALDISCS%'),
      ('%MISSING%', '%TOTALDISCS%'),
      ('%TOTALDISCS%', '%MISSING%'),
      ('%MISSING%', '%MISSING%'),
  ):
    fmt = '$%s(%s,%s)' % (fn, t1, t2)
    t1s = unistr(t1).strip('%')
    t2s = unistr(t2).strip('%')
    val1 = t1 if type(t1) is int else int(cs_01[t1s]) if t1s in cs_01 else 0
    val2 = t2 if type(t2) is int else int(cs_01[t2s]) if t2s in cs_01 else 0
    expected = unistr(arity2_answer_key[fn](val1, val2))
    test_eval_cases.append(pytest.param(
        fmt, expected, t1s in cs_01 or t2s in cs_01, cs_01,
        id="arithmetic:arity2<%s = '%s'>" % (fmt, expected)))

# Add min/max tests
for fn in ('min', 'max'):
  for cases in (
      (['0'], '0', False),
      (['123'], '123', False),
      (['-'], '0', False),
      (['',''], '0', False),
      (['2','1'], '1' if fn == 'min' else '2', False),
      (['-2','1'], '-2' if fn == 'min' else '1', False),
      (['1','2'], '1' if fn == 'min' else '2', False),
      (['-1','2'], '-1' if fn == 'min' else '2', False),
      (['','',''], '0', False),
      (['-1','-2','-3'], '-3' if fn == 'min' else '-1', False),
      (['','-2','-3'], '-3' if fn == 'min' else '0', False),
      (['-2','-1','3', '2', ''], '-2' if fn == 'min' else '3', False),
      (['%missing%'], '0', False),
      (['%totaltracks%'], cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%'], '0', False),
      (['%totaltracks%', '%missing%'],
        '0' if fn == 'min' else cs_01['TOTALTRACKS'], True),
      (['%missing%', '%totaltracks%'],
        '0' if fn == 'min' else cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%', '%missing%'], '0', False),
      (['%totaltracks%', '%missing%', '%missing%'],
        '0' if fn == 'min' else cs_01['TOTALTRACKS'], True),
      (['%missing%', '%totaltracks%', '%missing%'],
        '0' if fn == 'min' else cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%', '%totaltracks%'],
        '0' if fn == 'min' else cs_01['TOTALTRACKS'], True),
  ):
    test_eval_cases.append(pytest.param(
      '$%s(%s)' % (fn, ','.join(cases[0])), cases[1], cases[2], cs_01,
      id='%s_arity%s(%s)' % (fn, len(cases[0]), ','.join(cases[0]))))


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

