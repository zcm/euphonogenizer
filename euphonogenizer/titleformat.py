#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from __future__ import unicode_literals

from functools import reduce

import binascii
import codecs
import itertools
import os
import platform
import random
import re
import six
import sys
import unicodedata

from .common import dbg, unistr


class EvaluatorAtom:
  def __init__(self, string_value, truth_value):
    self.string_value = string_value
    self.truth_value = truth_value

  def __add__(self, other):
    return EvaluatorAtom(
        self.string_value + other.string_value,
        self.truth_value or other.truth_value)

  def __iadd__(self, other):
    self.string_value += other.string_value
    self.truth_value |= other.truth_value
    return self

  def __sub__(self, other):
    return EvaluatorAtom(
        self.string_value - other.string_value,
        self.truth_value or other.truth_value)

  def __isub__(self, other):
    self.string_value -= other.string_value
    self.truth_value |= other.truth_value
    return self

  def __mul__(self, other):
    return EvaluatorAtom(
        self.string_value * other.string_value,
        self.truth_value or other.truth_value)

  def __imul__(self, other):
    self.string_value *= other.string_value
    self.truth_value |= other.truth_value
    return self

  def __foo_div_logic(self, x, y):
    if y == 0:
      # Foobar skips division for zeros instead of exploding.
      return x
    # For some reason, Foobar rounds up when negative and down when positive.
    if x * y < 0:
      return x * -1 // y * -1
    return x // y

  def __floordiv__(self, other):
    return EvaluatorAtom(
        self.__foo_div_logic(self.string_value, other.string_value),
        self.truth_value or other.truth_value)

  def __ifloordiv__(self, other):
    self.string_value = self.__foo_div_logic(
        self.string_value, other.string_value)
    self.truth_value |= other.truth_value
    return self

  def __foo_mod_logic(self, x, y):
    if x == 0:
      return 0
    if y == 0:
      return x
    return x % y

  def __mod__(self, other):
    return EvaluatorAtom(
        self.__foo_mod_logic(self.string_value, other.string_value),
        self.truth_value or other.truth_value)

  def __imod__(self, other):
    self.string_value = self.__foo_mod_logic(
        self.string_value, other.string_value)
    self.truth_value |= other.truth_value
    return self

  def __eq__(self, other):
    if (isinstance(other, EvaluatorAtom)):
      return (self.string_value == other.string_value
          and self.truth_value is other.truth_value)
    return NotImplemented

  def __ne__(self, other):
    e = self.__eq__(other)
    return NotImplemented if e is NotImplemented else not e

  def __gt__(self, other):
    return self.string_value > other.string_value

  def __lt__(self, other):
    return self.string_value < other.string_value

  def __and__(self, other):
    return self.truth_value and other.truth_value

  def __iand__(self, other):
    self.truth_value &= other.truth_value
    return self

  def __or__(self, other):
    return self.truth_value or other.truth_value

  def __ior__(self, other):
    self.truth_value |= other.truth_value
    return self

  def __hash__(self):
    return hash(tuple(sorted(self.__dict__.items())))

  def __str__(self):
    return str(self.string_value)

  def __unicode__(self):
    return unistr(self.string_value)

  def __nonzero__(self):
    return self.truth_value

  def __bool__(self):
    return self.truth_value

  def __len__(self):
    return len(str(self.string_value))

  def __repr__(self):
    return 'atom(%s, %s)' % (repr(self.string_value), self.truth_value)

  def eval(self):
    # Evaluating an expression that's already been evaluated returns itself.
    return self


def magic_map_filename(formatter, track):
  value = track.get('@')
  if value is not None and value is not False:
    return unistr(foo_filename(None, None, [value]))
  return None

def magic_map_filename_ext(formatter, track):
  value = track.get('@')
  if value is not None and value is not False:
    filename = unistr(foo_filename(None, None, [value]))
    ext = unistr(foo_ext(None, None, [value]))
    if ext:
      filename += '.' + ext
    return filename
  return None

def magic_map_track_artist(formatter, track):
  artist = formatter.magic_resolve_variable(track, 'artist')
  album_artist = formatter.magic_resolve_variable(track, 'album artist')
  if artist != album_artist:
    return artist
  return None

def __find_tracknumber(track):
  value = track.get('TRACKNUMBER')
  if (value is None or value is False) and 'TRACK' in track:
    # This is undocumented behavior. Foobar will fall back to a freeform TRACK
    # field if it's present and TRACKNUMBER is missing.
    return track.get('TRACK')
  return value

def magic_map_tracknumber(formatter, track):
  value = __find_tracknumber(track)
  if value is not None and value is not False:
    return value.zfill(2)
  return None

def magic_map_track_number(formatter, track):
  value = __find_tracknumber(track)
  if value is not None and value is not False:
    return unistr(int(value))
  return None


magic_mappings = {
    'album artist': ['ALBUM ARTIST', 'ARTIST', 'COMPOSER', 'PERFORMER'],
    'album': ['ALBUM', 'VENUE'],
    'artist': ['ARTIST', 'ALBUM ARTIST', 'COMPOSER', 'PERFORMER'],
    'discnumber': ['DISCNUMBER', 'DISC'],
    'filename': magic_map_filename,
    'filename_ext': magic_map_filename_ext,
    'track artist': magic_map_track_artist,
    'title': ['TITLE', '@'],
    # %track% is undocumented, even on HydrogenAudio when I wrote this.
    'track': magic_map_tracknumber,
    'tracknumber': magic_map_tracknumber,
    'track number': magic_map_track_number,
    '_date_': ['DATE'],
}

def __foo_bool(b):
  if b:
    return True
  return False

def __foo_int(n):
  # Note that this "string value" might actually already be an int, in which
  # case, this function simply ends up stripping the atom wrapper.
  try:
    if n is not None and n != '':
      return int(n.string_value)
  except AttributeError:
    try:
      return int(n)
    except ValueError:
      return 0
  return 0

def __foo_va_conv_n_unsafe(n):
  strval = ''
  truth = False

  integer_value = 0

  try:
    strval = n.string_value.strip()
    truth = n.truth_value
  except AttributeError:
    strval = n
    try:
      strval = strval.strip()
    except AttributeError:
      pass

  if strval:
    try:
      integer_value = int(strval)
    except ValueError:
      start = 1 if strval[0] == '-' else 0
      last_found_number = -1
      try:
        for i in range(start, len(strval)):
          if int(strval[i]) >= 0:
            last_found_number = i
      except ValueError:
        if last_found_number >= 0:
          integer_value = int(strval[0:last_found_number+1])

  return EvaluatorAtom(integer_value, truth)

def __foo_va_conv_n(n):
  try:
    return __foo_va_conv_n_unsafe(n)
  except ValueError:
    pass
  except KeyError:
    pass

  try:
    return EvaluatorAtom(0, n.truth_value)
  except AttributeError:
    pass

  return EvaluatorAtom(0, False)

def __foo_va_conv_n_lazy(n):
  return __foo_va_conv_n(n.eval())

def __foo_va_conv_bool_lazy(b):
  try:
    value = b.eval()
    try:
      return value.truth_value
    except AttributeError:
      return value
  except AttributeError:
    if b:
      return True
  return False

def __foo_va_conv_n_lazy_int(n):
  return __foo_int(__foo_va_conv_n_lazy(n))

def __foo_va_lazy(x):
  return x.eval()

def __foo_is_word_sep(c):
  return c in ' /\\()[]'

def foo_true(track, memory, va):
  return True

def foo_false(track, memory, va):
  pass

def foo_zero(track, memory, va):
  return '0'

def foo_one(track, memory, va):
  return '1'

def foo_nop(track, memory, va):
  return va[0].eval()

def foo_unknown(track, memory, va):
  return '[UNKNOWN FUNCTION]'

nnop_known_table = {
    '' : '0',
    '-' : '0',
    '-0' : '0',
}

def foo_nnop(track, memory, va):
  val = va[0].eval()

  try:
    try:
      val.string_value = nnop_known_table[val.string_value]
      return val
    except KeyError:
      pass

    val = __foo_va_conv_n_unsafe(val)
    val.string_value = unistr(val.string_value)
    return val
  except AttributeError:
    pass
  except ValueError:
    pass
  except KeyError:
    pass

  return '0'

def foo_bnop(track, memory, va):
  return __foo_va_conv_bool_lazy(va[0])

def foo_invalid(fn):
  return lambda *args, x='[INVALID $%s SYNTAX]' % fn.upper(): x

def foo_if_arity2(track, memory, va_cond_then):
  if va_cond_then[0].eval():
    return va_cond_then[1].eval()

def foo_if_arity3(track, memory, va_cond_then_else):
  if va_cond_then_else[0].eval():
    return va_cond_then_else[1].eval()
  return va_cond_then_else[2].eval()

def foo_if2(track, memory, va_a_else):
  return va_a_else[0].eval() if va_a_else[0].eval() else va_a_else[1].eval()

def foo_if3(track, memory, va_a1_a2_aN_else):
  for i in range(0, len(va_a1_a2_aN_else) - 1):
    if va_a1_a2_aN_else[i].eval():
      return va_a1_a2_aN_else[i].eval()
  return va_a1_a2_aN_else[-1].eval()

def foo_ifequal(track, memory, va_n1_n2_then_else):
  n1 = __foo_va_conv_n_lazy_int(va_n1_n2_then_else[0])
  n2 = __foo_va_conv_n_lazy_int(va_n1_n2_then_else[1])
  if n1 == n2:
    return va_n1_n2_then_else[2].eval()
  return va_n1_n2_then_else[3].eval()

def foo_ifgreater(track, memory, va_n1_n2_then_else):
  n1 = __foo_va_conv_n_lazy_int(va_n1_n2_then_else[0])
  n2 = __foo_va_conv_n_lazy_int(va_n1_n2_then_else[1])
  if n1 > n2:
    return va_n1_n2_then_else[2].eval()
  return va_n1_n2_then_else[3].eval()

def foo_iflonger(track, memory, va_s_n_then_else):
  n = __foo_va_conv_n_lazy_int(va_s_n_then_else[1])
  if len(va_s_n_then_else[0].eval()) > n:
    return va_s_n_then_else[2].eval()
  return va_s_n_then_else[3].eval()

def foo_select(track, memory, va_n_a1_aN):
  n = __foo_va_conv_n_lazy_int(va_n_a1_aN[0])
  if n > 0 and n <= len(va_n_a1_aN) - 1:
    return va_n_a1_aN[n].eval()

def foo_select2(track, memory, va_n_a1_a2):
  if __foo_va_conv_n_lazy_int(va_n_a1_a2[0]) == 1:
    return va_n_a1_a2[1].eval()

def foo_add(track, memory, va_aN):
  value = __foo_va_conv_n_lazy(va_aN[0])
  for a in va_aN[1:]:
    value += __foo_va_conv_n_lazy(a)
  return value

def foo_div(track, memory, va_aN):
  value = __foo_va_conv_n_lazy(va_aN[0])
  for a in va_aN[1:]:
    value //= __foo_va_conv_n_lazy(a)
  return value

def foo_greater(track, memory, va_a_b):
  a = __foo_va_conv_n_lazy_int(va_a_b[0])
  b = __foo_va_conv_n_lazy_int(va_a_b[1])
  if a > b:
    return True
  return False

def __foo_max_logic(a, b):
  if a > b:
    a |= b
    return a
  b |= a
  return b

def foo_max(track, memory, va_a_b):
  return __foo_max_logic(*map(__foo_va_conv_n_lazy, va_a_b))

def foo_maxN(track, memory, va_aN):
  return reduce(__foo_max_logic, map(__foo_va_conv_n_lazy, va_aN))

def __foo_min_logic(a, b):
  if a < b:
    a |= b
    return a
  b |= a
  return b

def foo_min(track, memory, va_a_b):
  return __foo_min_logic(*map(__foo_va_conv_n_lazy, va_a_b))

def foo_minN(track, memory, va_aN):
  return reduce(__foo_min_logic, map(__foo_va_conv_n_lazy, va_aN))

def foo_mod(track, memory, va_a_b):
  a = __foo_va_conv_n_lazy(va_a_b[0])
  b = __foo_va_conv_n_lazy(va_a_b[1])
  a %= b
  return a

def foo_modN(track, memory, va_aN):
  value = __foo_va_conv_n_lazy(va_aN[0])
  for a in va_aN[1:]:
    value %= __foo_va_conv_n_lazy(a)
  return value

def foo_mul(track, memory, va_aN):
  value = __foo_va_conv_n_lazy(va_aN[0])
  for a in va_aN[1:]:
    value *= __foo_va_conv_n_lazy(a)
  return value

def foo_muldiv(track, memory, va_a_b_c):
  c = __foo_va_conv_n_lazy(va_a_b_c[2])
  c.truth_value = True  # Truth behavior confirmed by experimentation.
  if c.string_value == 0:
    # This is real Foobar behavior for some reason, probably a bug.
    c.string_value = -1
    return c
  a = __foo_va_conv_n_lazy(va_a_b_c[0])
  a *= __foo_va_conv_n_lazy(va_a_b_c[1])
  a //= c
  return a

def foo_rand(track, memory, va):
  random.seed()
  return random.randint(0, sys.maxint)

def foo_sub(track, memory, va_aN):
  value = __foo_va_conv_n_lazy(va_aN[0])
  for a in va_aN[1:]:
    value -= __foo_va_conv_n_lazy(a)
  return value

def foo_and(track, memory, va_N):
  for each in va_N:
    if not __foo_va_conv_bool_lazy(each):
      return False
  return True

def foo_or(track, memory, va_N):
  for each in va_N:
    if __foo_va_conv_bool_lazy(each):
      return True
  return False

def foo_not(track, memory, va_x):
  return not __foo_va_conv_bool_lazy(va_x[0])

def foo_xor(track, memory, va_N):
  r = False
  for each in va_N:
    r ^= __foo_va_conv_bool_lazy(each)
  return r

__foo_abbr_charstrip = re.compile('[()/\\\\,]')

def foo_abbr(string_value):
  parts = __foo_abbr_charstrip.sub(' ', string_value).split(' ')
  abbr = ''
  for each in parts:
    if len(each):
      if each.isnumeric():
        abbr += each
      else:
        if each[0] in ('[]'):
          abbr += each
        else:
          abbr += each[0]
  return abbr

def foo_abbr1(track, memory, va_x):
  x = va_x[0].eval()
  x.string_value = foo_abbr(str(x))
  return x

def foo_abbr2(track, memory, va_x_len):
  x = va_x_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_x_len[1])
  sx = str(x)
  if len(sx) > length:
    x.string_value = foo_abbr(sx)
  return x


__foo_ascii_charmap = {
    # Latin-1 Supplement
    '¡':'!', '¢':'c', '¤':'$', '¥':'Y', '¦':'|', '©':'C', 'ª':'a', '«':'<',
    '­':'-', '®':'R', '²':'2', '³':'3', '·':'.', '¸':',', '¹':'1', 'º':'o',
    '»':'>', 'À':'A', 'Á':'A', 'Â':'A', 'Ã':'A', 'Ä':'A', 'Å':'A', 'Æ':'A',
    'Ç':'C', 'È':'E', 'É':'E', 'Ê':'E', 'Ë':'E', 'Ì':'I', 'Í':'I', 'Î':'I',
    'Ï':'I', 'Ð':'D', 'Ñ':'N', 'Ò':'O', 'Ó':'O', 'Ô':'O', 'Õ':'O', 'Ö':'O',
    'Ø':'O', 'Ù':'U', 'Ú':'U', 'Û':'U', 'Ü':'U', 'Ý':'Y', 'à':'a', 'á':'a',
    'â':'a', 'ã':'a', 'ä':'a', 'å':'a', 'æ':'a', 'ç':'c', 'è':'e', 'é':'e',
    'ê':'e', 'ë':'e', 'ì':'i', 'í':'i', 'î':'i', 'ï':'i', 'ñ':'n', 'ò':'o',
    'ó':'o', 'ô':'o', 'õ':'o', 'ö':'o', 'ø':'o', 'ù':'u', 'ú':'u', 'û':'u',
    'ü':'u', 'ý':'y', 'þ':'?', 'ÿ':'y',
    # Latin Extended-A
    'Ā':'A', 'ā':'a', 'Ă':'A', 'ă':'a', 'Ą':'A', 'ą':'a', 'Ć':'C', 'ć':'c',
    'Ĉ':'C', 'ĉ':'c', 'Ċ':'C', 'ċ':'c', 'Č':'C', 'č':'c', 'Ď':'D', 'ď':'d',
    'Đ':'D', 'đ':'d', 'Ē':'E', 'ē':'e', 'Ĕ':'E', 'ĕ':'e', 'Ė':'E', 'ė':'e',
    'Ę':'E', 'ę':'e', 'Ě':'E', 'ě':'e', 'Ĝ':'G', 'ĝ':'g', 'Ğ':'G', 'ğ':'g',
    'Ġ':'G', 'ġ':'g', 'Ģ':'G', 'ģ':'g', 'Ĥ':'H', 'ĥ':'h', 'Ħ':'H', 'ħ':'h',
    'Ĩ':'I', 'ĩ':'i', 'Ī':'I', 'ī':'i', 'Ĭ':'I', 'ĭ':'i', 'Į':'I', 'į':'i',
    'İ':'I', 'ı':'i', 'Ĵ':'J', 'ĵ':'j', 'Ķ':'K', 'ķ':'k', 'Ĺ':'L', 'ĺ':'l',
    'Ļ':'L', 'ļ':'l', 'Ľ':'L', 'ľ':'l', 'Ł':'L', 'ł':'l', 'Ń':'N', 'ń':'n',
    'Ņ':'N', 'ņ':'n', 'Ň':'N', 'ň':'n', 'Ō':'O', 'ō':'o', 'Ŏ':'O', 'ŏ':'o',
    'Ő':'O', 'ő':'o', 'Œ':'O', 'œ':'o', 'Ŕ':'R', 'ŕ':'r', 'Ŗ':'R', 'ŗ':'r',
    'Ř':'R', 'ř':'r', 'Ś':'S', 'ś':'s', 'Ŝ':'S', 'ŝ':'s', 'Ş':'S', 'ş':'s',
    'Š':'S', 'š':'s', 'Ţ':'T', 'ţ':'t', 'Ť':'T', 'ť':'t', 'Ŧ':'T', 'ŧ':'t',
    'Ũ':'U', 'ũ':'u', 'Ū':'U', 'ū':'u', 'Ŭ':'U', 'ŭ':'u', 'Ů':'U', 'ů':'u',
    'Ű':'U', 'ű':'u', 'Ų':'U', 'ų':'u', 'Ŵ':'W', 'ŵ':'w', 'Ŷ':'Y', 'ŷ':'y',
    'Ÿ':'Y', 'Ź':'Z', 'ź':'z', 'Ż':'Z', 'ż':'z', 'Ž':'Z', 'ž':'z',
    # Latin Extended-B
    'ƀ':'b', 'Ɖ':'D', 'Ƒ':'F', 'ƒ':'f', 'Ɨ':'I', 'ƚ':'l', 'Ɵ':'O', 'Ơ':'O',
    'ơ':'o', 'ƫ':'t', 'Ʈ':'T', 'Ư':'U', 'ư':'u', 'ƶ':'z', 'Ǎ':'A', 'ǎ':'a',
    'Ǐ':'I', 'ǐ':'i', 'Ǒ':'O', 'ǒ':'o', 'Ǔ':'U', 'ǔ':'u', 'Ǖ':'U', 'ǖ':'u',
    'Ǘ':'U', 'ǘ':'u', 'Ǚ':'U', 'ǚ':'u', 'Ǜ':'U', 'ǜ':'u', 'Ǟ':'A', 'ǟ':'a',
    'Ǥ':'G', 'ǥ':'g', 'Ǧ':'G', 'ǧ':'g', 'Ǩ':'K', 'ǩ':'k', 'Ǫ':'O', 'ǫ':'o',
    'Ǭ':'O', 'ǭ':'o', 'ǰ':'j',
    # General Punctuation
    '\u2000':' ', '\u2001':' ', '\u2002':' ', '\u2003':' ', '\u2004':' ',
    '\u2005':' ', '\u2006':' ',
    '‐':'-', '‑':'-', '–':'-', '—':'-', '‘':"'", '’':"'", '‚':',', '“':'"',
    '”':'"', '„':'"', '•':'.', '…':'.', '′':"'", '‵':'`', '‹':'<', '›':'>',
}

__foo_ansi_charmap = {
    'Đ':'Ð', 'Ɖ':'Ð', 'Ƒ':'ƒ', 'ǀ':'|', 'ǃ':'!', '‗':'=', '․':'·', '⁄':'/',
}


def __foo_ansi_replace(exc):
  if isinstance(exc, UnicodeEncodeError):
    s = ''
    for c in exc.object[exc.start:exc.end]:
      try:
        s += __foo_ansi_charmap[c]
      except KeyError:
        try:
          s += __foo_ascii_charmap[c]
        except KeyError:
          s += '?'
    return (s, exc.end)
  return codecs.replace_error(exc)

def __foo_ascii_replace(exc):
  if isinstance(exc, UnicodeEncodeError):
    s = ''
    for c in exc.object[exc.start:exc.end]:
      s += '?' if c not in __foo_ascii_charmap else __foo_ascii_charmap[c]
    return (s, exc.end)
  return codecs.replace_error(exc)


codecs.register_error('__foo_ansi_replace', __foo_ansi_replace)
codecs.register_error('__foo_ascii_replace', __foo_ascii_replace)


def foo_ansi(track, memory, va_x):
  x = va_x[0].eval()
  # Doing the conversion this way will probably not produce the same output with
  # wide characters as Foobar, which produces two '??' instead of one. I don't
  # have a multibyte build of Python lying around right now, so I can't
  # confirm at the moment. But really, it probably doesn't matter.
  result = unistr(x).encode('windows-1252', '__foo_ansi_replace')
  return EvaluatorAtom(str(result, 'windows-1252', 'replace'), __foo_bool(x))

def foo_ascii(track, memory, va_x):
  x = va_x[0].eval()
  result = unistr(x).encode('ascii', '__foo_ascii_replace')
  return EvaluatorAtom(result.decode('utf-8', 'replace'), __foo_bool(x))

def foo_caps_impl(va_x, on_nonfirst):
  x = va_x[0].eval()
  result = ''
  new_word = True
  for c in unistr(x):
    if __foo_is_word_sep(c):
      new_word = True
      result += c
    else:
      if new_word:
        result += c.upper()
        new_word = False
      else:
        result += on_nonfirst(c)
  return EvaluatorAtom(result, __foo_bool(x))

def foo_caps(track, memory, va_x):
  return foo_caps_impl(va_x, on_nonfirst=lambda c: c.lower())

def foo_caps2(track, memory, va_x):
  return foo_caps_impl(va_x, on_nonfirst=lambda c: c)

def foo_char(track, memory, va_x):
  x = __foo_va_conv_n_lazy_int(va_x[0])
  if x <= 0:
    return ''
  if x > 1048575:
    # FB2k only supports doing this with 20-bit integers for some reason.
    # In the future, we might want a better, non-compliant implementation.
    return '?'
  try:
    return six.unichr(x)
  except ValueError:
    # Also happens when using a narrow Python build
    return '?'
  except OverflowError:
    return ''

def foo_crc32(track, memory, va_x):
  x = va_x[0].eval()
  crc = binascii.crc32(unistr(x))
  return EvaluatorAtom(crc, __foo_bool(x))

def foo_crlf(track, memory, va):
  return '\r\n'

def foo_cut(track, memory, va_a_len):
  return foo_left(track, memory, va_a_len)

def foo_directory_arity1(track, memory, va_x):
  x = va_x[0].eval()
  parts = re.split('[\\\\/:|]', unistr(x))
  if len(parts) < 2:
    return EvaluatorAtom('', __foo_bool(x))
  return EvaluatorAtom(parts[-2], __foo_bool(x))

def foo_directory_arity2(track, memory, va_x_n):
  x = va_x_n[0].eval()
  n = __foo_va_conv_n_lazy_int(va_x_n[1])
  if n <= 0:
    return EvaluatorAtom('', __foo_bool(x))
  parts = re.split('[\\\\/:|]', unistr(x))
  parts_len = len(parts)
  if n >= parts_len or parts_len < 2:
    return EvaluatorAtom('', __foo_bool(x))
  return EvaluatorAtom(parts[parts_len - n - 1], __foo_bool(x))

def foo_directory_path(track, memory, va_x):
  x = va_x[0].eval()
  parts = re.split('[\\\\/:|]', unistr(x)[::-1], 1)
  if len(parts) < 2:
    return EvaluatorAtom('', __foo_bool(x))
  return EvaluatorAtom(parts[1][::-1], __foo_bool(x))

def foo_ext(track, memory, va_x):
  x = va_x[0]

  try:
    x = x.eval()
  except AttributeError:
    pass

  ext = unistr(x).split('.')[-1]
  for c in ext:
    if c in '/\\|:':
      return EvaluatorAtom('', __foo_bool(x))
  return EvaluatorAtom(ext.split('?')[0], __foo_bool(x))

def foo_filename(track, memory, va_x):
  x = va_x[0]

  try:
    x = x.eval()
  except AttributeError:
    pass

  x_str = unistr(x)
  parts = re.split('[\\\\/:|]', x_str)
  parts_len = len(parts)
  if parts_len <= 0:
    return EvaluatorAtom('', __foo_bool(x))
  filename = x_str
  if parts_len >= 2:
    filename = parts[-1]
  return EvaluatorAtom(filename[::-1].split('.', 1)[-1][::-1], __foo_bool(x))

def foo_fix_eol_arity1(track, memory, va_x):
  return foo_fix_eol_arity2(track, memory, va_x + [' (...)'])

def foo_fix_eol_arity2(track, memory, va_x_indicator):
  x = va_x_indicator[0].eval()
  indicator = va_x_indicator[1]

  try:
    indicator = unistr(indicator.eval())
  except AttributeError:
    pass

  result = unistr(x).split('\r\n')[0].split('\n')[0]

  return EvaluatorAtom(result + indicator, __foo_bool(x))

def foo_hex_arity1(track, memory, va_n):
  return foo_hex_arity2(track, memory, [va_n[0], 0])

def foo_hex_arity2(track, memory, va_n_len):
  n = __foo_va_conv_n_lazy_int(va_n_len[0])
  length = __foo_va_conv_n_lazy_int(va_n_len[1])
  if length < 0:
    length = 0
  value = None
  if n < 0:
    value = hex(((abs(n) ^ 0xFFFFFFFF) + 1) & 0xFFFFFFFF)
  elif n > 2**63-1:
    value = '0xFFFFFFFF'
  else:
    value = hex(n)
  hex_value = value.split('L')[0][2:]
  if len(hex_value) > 8:
    hex_value = hex_value[-8:]
  return hex_value.upper().zfill(length)

def foo_insert(track, memory, va_a_b_n):
  a = va_a_b_n[0].eval()
  a_str = unistr(a)
  b = va_a_b_n[1].eval()
  b_str = unistr(b)
  n = __foo_va_conv_n_lazy_int(va_a_b_n[2])
  return EvaluatorAtom(a_str[0:n] + b_str + a_str[n:], __foo_bool(a))

def foo_left(track, memory, va_a_len):
  a = va_a_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_a_len[1])
  a_str = unistr(a)
  a_len = len(a_str)
  if length < 0 or a_len == 0 or length >= a_len:
    return a
  elif length == 0:
    return EvaluatorAtom('', __foo_bool(a))
  return EvaluatorAtom(a_str[0:length], __foo_bool(a))

def foo_len(track, memory, va_a):
  a = va_a[0].eval()
  return EvaluatorAtom(len(unistr(a)), __foo_bool(a))

def foo_len2(track, memory, va_a):
  a = va_a[0].eval()
  length = 0
  str_a = unistr(a)
  for c in str_a:
    width = unicodedata.east_asian_width(c)
    if width == 'N' or width == 'Na' or width == 'H':
      # Narrow / Halfwidth character
      length += 1
    elif width == 'W' or width == 'F' or width == 'A':
      # Wide / Fullwidth / Ambiguous character
      length += 2
  return EvaluatorAtom(length, __foo_bool(a))

def foo_longer(track, memory, va_a_b):
  len_a = len(unistr(va_a_b[0].eval()))
  len_b = len(unistr(va_a_b[1].eval()))
  return len_a > len_b

def foo_lower(track, memory, va_a):
  a = va_a[0].eval()
  return EvaluatorAtom(unistr(a).lower(), __foo_bool(a))

def foo_longest(track, memory, va_a1_aN):
  longest = None
  longest_len = -1
  for each in va_a1_aN:
    current = each.eval()
    current_len = len(unistr(current))
    if current_len > longest_len:
      longest = current
      longest_len = current_len
  return longest

def foo_num(track, memory, va_n_len):
  n = va_n_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_n_len[1])
  string_value = None
  if (length > 0):
    string_value = unistr(__foo_va_conv_n(n)).zfill(length)
  else:
    string_value = unistr(__foo_int(__foo_va_conv_n(n)))
  return EvaluatorAtom(string_value, __foo_bool(n))

def foo_pad_universal(va_x_len_char, right):
  x = va_x_len_char[0].eval()
  length = __foo_va_conv_n_lazy_int(va_x_len_char[1])
  char = va_x_len_char[2]

  try:
    char = unistr(char.eval())[0]
  except AttributeError:
    pass

  if not char:
    return x

  x_str = unistr(x)
  x_len = len(x_str)

  if x_len < length:
    padded = None
    if not right:
      padded = x_str + char * (length - x_len)
    else:
      padded = char * (length - x_len) + x_str
    return EvaluatorAtom(padded, __foo_bool(x))
  return x

def foo_pad_arity2(track, memory, va_x_len):
  return foo_pad_arity3(track, memory, va_x_len + [' '])

def foo_pad_arity3(track, memory, va_x_len_char):
  return foo_pad_universal(va_x_len_char, right=False)

def foo_pad_right_arity2(track, memory, va_x_len):
  return foo_pad_right_arity3(track, memory, va_x_len + [' '])

def foo_pad_right_arity3(track, memory, va_x_len_char):
  return foo_pad_universal(va_x_len_char, right=True)

def foo_padcut(track, memory, va_x_len):
  cut = foo_cut(track, memory, va_x_len)
  return foo_pad_arity2(track, memory, [cut, va_x_len[1]])

def foo_padcut_right(track, memory, va_x_len):
  cut = foo_cut(track, memory, va_x_len)
  return foo_pad_right_arity2(track, memory, [cut, va_x_len[1]])

def foo_progress_universal(va_pos_range_len_a_b, is2):
  pos = va_pos_range_len_a_b[0].eval()
  range_value = va_pos_range_len_a_b[1].eval()
  length = __foo_va_conv_n_lazy_int(va_pos_range_len_a_b[2])
  a = unistr(va_pos_range_len_a_b[3].eval())
  b = unistr(va_pos_range_len_a_b[4].eval())
  pos_int = __foo_int(__foo_va_conv_n(pos))
  range_int = __foo_int(__foo_va_conv_n(range_value))

  if pos_int > range_int:
    pos_int = range_int
  elif pos_int < 0:
    pos_int = 0

  progress = None

  if not is2:
    cursor_pos = 0

    if range_int == 0:
      if __foo_va_conv_n_lazy_int(pos) > 0:
        progress = a + b * (length - 1)
      else:
        progress = b * (length - 1) + a
    else:
      cursor_pos = (pos_int * length + range_int // 2) // range_int

      # This appears to be a foobar2000 bug. The cursor position is off by one.
      # Remove this line if the bug is ever fixed.
      cursor_pos += 1

      if cursor_pos <= 0:
        cursor_pos = 1
      elif cursor_pos >= length:
        cursor_pos = length

      progress = a * (cursor_pos - 1) + b + a * (length - cursor_pos)
  else:
    if range_int == 0:
      if __foo_va_conv_n_lazy_int(pos) > 0:
        progress = a * length
      else:
        progress = b * length
    else:
      left_count = pos_int * length // range_int

      progress = a * left_count + b * (length - left_count)

  return EvaluatorAtom(progress, foo_and(None, [pos, range_value]))

def foo_progress(track, memory, va_pos_range_len_a_b):
  return foo_progress_universal(va_pos_range_len_a_b, False)

def foo_progress2(track, memory, va_pos_range_len_a_b):
  return foo_progress_universal(va_pos_range_len_a_b, True)

def foo_repeat(track, memory, va_a_n):
  a = va_a_n[0].eval()
  n = __foo_va_conv_n_lazy_int(va_a_n[1])
  return EvaluatorAtom(unistr(a) * n, __foo_bool(a))

def foo_replace_explode_recursive(a, va_a_bN_cN, i):
  if i + 1 < len(va_a_bN_cN):
    b = unistr(va_a_bN_cN[i].eval())
    splits = a.split(b)
    current = []
    for each in splits:
      sub_splits = foo_replace_explode_recursive(each, va_a_bN_cN, i + 2)
      if sub_splits is not None:
        current.append(sub_splits)
    if not current:
      current = splits
    return current

def foo_replace_join_recursive(splits, va_a_bN_cN, i):
  if i < len(va_a_bN_cN):
    current = []
    for each in splits:
      sub_joined = foo_replace_join_recursive(each, va_a_bN_cN, i + 2)
      if sub_joined is not None:
        current.append(sub_joined)
    c = unistr(va_a_bN_cN[i].eval())
    if not current:
      current = splits
    joined = c.join(current)
    return joined

def foo_replace(track, memory, va_a_bN_cN):
  a = va_a_bN_cN[0].eval()
  splits = foo_replace_explode_recursive(unistr(a), va_a_bN_cN, 1)
  result = foo_replace_join_recursive(splits, va_a_bN_cN, 2)
  # Truthfully, I have no idea if this is actually right, but it's probably good
  # enough for what it does. The sample cases check out, at least.
  return EvaluatorAtom(result, __foo_bool(a))

def foo_right(track, memory, va_a_len):
  a = va_a_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_a_len[1])
  a_str = unistr(a)
  a_len = len(a_str)
  if a_len == 0 or length >= a_len:
    return a
  elif length <= 0:
    return EvaluatorAtom('', __foo_bool(a))
  return EvaluatorAtom(a_str[a_len-length:], __foo_bool(a))

__roman_numerals = (
    ('M',  1000),
    ('CM', 900),
    ('D',  500),
    ('CD', 400),
    ('C',  100),
    ('XC', 90),
    ('L',  50),
    ('XL', 40),
    ('X',  10),
    ('IX', 9),
    ('V',  5),
    ('IV', 4),
    ('I',  1),
)

def foo_roman(track, memory, va_n):
  n = va_n[0].eval()
  n_int = __foo_int(__foo_va_conv_n(n))
  result = ''
  if n_int > 0 and n_int <= 100000:
    for numeral, value in __roman_numerals:
      while n_int >= value:
        result += numeral
        n_int -= value
  return EvaluatorAtom(result, __foo_bool(n))

def foo_rot13(track, memory, va_a):
  a = va_a[0].eval()
  rot = codecs.encode(unistr(a), 'rot_13')
  return EvaluatorAtom(rot, __foo_bool(a))

def foo_shortest(track, memory, va_aN):
  shortest = None
  shortest_len = -1
  for each in va_aN:
    current = each.eval()
    current_len = len(unistr(current))
    if shortest_len == -1 or current_len < shortest_len:
      shortest = current
      shortest_len = current_len
  return shortest

def foo_strchr(track, memory, va_s_c):
  s = unistr(va_s_c[0].eval())
  c = unistr(va_s_c[1].eval())
  if c:
    c = c[0]
    for i, char in enumerate(s):
      if c == char:
        return EvaluatorAtom(i + 1, True)
  return EvaluatorAtom(0, False)

def foo_strrchr(track, memory, va_s_c):
  s = unistr(va_s_c[0].eval())
  c = unistr(va_s_c[1].eval())
  if c:
    c = c[0]
    for i, char in itertools.izip(reversed(xrange(len(s))), reversed(s)):
      if c == char:
        return EvaluatorAtom(i + 1, True)
  return EvaluatorAtom(0, False)

def foo_strstr(track, memory, va_s1_s2):
  s1 = unistr(va_s1_s2[0].eval())
  s2 = unistr(va_s1_s2[1].eval())
  found_index = 0
  if s1 and s2:
    found_index = s1.find(s2) + 1
  return EvaluatorAtom(found_index, __foo_bool(found_index))

def foo_strcmp(track, memory, va_s1_s2):
  s1 = va_s1_s2[0].eval()
  s2 = va_s1_s2[1].eval()
  if unistr(s1) == unistr(s2):
    return EvaluatorAtom(1, True)
  return EvaluatorAtom('', False)

def foo_stricmp(track, memory, va_s1_s2):
  s1 = va_s1_s2[0].eval()
  s2 = va_s1_s2[1].eval()
  if unistr(s1).lower() == unistr(s2).lower():
    return EvaluatorAtom(1, True)
  return EvaluatorAtom('', False)

def foo_substr(track, memory, va_s_m_n):
  s = va_s_m_n[0].eval()
  m = __foo_va_conv_n_lazy_int(va_s_m_n[1]) - 1
  n = __foo_va_conv_n_lazy_int(va_s_m_n[2])
  if n < m:
    return EvaluatorAtom('', __foo_bool(s))
  if m < 0:
    m = 0
  s_str = unistr(s)
  s_len = len(s_str)
  result = None
  if n > s_len:
    n = s_len
  if m == 0 and n == s_len:
    return s
  elif n == s_len:
    result = s_str[m:]
  else:
    result = s_str[m:n]
  return EvaluatorAtom(result, __foo_bool(s))

def foo_strip_swap_prefix(va_x_prefixN, should_swap):
  x = va_x_prefixN[0].eval()
  x_str = unistr(x)
  x_str_lower = x_str.lower()

  for i in range(1, len(va_x_prefixN)):
    prefix = va_x_prefixN[i]

    try:
      prefix = unistr(prefix.eval())
    except AttributeError:
      pass

    if x_str_lower.startswith(prefix.lower() + ' '):
      prefix_len = len(prefix)
      result = x_str[prefix_len+1:]

      if should_swap:
        actual_prefix = x_str[0:prefix_len]
        result += ', ' + actual_prefix

      return EvaluatorAtom(result, __foo_bool(x))

  return x

def foo_stripprefix_arity1(track, memory, va_x):
  return foo_stripprefix_arityN(track, memory, va_x + ['A', 'The'])

def foo_stripprefix_arityN(track, memory, va_x_prefixN):
  return foo_strip_swap_prefix(va_x_prefixN, False)

def foo_swapprefix_arity1(track, memory, va_x):
  return foo_swapprefix_arityN(track, memory, va_x + ['A', 'The'])

def foo_swapprefix_arityN(track, memory, va_x_prefixN):
  return foo_strip_swap_prefix(va_x_prefixN, True)

def foo_trim(track, memory, va_s):
  s = va_s[0].eval()
  return EvaluatorAtom(unistr(s).strip(), __foo_bool(s))

def foo_tab_arity0(track, memory, va):
  return '\t'

def foo_tab_arity1(track, memory, va_n):
  n = __foo_va_conv_n_lazy_int(va_n[0])
  if n < 0 or n > 16:
    n = 16
  return '\t' * n

def foo_upper(track, memory, va_s):
  s = va_s[0].eval()
  return EvaluatorAtom(unistr(s).upper(), __foo_bool(s))

def foo_meta_arity1(track, memory, va_name):
  return foo_meta_sep_arity2(track, memory, va_name + [', '])

def foo_meta_arity2(track, memory, va_name_n):
  name = unistr(va_name_n[0].eval())
  n = __foo_va_conv_n_lazy_int(va_name_n[1])
  if n < 0:
    return False
  value = track.get(name)
  if not value:
    value = track.get(name.upper())
    if not value:
      return False
  if isinstance(value, list):
    if n >= len(value):
      return False
    value = value[n]
  elif n != 0:
    return False
  return EvaluatorAtom(value, True)

def foo_meta_sep_arity2(track, memory, va_name_sep):
  name = unistr(va_name_sep[0].eval())

  sep = va_name_sep[1]
  try:
    sep = unistr(sep.eval())
  except AttributeError:
    pass

  value = track.get(name)
  if not value:
    value = track.get(name.upper())
    if not value:
      return False
  if isinstance(value, list):
    value = sep.join(value)
  return EvaluatorAtom(value, True)

def foo_meta_sep_arity3(track, memory, va_name_sep_lastsep):
  name = unistr(va_name_sep_lastsep[0].eval())
  sep = unistr(va_name_sep_lastsep[1].eval())
  lastsep = unistr(va_name_sep_lastsep[2].eval())
  value = track.get(name)
  if not value:
    value = track.get(name.upper())
    if not value:
      return False
  if isinstance(value, list):
    if len(value) > 1:
      value = sep.join(value[:-1]) + lastsep + value[-1]
    else:
      value = value[0]
  return EvaluatorAtom(value, True)

def foo_meta_test(track, memory, va_nameN):
  for each in va_nameN:
    name = unistr(each.eval())
    value = track.get(name)
    if not value:
      value = track.get(name.upper())
      if not value:
        return False
  return EvaluatorAtom(1, True)

def foo_meta_num(track, memory, va_name):
  name = unistr(va_name[0].eval())
  value = track.get(name)
  if not value:
    value = track.get(name.upper())
    if not value:
      return 0
  if isinstance(value, list):
    return EvaluatorAtom(len(value), True)
  return EvaluatorAtom(1, True)

def foo_get(track, memory, va_name):
  name = va_name[0].eval()
  name_str = unistr(name)
  if name_str == '':
    return False
  value = memory.get(name_str)
  if value is not None and value is not False and value != '':
    return EvaluatorAtom(value, True)
  return False

def foo_put(track, memory, va_name_value):
  name = unistr(va_name_value[0].eval())
  value = va_name_value[1].eval()
  if name != '':
    memory[name] = unistr(value)
  return value

def foo_puts(track, memory, va_name_value):
  value = foo_put(track, memory, va_name_value)
  return __foo_bool(value)


foo_function_vtable = {
    '(default)' : {'n': foo_unknown},
    # TODO: With strict rules, $if 'n' should throw exception
    'if': {2: foo_if_arity2, 3: foo_if_arity3, 'n': foo_invalid('if')},
    'if2': {2: foo_if2, 'n': foo_invalid('if2')},
    'if3': {0: foo_false, 1: foo_false, 'n': foo_if3},
    'ifequal': {4: foo_ifequal, 'n': foo_invalid('ifequal')},
    'ifgreater': {4: foo_ifgreater, 'n': foo_invalid('ifgreater')},
    'iflonger': {4: foo_iflonger, 'n': foo_invalid('iflonger')},
    'select': {0: foo_false, 1: foo_false, 2: foo_select2, 'n': foo_select},
    'add': {0: foo_zero, 1: foo_nnop, 'n': foo_add},
    'div': {0: foo_false, 1: foo_nnop, 'n': foo_div},
    # TODO: With strict rules, $greater 'n' should throw exception
    'greater': {2: foo_greater, 'n': foo_false},
    'max': {0: foo_false, 1: foo_nnop, 2: foo_max, 'n': foo_maxN},
    'min': {0: foo_false, 1: foo_nnop, 2: foo_min, 'n': foo_minN},
    'mod': {0: foo_false, 1: foo_nnop, 2: foo_mod, 'n': foo_modN},
    'mul': {0: foo_one, 1: foo_nnop, 'n': foo_mul},
    # TODO: With strict rules, $muldiv 'n' should throw exception
    'muldiv': {3: foo_muldiv, 'n': foo_false},
    'rand': {0: foo_rand},
    'sub': {0: foo_false, 'n': foo_sub},
    'and': {0: foo_true, 'n': foo_and},
    'or': {0: foo_false, 'n': foo_or},
    # TODO: With strict rules, $not 'n' should throw exception
    'not': {0: foo_false, 1: foo_not, 'n': foo_false},
    'xor': {0: foo_false, 1: foo_bnop, 'n': foo_xor},
    'abbr': {1: foo_abbr1, 2: foo_abbr2, 'n': foo_false},
    # TODO: With strict rules, $ansi 'n' should throw exception
    'ansi': {0: foo_false, 1: foo_ansi, 'n': foo_false},
    # TODO: With strict rules, $ascii 'n' should throw exception
    'ascii': {0: foo_false, 1: foo_ascii, 'n': foo_false},
    # TODO: With strict rules, $caps and $caps2 'n' should throw exception
    'caps': {0: foo_false, 1: foo_caps, 'n': foo_false},
    'caps2': {0: foo_false, 1: foo_caps2, 'n': foo_false},
    # TODO: Strict rules, etc. You get the idea.
    'char': {0: foo_false, 1: foo_char, 'n': foo_false},
    'crc32': {1: foo_crc32},
    'crlf': {0: foo_crlf},
    'cut': {2: foo_cut},
    'directory': {1: foo_directory_arity1, 2: foo_directory_arity2},
    'directory_path': {1: foo_directory_path},
    'ext': {1: foo_ext},
    'filename': {1: foo_filename},
    'fix_eol': {1: foo_fix_eol_arity1, 2: foo_fix_eol_arity2},
    'hex': {1: foo_hex_arity1, 2: foo_hex_arity2},
    'insert': {3: foo_insert},
    'left': {2: foo_left},
    'len': {1: foo_len},
    'len2': {1: foo_len2},
    'longer': {2: foo_longer},
    'lower': {1: foo_lower},
    'longest': {0: foo_false, 1: foo_nop, 'n': foo_longest},
    'num': {2: foo_num},
    'pad': {2: foo_pad_arity2, 3: foo_pad_arity3},
    'pad_right': {2: foo_pad_right_arity2, 3: foo_pad_right_arity3},
    'padcut': {2: foo_padcut},
    'padcut_right': {2: foo_padcut_right},
    'progress': {5: foo_progress},
    'progress2': {5: foo_progress2},
    'repeat': {2: foo_repeat},
    'replace': {
        0: foo_false,
        1: foo_false,
        2: foo_false,
        'n': foo_replace
    },
    'right': {2: foo_right},
    'roman': {1: foo_roman},
    'rot13': {1: foo_rot13},
    'shortest': {0: foo_false, 1: foo_nop, 'n': foo_shortest},
    'strchr': {2: foo_strchr},
    'strrchr': {2: foo_strrchr},
    'strstr': {2: foo_strstr},
    'strcmp': {2: foo_strcmp},
    'stricmp': {2: foo_stricmp},
    'substr': {3: foo_substr},
    'stripprefix': {
        0: foo_false,
        1: foo_stripprefix_arity1,
        'n': foo_stripprefix_arityN
    },
    'swapprefix': {
        0: foo_false,
        1: foo_swapprefix_arity1,
        'n': foo_swapprefix_arityN
    },
    'trim': {1: foo_trim},
    'tab': {0: foo_tab_arity0, 1: foo_tab_arity1},
    'upper': {1: foo_upper},
    'meta': {1: foo_meta_arity1, 2: foo_meta_arity2},
    'meta_sep': {2: foo_meta_sep_arity2, 3: foo_meta_sep_arity3},
    'meta_test': {'n': foo_meta_test},
    'meta_num': {1: foo_meta_num},
    'get': {0: foo_false, 1: foo_get},
    'put': {2: foo_put},
    'puts': {2: foo_puts},
}


class FunctionVirtualInvocationException(Exception):
  pass


def vmarshal(value):
  if type(value) is EvaluatorAtom:
    return value

  if value is True or value is False:
    return EvaluatorAtom('', value)

  if value is None:
    return None

  return EvaluatorAtom(value, False)

def vlookup(function, arity):
  try:
    fn_vector = foo_function_vtable[function]
    try:
      return fn_vector[arity]
    except KeyError:
      try:
        return fn_vector['n']
      except KeyError:
        raise FunctionVirtualInvocationException(
            'The function with name "%s" has no definition for arity %s' % (
              function, arity))
  except KeyError:
    try:
      fn_vector = foo_function_vtable['(default)']
      try:
        return fn_vector[arity]
      except KeyError:
        try:
          return fn_vector['n']
        except KeyError:
          raise FunctionVirtualInvocationException(
              'Function "' + function + '" is undefined and the default'
              + ' handler has no definition for arity ' + arity)
    except KeyError:
      raise FunctionVirtualInvocationException(
          'The function with name "' + function + '" has no definition and no'
          + ' default handler has been defined')

def vinvoke(track, function, argv, memory={}):
  arity = len(argv)
  funcref = vlookup(function, arity)
  return vmarshal(funcref(track, memory, argv))

def vcallmarshal(atom):
  if atom is None:
    return ('', 0)

  return (unistr(atom), 1 if atom else 0)

def vcondmarshal(atom):
  if not atom:
    return ('', 0)

  return (unistr(atom), 1)

def foobar_filename_escape(output):
  system = platform.system()
  output = re.sub(' *([' + re.escape(os.sep) + ']) *', '\\1', output)
  if system == 'Windows':
    if re.match('^[A-Z]:', output, flags=re.I):
      disk_id = output[0:2]
      output = disk_id + re.sub('[\\\\/:|]', re.escape(os.sep), output[2:])
    else:
      output = re.sub('[\\\\/:|]', re.escape(os.sep), output)
  else:
    output = re.sub('[\\\\:|]', re.escape('\\'), output)
  output = re.sub('[*]', 'x', output)
  output = re.sub('"', "''", output)
  output = re.sub('[?<>]', '_', output)
  return output


class LazyExpression:
  def __init__(self,
      formatter, track, expression, conditional, depth, offset, track_memory):
    self.formatter = formatter
    self.track = track
    self.current = expression
    self.conditional = conditional
    self.depth = depth
    self.offset = offset
    self.memory = track_memory
    self.value = None
    self.evaluated = False

  def eval(self):
    if not self.evaluated:
      self.value = self.formatter.eval(
          self.track, self.current, self.conditional, self.depth, self.offset,
          self.memory)
      self.evaluated = True
    return self.value

  def __str__(self):
    return self.current

  def __repr__(self):
    return "lazy(%s)" % repr(self.current)


class CurriedCompilation:
  def __init__(self, lazycomp, track):
    self.lazycomp = lazycomp
    self.track = track
    self.value = None

  def eval(self):
    if self.value is None:
      self.value = self.lazycomp(self.track)
    return self.value

  @property
  def string_value(self):
    return self.eval()[0].string_value

  @property
  def truth_value(self):
    return self.eval()[0].truth_value

  @property
  def evaluation_count(self):
    return self.eval()[1]

  def __repr__(self):
    return 'curriedcomp(%s)' % repr(self.lazycomp)


class LazyCompilation:
  def __init__(self,
      formatter, expression, conditional, depth, offset, track_memory,
      debug=False):
    self.formatter = formatter
    self.current = expression
    self.conditional = conditional
    self.depth = depth
    self.offset = offset
    self.memory = track_memory
    self.debug = debug
    self.codeblock = None

  def curry(self, track):
    return CurriedCompilation(self, track)

  def eval(self, track):
    if self.codeblock is None:
      if self.debug:
        dbg('lazily compiling block: %s' % self.current, self.depth)
      self.codeblock = self.formatter.eval(
          None, self.current, self.conditional, self.depth, self.offset,
          self.memory, True)
    return self.codeblock(track)

  def __call__(self, track):
    return self.eval(track)

  def __str__(self):
    return self.current

  def __repr__(self):
    return 'lazycomp(cb=%s, %s)' % (repr(self.codeblock), repr(self.current))

class TitleFormatParseException(Exception):
  pass


class TitleFormatter:
  def __init__(
      self, case_sensitive=False, magic=True, for_filename=False,
      compatible=True, debug=False):
    self.case_sensitive = case_sensitive
    self.magic = magic
    self.for_filename = for_filename
    self.compatible = compatible
    self.debug = debug

  def format(self, track, title_format):
    evaluated_value = self.eval(track, title_format)
    if evaluated_value is not None:
      return unistr(evaluated_value)
    return None

  def eval(self, track, title_format, conditional=False, depth=0, offset=0,
      memory={}, compiling=False):
    lookbehind = None
    outputting = True
    literal = False
    literal_count = None
    parsing_variable = False
    parsing_function = False
    parsing_function_args = False
    parsing_function_recursive = False
    parsing_conditional = False
    paren_poisoned = False
    offset_start = 0
    fn_offset_start = 0
    bad_var_char = None
    conditional_parse_count = 0
    evaluation_count = 0
    argparen_count = 0
    recursive_lparen_count = 0
    recursive_rparen_count = 0
    output = ''
    current = ''
    current_fn = ''
    current_argv = []

    compiled = []

    if self.debug:
      dbg('fresh call to eval(); format="%s" offset=%s' % (
        title_format, offset), depth)

    for i, c in enumerate(title_format):
      if outputting:
        if literal:
          next_output, literal, chars_parsed = self.parse_literal(
              c, i, lookbehind, literal_count, False, depth, offset + i)
          output += next_output
          literal_count += chars_parsed
        else:
          if c == "'":
            if self.debug:
              dbg('entering literal mode at char %s' % i, depth)
            literal = True
            literal_count = 0
          elif c == '%':
            if self.debug:
              dbg('begin parsing variable at char %s' % i, depth)
            if parsing_variable or parsing_function or parsing_conditional:
              raise TitleFormatParseException(
                  "Something went horribly wrong while parsing token '%'")
            outputting = False
            parsing_variable = True
          elif c == '$':
            if self.debug:
              dbg('begin parsing function at char %s' % i, depth)
            if parsing_variable or parsing_function or parsing_conditional:
              raise TitleFormatParseException(
                  "Something went horribly wrong while parsing token '$'")
            outputting = False
            parsing_function = True
            fn_offset_start = i + 1
          elif c == '[':
            if self.debug:
              dbg('begin parsing conditional at char %s' % i, depth)
            if parsing_variable or parsing_function or parsing_conditional:
              raise TitleFormatParseException(
                  "Something went horribly wrong while parsing token '['")
            outputting = False
            parsing_conditional = True
            offset_start = i + 1
          elif c == ']':
            message = self.make_backwards_error(']', '[', offset, i)
            if self.compatible:
              if self.debug:
                dbg(self.make_noncompatible_dbg_msg(message), depth)
            else:
              raise TitleFormatParseException(message)
          elif (c == '(' or c == ')') and self.compatible:
            # This seems like a foobar bug; parens shouldn't do anything outside
            # of a function call, but foobar will just explode if it sees a lone
            # paren floating around in the input.
            break
          else:
            output += c
        if compiling and not outputting and len(output) > 0:
          # This is a state transition; flush buffers to compiled lambda units
          compiled.append(lambda t, output=output: (output, 0))
          output = ''
      else:
        if parsing_variable:
          if literal:
            raise TitleFormatParseException(
                'Invalid parse state: Cannot parse names while in literal mode')
          if c == '%':
            if compiling:
              compiled.append(
                  lambda t, self=self, current=current, i=i, depth=depth:
                    self.handle_var_resolution(t, current, i, depth))
            else:
              val, edelta = self.handle_var_resolution(track, current, i, depth)
              output += val
              evaluation_count += edelta
              if self.debug:
                dbg('evaluation count is now %s' % evaluation_count, depth)

            current = ''
            outputting = True
            parsing_variable = False
          elif not self.is_valid_var_identifier(c):
            dbg('probably an invalid character: %s at char %i' % (c, i), depth)
            # Only record the first instance.
            if bad_var_char is None:
              bad_var_char = (c, offset + i)

            current += c
          else:
            current += c
        elif parsing_function:
          if literal:
            raise TitleFormatParseException(
                'Invalid parse state: Cannot parse names while in literal mode')
          if c == '(':
            if self.debug:
              dbg('parsed function "%s" at char %s' % (current, i), depth)

            current_fn = current
            current = ''
            parsing_function = False
            parsing_function_args = True
            offset_start = i + 1
          elif c == ')':
            message = self.make_backwards_error(')', '(', offset, i)
            raise TitleFormatParseException(message)
          elif c == '$' and lookbehind == '$':
            if self.debug:
              dbg('output of single $ due to lookbehind at char %s' % i, depth)
            output += c
            outputting = True
            parsing_function = False
          elif not (c == '_' or c.isalnum()):
            if self.compatible:
              break
            raise TitleFormatParseException(
                "Illegal token '%s' encountered at char %s" % (c, i))
          else:
            current += c
        elif parsing_function_args:
          if not parsing_function_recursive:
            if literal:
              next_current, literal, chars_parsed = self.parse_literal(
                  c, i, lookbehind, literal_count, True, depth, offset + i)
              current += next_current
              literal_count += chars_parsed
            else:
              if paren_poisoned:
                if self.debug:
                  dbg('checking poison state at char %s' % i, depth)
                if c == '(':
                  argparen_count += 1
                  if self.debug:
                    dbg('paren poisoning count now %s at char %s' % (
                      argparen_count, i), depth)
                  continue
                if argparen_count == 0:
                  if c == ',' or c == ')':
                    if self.debug:
                      dbg('stopped paren poisoning at char %s' % i, depth)
                    # Resume normal execution and fall through; don't continue.
                    paren_poisoned = False
                  else:
                    continue
                elif c == ')':
                  argparen_count -= 1
                  if self.debug:
                    dbg('paren poisoning count now %s at char %s' % (
                      argparen_count, i), depth)
                  continue
                else:
                  continue
              if c == ')' and argparen_count == 0:
                if current != '' or len(current_argv) > 0:
                  current, arg = self.parse_fn_arg(track, current_fn, current,
                      current_argv, c, i, depth, offset + offset_start, memory,
                      compiling)
                  current_argv.append(arg)

                if self.debug:
                  dbg('finished parsing function arglist at char %s' % i, depth)

                if compiling:
                  compiled.append(self.compile_fn_call(
                    current_fn, current_argv, depth, offset + fn_offset_start))
                else:
                  val, edelta = self.handle_fn_invocation(
                      track, current_fn, current_argv,
                      depth, offset + fn_offset_start)

                  if val:
                    output += val

                  evaluation_count += edelta

                  if self.debug:
                    dbg('evaluation count is now %s' % evaluation_count, depth)

                current_argv = []
                outputting = True
                parsing_function_args = False
              elif c == ')':
                argparen_count -= 1
                current += c
              elif c == '(':
                argparen_count += 1
                if self.compatible:
                  if self.debug:
                    dbg('detected paren poisoning at char %s' % i, depth)
                  paren_poisoned = True
                  continue
                else:
                  current += c
              elif c == "'":
                if self.debug:
                  dbg('entering arglist literal mode at char %s' % i, depth)
                literal = True
                literal_count = 0
                # Include the quotes because we reparse function arguments.
                current += c
              elif c == ',' and argparen_count == 0:
                current, arg = self.parse_fn_arg(track, current_fn, current,
                    current_argv, c, i, depth, offset + offset_start, memory,
                    compiling)
                current_argv.append(arg)
                offset_start = i + 1
              elif c == '$':
                if self.debug:
                  dbg('stopped evaluation for function in arg at char %s' % i,
                      depth)
                current += c
                parsing_function_recursive = True
                recursive_lparen_count = 0
                recursive_rparen_count = 0
              else:
                current += c
          else: # parsing_function_recursive
            current += c
            if c == '(':
              recursive_lparen_count += 1
            elif c == ')':
              recursive_rparen_count += 1
              if recursive_lparen_count == recursive_rparen_count:
                # Stop skipping evaluation.
                if self.debug:
                  dbg('resumed evaluation at char %s' % i, depth)
                parsing_function_recursive = False
              elif recursive_lparen_count < recursive_rparen_count:
                message = self.make_backwards_error(')', '(', offset, i)
                raise TitleFormatParseException(message)
        elif parsing_conditional:
          if literal:
            current += c
            if c == "'":
              if self.debug:
                dbg('leaving conditional literal mode at char %s' % i, depth)
              literal = False
          else:
            if c == '[':
              if self.debug:
                dbg('found a pending conditional at char %s' % i, depth)
              conditional_parse_count += 1
              if self.debug:
                dbg('conditional parse count now %s' % conditional_parse_count,
                    depth)
              current += c
            elif c == ']':
              if conditional_parse_count > 0:
                if self.debug:
                  dbg('found a terminating conditional at char %s' % i, depth)
                conditional_parse_count -= 1
                if self.debug:
                  dbg('conditional parse count now %s at char %s' % (
                    conditional_parse_count, i), depth)
                current += c
              else:
                if self.debug:
                  dbg('finished parsing conditional at char %s' % i, depth)

                if compiling:
                  compiled_cond = self.eval(
                      None, current, True, depth + 1, offset + offset_start,
                      memory, True)
                  compiled.append(lambda t, c=compiled_cond: vcondmarshal(c(t)))
                else:
                  evaluated_value = self.eval(
                      track, current, True, depth + 1, offset + offset_start,
                      memory)

                  if self.debug:
                    dbg('value is: %s' % evaluated_value, depth)
                  if evaluated_value:
                    output += unistr(evaluated_value)
                    evaluation_count += 1
                  if self.debug:
                    dbg('evaluation count is now %s' % evaluation_count, depth)

                current = ''
                conditional_parse_count = 0
                outputting = True
                parsing_conditional = False
            elif c == "'":
              if self.debug:
                dbg('entering conditional literal mode at char %s' % i, depth)
              current += c
              literal = True
            else:
              current += c
        else:
          # Whatever is happening is invalid.
          raise TitleFormatParseException(
              "Invalid title format parse state: Can't handle character " + c)
      lookbehind = c

    # At this point, we have reached the end of the input.
    message = None
    if outputting:
      if literal:
        message = self.make_unterminated_error('literal', "'", offset, i)
    else:
      if parsing_variable:
        message = self.make_unterminated_error('variable', '%', offset, i)
        if bad_var_char is not None:
          message += " (probably caused by char '%s' in position %s)" % (
              bad_var_char[0], bad_var_char[1])
      elif parsing_function:
        message = self.make_unterminated_error('function', '(', offset, i)
      elif parsing_function_args:
        message = self.make_unterminated_error('function call', ')', offset, i)
      elif parsing_conditional:
        message = self.make_unterminated_error('conditional', ']', offset, i)
      else:
        message = "Invalid title format parse state: Unknown error"
        raise TitleFormatParseException(message)  # Always raise this

    if message is not None:
      if self.compatible:
        if self.debug:
          dbg(self.make_noncompatible_dbg_msg(message), depth)
      else:
        raise TitleFormatParseException(message)

    if compiling:
      if len(output) > 0:
        # We need to flush the output buffer to a lambda once more
        compiled.append(lambda t, output=output: (output, 0))
        output = ''
      if self.debug:
        dbg('eval() compiled the input into %s blocks' % len(compiled), depth)
      return (lambda t, self=self, compiled=compiled, depth=depth:
        self.invoke_jit_eval(compiled, depth, t))

    if conditional and evaluation_count == 0:
      if self.debug:
        dbg('about to return nothing for output: %s' % output, depth)
      return None

    if depth == 0 and self.for_filename:
      output = foobar_filename_escape(output)

    result = EvaluatorAtom(output, False if evaluation_count == 0 else True)

    if self.debug:
      dbg('eval() is returning: ' + repr(result), depth)

    return result

  def invoke_jit_eval(self, compiled, depth, track):
    output = ''
    evaluation_count = 0

    for c in compiled:
      c_output, c_count = c(track)
      output += c_output
      evaluation_count += c_count

    return EvaluatorAtom(output, evaluation_count != 0)

  def is_valid_var_identifier(self, c):
    return c == ' ' or c == '@' or c == '_' or c == '-' or c.isalnum()

  def make_noncompatible_dbg_msg(self, message):
    return ('A non-compatible formatter would have raised an exception with'
        + ' the message "' + message + '"')

  def make_backwards_error(self, right, left_expected, offset, i):
    message = "Encountered '%s' with no matching '%s'" % (right, left_expected)
    message += " at position %s" % (offset + i)
    return message

  def make_unterminated_error(self, token, expected, offset, i):
    message = "Unterminated %s; " % token
    if offset == 0:
      message += "reached end of input, "
    message += "expected '%s'" % expected
    if offset != 0:
      message += " at position %s" % (offset + i + 1)

    return message

  def parse_literal(self, c, i, lookbehind, literal_count, include_quote,
      depth=0, offset=0):
    next_output = ''
    next_literal_state = True
    literal_chars_parsed = 0

    if c == "'":
      if lookbehind == "'" and literal_count == 0:
        if self.debug:
          dbg('output of single quote due to lookbehind at char %s' % i, depth)
        next_output += c
      elif include_quote:
        next_output += c
      if self.debug:
        dbg('leaving literal mode at char %s' % i, depth)
      next_literal_state = False
    else:
      next_output += c
      literal_chars_parsed += 1

    return (next_output, next_literal_state, literal_chars_parsed)

  def parse_fn_arg(self, track, current_fn, current, current_argv, c, i,
      depth=0, offset=0, memory={}, compiling=False):
    next_current = ''

    if self.debug:
      dbg('finished argument %s for function "%s" at char %s' % (
          len(current_argv), current_fn, i), depth)

    if compiling:
      lazy = LazyCompilation(self, current, False, depth + 1, offset, memory,
          self.debug)
      return (next_current, lazy)

    # The lazy expression will parse the current buffer if it's ever needed.
    lazy = LazyExpression(
        self, track, current, False, depth + 1, offset, memory)
    return (next_current, lazy)

  def handle_var_resolution(self, track, field, i, depth):
    evaluated_value = self.resolve_variable(track, field, i, depth)

    if self.debug:
      dbg('value is: %s' % evaluated_value, depth)

    evaluated_value_str = unistr(evaluated_value)

    if evaluated_value or evaluated_value == '':
      if evaluated_value is not True:
        return (evaluated_value_str, 1)
      return ('', 1)
    elif evaluated_value is not None and evaluated_value is not False:
      # This is the case where no evaluation happened but there is still a
      # string value (that won't output conditionally).
      return (evaluated_value_str, 0)

    return ('?', 0)

  def resolve_variable(self, track, field, i, depth):
    if field == '':
      if self.debug:
        dbg('output of single percent at char %s' % i, depth)
      return EvaluatorAtom('%', False)

    local_field = field
    if not self.case_sensitive:
      local_field = field.upper()
    if self.debug:
      dbg('parsed variable %s at char %s' % (local_field, i), depth)

    resolved = None

    if not self.magic:
      resolved = track.get(local_field)
    else:
      resolved = self.magic_resolve_variable(track, local_field, depth)

    if resolved is None or resolved is False:
      return None

    if self.for_filename:
      resolved = re.sub('[\\\\/:|]', '-', resolved)

    return EvaluatorAtom(resolved, True)

  def magic_resolve_variable(self, track, field, depth):
    field_lower = field.lower()
    if self.debug:
      dbg('checking %s for magic mappings' % field_lower, depth)
    if field_lower in magic_mappings:
      mapping = magic_mappings[field_lower]
      if not mapping:
        dbg('mapping "%s" is not valid' % field_lower, depth)
        return track.get(field)
      else:
        # First try to call it -- the mapping can be a function.
        try:
          magically_resolved = mapping(self, track)
          if self.debug:
            dbg('mapped %s via function mapping' % field_lower, depth)
          return magically_resolved
        except TypeError:
          # That didn't work. It's a list.
          if self.debug:
            dbg('mapping "%s" is not a function' % field_lower, depth)
          for each in mapping:
            if self.debug:
              dbg('attempting to map "%s"' % each, depth)
            if each in track:
              return track.get(each)
            if self.case_sensitive:
              each_lower = each.lower()
              if self.debug:
                dbg('attempting to map "%s"' % each_lower, depth)
              if each_lower in track:
                return track.get(each_lower)

          # Still couldn't find it.
          if self.debug:
            dbg('mapping %s failed to map magic variable' % field_lower, depth)
          return track.get(field)

    if self.debug:
      dbg('mapping %s not found in magic variables' % field_lower, depth)
    return track.get(field)

  def compile_fn_call(
      self, current_fn, current_argv, depth, offset):
    fn = vlookup(current_fn, len(current_argv))
    return (lambda t, fn=fn, argv=current_argv:
      vcallmarshal(vmarshal(
        fn(t, {}, [x.curry(t) if hasattr(x, 'curry') else x for x in argv]))))

  def handle_fn_invocation(
      self, track, current_fn, current_argv, depth, offset):
    fn_result = self.invoke_function(
        track, current_fn, current_argv, depth, offset)

    if self.debug:
      dbg('finished invoking function %s, value: %s' % (
          current_fn, repr(fn_result)), depth)

    return vcallmarshal(fn_result)

  def invoke_function(
      self, track, function_name, function_argv, depth=0, offset=0, memory={}):
    if self.debug:
      dbg('invoking function %s, args %s' % (
          function_name, function_argv), depth)
    curried_argv = [
        x.curry(track) if hasattr(x, 'curry') else x
        for x in function_argv]
    return vinvoke(track, function_name, curried_argv, memory)

