#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from euphonogenizer import titleformat

import pytest

collective_soul_01 = {
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
    pytest.param(
      '%artist% - ', 'Collective Soul - ', True, collective_soul_01,
      id='artist_variable_lookup'),
    pytest.param(
      '[%artist% - ]', 'Collective Soul - ', True, collective_soul_01,
      id='artist_variable_lookup_cond'),
    pytest.param('$add()!a$add()', '0!a0', False, {}, id='add_arity0'),
    pytest.param('$add(123)', '123', False, {}, id='add_arity1'),
    pytest.param('$add(-)', '0', False, {}, id='add_arity1_dash'),
    pytest.param('$add(0)', '0', False, {}, id='add_arity1_zero'),
    pytest.param('$add(-0)', '0', False, {}, id='add_arity1_negative_zero'),
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
    # Foobar can't negate functions, so it will return the first value.
    pytest.param(
        '$add(-1,-$add(-2,-$add(-3)))', '-1', False, {},
        id='add_arity2_nested_negative_integers_negation'),
    # Same here, but it actually sums the first two.
    pytest.param(
        '$add(-2,-6,-$add(-2,-$add(-3)))', '-8', False, {},
        id='add_arity3_nested_negative_integers_negation1'),
    pytest.param(
        '$add(-3,-$add(-2,-$add(-3)),-4)', '-7', False, {},
        id='add_arity3_nested_negative_integers_negation2'),
    pytest.param(
        '$add($add($add(1,$add(5))),$add(2,$add(3,$add(4))))', '15', False, {},
        id='add_arity2_nested_branching_positive_integers'),
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
    pytest.param('$div(-1,-)', '-1', False, {}, id='div_arity2_negative_then_dash'),
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
    pytest.param(
        window_title_integration_fmt, window_title_integration_expected, True,
        collective_soul_01, id='window_title_integration'),
]


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

