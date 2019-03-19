#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from euphonogenizer import titleformat
from euphonogenizer.titleformat import EvaluatorAtom

from functools import reduce
from itertools import product

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

fake = {
    "DASH" : "-",
    "DOT" : ".",
    "SLASH" : "/",
    "TEN" : "10",
    "TWO" : "02",
}

mm_album_artist = {
    "ALBUM ARTIST" : "me",
    "ARTIST" : "not me",
    "COMPOSER" : "someone else",
    "PERFORMER" : "that other guy",
}

mm_album_artist_only = {
    "ALBUM ARTIST" : "me",
    "COMPOSER" : "someone else",
    "PERFORMER" : "that other guy",
}

mm_artist = {
    "ARTIST" : "me this time",
    "COMPOSER" : "still not me",
    "PERFORMER" : "but this time it's that other guy",
}

mm_composer = {
    "COMPOSER" : "just taking credit",
    "PERFORMER" : "this guy",
}

mm_performer = {
    "PERFORMER" : "Britney Spears",
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

test_url = 'www.techtv.com/screensavers/supergeek/story/0,24330,3341900,00.html'

def _tcid(prefix, testcase):
  suffix = '' if len(testcase) <= 4 or not testcase[4] else ':' + testcase[4]
  return "%s%s<'%s' = '%s'>" % (prefix, suffix, testcase[0], testcase[1])

def _testcasegroup(idprefix, *testcases):
  return [pytest.param(*x[:4], id=_tcid(idprefix, x))
          for x in testcases]

def _generatecases(idsuffix, fn, answers, *inputs):
  return [('$%s(%s)' % (fn, ','.join(x)), *answers(x), idsuffix)
          for x in product(*inputs)]

def resolve_var(v, track, missing='?', stripped=False):
  if '%' in v or stripped:
    if not stripped:
      v = v.strip('%')
    return track[v] if v in track else missing
  return v

def resolve_int_var(v, track, stripped=False):
  try:
    if stripped:
      return int(v)
    else:
      return int(v.rstrip(' abc').lstrip(' '))
  except ValueError:
    pass

  r = resolve_var(v, track, missing=0, stripped=stripped)

  try:
    return int(r)
  except ValueError:
    return 0

test_eval_cases = [
    # Basic parsing tests -- test various interesting parser states
    *_testcasegroup('parser:basic',
      ('', '', False, {}),
      (' ', ' ', False, {}),
      (',', ',', False, {}),
      ('asdf1234', 'asdf1234', False, {}),
      ("''", "'", False, {}),
      ("''''", "''", False, {}),
      ("'a'''b", "a'b", False, {}),
      ("'a''''''b'", "a''b", False, {}),
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
    *_testcasegroup('parser:invalid',
      ("'", '', False, None),
      ("'''", "'", False, None),
      ("a'b", 'a', False, None),
      ('$', '', False, None),
      ('a$b', 'a', False, None),
      ('$a$', '', False, None),
      ('(', '', False, None),
      ('a(b', 'a', False, None),
      (')', '', False, None),
      ('a)b', 'a', False, None),
      ('[', '', False, None),
      ('a[b', 'a', False, None),
      (']', '', False, None),
      ('a]b', 'a', False, None),
      ('%', '', False, None),
      ('a%b', 'a', False, None),
      ('a$invalid(', 'a', False, None),
      ('a$invalid)', 'a', False, None),
      ('a$invalid(b', 'a', False, None),
      ('a$invalid(b,', 'a', False, None),
      ('a$invalid(b$invalid(,', 'a', False, None),
      ('a$invalid(b$invalid),', 'a', False, None),
      ("a$invalid'('')'(b)", 'a', False, None),
      ("a$invalid')''(')b(", 'a', False, None),
      ("a$invalid(b$invalid($invalid')''('(')'))))",
        'a[UNKNOWN FUNCTION]', False, None),
      ("$if2(a,b$if2(c,$invalid(')'')'')')))",
        'b[UNKNOWN FUNCTION]', False, None),
      ("a$add('3", 'a', False, None),
    ),
    *_testcasegroup('parser:functions',
      ('$', '', False, {}),
      ("'$", '', False, {}),
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
    ),
    *_testcasegroup('parser:numbers',
      ("$add(0)", '0', False, {}),
      ("$add(1)", '1', False, {}),
      ("$add(False)", '0', False, {}),
      ("$add(True)", '0', False, {}),
      ("$add(None)", '0', False, {}),
      ("$add(,)", '0', False, {}),
      ("$add('1234')", '1234', False, {}),
    ),
    *_testcasegroup('parser:functions_complex',
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
      ("$if2(,'$if2(,'$if2(,'''''$if2(,'$if2(,'a')')')')')",
        "$if2(,''$if2(,a))", False, {}),
      ('$$&$$$$$$$add(1,2)$$$$$$&$$', '$&$$$3$$$&$', False, {}),
      ('$$&$$$$$$%track%$$$$$$&$$', '$&$$$01$$$&$', True, cs_01),
      ('$$&$$$$$$[%track%]$$$$$$&$$', '$&$$$01$$$&$', True, cs_01),
    ),
    # Variable resolution tests
    *_testcasegroup('variable',
      ('%artist% - ', 'Collective Soul - ', True, cs_01),
      ('[%artist% - ]', 'Collective Soul - ', True, cs_01),
      ('*[%missing% - ]*', '**', False, cs_01),
      ("'%artist%'", '%artist%', False, cs_01),
    ),
    # Magic mappings
    *_testcasegroup('variable:magic_mapping',
      #('%artist%', '', False, None),  # TODO: broken, will fix later
      ('%album artist%-1', 'me-1', True, mm_album_artist),
      ('%album artist%-2', 'me this time-2', True, mm_artist),
      ('%album artist%-3', 'just taking credit-3', True, mm_composer),
      ('%album artist%-4', 'Britney Spears-4', True, mm_performer),
      ('%album artist%-5', '?-5', False, fake),
      ('%artist%-1', 'not me-1', True, mm_album_artist),
      ('%artist%-2', 'me-2', True, mm_album_artist_only),
      ('%artist%-3', 'me this time-3', True, mm_artist),
      ('%artist%-4', 'just taking credit-4', True, mm_composer),
      ('%artist%-5', 'Britney Spears-5', True, mm_performer),
      ('%artist%-6', '?-6', False, fake),
    ),
    # Bizarre variable resolution, yes this actually works in foobar
    *_testcasegroup('variable:arithmetic_magic',
      ('$add(1%track%,10)', '111', True, cs_01),
      ('$sub(1%track%,10)', '91', True, cs_01),
      ('$mul(1%track%,10)', '1010', True, cs_01),
      ('$div(1%track%,10)', '10', True, cs_01),
    ),
    *_testcasegroup('conditional',
      ("[']'%artist%'[']", ']Collective Soul[', True, cs_01),
      ('asdf[jkl][qwer%disc%[ty]uiop]%track%[a[b[$add(1,%track%)]c]d]',
        'asdfqwer1uiop01ab2cd', True, cs_01),
    ),
    # Sanity tests, basic non-generated cases that validate generated ones
    *_testcasegroup('sanity:arithmetic',
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
      # $ifequal()
      ('*$ifequal()*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(a)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,,)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,,,)*', '**', False, {}),
      ('*$ifequal(,,,,)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(,0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(-0,0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,-0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(zero,one,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,1,yes,no)*', '*no*', False, {}),
      ('*$ifequal(1,1,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(1,0,yes,no)*', '*no*', False, {}),
      ('*$ifequal(-1,1,yes,no)*', '*no*', False, {}),
      ('*$ifequal(1,-1,yes,no)*', '*no*', False, {}),
      ('*$ifequal(-1,-1,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(2,2,%track%,no)*', '*01*', True, cs_01),
      ('*$ifequal(2,2,%track%,%missing%)*', '*01*', True, cs_01),
      ('*$ifequal(2,2,no,%track%)*', '*no*', False, cs_01),
      ('*$ifequal(2,2,%missing%,%track%)*', '*?*', False, cs_01),
      ('*$ifequal(123 a,-123 a,no,%track%)*', '*01*', True, cs_01),
      ('*$ifequal(123 a,-123 a,no,%missing%)*', '*?*', False, cs_01),
      ('*$ifequal(%artist%,0,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%track%,0,yes,no)*', '*no*', False, cs_01),
      ('*$ifequal(%missing%,0,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(0,%artist%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(0,%track%,yes,no)*', '*no*', False, cs_01),
      ('*$ifequal(0,%missing%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%artist%,%artist%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%track%,%track%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%missing%,%missing%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%artist%,0,%track%,no)*', '*01*', True, cs_01),
      ('*$ifequal(%track%,0,yes,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$ifequal(%missing%,0,%track%,no)*', '*01*', True, cs_01),
      ('*$ifequal(0,%artist%,%missing%,%track%)*', '*?*', False, cs_01),
      ('*$ifequal(0,%track%,%artist%,%missing%)*', '*?*', False, cs_01),
      ('*$ifequal(0,%missing%,yes,%missing%)*', '*yes*', False, cs_01),
      ('*$ifequal(%artist%,-1%artist%,yes,%missing%)*', '*?*', False, cs_01),
      ('*$ifequal(%track%,-1%track%,yes,%track%)*', '*01*', True, cs_01),
      ('*$ifequal(%missing%,-1%missing%,yes,%track%)*', '*01*', True, cs_01),
      # $ifgreater()
      ('*$ifgreater()*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(a)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,,)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,,,)*', '**', False, {}),
      ('*$ifgreater(,,,,)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(,0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(-0,0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,-0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(zero,one,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(1,1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(1,0,yes,no)*', '*yes*', False, {}),
      ('*$ifgreater(-1,1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(1,-1,yes,no)*', '*yes*', False, {}),
      ('*$ifgreater(-1,-1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(2,2,%track%,no)*', '*no*', False, cs_01),
      ('*$ifgreater(2,2,%track%,%missing%)*', '*?*', False, cs_01),
      ('*$ifgreater(2,2,no,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(2,2,%missing%,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(123 a,-123 a,%track%,no)*', '*01*', True, cs_01),
      ('*$ifgreater(123 a,-123 a,%missing%,no)*', '*?*', False, cs_01),
      ('*$ifgreater(%artist%,0,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%track%,0,yes,no)*', '*yes*', False, cs_01),
      ('*$ifgreater(%missing%,0,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(0,%artist%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(0,%track%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(0,%missing%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%artist%,%artist%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%track%,%track%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%missing%,%missing%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%artist%,0,%track%,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%track%,0,%artist%,no)*', '*Collective Soul*', True, cs_01),
      ('*$ifgreater(%missing%,0,no,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(0,%artist%,%missing%,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(0,%track%,%artist%,%missing%)*', '*?*', False, cs_01),
      ('*$ifgreater(0,%missing%,yes,%missing%)*', '*?*', False, cs_01),
      ('*$ifgreater(%artist%,-1%artist%,%missing%,no)*', '*?*', False, cs_01),
      ('*$ifgreater(%track%,-1%track%,%track%,no)*', '*01*', True, cs_01),
      ('*$ifgreater(%missing%,-1%missing%,%track%,no)*', '*01*', True, cs_01),
      # $iflonger()
      ('*$iflonger()*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(a)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(,)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(,,)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(,,,)*', '**', False, {}),
      ('*$iflonger(,,,,)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      *_generatecases('generated', 'iflonger',
        lambda x: (
          resolve_var(x[2], cs_01)
            if len(resolve_var(x[0], cs_01)) > resolve_int_var(x[1], cs_01)
            else resolve_var(x[3], cs_01),
          len(resolve_var(x[0], cs_01)) > resolve_int_var(x[1], cs_01)
            and 'A' in x[2]  # Bit of a hack here to avoid %MISSING% = True
            or len(resolve_var(x[0], cs_01)) <= resolve_int_var(x[1], cs_01)
            and 'A' in x[3],
          cs_01),
        ('', '0', '00', '-0', '1', '-1', '2', 'zero', 'one', '123 a', '-123 a',
          ' ', ' ' * 2, ' ' * 3, '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
        ('', '0', '-0', '1', '-1', '2', 'zero', 'one', ' 123 a', ' -123 a',
          '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
        ('yes', '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
        ('no', '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
      ),
      # $select()
      ('*$select()*', '**', False, {}),
      ('*$select(a)*' ,'**', False, {}),
      *_generatecases('generated:arity2', 'select',
        lambda x: (
          resolve_var(x[1], cs_01)
            if resolve_int_var(x[0], cs_01) == 1 else '',
          resolve_int_var(x[0], cs_01) == 1 and 'A' in x[1],
          cs_01),
        ('', 'a', '0', '1', '2', '3', '-1', '-2',
          '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
        ('', 'a', '123', '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
      ),
      *_generatecases('generated:arity3', 'select',
        lambda x: (
          *(lambda i=resolve_int_var(x[0], cs_01):
              (
                (resolve_var(x[1], cs_01), resolve_var(x[2], cs_01))[i - 1]
                  if i > 0 and i <= 2 else '',
                i > 0 and i <= 2 and 'A' in x[i],
              )
            )(),
          cs_01),
        ('', 'a', '0', '1', '2', '3', '-1', '-2', '-3',
          '%ARTIST%', '%TRACKNUMBER%', '%TOTALDISCS%', '%missing%'),
        ('', 'a', '123', '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
        ('', 'b', '-456', '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
      ),
      *_generatecases('generated:arity4', 'select',
        lambda x: (
          *(lambda i=resolve_int_var(x[0], cs_01):
              (
                (
                  resolve_var(x[1], cs_01),
                  resolve_var(x[2], cs_01),
                  resolve_var(x[3], cs_01),
                )[i - 1]
                  if i > 0 and i <= 3 else '',
                i > 0 and i <= 3 and 'A' in x[i],
              )
            )(),
          cs_01),
        ('', 'a', '0', '1', '2', '3', '-1', '-4',
          '%ARTIST%', '%TOTALDISCS%', '%missing%'),
        ('', 'a', '%ARTIST%', '%missing%'),
        ('', 'b', '%TRACKNUMBER%', '%missing%'),
        ('', 'c', '%DATE%', '%missing%'),
      ),
    ),
    *_testcasegroup('strings',
      # $abbr()
      ('$abbr()', '', False, {}),
      ('$abbr(,)', '', False, {}),
      ('$abbr(,,)', '', False, {}),
      ('$abbr(,,,)', '', False, {}),
      ("$abbr('')", "'", False, {}),
      ("$abbr(' ')", '', False, {}),
      ("$abbr(''a)", "'", False, {}),
      ("$abbr('a'b)", 'a', False, {}),
      ('$abbr(/a)', 'a', False, {}),  # Why does fb2k do this??
      ('$abbr(\\a)', 'a', False, {}),
      ("$abbr(','a)", 'a', False, {}),
      ('$abbr(¿a)', '¿', False, {}),
      ("$abbr('['a)", '[a', False, {}),
      ("$abbr(']'a)", ']a', False, {}),
      ("$abbr(a'[')", 'a', False, {}),
      ("$abbr(a']')", 'a', False, {}),
      ("$abbr('[]'a'[')", '[]a[', False, {}),
      ("$abbr('a(b)c')", 'abc', False, {}),
      ("$abbr('a/b/c')", 'abc', False, {}),
      ("$abbr('a\\b\\c')", 'abc', False, {}),
      ("$abbr('a,b,c')", 'abc', False, {}),
      ("$abbr('a.b.c')", 'a', False, {}),
      ('$abbr(-1234 5678)', '-5678', False, {}),
      ("$abbr('[a(b[c]d)e]')", '[abe', False, {}),
      ("$abbr('[ab/cd/ef[gh]')", '[abce', False, {}),
      ("$abbr('/a \\b [c ]d (e )f (g(h )i)j [k(l/m]n ]o/p)q]r -123')",
        'ab[c]defghij[klm]opq-', False, {}),
      ("$abbr('[a(b[c'%artist%')')", '[abS', True, cs_01),
      ('$abbr(%missing%a)', '?', False, {}),
      ('$abbr(%artist%)', 'CS', True, cs_01),
      ("$abbr('%artist%')", '%', False, cs_01),
      ('$abbr([%artist%])', 'CS', True, cs_01),
      ("$abbr(%date%)", '2015', True, cs_01),
      ("$abbr('ああ')", 'あ', False, {}),
      # Unfortunately fb2k doesn't understand other Unicode spaces
      ("$abbr('。あ　亜。')", '。', False, {}),
      ('$abbr(!abc)', '!', False, {}),
      ('$abbr(Memoirs of 2005)', 'Mo2005', False, {}),
      ('$abbr(Memoirs of 2005a)', 'Mo2', False, {}),
      # Examples from documentation
      ("$abbr('This is a Long Title (12-inch version) [needs tags]')",
        'TiaLT1v[needst', False, {}),
      # NOTE: There are more encoding tests for $ansi() and $ascii() later.
      # $ansi()
      ('$ansi()', '', False, {}),
      ('$ansi( a )', ' a ', False, {}),
      ('$ansi(%artist%)', 'Collective Soul', True, cs_01),
      ('$ansi(2814 - 新しい日の誕生)', '2814 - ???????', False, {}),
      ('$ansi(a,b)', '', False, {}),
      # $ascii
      ('$ascii()', '', False, {}),
      ('$ascii( a )', ' a ', False, {}),
      ('$ascii(%artist%)', 'Collective Soul', True, cs_01),
      ('$ascii(2814 - 新しい日の誕生)', '2814 - ???????', False, {}),
      ('$ascii(a,b)', '', False, {}),
      # $caps
      ('$caps()', '', False, {}),
      ('$caps(a)', 'A', False, {}),
      ('$caps(á)', 'Á', False, {}),
      ('$caps(a c a b)', 'A C A B', False, {}),
      ("$caps('ŭaŭ, la ĥoraĉo eĥadas en ĉi tiu preĝejo')",
        'Ŭaŭ, La Ĥoraĉo Eĥadas En Ĉi Tiu Preĝejo', False, {}),
      ("$caps('ŬAŬ, LA ĤORAĈO EĤADAS EN ĈI TIU PREĜEJO')",
        'Ŭaŭ, La Ĥoraĉo Eĥadas En Ĉi Tiu Preĝejo', False, {}),
      ('$caps(У Сашки в карма́шке ши́шки да ша́шки)',
        'У Сашки В Карма́шке Ши́шки Да Ша́шки', False, {}),
      ('$caps(У САШКИ В КАРМА́ШКЕ ШИ́ШКИ ДА ША́ШКИ)',
        'У Сашки В Карма́шке Ши́шки Да Ша́шки', False, {}),
      ('$caps(Μιὰ πάπια μὰ ποιά πάπια;)',
        'Μιὰ Πάπια Μὰ Ποιά Πάπια;', False, {}),
      ('$caps(ΜΙᾺ ΠΆΠΙΑ ΜᾺ ΠΟΙΆ ΠΆΠΙΑ;)',
        'Μιὰ Πάπια Μὰ Ποιά Πάπια;', False, {}),
      (r"""$caps('aaA ɐɐⱯ`bbB,əəƏ~ccC.ddD/eeE;ffF:ggG''''hhH"kkK[ααΑ]ϟϟϞ')""",
        r"""Aaa Ɐɐɐ`bbb,Əəə~ccc.ddd/Eee;fff:ggg'hhh"kkk[Ααα]Ϟϟϟ""", False, {}),
      (r"""$caps('aaA{mmM}nnN|ooO\ááÁ=ppP+qqQ-rrR(ⅶⅶⅦ)ɔɔƆ*ssS&ttT^uuU')""",
        r"""Aaa{mmm}nnn|Ooo\Ááá=ppp+qqq-rrr(Ⅶⅶⅶ)Ɔɔɔ*sss&ttt^uuu""", False, {}),
      (r"""$caps('aaA%vvV$wwW#xxX@yyY!zzZ?jjJ　ppP。iiI（jjJ）aaA⸱bbB')""",
        r"""Aaa%vvv$www#xxx@yyy!zzz?jjj　ppp。iii（jjj）aaa⸱bbb""", False, {}),
      (r"""$caps('qqQ【ccC】ddD⁽eeE︵ffF༺ggG')""",
        'Qqq【ccc】ddd⁽eee︵fff༺ggg', False, {}),
      ('$caps(%artist%)', 'Collective Soul', True, cs_01),
      ('$caps(%artist%, b)', '', False, cs_01),
      # $caps2
      ('$caps2()', '', False, {}),
      ('$caps2(a)', 'A', False, {}),
      ('$caps2(á)', 'Á', False, {}),
      ('$caps2(a c a b)', 'A C A B', False, {}),
      ("$caps2('ŭaŭ, la ĥoraĉo eĥadas en ĉi tiu preĝejo')",
        'Ŭaŭ, La Ĥoraĉo Eĥadas En Ĉi Tiu Preĝejo', False, {}),
      ("$caps2('ŬAŬ, LA ĤORAĈO EĤADAS EN ĈI TIU PREĜEJO')",
        'ŬAŬ, LA ĤORAĈO EĤADAS EN ĈI TIU PREĜEJO', False, {}),
      ('$caps2(У Сашки в карма́шке ши́шки да ша́шки)',
        'У Сашки В Карма́шке Ши́шки Да Ша́шки', False, {}),
      ('$caps2(У САШКИ В КАРМА́ШКЕ ШИ́ШКИ ДА ША́ШКИ)',
        'У САШКИ В КАРМА́ШКЕ ШИ́ШКИ ДА ША́ШКИ', False, {}),
      ('$caps2(Μιὰ πάπια μὰ ποιά πάπια;)',
        'Μιὰ Πάπια Μὰ Ποιά Πάπια;', False, {}),
      ('$caps2(ΜΙᾺ ΠΆΠΙΑ ΜᾺ ΠΟΙΆ ΠΆΠΙΑ;)',
        'ΜΙᾺ ΠΆΠΙΑ ΜᾺ ΠΟΙΆ ΠΆΠΙΑ;', False, {}),
      (r"""$caps2('aaA ɐɐⱯ`bbB,əəƏ~ccC.ddD/eeE;ffF:ggG''''hhH"kkK[ααΑ]ϟϟϞ')""",
        r"""AaA ⱯɐⱯ`bbB,ƏəƏ~ccC.ddD/EeE;ffF:ggG'hhH"kkK[ΑαΑ]ϞϟϞ""", False, {}),
      (r"""$caps2('aaA{mmM}nnN|ooO\ááÁ=ppP+qqQ-rrR(ⅶⅶⅦ)ɔɔƆ*ssS&ttT^uuU')""",
        r"""AaA{mmM}nnN|OoO\ÁáÁ=ppP+qqQ-rrR(ⅦⅶⅦ)ƆɔƆ*ssS&ttT^uuU""", False, {}),
      (r"""$caps2('aaA%vvV$wwW#xxX@yyY!zzZ?jjJ　ppP。iiI（jjJ）aaA⸱bbB')""",
        r"""AaA%vvV$wwW#xxX@yyY!zzZ?jjJ　ppP。iiI（jjJ）aaA⸱bbB""", False, {}),
      (r"""$caps2('qqQ【ccC】ddD⁽eeE︵ffF༺ggG')""",
        'QqQ【ccC】ddD⁽eeE︵ffF༺ggG', False, {}),
      ('$caps2(%artist%)', 'Collective Soul', True, cs_01),
      ('$caps2(%artist%, b)', '', False, cs_01),
      # $char
      ('$char()', '', False, {}),
      ('$char(0)', '', False, {}),
      ('$char(-1)', '', False, {}),
      ('$char(208)$char(111)$char(103)$char(101)', 'Ðoge', False, {}),
      ('$char(20811)', '克', False, {}),
      ('$char(1048575)', '󿿿', False, {}),
      ('$char(1048576)', '?', False, {}),
      ('$char(asdf)', '', False, {}),
      ('$char(%totaltracks%)', '', False, cs_01),
      ('$char(a,b)', '', False, {}),
      # $crc32
      ('$crc32()', '', False, {}),
      ('$crc32( )', '3916222277', False, {}),
      ('$crc32(abc)', '891568578', False, {}),
      ('$crc32(%totaltracks%)', '3596227959', True, cs_01),
      ("$crc32('')", '1997036262', False, {}),
      ('$crc32(a b c)', '3358461392', False, {}),
      ('$crc32(1,%totaltracks%)', '', False, cs_01),
      ("$crc32(G#1cW)$crc32('J]GAD')$crc32(in0W=)$crc32('eAe%Y')"
          "$crc32(6Nc6p)$crc32('9]rkV')$crc32('7Rm[j')", '0234568', False, {}),
      # TODO: $crlf, $cut
      # $directory
      ('$directory()', '', False, {}),
      ('$directory( )', '', False, {}),
      ('$directory(\\ \\)', ' ', False, {}),
      ('$directory(\\\\server\\dir\\file.fil)', 'dir', False, {}),
      ('$directory(/local/home/user/file.tar.xz)', 'user', False, {}),
      ('$directory(a|b|c)', 'b', False, cs_01),
      ('$directory(c:\\a|b|c|d, 3)', 'a', False, {}),
      ('$directory(/a/b/)', 'b', False, {}),
      ('$directory(/a/b/, 2)', 'a', False, {}),
      ('$directory(/a/b/, 3)', '', False, {}),
      ('$directory(/a/b/, 4)', '', False, {}),
      ('$directory(||||)', '', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt)',
          'Text Files', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\%totaltracks%.txt)',
          'Text Files', True, cs_01),
      ('$directory(C:\\My Documents\\Text Files\\%missing%.txt)',
          'Text Files', False, cs_01),
      ('$directory(C:\\My Documents\\%totaltracks%\\file.txt)',
          '11', True, cs_01),
      ('$directory(C:\\My Documents\\%totaltracks%\\file.txt, 2)',
          'My Documents', True, cs_01),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 0)', '', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 1)',
          'Text Files', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 2)',
          'My Documents', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 3)', '', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 4)', 'C', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, -1)', '', False, {}),
      ('$directory(.././../file.txt)', '..', False, {}),
      ('$directory(.././../file.txt, 1)', '..', False, {}),
      ('$directory(.././../file.txt, 2)', '.', False, {}),
      ('$directory(.././../file.txt, 3)', '..', False, {}),
      ('$directory(.././../file.txt, 4)', '', False, {}),
      ('$directory(%SLASH%%SLASH%)', '', True, fake),
      ('$directory(a%SLASH%b%SLASH%c)', 'b', True, fake),
      ('$directory(a%SLASH%b%SLASH%c%DOT%d)', 'b', True, fake),
      ('$directory(%SLASH%%SLASH%, 2)', '', True, fake),
      ('$directory(a%SLASH%b%SLASH%c, 2)', 'a', True, fake),
      ('$directory(a%SLASH%b%SLASH%c%DOT%d, 2)', 'a', True, fake),
      ('$directory(a,b,c)', '', False, {}),
      # $directory_path
      ('$directory_path()', '', False, {}),
      ("$directory_path('//')", '/', False, {}),
      ('$directory_path(/usr/bin/vim)', '/usr/bin', False, {}),
      ('$directory_path(C:\\My Documents\\Text Files\\file.txt)',
          'C:\\My Documents\\Text Files', False, {}),
      ('$directory_path(.././../file.txt)', '.././..', False, {}),
      ('$directory_path(a|b|c)', 'a|b', False, {}),
      ('$directory_path(a|%totaltracks%|c|d)', 'a|11|c', True, cs_01),
      ('$directory_path(%SLASH%%SLASH%)', '/', True, fake),
      ('$directory_path(a%SLASH%b%SLASH%c)', 'a/b', True, fake),
      ('$directory_path(a%SLASH%b%SLASH%c%DOT%d)', 'a/b', True, fake),
      ('$directory_path(a,b)', '', False, {}),
      # $ext
      ('$ext()', '', False, {}),
      ('$ext(a)', '', False, {}),
      ('$ext(a.b)', 'b', False, {}),
      ('$ext( before.after   )', 'after   ', False, {}),
      ('$ext(example.com/test)', '', False, {}),
      ('$ext(cat.tar.gz)', 'gz', False, {}),
      ('$ext(abc.d:e)', '', False, {}),
      ('$ext(abc.d|e)', '', False, {}),
      ('$ext(abc.d\\e)', '', False, {}),
      ('$ext(file.txt?a/b)', '', False, {}),
      ('$ext(%totaltracks%)', '', False, cs_01),  # Actual FB2k behavior
      ('$ext(a.%totaltracks%)', '11', True, cs_01),
      ('$ext(%totaltracks%.a)', 'a', True, cs_01),
      ('$ext(\\a|:b%totaltracks%/c.d\\e)', '', False, cs_01),
      ('$ext(\\a|:b%totaltracks%/c.d\\e.a)', 'a', True, cs_01),
      ('$ext(/usr/bin/vim)', '', False, {}),
      ('$ext(C:\\My Documents\\Text Files\\file.txt)', 'txt', False, {}),
      ('$ext(.././../file.txt)', 'txt', False, {}),
      ("$ext('http://neopets.com/randomfriend.phtml?user=adam')",
          'phtml', False, {}),
      ("$ext('%s?')" % test_url, 'html', False, {}),
      ("$ext('%s#target')" % test_url, 'html#target', False, {}),
      ("$ext('%s?param=value')" % test_url, 'html', False, {}),
      ("$ext('%s?p1=val1&p2=val2')" % test_url, 'html', False, {}),
      ("$ext('%s?file=test.txt')" % test_url, 'txt', False, {}),
      ("$ext('%s?f=a.txt&m=upload')" % test_url, 'txt&m=upload', False, {}),
      ("$ext('" + test_url + "?ab.bc?de??'%track%)", 'bc', True, cs_01),
      ('$ext(%SLASH%%SLASH%)', '', False, fake),
      ('$ext(a%SLASH%b%SLASH%c)', '', False, fake),
      ('$ext(a%SLASH%b%SLASH%c%DOT%d)', 'd', True, fake),
      ('$ext(a,b)', '', False, {}),
      # $filename
      ('$filename()', '', False, {}),
      ('$filename(a)', 'a', False, {}),
      ('$filename(a.b)', 'a', False, {}),
      ('$filename( before.after   )', ' before', False, {}),
      ('$filename(example.com/test)', 'test', False, {}),
      ('$filename(cat.tar.gz)', 'cat.tar', False, {}),
      ('$filename(abc.d:e)', 'e', False, {}),
      ('$filename(abc.d|e)', 'e', False, {}),
      ('$filename(abc.d\\e)', 'e', False, {}),
      ('$filename(file.txt?a/b)', 'b', False, {}),
      ('$filename(%totaltracks%)', '11', True, cs_01),
      ('$filename(a.%totaltracks%)', 'a', True, cs_01),
      ('$filename(%totaltracks%.a)', '11', True, cs_01),
      ('$filename(\\a|:b%totaltracks%/c.d\\e)', 'e', True, cs_01),
      ('$filename(\\a|:b%totaltracks%/c.d\\e.a)', 'e', True, cs_01),
      ('$filename(/usr/bin/vim)', 'vim', False, {}),
      ('$filename(C:\\My Documents\\Text Files\\file.txt)', 'file', False, {}),
      ('$filename(.././../file.txt)', 'file', False, {}),
      ("$filename('http://neopets.com/randomfriend.phtml?user=adam')",
          'randomfriend', False, {}),
      ("$filename('%s?')" % test_url, '0,24330,3341900,00', False, {}),
      ("$filename('%s#target')" % test_url, '0,24330,3341900,00', False, {}),
      ("$filename('%s?param=value')" % test_url,
          '0,24330,3341900,00', False, {}),
      ("$filename('%s?p1=val1&p2=val2')" % test_url,
          '0,24330,3341900,00', False, {}),
      ("$filename('%s?file=test.txt')" % test_url,
          '0,24330,3341900,00', False, {}),
      ("$filename('%s?f=a.txt&m=upl')" % test_url,
          '0,24330,3341900,00', False, {}),
      ("$filename('" + test_url + "?ab.bc?de??'%track%)",
          '0,24330,3341900,00', True, cs_01),
      ('$filename(%SLASH%%SLASH%)', '', True, fake),
      ('$filename(a%SLASH%b%SLASH%c)', 'c', True, fake),
      ('$filename(a%SLASH%b%SLASH%c%DOT%d)', 'c', True, fake),
      ('$filename(a,b)', '', False, {}),
      # $fix_eol
      ('$fix_eol()', '', False, {}),
      ('$fix_eol(a)', 'a', False, {}),
      ('$fix_eol(%totaltracks%)', '11', True, cs_01),
      ('$fix_eol(cats$crlf()dogs)', 'cats (...)', False, {}),
      ('$fix_eol(cats$crlf()%track%)', 'cats (...)', True, cs_01),
      ('$fix_eol(%tracknumber%$crlf()dogs)', '01 (...)', True, cs_01),
      ('$fix_eol(cats\ndogs)', 'cats (...)', False, {}), # Unix
      ('$fix_eol(cats\r\ndogs)', 'cats (...)', False, {}), # DOS
      ('$fix_eol(cats\rdogs)', 'cats (...)', False, {}), # Mac OS Classic
      ('$fix_eol(cats$char(10)dogs)', 'cats (...)', False, {}), # Unix
      ('$fix_eol(cats$char(13)$char(10)dogs)', 'cats (...)', False, {}), # DOS
      ('$fix_eol(cats$char(13)dogs)', 'cats (...)', False, {}), # Mac OS Classic
      ('$fix_eol(cats$char(30)dogs)', 'catsdogs', False, {}), # Old QNX
      ('$fix_eol(cats\ndogs, meow)', 'cats meow', False, {}), # Unix
      ('$fix_eol(cats\r\ndogs,meow)', 'catsmeow', False, {}), # DOS
      ('$fix_eol(cats\rdogs, meow)', 'cats meow', False, {}), # Mac OS Classic
      ('$fix_eol(cats\n%track%, meow)', 'cats meow', True, cs_01),
      ('$fix_eol(%totaltracks%\ndogs, meow)', '11 meow', True, cs_01),
      ('$fix_eol(cats\ndogs, %totaltracks%)', 'cats 11', False, cs_01),
      ('$fix_eol(a$crlf()b,c,d)', '', False, {}),
      # $hex
      ('$hex()', '', False, {}),
      ('$hex(43)', '', False, {}),  # Probably a bug in FB2k; should be '2B'
      ('$hex(,)', '0', False, {}),
      ('$hex(43,)', '2B', False, {}),
      ('$hex(,3)', '000', False, {}),
      ('$hex(0,)', '0', False, {}),
      ('$hex(-1,)', 'FFFFFFFF', False, {}),
      ('$hex(-2,)', 'FFFFFFFE', False, {}),
      ('$hex(4294967294,)', 'FFFFFFFE', False, {}),
      ('$hex(4294967295,)', 'FFFFFFFF', False, {}),
      ('$hex(4294967296,)', '0', False, {}),
      ('$hex(-4294967295,)', '1', False, {}),
      ('$hex(-4294967296,)', '0', False, {}),
      ('$hex(-4294967297,)', 'FFFFFFFF', False, {}),
      ('$hex(9223372036854775806,)', 'FFFFFFFE', False, {}),
      ('$hex(9223372036854775807,)', 'FFFFFFFF', False, {}),
      ('$hex(9223372036854775808,)', 'FFFFFFFF', False, {}),
      ('$hex(-9223372036854775807,)', '1', False, {}),
      ('$hex(-9223372036854775808,)', '0', False, {}),
      ('$hex(-9223372036854775809,)', '0', False, {}),
      ('$hex(9223372036854775807,31)',
          '00000000000000000000000FFFFFFFF', False, {}),
      ('$hex(9223372036854775807,32)',
          '000000000000000000000000FFFFFFFF', False, {}),
      ('$hex(9223372036854775807,33)',
          '000000000000000000000000FFFFFFFF', False, {}),
      ('$hex(100,%totaltracks%)', '00000000064', False, cs_01),
      ('$hex(%totaltracks%,012)', '00000000000B', True, cs_01),
      ('$hex(0,1,2)', '', False, {}),
    ),
    *_testcasegroup('strings',  # Due to Python limit of 255 arguments
      # $insert
      ('$insert()', '', False, {}),
      ('$insert(a)', '', False, {}),
      ('$insert(a,b)', '', False, {}),
      ('$insert(a,b,)', 'ba', False, {}),
      ('$insert(a,b,1)', 'ab', False, {}),
      ('$insert(a,b,-1)', 'ab', False, {}),
      ('$insert(abc,de,)', 'deabc', False, {}),
      ('$insert(abc,de,-1)', 'abcde', False, {}),
      ('$insert(abc,de,1)', 'adebc', False, {}),
      ('$insert(abc,de,2)', 'abdec', False, {}),
      ('$insert(abc,de,3)', 'abcde', False, {}),
      ('$insert(abc,de,4)', 'abcde', False, {}),
      ('$insert(%title%,CATS,2)', 'ThCATSis', True, cs_01),
      ('$insert(CATS,%title%,%track%)', 'CThisATS', False, cs_01),
      ('$insert(a,b,2,c)', '', False, {}),
    ),
    *_testcasegroup('strings',
      ('$left()', '', False, {}),
      ('$left(a)', '', False, {}),
      ('$left(,)', '', False, {}),
      ('$left(asdf,0)', '', False, {}),
      ('$left(asdf,-1)', 'asdf', False, {}),
      ('$left(asdf,1)', 'a', False, {}),
      ('$left(asdf,2)', 'as', False, {}),
      ('$left(asdf,3)', 'asd', False, {}),
      ('$left(asdf,4)', 'asdf', False, {}),
      ('$left(asdf,5)', 'asdf', False, {}),
      ('$left(%title%,)', '', True, cs_01),
      ('$left(%title%,1)', 'T', True, cs_01),
      ('$left(%title%,2)', 'Th', True, cs_01),
      ('$left(asdf,%track%)', 'a', False, cs_01),
      ('$left(%title%,2,c)', '', False, cs_01),
    ),
    *_testcasegroup('strings',
      ('$len()', '', False, cs_01),
      ('$len(a)', '1', False, cs_01),
      ('$len(0)', '1', False, cs_01),
      ('$len(asdf)', '4', False, cs_01),
      ('$len(12345)', '5', False, cs_01),
      ('$len(%title%)', '4', True, cs_01),
      ('$len(明後日の夢)', '5', False, None),
      ("$len(my 明後日の夢',')", '9', False, None),
      ('$len(ZA̡͊͠͝LGΌ ISͮ̂҉̯͈͕̹̘̱ TO͇̹̺ͅƝ̴ȳ̳ TH̘Ë͖́̉ ͠P̯͍̭O̚​N̐Y̡ H̸̡̪̯ͨ͊̽̅̾̎Ȩ̬̩̾͛ͪ̈́̀́͘ ̶̧̨̱̹̭̯ͧ̾ͬC̷̙̲̝͖ͭ̏ͥͮ͟Oͮ͏̮̪̝͍M̲̖͊̒ͪͩͬ̚̚͜Ȇ̴̟̟͙̞ͩ͌͝S̨̥̫͎̭ͯ̿̔̀ͅ)', '137', False, None),
      ('$len(%track%,0)', '', False, cs_01),
      ('$len2()', '', False, cs_01),
      ('$len2(a)', '1', False, cs_01),
      ('$len2(0)', '1', False, cs_01),
      ('$len2(asdf)', '4', False, cs_01),
      ('$len2(12345)', '5', False, cs_01),
      ('$len2(%title%)', '4', True, cs_01),
      ('$len2(明後日の夢)', '5', False, None),
      ("$len2(my 明後日の夢',')", '9', False, None),
      ('$len2(ZA̡͊͠͝LGΌ ISͮ̂҉̯͈͕̹̘̱ TO͇̹̺ͅƝ̴ȳ̳ TH̘Ë͖́̉ ͠P̯͍̭O̚​N̐Y̡ H̸̡̪̯ͨ͊̽̅̾̎Ȩ̬̩̾͛ͪ̈́̀́͘ ̶̧̨̱̹̭̯ͧ̾ͬC̷̙̲̝͖ͭ̏ͥͮ͟Oͮ͏̮̪̝͍M̲̖͊̒ͪͩͬ̚̚͜Ȇ̴̟̟͙̞ͩ͌͝S̨̥̫͎̭ͯ̿̔̀ͅ)', '137', False, None),
      ('$len2(%track%,0)', '', False, cs_01),
    ),
    *_testcasegroup('strings',
      ('$longer()', '', False, None),
      ('$longer(yes)', '', False, None),
      ('$longer(%track%)', '', False, cs_01),
      ('$longer(yes,)', '', True, None),
      ('$longer(longer,short)', '', True, None),
      ("$longer('short',longer)", '', False, None),
      ('$longer(%track%,long)', '', False, cs_01),
      ('$longer(short,     )', '', False, None),
      ('$longer(yes,no,a)', '', False, None),
      ('$longer(%track%,,)', '', False, cs_01),
    ),
    *_testcasegroup('progress',
      ('$progress()', '', False, None),
      ('$progress( )', '', False, None),
      ('$progress( , )', '', False, None),
      ('$progress( , , )', '', False, None),
      ('$progress( , , , )', '', False, None),
      ('$progress( , , , , )', ' ', False, None),
      ('$progress(0,0,0,#,=)', '#', False, None),
      ('$progress(0,10,10,#,=)', '#=========', False, None),
      ('$progress(1,10,10,#,=)', '=#========', False, None),
      ('$progress(%track%,11,11,#,=)', '=#=========', False, cs_01),
      ('$progress(01,%totaltracks%,11,#,=)', '=#=========', False, cs_01),
      ('$progress(%track%,%totaltracks%,11,#,=)', '=#=========', True, cs_01),
      ('$progress(%track%,11,%totaltracks%,#,=)', '=#=========', False, cs_01),
      ('$progress(01,%ten%,%ten%,#,=)', '=#========', False, fake),
      ('$progress(%two%,%ten%,%ten%,#,=)', '==#=======', True, fake),
      ('$progress(02,10,10,%dash%,%dot%)', '..-.......', False, fake),
      ('$progress(02,10,%ten%,%dash%,%dot%)', '..-.......', False, fake),
      ('$progress(02,%ten%,%ten%,%dash%,%dot%)', '..-.......', False, fake),
      ('$progress(%two%,10,%ten%,%dash%,%dot%)', '..-.......', False, fake),
      ('$progress(%two%,%ten%,%ten%,%dash%,%dot%)', '..-.......', True, fake),
      ('$progress(-1,3,10,!,-)', '!---------', False, None),
      ('$progress( 0,3,10,!,-)', '!---------', False, None),
      ('$progress( 1,3,10,!,-)', '---!------', False, None),
      ('$progress( 2,3,10,!,-)', '-------!--', False, None),
      ('$progress( 3,3,10,!,-)', '---------!', False, None),
      ('$progress( 4,3,10,!,-)', '---------!', False, None),
      ('$progress( 0,0,10,!,-)', '!---------', False, None),
      ('$progress( 1,0,10,!,-)', '---------!', False, None),
      ('$progress(0,-5,10,!,-)', '!---------', False, None),
      ('$progress(1,-5,10,!,-)', '---------!', False, None),
      ('$progress(-1,-5,10,!,-)', '!---------', False, None),
      ('$progress(0,5,0,!,-)', '!', False, None),
      ('$progress(0,5,1,!,-)', '!', False, None),
      ('$progress(1,5,1,!,-)', '!', False, None),
      ('$progress(0,5,2,!,-)', '!-', False, None),
      ('$progress(1,5,2,!,-)', '!-', False, None),
      ('$progress(2,5,2,!,-)', '-!', False, None),
      ('$progress(3,5,2,!,-)', '-!', False, None),
      ('$progress(5,5,2,!,-)', '-!', False, None),
      ('$progress(0,5,3,!,-)', '!--', False, None),
      ('$progress(1,5,3,!,-)', '-!-', False, None),
      ('$progress(2,5,3,!,-)', '-!-', False, None),
      ('$progress(3,5,3,!,-)', '--!', False, None),
      ('$progress(4,5,3,!,-)', '--!', False, None),
      ('$progress(5,5,3,!,-)', '--!', False, None),
      ('$progress( , , , , , )', '', False, None),
      ('$progress2()', '', False, None),
      ('$progress2( )', '', False, None),
      ('$progress2( , )', '', False, None),
      ('$progress2( , , )', '', False, None),
      ('$progress2( , , , )', '', False, None),
      ('$progress2( , , , , )', ' ', False, None),
      ('$progress2(0,0,0,#,=)', '=', False, None),
      ('$progress2(0,10,10,#,=)', '==========', False, None),
      ('$progress2(1,10,10,#,=)', '#=========', False, None),
      ('$progress2(%track%,11,11,#,=)', '#==========', False, cs_01),
      ('$progress2(01,%totaltracks%,11,#,=)', '#==========', False, cs_01),
      ('$progress2(%track%,%totaltracks%,11,#,=)', '#==========', True, cs_01),
      ('$progress2(%track%,11,%totaltracks%,#,=)', '#==========', False, cs_01),
      ('$progress2(01,%ten%,%ten%,#,=)', '#=========', False, fake),
      ('$progress2(%two%,%ten%,%ten%,#,=)', '##========', True, fake),
      ('$progress2(02,10,10,%dash%,%dot%)', '--........', False, fake),
      ('$progress2(02,10,%ten%,%dash%,%dot%)', '--........', False, fake),
      ('$progress2(02,%ten%,%ten%,%dash%,%dot%)', '--........', False, fake),
      ('$progress2(%two%,10,%ten%,%dash%,%dot%)', '--........', False, fake),
      ('$progress2(%two%,%ten%,%ten%,%dash%,%dot%)', '--........', True, fake),
      ('$progress2(-1,3,10,!,-)', '----------', False, None),
      ('$progress2( 0,3,10,!,-)', '----------', False, None),
      ('$progress2( 1,3,10,!,-)', '!!!-------', False, None),
      ('$progress2( 2,3,10,!,-)', '!!!!!!!---', False, None),
      ('$progress2( 3,3,10,!,-)', '!!!!!!!!!!', False, None),
      ('$progress2( 4,3,10,!,-)', '!!!!!!!!!!', False, None),
      ('$progress2( 0,0,10,!,-)', '----------', False, None),
      ('$progress2( 1,0,10,!,-)', '!!!!!!!!!!', False, None),
      ('$progress2(0,-5,10,!,-)', '----------', False, None),
      ('$progress2(1,-5,10,!,-)', '!!!!!!!!!!', False, None),
      ('$progress2(-1,-5,10,!,-)', '----------', False, None),
      ('$progress2(0,5,0,!,-)', '-', False, None),
      ('$progress2(0,5,1,!,-)', '-', False, None),
      ('$progress2(1,5,1,!,-)', '-', False, None),
      ('$progress2(2,5,1,!,-)', '-', False, None),
      ('$progress2(3,5,1,!,-)', '!', False, None),
      ('$progress2(5,5,1,!,-)', '!', False, None),
      ('$progress2(0,5,2,!,-)', '--', False, None),
      ('$progress2(1,5,2,!,-)', '--', False, None),
      ('$progress2(2,5,2,!,-)', '!-', False, None),
      ('$progress2(3,5,2,!,-)', '!-', False, None),
      ('$progress2(4,5,2,!,-)', '!!', False, None),
      ('$progress2(5,5,2,!,-)', '!!', False, None),
      ('$progress2(0,5,3,!,-)', '---', False, None),
      ('$progress2(1,5,3,!,-)', '!--', False, None),
      ('$progress2(2,5,3,!,-)', '!--', False, None),
      ('$progress2(3,5,3,!,-)', '!!-', False, None),
      ('$progress2(4,5,3,!,-)', '!!-', False, None),
      ('$progress2(5,5,3,!,-)', '!!!', False, None),
      ('$progress2( , , , , , )', '', False, None),
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
      fmt = '$%s(%s)' % (fn, testarg)

      if group == 'arithmetic':
        expected = str(resolve_int_var(testarg, cs_01))
        try:
          expected = str(int(expected))
        except ValueError:
          expected = '0'
      elif group == 'boolean':
        expected = ''

      testarg_stripped = testarg.strip('%')
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
        expected = str(int(expected) * -1)
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
          s1 = str(t1)
          literal_s1 = "'" + s1 + "'"
          a1 = t1 if type(t1) is int else resolve_int_var(t1, cs_01)
          a2 = t2 if type(t2) is int else resolve_int_var(t2, cs_01)
          fmt = '$%s(%s,%s)' % (fn, literal_s1, t2)
          expected = '' if group == 'boolean' else str(answer(a1, a2))
          expected_truth = False if fn == 'and' else '%' in str(t2)
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
        val1 = resolve_int_var(t1s, cs_01, stripped=True)
        val2 = resolve_int_var(t2s, cs_01, stripped=True)

        if group == 'arithmetic':
          expected = str(answer(val1, val2))
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
      fmt = '$%s(%s)' % (fn, ','.join(map(str, t)))
      ts = [x for x in
            map(lambda x:
                x.lstrip('% ').replace('2 -9-', '2').rstrip(stripchars),
              map(str, t))]
      vals = [resolve_int_var(x, cs_01, stripped=True) for x in ts]

      if group == 'boolean':
        expected = ''
      else:
        expected = answer(vals[0], vals[1])
        for x in vals[2:]:
          expected = answer(expected, x)
        expected = str(expected)

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
      expected = str(-int(max_expected if fn == 'min' else min_expected))
      fmt = '$%s(%s)' % (fn, ','.join(negated))
      test_eval_cases.append(pytest.param(
        fmt, expected, expected_truth, cs_01,
        id="arithmetic:arity%s('%s' = '%s')" % (arity, fmt, expected)))


# Encoding tests for Unicode; $ansi() and $ascii(), etc. Format is:
# UNICODE_INPUT, ANSI_OUTPUT, ASCII_OUTPUT
encoding_tests = {
    # Latin-1 Supplement
    '00A0-00AF': (' ¡¢£¤¥¦§¨©ª«¬­®¯', ' ¡¢£¤¥¦§¨©ª«¬­®¯', ' !c?$Y|??Ca<?-R?'),
    '00B0-00BF': ('°±²³´µ¶·¸¹º»¼½¾¿', '°±²³´µ¶·¸¹º»¼½¾¿', '??23???.,1o>????'),
    '00C0-00CF': ('ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ', 'ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ', 'AAAAAAACEEEEIIII'),
    '00D0-00DF': ('ÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß', 'ÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß', 'DNOOOOO?OUUUUY??'),
    '00E0-00EF': ('àáâãäåæçèéêëìíîï', 'àáâãäåæçèéêëìíîï', 'aaaaaaaceeeeiiii'),
    '00F0-00FF': ('ðñòóôõö÷øùúûüýþÿ', 'ðñòóôõö÷øùúûüýþÿ', '?nooooo?ouuuuy?y'),
    # Latin Extended-A
    '0100-010F': ('ĀāĂăĄąĆćĈĉĊċČčĎď', 'AaAaAaCcCcCcCcDd', 'AaAaAaCcCcCcCcDd'),
    '0110-011F': ('ĐđĒēĔĕĖėĘęĚěĜĝĞğ', 'ÐdEeEeEeEeEeGgGg', 'DdEeEeEeEeEeGgGg'),
    '0120-012F': ('ĠġĢģĤĥĦħĨĩĪīĬĭĮį', 'GgGgHhHhIiIiIiIi', 'GgGgHhHhIiIiIiIi'),
    '0130-013F': ('İıĲĳĴĵĶķĸĹĺĻļĽľĿ', 'Ii??JjKk?LlLlLl?', 'Ii??JjKk?LlLlLl?'),
    '0140-014F': ('ŀŁłŃńŅņŇňŉŊŋŌōŎŏ', '?LlNnNnNn???OoOo', '?LlNnNnNn???OoOo'),
    '0150-015F': ('ŐőŒœŔŕŖŗŘřŚśŜŝŞş', 'OoŒœRrRrRrSsSsSs', 'OoOoRrRrRrSsSsSs'),
    '0160-016F': ('ŠšŢţŤťŦŧŨũŪūŬŭŮů', 'ŠšTtTtTtUuUuUuUu', 'SsTtTtTtUuUuUuUu'),
    '0170-017F': ('ŰűŲųŴŵŶŷŸŹźŻżŽžſ', 'UuUuWwYyŸZzZzŽž?', 'UuUuWwYyYZzZzZz?'),
    # Latin Extended-B
    '0180-018F': ('ƀƁƂƃƄƅƆƇƈƉƊƋƌƍƎƏ', 'b????????Ð??????', 'b????????D??????'),
    '0190-019F': ('ƐƑƒƓƔƕƖƗƘƙƚƛƜƝƞƟ', '?ƒƒ????I??l????O', '?Ff????I??l????O'),
    '01A0-01AF': ('ƠơƢƣƤƥƦƧƨƩƪƫƬƭƮƯ', 'Oo?????????t??TU', 'Oo?????????t??TU'),
    '01B0-01BF': ('ưƱƲƳƴƵƶƷƸƹƺƻƼƽƾƿ', 'u?????z?????????', 'u?????z?????????'),
    '01C0-01CF': ('ǀǁǂǃǄǅǆǇǈǉǊǋǌǍǎǏ', '|??!?????????AaI', '?????????????AaI'),
    '01D0-01DF': ('ǐǑǒǓǔǕǖǗǘǙǚǛǜǝǞǟ', 'iOoUuUuUuUuUu?Aa', 'iOoUuUuUuUuUu?Aa'),
    '01E0-01EF': ('ǠǡǢǣǤǥǦǧǨǩǪǫǬǭǮǯ', '????GgGgKkOoOo??', '????GgGgKkOoOo??'),
    '01F0-01FF': ('ǰǱǲǳǴǵǶǷǸǹǺǻǼǽǾǿ', 'j???????????????', 'j???????????????'),
    '0200-020F': ('ȀȁȂȃȄȅȆȇȈȉȊȋȌȍȎȏ', '????????????????', '????????????????'),
    '0210-021F': ('ȐȑȒȓȔȕȖȗȘșȚțȜȝȞȟ', '????????????????', '????????????????'),
    '0220-022F': ('ȠȡȢȣȤȥȦȧȨȩȪȫȬȭȮȯ', '????????????????', '????????????????'),
    '0230-023F': ('ȰȱȲȳȴȵȶȷȸȹȺȻȼȽȾȿ', '????????????????', '????????????????'),
    '0240-024F': ('ɀɁɂɃɄɅɆɇɈɉɊɋɌɍɎɏ', '????????????????', '????????????????'),
    # General Punctuation
    '2000-200F': ('           ​‌‍‎‏',
                  '       ?????????',
                  '       ?????????'),
    '2010-201F': ('‐‑‒–—―‖‗‘’‚‛“”„‟',
                  '--?–—??=‘’‚?“”„?',
                  '--?--???\'\',?"""?'),
    '2020-202F': ('†‡•‣․‥…‧  ‪‫‬‭‮ ',
                  '†‡•?·?…?????????',
                  '??.???.?????????'),
    '2030-203F': ('‰‱′″‴‵‶‷‸‹›※‼‽‾‿',
                  '‰?\'??`???‹›?????',
                  '??\'??`???<>?????'),
    '2040-204F': ('⁀⁁⁂⁃⁄⁅⁆⁇⁈⁉⁊⁋⁌⁍⁎⁏',
                  '????/???????????',
                  '????????????????'),
    '2050-205F': ('⁐⁑⁒⁓⁔⁕⁖⁗⁘⁙⁚⁛⁜⁝⁞ ',
                  '????????????????',
                  '????????????????'),
    '2060-206F': ('⁠⁡⁢⁣⁤⁦⁧⁨⁩⁪⁫⁬⁭⁮⁯',
                  '???????????????',
                  '???????????????'),
}


atoms = [
    False, True, None, '', 'nonempty',
    EvaluatorAtom(None),
    EvaluatorAtom(None, True),
    EvaluatorAtom(''),
    EvaluatorAtom('', True),
    EvaluatorAtom('nonempty'),
    EvaluatorAtom('nonempty', True),
    EvaluatorAtom(0),
    EvaluatorAtom(0, True),
    EvaluatorAtom(123),
    EvaluatorAtom(123, True),
]

atoms = [*atoms, *map(lambda x: lambda: x, atoms)]

bool_atoms = [*zip(atoms, [
    False, True, False, False, False,
    False, True, False, True, False, True, False, True, False, True,
  ] * 2)]

str_atoms = [*zip(atoms, [
    EvaluatorAtom(None, False),
    EvaluatorAtom(None, True),
    EvaluatorAtom(None, False),
    EvaluatorAtom('', False),
    EvaluatorAtom('nonempty', False),
    EvaluatorAtom(None, False),
    EvaluatorAtom(None, True),
    EvaluatorAtom('', False),
    EvaluatorAtom('', True),
    EvaluatorAtom('nonempty', False),
    EvaluatorAtom('nonempty', True),
    EvaluatorAtom(0, False),
    EvaluatorAtom(0, True),
    EvaluatorAtom(123, False),
    EvaluatorAtom(123, True),
  ] * 2)]


@pytest.mark.api
class TestTitleformat_APITests:
  @pytest.mark.parametrize('cond,atomized_cond', bool_atoms)
  @pytest.mark.parametrize('then_case,atomized_then_case', str_atoms)
  def test_foo_if__2(self, cond, atomized_cond, then_case, atomized_then_case):
    if callable(cond): print(f'cond = lambda -> {repr(cond())}')
    else: print(f'cond = {repr(cond)}')
    if callable(then_case): print(f'then = lambda -> {repr(then_case)}')
    else: print(f'then = {repr(then_case)}')

    result_atom = titleformat.foo_if__2(cond, then_case)
    assert result_atom == (atomized_then_case if atomized_cond else None)


@pytest.mark.known
class TestTitleformat_KnownValues:
  @pytest.mark.parametrize('compiled', [
    pytest.param(False, id='interpreted'),
    pytest.param(True, id='compiled'),
  ])
  @pytest.mark.parametrize('fmt,expected,expected_truth,track', test_eval_cases)
  def test_eval(self, fmt, expected, expected_truth, track, compiled):
    if compiled:
      result = titleformat.compile(fmt)(track)
    else:
      result = titleformat.format(fmt, track)

    assert result.value == expected
    assert result.truth is expected_truth

  @pytest.mark.parametrize('block', encoding_tests.keys())
  def test_eval_ansi_encoding(self, block):
    unicode_input, expected_ansi, _ = encoding_tests[block]

    result_ansi = titleformat.format(f"$ansi('{unicode_input}')", None)

    assert result_ansi.value == expected_ansi
    assert not result_ansi.truth

  @pytest.mark.parametrize('block', encoding_tests.keys())
  def test_eval_ascii_encoding(self, block):
    unicode_input, _, expected_ascii = encoding_tests[block]

    result_ascii= titleformat.format(f"$ascii('{unicode_input}')", None)

    assert result_ascii.value == expected_ascii
    assert not result_ascii.truth


def run_tests():
  ttf = TestTitleformat_KnownValues()
  for t in test_eval_cases:
    ttf.test_eval(*t.values, 0)
    ttf.test_eval(*t.values, 1)
  for e in encoding_tests.keys():
    ttf.test_eval_ansi_encoding(e)
    ttf.test_eval_ascii_encoding(e)


if __name__ == '__main__':
  run_tests()
