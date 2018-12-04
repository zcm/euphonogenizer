#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from euphonogenizer import titleformat
from euphonogenizer.common import unistr

from functools import reduce

import sys
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

def _testcasegroup(idprefix, *testcases):
  return [pytest.param(*x, id="%s<'%s' = '%s'>" % (idprefix, x[0], x[1]))
          for x in testcases]

test_eval_cases = [
    # Basic parsing tests -- test various interesting parser states
    *_testcasegroup('parser:basic',
      ('', '', False, {}),
      (' ', ' ', False, {}),
      (',', ',', False, {}),
      ('(', '', False, {}),
      (')', '', False, {}),
      ('asdf1234', 'asdf1234', False, {}),
      ("''", "'", False, {}),
      ("''''", "''", False, {}),
      ('%%', '%', False, {}),
      ('%%%%', '%%', False, {}),
      ('[]', '', False, {}),
      ('[[]]', '', False, {}),
      ("['']", '', False, {}),
      ('[%]', '', False, {}),
      ('[%%]', '', False, {}),
      ("'['", '[', False, {}),
      ("']'", ']', False, {}),
      ("'[]'", '[]', False, {}),
      ("'['']'", '[]', False, {}),
      ('%[%', '?', False, {}),
      ('[%[%]]', '', False, {}),
      ('%]%', '?', False, {}),
    ),
    *_testcasegroup('parser:functions',
      ('$', '', False, {}),
      ("'$", '$', False, {}),
      ("'$'", '$', False, {}),
      ('$$', '$', False, {}),
      ('*$$*', '*$*', False, {}),
      ('*$$$*', '*$', False, {}),
      ('$()', '[UNKNOWN FUNCTION]', False, {}),
      ('*$*', '*', False, {}),
      ('*$(*', '*', False, {}),
      ('$([])', '[UNKNOWN FUNCTION]', False, {}),
      ('*$[a', '*', False, {}),
      ('*$[]a', '*', False, {}),
      ('*$[()]a', '*', False, {}),
      ('*()$add(1,2)', '*', False, {}),
      ('*$ad$if($add(),a,d)d(2)', '*', False, {}),
      ('*$if($ad$if($add(),a,d),yes,no)d(2)', '*nod', False, {}),
      ('*$if((),yes,no)*', '*no*', False, {}),
      ("*$if('()',yes,no)*", '*no*', False, {}),
      ('*$if((((what,ever))),yes(,)oof,no($)gmb)*', '*no*', False, {}),
      ('*$if((%artist%),yes(,)oof,no($)gmb)*', '*no*', False, cs_01),
      ('*$if(%artist%(%a,b%),yes(,)oof,no($)gmb)*', '*yes*', False, cs_01),
      ('*$if(%missing%(%a,b%),yes(,)oof,no($)gmb)*', '*no*', False, cs_01),
      ('*$if(,fail,add)(1,2)*', '*add', False, {}),
      ('$$&$$$$$$$add(1,2)$$$$$$&$$', '$&$$$3$$$&$', False, {}),
    ),
    # Variable resolution tests
    *_testcasegroup('variable',
      ('%artist% - ', 'Collective Soul - ', True, cs_01),
      ('[%artist% - ]', 'Collective Soul - ', True, cs_01),
      ('*[%missing% - ]*', '**', False, cs_01),
    ),
    # Bizarre variable resolution, yes this actually works in foobar
    *_testcasegroup('variable:arithmetic_magic',
      ('$add(1%track%,10)', '111', True, cs_01),
      ('$sub(1%track%,10)', '91', True, cs_01),
      ('$mul(1%track%,10)', '1010', True, cs_01),
      ('$div(1%track%,10)', '10', True, cs_01),
    ),
    # Sanity tests, basic non-generated cases that validate generated ones
    *_testcasegroup('sanity:arithmetic',
      ("$add('1234')", '1234', False, {}),
      ("$add(,,  '    1234    '  ,,)", '1234', False, {}),
      ('$add($div($mul($sub(100,1),2),10),2)', '21', False, {}),
    ),
    # Nested arithmetic: $add() and $sub() -- other arithmetic tests generated
    *_testcasegroup('arithmetic:nested',
      ('$add(1,$add(1,$add(1,$add(1))))', '4', False, {}),
      ('$add(1,$add(2,$add(3,$add(4))))', '10', False, {}),
      ('$add(-1,$add(-2,$add(-3,$add(-4))))', '-10', False, {}),
      # Foobar will negate a value returned to it by a function, but only if
      # it's positive. If it's negative, it will be treated as text (--).
      ("$add(-$add('1','2'),' 10')", '7', False, {}),
      # Foobar can't negate functions that return negative values.
      ('$add(-1,-$add(-2,-$add(-3)))', '-1', False, {}),
      # Same here, but it actually sums the first two.
      ('$add(-2,-6,-$add(-2,-$add(-3)))', '-8', False, {}),
      ('$add(-3,-$add(-2,-$add(-3)),-4)', '-7', False, {}),
      ('$add($add($add(1,$add(5))),$add(2,$add(3,4)))', '15', False, {}),
      ('$sub(1,$sub(1,$sub(1)))', '1', False, {}),
      ('$sub(1,$sub(1,$sub(1,$sub(1))))', '0', False, {}),
      ('$sub(1,$sub(2,$sub(3,$sub(4))))', '-2', False, {}),
      ('$sub(-1,$sub(-2,$sub(-3,$sub(-4))))', '2', False, {}),
      ("$sub(-$sub('2','1'),'10')",'-11', False, {}),
      # Foobar still can't negate functions that return negative values.
      ('$sub(-1,-$sub(-2,-$sub(-3)))', '-1', False, {}),
      # Same here, but it actually subtracts for the first two.
      ('$sub(-2,-6,-$sub(-2,-$sub(-3)))', '4', False, {}),
      ('$sub(-3,-$sub(-2,-$sub(-3)),-4)', '1', False, {}),
      ('$sub($sub($sub(1,$sub(5))),$sub(2,$sub(3,4)))', '-7', False, {}),
    ),
    # NOTE: This function is weird. Any valid call is True, according to Foobar.
    *_testcasegroup('arithmetic:muldiv',
      ('$muldiv()!a$muldiv()', '!a', False, {}),
      ('$muldiv(123)', '', False, {}),
      ('$muldiv(-456)', '', False, {}),
      ('$muldiv(-)', '', False, {}),
      ('$muldiv(0)', '', False, {}),
      ('$muldiv(-0)', '', False, {}),
      ('$muldiv(1000, 10)', '', False, {}),
      ('$muldiv(,)', '', False, {}),
      ('$muldiv(-,)', '', False, {}),
      ('$muldiv(,-)', '', False, {}),
      ('$muldiv(-,-)', '', False, {}),
      ('$muldiv(-1,-)', '', False, {}),
      ('$muldiv(0, 123)', '', False, {}),
      ('$muldiv(1, 0)', '', False, {}),
      ('$muldiv(0, 0)', '', False, {}),
      ('$muldiv(-10, 3)', '', False, {}),
      ('$muldiv(10, -3)', '', False, {}),
      ('$muldiv(-10, -3)', '', False, {}),
      ('$muldiv(128,2,2)', '128', True, {}),
      ('$muldiv(,,)', '-1', True, {}),
      ('$muldiv(-,-,-)', '-1', True, {}),
      ('$muldiv(5,3,1)', '15', True, {}),
      ('$muldiv(-5,3,1)', '-15', True, {}),
      ('$muldiv(5,-3,1)', '-15', True, {}),
      ('$muldiv(-5,-3,1)', '15', True, {}),
      # Test rounding down behavior
      ('$muldiv(5,3,2)', '7', True, {}),
      ('$muldiv(-5,3,2)', '-7', True, {}),
      ('$muldiv(5,-3,2)', '-7', True, {}),
      ('$muldiv(-5,-3,2)', '7', True, {}),
      ('$muldiv(5,2,3)', '3', True, {}),
      ('$muldiv(-5,2,3)', '-3', True, {}),
      ('$muldiv(5,-2,3)', '-3', True, {}),
      ('$muldiv(-5,-2,3)', '3', True, {}),
      ('$muldiv(5,7,8)', '4', True, {}),
      ('$muldiv(-5,7,8)', '-4', True, {}),
      ('$muldiv(5,-7,8)', '-4', True, {}),
      ('$muldiv(-5,-7,8)', '4', True, {}),
      ('$muldiv(5,3,-1)', '-15', True, {}),
      ('$muldiv(-5,3,-1)', '15', True, {}),
      ('$muldiv(5,-3,-1)', '15', True, {}),
      ('$muldiv(-5,-3,-1)', '-15', True, {}),
      ('$muldiv(5,3,-2)', '-7', True, {}),
      ('$muldiv(-5,3,-2)', '7', True, {}),
      ('$muldiv(5,-3,-2)', '7', True, {}),
      ('$muldiv(-5,-3,-2)', '-7', True, {}),
      ('$muldiv(5,2,-3)', '-3', True, {}),
      ('$muldiv(-5,2,-3)', '3', True, {}),
      ('$muldiv(5,-2,-3)', '3', True, {}),
      ('$muldiv(-5,-2,-3)', '-3', True, {}),
      ('$muldiv(5,7,-8)', '-4', True, {}),
      ('$muldiv(-5,7,-8)', '4', True, {}),
      ('$muldiv(5,-7,-8)', '4', True, {}),
      ('$muldiv(-5,-7,-8)', '-4', True, {}),
      ('$muldiv(128,0,3)', '0', True, {}),
      # WTF. This is actual Foobar behavior. It's obviously a bug but... HOW?
      ('$muldiv(128,5,0)', '-1', True, {}),
      ('$muldiv(6969,0,-0)', '-1', True, {}),
      ('$muldiv(,,,)', '', False, {}),
      ('$muldiv(1,1,1,1)', '', False, {}),
      ('$muldiv(%artist%,%artist%,%artist%)', '-1', True, cs_01),
      ('$muldiv(%date%,%totaldiscs%,%totaltracks%)', '366', True, cs_01),
      ('$muldiv(%no%,%nope%,%still no%)', '-1', True, cs_01),
    ),
    # Arithmetic: $greater()
    *_testcasegroup('arithmetic:greater',
      ('$greater()', '', False, {}),
      ('$greater(0)', '', False, {}),
      ('$greater(-)', '', False, {}),
      ('$greater(,)', '', False, {}),
      ('$greater(0,)', '', False, {}),
      ('$greater(,0)', '', False, {}),
      ('$greater(,-0)', '', False, {}),
      ('$greater(1,)', '', True, {}),
      ('$greater(,1)', '', False, {}),
      ('$greater(2,1)', '', True, {}),
      ('$greater(2,t)', '', True, {}),
      ('$greater(,,)', '', False, {}),
      ('$greater(2,,)', '', False, {}),
      ('$greater(2,1,)', '', False, {}),
      ('$greater(2,1,0)', '', False, {}),
      ('$greater(,-1)', '', True, {}),
      ('$greater(-1,-2)', '', True, {}),
      ('$greater(%totaltracks%,-1)', '', True, cs_01),
      ('$greater(-1,%totaltracks%)', '', False, cs_01),
      ('$greater(%totaltracks%,%totaltracks%)', '', False, cs_01),
      ('$greater($add(%totaltracks%,1),%totaltracks%)', '', True, cs_01),
      ('$greater(%totaltracks%,$add(%totaltracks%,1))', '', False, cs_01),
      ('$greater($add(1,%track%),$add(%track%,1))', '', False, cs_01),
    ),
    # Arithmetic: $max() and $min -- the rest are autogenerated
    pytest.param('$max()', '', False, {}, id='max_arity0'),
    pytest.param('$min()', '', False, {}, id='min_arity0'),
    *_testcasegroup('control_flow',
      # $if()
      ('*$if()*', '*[INVALID $IF SYNTAX]*', False, {}),
      ('*$if($add())*', '*[INVALID $IF SYNTAX]*', False, {}),
      ('*$if(%artist%)*', '*[INVALID $IF SYNTAX]*', False, cs_01),
      ('*$if(%missing%)*', '*[INVALID $IF SYNTAX]*', False, cs_01),
      ('*$if(,)*', '**', False, {}),
      ('*$if($add(),)*', '**', False, {}),
      ('*$if($add(),,)*', '**', False, {}),
      ('*$if($add(),yes)*', '**', False, {}),
      ('*$if($add(),yes,)*', '**', False, {}),
      ('*$if($add(),yes,no)*', '*no*', False, {}),
      ('*$if(%artist%,)*', '**', False, cs_01),
      ('*$if(%artist%,,)*', '**', False, cs_01),
      ('*$if(%artist%,yes)*', '*yes*', False, cs_01),
      ('*$if(%artist%,yes,)*', '*yes*', False, cs_01),
      ('*$if(%artist%,yes,no)*', '*yes*', False, cs_01),
      ('*$if($add(),%artist%)*', '**', False, cs_01),
      ('*$if(%tracknumber%,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if(%missing%,%artist%)*', '**', False, cs_01),
      ('*$if($add(),%artist%,)*', '**', False, cs_01),
      ('*$if($add(),,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if(%tracknumber%,%artist%,)*', '*Collective Soul*', True, cs_01),
      ('*$if(%tracknumber%,,%artist%)*', '**', False, cs_01),
      ('*$if(%artist%,%artist%,%track%)*', '*Collective Soul*', True, cs_01),
      ('*$if(%missing%,%artist%,%track%)*', '*01*', True, cs_01),
      ('*$if(,,)*', '**', False, {}),
      ('*$if(,yes,no)*', '*no*', False, {}),
      ('*$if($if($add()),yes,no)*', '*no*', False, {}),
      ('*$if($if(%artist%),yes,no)*', '*no*', False, cs_01),
      ('*$if(a,b,c,d)*', '*[INVALID $IF SYNTAX]*', False, {}),
      # $if2()
      ('*$if2()*', '*[INVALID $IF2 SYNTAX]*', False, {}),
      ('*$if2(a)*', '*[INVALID $IF2 SYNTAX]*', False, {}),
      ('*$if2(%artist%)*', '*[INVALID $IF2 SYNTAX]*', False, cs_01),
      ('*$if2(%missing%)*', '*[INVALID $IF2 SYNTAX]*', False, cs_01),
      ('*$if2(,)*', '**', False, {}),
      ('*$if2(,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if2(text,no)*', '*no*', False, {}),
      ('*$if2(%artist%,no)*', '*Collective Soul*', True, cs_01),
      ('*$if2(%missing%,no)*', '*no*', False, cs_01),
      ('*$if2(text,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if2(%track%,%artist%)*', '*01*', True, cs_01),
      ('*$if2(%missing%,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if2($if2(%artist%,no),nope)*', '*Collective Soul*', True, cs_01),
      ('*$if2(a,b,c)*', '*[INVALID $IF2 SYNTAX]*', False, {}),
      # $if3()
      ('*$if3()*', '**', False, {}),
      ('*$if3(a)*', '**', False, {}),
      ('*$if3(%artist%)*', '**', False, cs_01),
      ('*$if3(%missing%)*', '**', False, cs_01),
      ('*$if3(,)*', '**', False, {}),
      ('*$if3(a,no)*', '*no*', False, {}),
      ('*$if3(%artist%,no)*', '*Collective Soul*', True, cs_01),
      ('*$if3(%artist%,%missing%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(%artist%,%track%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,%missing%)*', '*?*', False, cs_01),
      ('*$if3(%missing%,no)*', '*no*', False, cs_01),
      ('*$if3(%missing1%,%missing2%)*', '*?*', False, cs_01),
      ('*$if3(,,)*', '**', False, {}),
      ('*$if3(,,no)*', '*no*', False, {}),
      ('*$if3(%artist%,no,still no)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,%artist%,still no)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,still no,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(%missing%,no,still no)*', '*still no*', False, cs_01),
      ('*$if3(no,%missing%,still no)*', '*still no*', False, cs_01),
      ('*$if3(no,still no,%missing%)*', '*?*', False, cs_01),
      ('*$if3(wow,no,%artist%,%missing%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(wow,no,%missing%,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(a,b,%missing%,d,e)*', '*e*', False, cs_01),
    ),
    # Real-world use-cases; integration tests
    pytest.param(
        window_title_integration_fmt, window_title_integration_expected, True,
        cs_01, id='window_title_integration'),
]


def __div_logic(x, y):
  if y == 0: return x
  if x == 0: return 0
  if x * y < 0:
    return x * -1 // y * -1
  return x // y

def div_logic(x, y):
  r = __div_logic(x, y)
  return r

def __mod_logic(x, y):
  if y == 0: return x
  return x % y

def mod_logic(x, y):
  r = __mod_logic(x, y)
  return r


arithmetic_resolutions = {
    'add': {'arity0': ('0', False), 'answer': lambda x, y: x + y},
    'sub': {'arity0': ('', False) , 'answer': lambda x, y: x - y},
    'mul': {'arity0': ('1', False), 'answer': lambda x, y: x * y},
    'div': {'arity0': ('', False) , 'answer': div_logic},
    'mod': {'arity0': ('', False) , 'answer': mod_logic},
}

boolean_resolutions = {
    'and': {'arity0': ('', True),   'answer': lambda x, y: x and y},
    'or':  {'arity0': ('', False),  'answer': lambda x, y: x or y},
    'not': {'arity0': ('', False),  'answer': lambda x: not x},
    'xor': {'arity0': ('', False),  'answer': lambda x, y: x ^ y},
}

for key in arithmetic_resolutions:
  arithmetic_resolutions[key]['group'] = 'arithmetic'

for key in boolean_resolutions:
  boolean_resolutions[key]['group'] = 'boolean'

expected_resolutions = arithmetic_resolutions.copy()
expected_resolutions.update(boolean_resolutions)


def resolve_int_var(fn, v, track):
  print("[TEST] Attempting to resolve variable '%s' for fn '%s'" % (v, fn))
  try:
    return int(v)
  except ValueError:
    pass

  try:
    r = int(track[v]) if v in track else 0
  except ValueError:
    return track[v]
  return r


# Generate arithmetic and boolean tests
def generate_tests():
  generated_cases = []
  stripchars = "% -!abc',"
  for fn in expected_resolutions.keys():
    group = expected_resolutions[fn]['group']

    # Arity 0 tests
    fmt = '$%s()' % fn
    expected = expected_resolutions[fn]['arity0'][0]
    expected_truth = expected_resolutions[fn]['arity0'][1]
    generated_cases.append(pytest.param(
        fmt, expected, expected_truth, {},
        id="%s:arity0<%s = '%s'>" % (group, fmt, expected)))

    fmt = '$%s()!a$%s()' % (fn, fn)
    expected = '%s!a%s' % (expected, expected)
    generated_cases.append(pytest.param(
        fmt, expected, expected_truth, {},
        id="%s:arity0<$%s() = '%s'>" % (group, fn, expected)))

    answer = expected_resolutions[fn]['answer']

    # Arity 1 tests
    for testarg in (
        '123', '-456', '-', '0', '-0', '007', '-007', '?',
        '%TOTALDISCS%', '%TRACKNUMBER%', '%ARTIST%', '%MISSING%',
    ):
      testarg_stripped = testarg.strip('%')
      fmt = '$%s(%s)' % (fn, testarg)

      if group == 'arithmetic':
        expected = unistr(resolve_int_var(fn, testarg_stripped, cs_01))
        try:
          expected = unistr(int(expected))
        except ValueError:
          expected = '0'
      elif group == 'boolean':
        expected = ''

      expected_truth = testarg_stripped in cs_01

      try:
        # If there's an arity 1 answer, use it.
        expected_truth = answer(expected_truth)
      except TypeError:
        pass

      generated_cases.append(pytest.param(
          fmt, expected, expected_truth, cs_01,
          id="%s:arity1<%s = '%s'>" % (group, fmt, expected)))

      if testarg[0] == '%' and group == 'arithmetic':
        # Attempts to negate a variable resolution actually work somehow!
        fmt = '$%s(-%s)' % (fn, testarg)
        expected = unistr(int(expected) * -1)
        generated_cases.append(pytest.param(
            fmt, expected, testarg_stripped in cs_01, cs_01,
            id="%s:arity1<%s = '%s'>" % (group, fmt, expected)))

    # Arity 2 tests
    for t1, t2 in (
        (12, 34), (70, 20), (1000, 10), (10, 3), (-10, 3), (10, -3), (-10, -3),
        (123, 0), (0, 123), (0, 0), (0, 10), (10, 0), (100, 0), (0, 100),
        (1, 1), (1, 10), (10, 1), (1, 100), (100, 1), (-1, 1), (1, -1),
        (-1, -1), (-1, 100), (1, -100), (-100, -1), (-1, 0), (0, -1), (0, '-0'),
        ('-0', 0), ('-0', '-0'), (1, '-0'), ('-0', 1), ('', ''), ('-', ''),
        ('', '-'), ('-', '-'), (-1,'-'), ('?', '?'), ('-?', '?'),
        ('%TOTALDISCS%', 1),
        (3, '%TOTALDISCS%'),
        ('%TOTALDISCS%', '?'),
        ('?', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%TOTALDISCS%'),
        ('%MISSING%', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%MISSING%'),
        ('%MISSING%', '%MISSING%'),
    ):
      # First check the literal parser and how it handles numbers
      if fn != 'not': # Skip this check for not
        if type(t1) is int or type(t1) is not int and '%' not in t1:
          s1 = unistr(t1)
          literal_s1 = "'" + s1 + "'"
          a1 = t1 if type(t1) is int else resolve_int_var(fn, t1, cs_01)
          a2 = t2 if type(t2) is int else resolve_int_var(
              fn, t2.strip('%'), cs_01)
          fmt = '$%s(%s,%s)' % (fn, literal_s1, t2)
          expected = '' if group == 'boolean' else unistr(answer(a1, a2))
          expected_truth = False if fn == 'and' else '%' in unistr(t2)
          generated_cases.append(pytest.param(
            fmt, expected, expected_truth, cs_01,
            id="%s:arity2literal<'%s' = '%s'>" % (group, fmt, expected)))
          if len(s1) > 1:
            literal_s1 = "'" + s1[0] + "'" + s1[1:]
            fmt = '$%s(%s,%s)' % (fn, literal_s1, t2)
            generated_cases.append(pytest.param(
              fmt, expected, False, cs_01,
              id="%s:arity2literal<'%s' = '%s'>" % (group, fmt, expected)))

      for g1, g2, g3, g4 in (  # Also generate some garbage text to test with
          ('', '', '', ''),  # The default, no garbage
          ('', '--', '', '--'),
          ('', '!a', '', "','"),
          ('', "','", '', '!a'),
          ('  ', '  ', ' ', ' '),
          ('  ', " ',' ", " ',' ", " ',' "),
      ):
        if fn == 'not' and (
            g2 != ''
            or type(t1) is int and (-1 > t1 or t1 > 1)
            or type(t2) is int and (-1 > t2 or t2 > 1)
        ):
          # We really don't need to test $not that much for arity 2.
          continue
        t1g = '%s%s%s' % (g1, t1, g2)
        t2g = '%s%s%s' % (g3, t2, g4)
        fmt = '$%s(%s,%s)' % (fn, t1g, t2g)
        t1s = t1g.lstrip('% ').rstrip(stripchars)
        t2s = t2g.lstrip('% ').rstrip(stripchars)
        val1 = resolve_int_var(fn, t1s, cs_01)
        val2 = resolve_int_var(fn, t2s, cs_01)

        if group == 'arithmetic':
          expected = unistr(answer(val1, val2))
          expected_truth = (
              t1s.strip(stripchars) in cs_01
              or t2s.strip(stripchars) in cs_01)
        elif group == 'boolean':
          expected = ''
          try:
            expected_truth = answer(t1 == '%TOTALDISCS%', t2 == '%TOTALDISCS%')
          except TypeError:
            # Assume False, this is probably $not.
            expected_truth = False

        generated_cases.append(pytest.param(
            fmt, expected, expected_truth, cs_01,
            id="%s:arity2<%s = '%s'>" % (group, fmt, expected)))

    if fn == 'not':
      # We really don't need to test $not beyond arity 2.
      continue

    # Arity 3+ tests
    for t in (
        (0, 0, 0),
        (1, 2, 3),
        (0, 2, 3),
        (1, 0, 3),
        (1, 2, 0),
        (128, 2, 2),
        (128, 0, 3),
        (128, 5, 0),
        (128, -2, 2),
        (128, -0, 3),
        (128, -5, 0),
        (128, -2, -2),
        (128, -0, -3),
        (128, -5, -0),
        (-128, -2, -2),
        (-128, -0, -3),
        (-128, -5, -0),
        (6969, 0, -0),
        ('', '', ''),
        ('-', '-', '-'),
        ('%MISSING%', '%MISSING%', '%MISSING%'),
        ('%TOTALDISCS%', '%TOTALDISCS%', '%TOTALDISCS%'),
        ('%MISSING%', '%TOTALDISCS%', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%MISSING%', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%TOTALDISCS%', '%MISSING%'),
        (0, 0, '%TOTALDISCS%'),
        (1, 1, '%TOTALDISCS%'),
        (0, 0, '%MISSING%'),
        (1, 1, '%MISSING%'),
        (1, 2, 3, 4),
        (-4, -3, -2, -1),
        ('  -1!a', '-1- ', ' -2 -9-  ', '-3a bc  '),
        ('  -1!a', '-1- ', ' -2 -9-  ', '-3a bc  ', '10-')
    ):
      fmt = '$%s(%s)' % (fn, ','.join(map(unistr, t)))
      ts = [x for x in
            map(lambda x:
                x.lstrip('% ').replace('2 -9-', '2').rstrip(stripchars),
              map(unistr, t))]
      vals = [resolve_int_var(fn, x, cs_01) for x in ts]

      if group == 'boolean':
        expected = ''
      else:
        expected = answer(vals[0], vals[1])
        for x in vals[2:]:
          expected = answer(expected, x)
        expected = unistr(expected)

      if group == 'boolean':
        try:
          expected_truth = reduce(answer, map(lambda x: x == '%TOTALDISCS%', t))
        except TypeError:
          # Assume False, this is probably $not.
          expected_truth = False
      else:
        expected_truth = reduce(
            lambda x, y: x or y, map(lambda z: z in cs_01, ts))
      generated_cases.append(pytest.param(
        fmt, expected, expected_truth, cs_01,
        id="%s:arity%s<'%s' = '%s'>" % (group, len(t), fmt, expected)))
  return generated_cases


test_eval_cases += generate_tests()


# Add min/max tests
for fn in ('min', 'max'):
  for case in (
      (['0'], '0', False),
      (['123'], '123', False),
      (['-'], '0', False),
      (['',''], '0', False),
      (['2','1'], '1', '2', False),
      (['-2','1'], '-2', '1', False),
      (['1','2'], '1', '2', False),
      (['-1','2'], '-1', '2', False),
      (['','',''], '0', False),
      (['-1','-2','-3'], '-3', '-1', False),
      (['','-2','-3'], '-3', '0', False),
      (['-2','-1','3', '2', ''], '-2', '3', False),
      (['%missing%'], '0', False),
      (['%totaltracks%'], cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%'], '0', False),
      (['%totaltracks%', '%missing%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%totaltracks%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%', '%missing%'], '0', False),
      (['%totaltracks%', '%missing%', '%missing%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%totaltracks%', '%missing%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%', '%totaltracks%'],
        '0', cs_01['TOTALTRACKS'], True),
  ):
    caselen = len(case)
    fmt = '$%s(%s)' % (fn, ','.join(case[0]))
    min_expected = case[1]
    max_expected = case[-2]
    expected = min_expected if fn == 'min' else max_expected
    expected_truth = case[-1]
    arity = len(case[0])

    test_eval_cases.append(pytest.param(
      fmt, expected, expected_truth, cs_01,
      id="arithmetic:arity%s('%s' = '%s')" % (arity, fmt, expected)))
    # Now check for variable negation
    if len([e1 for e1 in filter((
        lambda x: len([e2 for e2 in filter((
          lambda y: '%' in y), x)]) > 0), case[0])]) > 0:
      negated = ['-' + x for x in case[0]]
      expected = unistr(-int(max_expected if fn == 'min' else min_expected))
      fmt = '$%s(%s)' % (fn, ','.join(negated))
      test_eval_cases.append(pytest.param(
        fmt, expected, expected_truth, cs_01,
        id="arithmetic:arity%s('%s' = '%s')" % (arity, fmt, expected)))


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
      fn = f.eval(None, fmt, compiling=True)
      quiet_result = fn(track)
    else:
      quiet_result = f.eval(track, fmt)

    assert quiet_result.string_value == expected
    assert quiet_result.truth_value is expected_truth

