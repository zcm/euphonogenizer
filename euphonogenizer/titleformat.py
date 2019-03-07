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

from .common import dbg

from six import binary_type, text_type


@six.python_2_unicode_compatible
class EvaluatorAtom(object):
  __slots__ = 'value', 'truth'

  def __init__(self, value, truth):
    self.value = value
    self.truth = truth

  def __add__(self, other):
    return EvaluatorAtom(
        self.value + other.value,
        self.truth or other.truth)

  def __iadd__(self, other):
    self.value += other.value
    self.truth |= other.truth
    return self

  def __sub__(self, other):
    return EvaluatorAtom(
        self.value - other.value,
        self.truth or other.truth)

  def __isub__(self, other):
    self.value -= other.value
    self.truth |= other.truth
    return self

  def __mul__(self, other):
    return EvaluatorAtom(
        self.value * other.value,
        self.truth or other.truth)

  def __imul__(self, other):
    self.value *= other.value
    self.truth |= other.truth
    return self

  @staticmethod
  def __foo_div_logic(x, y):
    # Foobar skips division for zeros instead of exploding.
    # For some reason, Foobar rounds up when negative and down when positive.
    return x if y == 0 else x * -1 // y * -1 if x * y < 0 else x // y

  def __floordiv__(self, other):
    return EvaluatorAtom(
        self.__foo_div_logic(self.value, other.value),
        self.truth or other.truth)

  def __ifloordiv__(self, other):
    self.value = self.__foo_div_logic(self.value, other.value)
    self.truth |= other.truth
    return self

  def __foo_mod_logic(self, x, y):
    return 0 if x == 0 else x if y == 0 else x % y

  def __mod__(self, other):
    return EvaluatorAtom(
        self.__foo_mod_logic(self.value, other.value),
        self.truth or other.truth)

  def __imod__(self, other):
    self.value = self.__foo_mod_logic(self.value, other.value)
    self.truth |= other.truth
    return self

  def __eq__(self, other):
    return (self.value == other.value and self.truth is other.truth
            if isinstance(other, EvaluatorAtom) else NotImplemented)

  def __ne__(self, other):
    return (self.value != other.value or self.truth is not other.truth
            if isinstance(other, EvaluatorAtom) else NotImplemented)

  def __gt__(self, other):
    return self.value > other.value

  def __lt__(self, other):
    return self.value < other.value

  def __and__(self, other):
    return self.truth and other.truth

  def __iand__(self, other):
    self.truth &= other.truth
    return self

  def __or__(self, other):
    return self.truth or other.truth

  def __ior__(self, other):
    self.truth |= other.truth
    return self

  def __hash__(self):
    return hash((self.value, self.truth))

  def __str__(self):
    return text_type(self.value)

  def __bytes__(self):
    return binary_type(self.value, 'utf-8')

  def __nonzero__(self):
    return self.truth

  def __bool__(self):
    return self.truth

  def __len__(self):
    return len(str(self.value))

  def __repr__(self):
    return 'atom(%s, %s)' % (repr(self.value), self.truth)

  def eval(self):
    # Evaluating an expression that's already been evaluated returns itself.
    return self


def magic_map_filename(formatter, track):
  value = track.get('@')
  if value is not None and value is not False:
    return text_type(foo_filename(None, None, [value]))
  return None

def magic_map_filename_ext(formatter, track):
  value = track.get('@')
  if value is not None and value is not False:
    filename = text_type(foo_filename(None, None, [value]))
    ext = text_type(foo_ext(None, None, [value]))
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
    return text_type(int(value))
  return None


# TODO: Figure out what should happen when newlines are present; multiline?
magic_mappings = {
    'album artist': ['ALBUM ARTIST', 'ARTIST', 'COMPOSER', 'PERFORMER'],
    'album': ['ALBUM', 'VENUE'],
    'artist': ['ARTIST', 'ALBUM ARTIST', 'COMPOSER', 'PERFORMER'],
    'disc': ['DISCNUMBER', 'DISC'],  # undocumented
    'discnumber': ['DISCNUMBER', 'DISC'],
    'disc number': ['DISCNUMBER', 'DISC'],  # undocumented
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

def __foo_int(n):
  # Note that this "string value" might actually already be an int, in which
  # case, this function simply ends up stripping the atom wrapper.
  try:
    if n is not None and n != '':
      return int(n.value)
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
    strval = n.value.strip()
    truth = n.truth
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
    return EvaluatorAtom(0, n.truth)
  except AttributeError:
    pass

  return EvaluatorAtom(0, False)

def __foo_va_conv_n_lazy(n):
  return __foo_va_conv_n(n.eval())

def __foo_va_conv_bool_lazy(b):
  try:
    value = b.eval()
    try:
      return value.truth
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
      val.value = nnop_known_table[val.value]
      return val
    except KeyError:
      pass

    val = __foo_va_conv_n_unsafe(val)
    val.value = text_type(val.value)
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
  c.truth = True  # Truth behavior confirmed by experimentation.
  if c.value == 0:
    # This is real Foobar behavior for some reason, probably a bug.
    c.value = -1
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

def foo_abbr(value):
  parts = __foo_abbr_charstrip.sub(' ', value).split(' ')
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
  x.value = foo_abbr(str(x))
  return x

def foo_abbr2(track, memory, va_x_len):
  x = va_x_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_x_len[1])
  sx = str(x)
  if len(sx) > length:
    x.value = foo_abbr(sx)
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
  result = text_type(x).encode('windows-1252', '__foo_ansi_replace')
  return EvaluatorAtom(str(result, 'windows-1252', 'replace'), bool(x))

def foo_ascii(track, memory, va_x):
  x = va_x[0].eval()
  result = text_type(x).encode('ascii', '__foo_ascii_replace')
  return EvaluatorAtom(result.decode('utf-8', 'replace'), bool(x))

def foo_caps_impl(va_x, on_nonfirst):
  x = va_x[0].eval()
  result = ''
  new_word = True
  for c in text_type(x):
    if __foo_is_word_sep(c):
      new_word = True
      result += c
    else:
      if new_word:
        result += c.upper()
        new_word = False
      else:
        result += on_nonfirst(c)
  return EvaluatorAtom(result, bool(x))

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
  crc = binascii.crc32(binary_type(x))
  return EvaluatorAtom(crc, bool(x))

def foo_crlf(track, memory, va):
  return '\r\n'

# foo_cut is the same as foo_left; see definition for it below

def foo_directory_1(track, memory, va_x):
  x = va_x[0].eval()
  # RFC 8089 allows pipe characters to be used instead of the colons in the
  # drive construct, and Foobar obeys this. For more information, see:
  # https://tools.ietf.org/html/rfc8089#appendix-E.2.2
  parts = re.split('[\\\\/:|]', text_type(x))
  if len(parts) < 2:
    return EvaluatorAtom('', bool(x))
  return EvaluatorAtom(parts[-2], bool(x))

def foo_directory_2(track, memory, va_x_n):
  x = va_x_n[0].eval()
  n = __foo_va_conv_n_lazy_int(va_x_n[1])
  if n <= 0:
    return EvaluatorAtom('', bool(x))
  parts = re.split('[\\\\/:|]', text_type(x))
  parts_len = len(parts)
  if n >= parts_len or parts_len < 2:
    return EvaluatorAtom('', bool(x))
  return EvaluatorAtom(parts[parts_len - n - 1], bool(x))

def foo_directory_path(track, memory, va_x):
  x = va_x[0].eval()
  parts = re.split('[\\\\/:|]', text_type(x)[::-1], 1)
  if len(parts) < 2:
    return EvaluatorAtom('', bool(x))
  return EvaluatorAtom(parts[1][::-1], bool(x))

def foo_ext(track, memory, va_x):
  x = va_x[0]

  try:
    x = x.eval()
  except AttributeError:
    pass

  _, delimiter, ext = text_type(x).rpartition('.')

  if not delimiter or any(c in '/\\|:' for c in ext):
    return ''

  return EvaluatorAtom(ext.partition('?')[0], bool(x))

def foo_filename(track, memory, va_x):
  x = va_x[0]

  try:
    x = x.eval()
  except AttributeError:
    pass

  parts = re.split('[\\\\/:|]', text_type(x))

  return EvaluatorAtom(
      parts[-1].partition('?')[0].rsplit('.', 1)[0], bool(x))

def foo_fix_eol_1(track, memory, va_x):
  return foo_fix_eol(track, memory, va_x[0], ' (...)')

def foo_fix_eol_2(track, memory, va_x_indicator):
  return foo_fix_eol(track, memory, *va_x_indicator)

def foo_fix_eol(track, memory, x, indicator):
  try:
    x = x.eval()
  except AttributeError:
    pass

  try:
    indicator = text_type(indicator.eval())
  except AttributeError:
    pass

  parts = re.split('[\r\n]', text_type(x), 1)

  if len(parts) > 1:
    return EvaluatorAtom(parts[0] + indicator, bool(x))

  return x

def foo_hex_1(track, memory, va_n):
  # While technically in the documentation, $hex(n) doesn't actually do anything
  # as of foobar2000 1.4.2. This is probably a bug that no one has noticed. This
  # documentation-based implementation is provided for non-compliant uses.
  return foo_hex(track, memory, va_n[0])

def foo_hex_2(track, memory, va_n_len):
  return foo_hex(track, memory, *va_n_len)

def foo_hex(track, memory, n, length=0):
  n = __foo_va_conv_n_lazy(n)
  length = __foo_va_conv_n_lazy_int(length)

  n.value = hex(
      max(-0x8000000000000000, min(__foo_int(n), 0x7FFFFFFFFFFFFFFF)
        ) % 0x100000000)[2:].upper().zfill(max(0, min(length, 32)))

  return n

def foo_insert(track, memory, va_a_b_n):
  a = va_a_b_n[0].eval()
  b = text_type(va_a_b_n[1].eval())
  n = __foo_va_conv_n_lazy_int(va_a_b_n[2])

  if n < 0:
    a.value += b
  else:
    a.value = a.value[0:n] + b + a.value[n:]
  return a

def foo_left(track, memory, va_a_len):
  a = va_a_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_a_len[1])

  if length >= 0:
    a.value = a.value[0:length]

  return a

foo_cut = foo_left  # These are the same, so just alias for completeness

def foo_len(track, memory, va_a):
  a = va_a[0].eval()
  return EvaluatorAtom(len(text_type(a)), bool(a))

def foo_len2(track, memory, va_a):
  a = va_a[0].eval()
  length = 0
  str_a = text_type(a)
  for c in str_a:
    width = unicodedata.east_asian_width(c)
    if width == 'N' or width == 'Na' or width == 'H':
      # Narrow / Halfwidth character
      length += 1
    elif width == 'W' or width == 'F' or width == 'A':
      # Wide / Fullwidth / Ambiguous character
      length += 2
  return EvaluatorAtom(length, bool(a))

def foo_longer(track, memory, va_a_b):
  len_a = len(text_type(va_a_b[0].eval()))
  len_b = len(text_type(va_a_b[1].eval()))
  return len_a > len_b

def foo_lower(track, memory, va_a):
  a = va_a[0].eval()
  return EvaluatorAtom(text_type(a).lower(), bool(a))

def foo_longest(track, memory, va_a1_aN):
  longest = None
  longest_len = -1
  for each in va_a1_aN:
    current = each.eval()
    current_len = len(text_type(current))
    if current_len > longest_len:
      longest = current
      longest_len = current_len
  return longest

def foo_num(track, memory, va_n_len):
  n = va_n_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_n_len[1])
  value = None
  if (length > 0):
    value = text_type(__foo_va_conv_n(n)).zfill(length)
  else:
    value = text_type(__foo_int(__foo_va_conv_n(n)))
  return EvaluatorAtom(value, bool(n))

def foo_pad_universal(va_x_len_char, right):
  x = va_x_len_char[0].eval()
  length = __foo_va_conv_n_lazy_int(va_x_len_char[1])
  char = va_x_len_char[2]

  try:
    char = text_type(char.eval())[0]
  except AttributeError:
    pass

  if not char:
    return x

  x_str = text_type(x)
  x_len = len(x_str)

  if x_len < length:
    padded = None
    if not right:
      padded = x_str + char * (length - x_len)
    else:
      padded = char * (length - x_len) + x_str
    return EvaluatorAtom(padded, bool(x))
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
  a = text_type(va_pos_range_len_a_b[3].eval())
  b = text_type(va_pos_range_len_a_b[4].eval())
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
  return EvaluatorAtom(text_type(a) * n, bool(a))

def foo_replace_explode_recursive(a, va_a_bN_cN, i):
  if i + 1 < len(va_a_bN_cN):
    b = text_type(va_a_bN_cN[i].eval())
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
    c = text_type(va_a_bN_cN[i].eval())
    if not current:
      current = splits
    joined = c.join(current)
    return joined

def foo_replace(track, memory, va_a_bN_cN):
  a = va_a_bN_cN[0].eval()
  splits = foo_replace_explode_recursive(text_type(a), va_a_bN_cN, 1)
  result = foo_replace_join_recursive(splits, va_a_bN_cN, 2)
  # Truthfully, I have no idea if this is actually right, but it's probably good
  # enough for what it does. The sample cases check out, at least.
  return EvaluatorAtom(result, bool(a))

def foo_right(track, memory, va_a_len):
  a = va_a_len[0].eval()
  length = __foo_va_conv_n_lazy_int(va_a_len[1])
  a_str = text_type(a)
  a_len = len(a_str)
  if a_len == 0 or length >= a_len:
    return a
  elif length <= 0:
    return EvaluatorAtom('', bool(a))
  return EvaluatorAtom(a_str[a_len-length:], bool(a))

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
  return EvaluatorAtom(result, bool(n))

def foo_rot13(track, memory, va_a):
  a = va_a[0].eval()
  rot = codecs.encode(text_type(a), 'rot_13')
  return EvaluatorAtom(rot, bool(a))

def foo_shortest(track, memory, va_aN):
  shortest = None
  shortest_len = -1
  for each in va_aN:
    current = each.eval()
    current_len = len(text_type(current))
    if shortest_len == -1 or current_len < shortest_len:
      shortest = current
      shortest_len = current_len
  return shortest

def foo_strchr(track, memory, va_s_c):
  s = text_type(va_s_c[0].eval())
  c = text_type(va_s_c[1].eval())
  if c:
    c = c[0]
    for i, char in enumerate(s):
      if c == char:
        return EvaluatorAtom(i + 1, True)
  return EvaluatorAtom(0, False)

def foo_strrchr(track, memory, va_s_c):
  s = text_type(va_s_c[0].eval())
  c = text_type(va_s_c[1].eval())
  if c:
    c = c[0]
    for i, char in itertools.izip(reversed(xrange(len(s))), reversed(s)):
      if c == char:
        return EvaluatorAtom(i + 1, True)
  return EvaluatorAtom(0, False)

def foo_strstr(track, memory, va_s1_s2):
  s1 = text_type(va_s1_s2[0].eval())
  s2 = text_type(va_s1_s2[1].eval())
  found_index = 0
  if s1 and s2:
    found_index = s1.find(s2) + 1
  return EvaluatorAtom(found_index, bool(found_index))

def foo_strcmp(track, memory, va_s1_s2):
  s1 = va_s1_s2[0].eval()
  s2 = va_s1_s2[1].eval()
  if text_type(s1) == text_type(s2):
    return EvaluatorAtom(1, True)
  return EvaluatorAtom('', False)

def foo_stricmp(track, memory, va_s1_s2):
  s1 = va_s1_s2[0].eval()
  s2 = va_s1_s2[1].eval()
  if text_type(s1).lower() == text_type(s2).lower():
    return EvaluatorAtom(1, True)
  return EvaluatorAtom('', False)

def foo_substr(track, memory, va_s_m_n):
  s = va_s_m_n[0].eval()
  m = __foo_va_conv_n_lazy_int(va_s_m_n[1]) - 1
  n = __foo_va_conv_n_lazy_int(va_s_m_n[2])
  if n < m:
    return EvaluatorAtom('', bool(s))
  if m < 0:
    m = 0
  s_str = text_type(s)
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
  return EvaluatorAtom(result, bool(s))

def foo_strip_swap_prefix(va_x_prefixN, should_swap):
  x = va_x_prefixN[0].eval()
  x_str = text_type(x)
  x_str_lower = x_str.lower()

  for i in range(1, len(va_x_prefixN)):
    prefix = va_x_prefixN[i]

    try:
      prefix = text_type(prefix.eval())
    except AttributeError:
      pass

    if x_str_lower.startswith(prefix.lower() + ' '):
      prefix_len = len(prefix)
      result = x_str[prefix_len+1:]

      if should_swap:
        actual_prefix = x_str[0:prefix_len]
        result += ', ' + actual_prefix

      return EvaluatorAtom(result, bool(x))

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
  return EvaluatorAtom(text_type(s).strip(), bool(s))

def foo_tab_arity0(track, memory, va):
  return '\t'

def foo_tab_arity1(track, memory, va_n):
  n = __foo_va_conv_n_lazy_int(va_n[0])
  if n < 0 or n > 16:
    n = 16
  return '\t' * n

def foo_upper(track, memory, va_s):
  s = va_s[0].eval()
  return EvaluatorAtom(text_type(s).upper(), bool(s))

def foo_meta_arity1(track, memory, va_name):
  return foo_meta_sep_arity2(track, memory, va_name + [', '])

def foo_meta_arity2(track, memory, va_name_n):
  name = text_type(va_name_n[0].eval())
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
  name = text_type(va_name_sep[0].eval())

  sep = va_name_sep[1]
  try:
    sep = text_type(sep.eval())
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
  name = text_type(va_name_sep_lastsep[0].eval())
  sep = text_type(va_name_sep_lastsep[1].eval())
  lastsep = text_type(va_name_sep_lastsep[2].eval())
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
    name = text_type(each.eval())
    value = track.get(name)
    if not value:
      value = track.get(name.upper())
      if not value:
        return False
  return EvaluatorAtom(1, True)

def foo_meta_num(track, memory, va_name):
  name = text_type(va_name[0].eval())
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
  name_str = text_type(name)
  if name_str == '':
    return False
  value = memory.get(name_str)
  if value is not None and value is not False and value != '':
    return EvaluatorAtom(value, True)
  return False

def foo_put(track, memory, va_name_value):
  name = text_type(va_name_value[0].eval())
  value = va_name_value[1].eval()
  if name != '':
    memory[name] = text_type(value)
  return value

def foo_puts(track, memory, va_name_value):
  value = foo_put(track, memory, va_name_value)
  return bool(value)


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
    'crc32': {0: foo_false, 1: foo_crc32, 'n': foo_false},
    'crlf': {0: foo_crlf},
    'cut': {2: foo_cut},
    'directory': {1: foo_directory_1, 2: foo_directory_2, 'n': foo_false},
    'directory_path': {1: foo_directory_path, 'n': foo_false},
    'ext': {1: foo_ext, 'n': foo_false},
    'filename': {1: foo_filename, 'n': foo_false},
    'fix_eol': {1: foo_fix_eol_1, 2: foo_fix_eol_2, 'n': foo_false},
    # NOTE: $hex 1 should be foo_hex_1, but foobar2000 actually does nothing
    'hex': {2: foo_hex_2, 'n': foo_false},
    'insert': {3: foo_insert, 'n': foo_false},
    'left': {2: foo_left, 'n': foo_false},
    'len': {1: foo_len, 'n': foo_false},
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
        raise TitleformatRuntimeError(
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
          raise TitleformatRuntimeError(
              'Function "' + function + '" is undefined and the default'
              + ' handler has no definition for arity ' + arity)
    except KeyError:
      raise TitleformatRuntimeError(
          'The function with name "' + function + '" has no definition and no'
          + ' default handler has been defined')

def vinvoke(track, function, argv, memory={}):
  arity = len(argv)
  funcref = vlookup(function, arity)
  return vmarshal(funcref(track, memory, argv))

def vcallmarshal(atom):
  if atom is None:
    return ('', 0)

  return (text_type(atom), 1 if atom else 0)

def vcondmarshal(atom):
  if not atom:
    return ('', 0)

  return (text_type(atom), 1)

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
  __slots__ = (
      'formatter', 'track', 'current', 'conditional', 'depth', 'offset',
      'memory', 'value', 'evaluated')

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


class CurriedCompilation(object):
  __slots__ = 'lazycomp', 'track', 'lazyvalue'

  def __init__(self, lazycomp, track):
    self.lazycomp = lazycomp
    self.track = track
    self.lazyvalue = None

  def eval(self):
    if self.lazyvalue is None:
      self.lazyvalue = self.lazycomp(self.track)
    return self.lazyvalue

  @property
  def value(self):
    return self.eval()[0].value

  @property
  def truth(self):
    return self.eval()[0].truth

  @property
  def eval_count(self):
    return self.eval()[1]

  def __repr__(self):
    return 'curriedcomp(%s)' % repr(self.lazycomp)


def nop(*args, **kwargs):
  pass

def dbglog(fmt, *args, **kwargs):
  try:
    dbg(fmt(), **kwargs)
  except TypeError:
    if args:
      dbg(fmt % args, **kwargs)
    else:
      dbg(fmt, **kwargs)


class LazyCompilation(object):
  __slots__ = (
      'formatter', 'current', 'conditional', 'depth', 'offset', 'memory', 'log',
      'codeblock')

  def __init__(self,
      formatter, expression, conditional, depth, offset, track_memory,
      log=nop):
    self.formatter = formatter
    self.current = expression
    self.conditional = conditional
    self.depth = depth
    self.offset = offset
    self.memory = track_memory
    self.log = log
    self.codeblock = None

  def curry(self, track):
    return CurriedCompilation(self, track)

  def eval(self, track):
    if self.codeblock is None:
      self.log('lazily compiling block: %s', self.current, depth=self.depth)
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


class TitleformatError(Exception):
  pass


class TitleformatRuntimeError(TitleformatError):
  pass


def noncompatible_dbg_msg(message):
  return ('A non-compatible formatter would have raised an exception with'
      ' the message "%s"' % message)

def backwards_error(right, left_expected, offset, i):
  message = "Encountered '%s' with no matching '%s'" % (right, left_expected)
  message += " at position %s" % (offset + i)
  return message

def unterminated_error(token, expected, offset, i):
  message = "Unterminated %s; " % token
  if offset == 0:
    message += "reached end of input, "
  message += "expected '%s'" % expected
  if offset != 0:
    message += " at position %s" % (offset + i + 1)
  return message


state_errors = {
    "'": lambda o, i: unterminated_error('literal', "'", o, i),
    '%': lambda o, i: unterminated_error('variable', "%", o, i),
    '$': lambda o, i: unterminated_error('function', "(", o, i),
    '[': lambda o, i: unterminated_error('conditional', "]", o, i),
}


default_ccache = {}
next_token = re.compile(r"['%$\[\]()]")
next_inner_token = re.compile(r"['$(,)]")


class TitleFormatter(object):
  __slots__ = (
      'case_sensitive', 'magic', 'for_filename', 'compatible', 'log', 'ccache')

  def __init__(
      self, case_sensitive=False, magic=True, for_filename=False,
      compatible=True, log=nop, ccache=default_ccache):
    self.case_sensitive = case_sensitive
    self.magic = magic
    self.for_filename = for_filename
    self.compatible = compatible
    self.log = log
    self.ccache = ccache

  def format(self, track, fmt):
    evaluated_value = self.eval(track, fmt)
    if evaluated_value is not None:
      return text_type(evaluated_value)
    return None

  def eval(self, track, fmt, conditional=False, depth=0, offset=0,
      memory={}, compiling=False):
    if fmt in self.ccache:
      return self.ccache[fmt] if compiling else self.ccache[fmt](track)

    lit, conds, evals, i, ss, offstart = False, 0, 0, 0, 0, 0
    output = []
    compiled = []

    self.log('fresh call to eval(); format="%s" offset=%s',
        fmt, offset, depth=depth)
    self.log(lambda: 'helpful char guide:           ' + (
        ''.join([str(x) * 9 + str(x + 1)
                 for x in range(0, 10)])[0:len(fmt)]), depth=depth)
    self.log(lambda: 'helpful char guide:           ' + (
        '1234567890' * (len(fmt) // 10 + 1))[0:len(fmt)], depth=depth)

    try:
      while 1:
        c = fmt[i]
        i += 1
        if c == "'":
          if fmt[i] == "'":
            ss = 1
            i += 1  # Fall through
          else:
            start = i
            i = fmt.index("'", i) + 1
            output.append(fmt[start:i-1])
            continue
        elif c == '%':
          if fmt[i] == '%':
            ss = 1
            i += 1  # Fall through
          else:
            if compiling and output:
              compiled.append(lambda t, output=''.join(output): (output, 0))
              output.clear()
            self.log('begin parsing variable at char %s', i, depth=depth)
            start = i
            i = fmt.index('%', i)
            if compiling:
              compiled.append(
                  lambda t, self=self, current=fmt[start:i], i=i, depth=depth:
                    self.handle_var_resolution(t, current, i, depth))
            else:
              val, edelta = self.handle_var_resolution(track, fmt[start:i], i, depth)
              output.append(val)
              evals += edelta
            i += 1
            continue
        elif c == '$':
          if fmt[i] == '$':
            ss = 1
            i += 1  # Fall through
          else:
            i, evals, offset, offstart = self.function(
                track, fmt, i, depth, compiling, compiled, output, evals,
                offset, offstart, memory)
            continue
        elif c == '[':
          i, evals = self.conditional(
              track, fmt, i, depth, compiling, compiled, output, evals,
              offset, offstart, memory)
          continue
        elif c == ']':
          if self.compatible:
            self.log(lambda: noncompatible_dbg_msg(
              backwards_error(']', '[', offset, i)), depth=depth)
            break
          else:
            raise TitleformatError(backwards_error(']', '[', offset, i))
        elif (c == '(' or c == ')') and self.compatible:
          # This seems like a foobar bug; parens shouldn't do anything outside
          # of a function call, but foobar will just explode if it sees a lone
          # paren floating around in the input.
          break
        rest = fmt[i-1:]
        match = next_token.search(rest, ss)
        if match:
          output.append(rest[:match.end() - 1])
          ss = 0
          i += match.end() - 2
        else:
          i = len(fmt)
          output.append(rest)
          break
    except (IndexError, ValueError, StopIteration) as e:
      self.log('Caught %s, ignoring: %s', e.__class__.__name__, e)
      pass

    # At this point, we have reached the end of the input.
    if i < len(fmt):
      if self.compatible:
        self.log(lambda: state_errors[c](offset, i), depth=depth)
      else:
        raise TitleformatError(state_errors[c](offset, i))

    if compiling:
      if output:
        # We need to flush the output buffer to a lambda once more
        compiled.append(lambda t, output=''.join(output): (output, 0))
      self.log('eval() compiled the input into %s blocks', len(compiled),
          depth=depth)
      self.ccache[fmt] = (lambda t, self=self, compiled=compiled, depth=depth:
        self.invoke_jit_eval(compiled, depth, t))
      return self.ccache[fmt]

    output = ''.join(output)

    if not depth and self.for_filename:
      output = foobar_filename_escape(output)

    result = EvaluatorAtom(output, bool(evals))

    self.log(lambda: 'eval() is returning: ' + repr(result), depth=depth)

    return result

  def invoke_jit_eval(self, compiled, depth, track):
    output = ''
    eval_count = 0

    for c in compiled:
      c_output, c_count = c(track)
      output += c_output
      eval_count += c_count

    self.log('JIT evaluation complete, output: %s', output, depth=depth)

    return EvaluatorAtom(output, eval_count != 0)

  @staticmethod
  def flush_compilation(compiling, compiled, output):
    if compiling and output:
      compiled.append(lambda t, output=''.join(output): (output, 0))
      output.clear()

  def function(
      self, track, fmt, i, depth, compiling, compiled, output, evals,
      offset, offstart, memory):
    if compiling and output:
      compiled.append(lambda t, output=''.join(output): (output, 0))
      output.clear()
    self.log('begin parsing function at char %s', i, depth=depth)
    state, current, argparens, innerparens = 0x0, '', 0, 0
    foffstart = i + 1
    current_argv = []
    while 1:
      c = fmt[i]
      i += 1
      if c.isalnum() or c == '_':
        current += c
      elif c == '(':
        self.log(
            'parsed function "%s" at char %s', current, i, depth=depth)
        current_fn = current
        current, state = '', 0x1
        off = i + 1
        break
      else:
        if self.compatible:
          break
        raise TitleformatError(
            "Illegal token '%s' encountered at char %s" % (c, i))
    if not state:
      raise StopIteration()
    while 1:
      c = fmt[i]
      i += 1
      if not argparens:
        if c == ',':
          current, arg = self.parse_fn_arg(track, current_fn,
              current, current_argv, c, i, depth,
              offset + offstart, memory, compiling)
          current_argv.append(arg)
          offstart = i + 1
          continue
        elif c == ')':
          if current != '' or len(current_argv) > 0:
            current, arg = self.parse_fn_arg(track, current_fn,
                current, current_argv, c, i, depth,
                offset + offstart, memory, compiling)
            current_argv.append(arg)

          self.log(
              'finished parsing function arglist at char %s', i,
              depth=depth)

          if compiling:
            compiled.append(self.compile_fn_call(
              current_fn, current_argv, depth,
              offset + foffstart))
          else:
            val, edelta = self.handle_fn_invocation(
                track, current_fn, current_argv, depth, offset + foffstart)

            if val:
              output.append(val)

            evals += edelta

            self.log('evaluation count is now %s', evals,
                depth=depth)

          state = 0x0
          break
      if c == "'":
        start = i
        i = fmt.index("'", i) + 1
        current += fmt[start-1:i]
      elif c == '$':
        self.log(
            'stopped evaluation for function in arg at char %s', i,
            depth=depth)
        current += c
        innerparens = 0
        while 1:  # Parse the nested function
          c = fmt[i]
          i += 1
          current += c
          if c == '(':
            innerparens += 1
          elif c == ')':
            innerparens -= 1
            if not innerparens:
              # Stop skipping evaluation.
              self.log('resumed evaluation at char %s', i, depth=depth)
              break
            elif innerparens < 0:
              if self.compatible:
                self.log(lambda: noncompatible_dbg_msg(
                  backwards_error(')', '(', offset, i)), depth=depth)
                raise StopIteration()
              else:
                raise TitleformatError(backwards_error(')', '(', offset, i))
      elif c == '(':
        argparens += 1
        self.log('detected paren poisoning at char %s', i,
            depth=depth)
        while 1:  # Paren poisoning
          c = fmt[i]
          if c == '(':
            argparens += 1
          elif not argparens:
            if c in ',)':
              self.log('stopped paren poisoning at char %s', i,
                  depth=depth)
              # Resume normal execution
              break
          elif c == ')':
            argparens -= 1
          i += 1  # Only need to do this if we're not actually breaking
      #elif c == ')':
        # I think this isn't possible anymore
        #argparens -= 1
        #current += c
      else:
        start = i - 1
        while fmt[i] not in "'$(,)":
          i += 1
        current += fmt[start:i]
        # I need to understand why the match implementation is not faster
        #match = next_inner_token.search(fmt, i)
        #if not match:
          #raise StopIteration()
        #i = match.start()
        #current += fmt[match.pos-1:i]
    if state:
      raise StopIteration()
    return i, evals, offset, offstart

  def conditional(
      self, track, fmt, i, depth, compiling, compiled, output, evals,
      offset, offstart, memory):
    TitleFormatter.flush_compilation(compiling, compiled, output)
    self.log('begin parsing conditional at char %s', i, depth=depth)
    current, lit, conds = '', False, 0
    while 1:
      c, start, i = fmt[i], i, i + 1
      if lit:
        current += c
        if c == "'":
          self.log('leaving conditional literal mode at char %s', i,
              depth=depth)
          lit = False
      elif c == '[':
          self.log(
              'found a pending conditional at char %s', i, depth=depth)
          conds += 1
          self.log('conditional parse count now %s',
              conds, depth=depth)
          current += c
      elif c == ']':
        if conds > 0:
          self.log('found a terminating conditional at char %s', i,
              depth=depth)
          conds -= 1
          self.log('conditional parse count now %s at char %s',
              conds, i, depth=depth)
          current += c
        else:
          self.log('finished parsing conditional at char %s', i,
              depth=depth)

          if compiling:
            compiled_cond = self.eval(
                None, current, True, depth + 1, offset + offstart,
                memory, True)
            compiled.append(lambda t, c=compiled_cond: vcondmarshal(c(t)))
          else:
            evaluated_value = self.eval(
                track, current, True, depth + 1, offset + offstart,
                memory)

            self.log('value is: %s', evaluated_value, depth=depth)
            if evaluated_value:
              output.append(str(evaluated_value))
              evals += 1
            self.log('evaluation count is now %s', evals,
                depth=depth)

          return i, evals
      elif c == "'":
        self.log('entering conditional literal mode at char %s', i,
            depth=depth)
        current += c
        lit = True
      else:
        while fmt[i] not in set(("'", '[', ']')):
          i += 1
        current += fmt[start:i]

  def parse_fn_arg(self, track, current_fn, current, current_argv, c, i,
      depth=0, offset=0, memory={}, compiling=False):
    next_current = ''

    self.log('finished argument %s for function "%s" at char %s: %s',
        len(current_argv), current_fn, i, current, depth=depth)

    if compiling:
      lazy = LazyCompilation(
          self, current, False, depth + 1, offset, memory, self.log)
      return (next_current, lazy)

    # The lazy expression will parse the current buffer if it's ever needed.
    lazy = LazyExpression(
        self, track, current, False, depth + 1, offset, memory)
    return (next_current, lazy)

  def handle_var_resolution(self, track, field, i, depth):
    evaluated_value = self.resolve_variable(track, field, i, depth)

    self.log('value is: %s', evaluated_value, depth=depth)

    return ((str(evaluated_value) if evaluated_value is not True else '', 1)
            if evaluated_value or evaluated_value == ''
            # This is the case where no evaluation happened but there is still a
            # string value (that won't output conditionally).
            else (str(evaluated_value), 0)
            if evaluated_value is not None and evaluated_value is not False
            else ('?', 0))

  def resolve_variable(self, track, field, i, depth):
    if not self.case_sensitive:
      field = field.upper()

    resolved = None

    if not self.magic:
      resolved = track.get(field)
    else:
      resolved = self.magic_resolve_variable(track, field, depth)

    if resolved is None or resolved is False:
      return None

    if self.for_filename:
      resolved = re.sub('[\\\\/:|]', '-', resolved)

    return EvaluatorAtom(resolved, True)

  def magic_resolve_variable(self, track, field, depth):
    field_lower = field.lower()
    self.log('checking %s for magic mappings', field_lower, depth=depth)
    if field_lower in magic_mappings:
      mapping = magic_mappings[field_lower]
      if not mapping:
        self.log('mapping "%s" is not valid', field_lower, depth=depth)
        return track.get(field)
      else:
        # First try to call it -- the mapping can be a function.
        try:
          magically_resolved = mapping(self, track)
          self.log('mapped %s via function mapping', field_lower, depth=depth)
          return magically_resolved
        except TypeError:
          # That didn't work. It's a list.
          self.log('mapping "%s" is not a function', field_lower, depth=depth)
          for each in mapping:
            self.log('attempting to map "%s"', each, depth=depth)
            if each in track:
              return track.get(each)
            if self.case_sensitive:
              each_lower = each.lower()
              self.log('attempting to map "%s"', each_lower, depth=depth)
              if each_lower in track:
                return track.get(each_lower)

          # Still couldn't find it.
          self.log('mapping %s failed to map magic variable', field_lower,
              depth=depth)
          return track.get(field)

    self.log('mapping %s not found in magic variables', field_lower,
        depth=depth)
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

    self.log('finished invoking function %s, value: %s',
        current_fn, repr(fn_result), depth=depth)

    return vcallmarshal(fn_result)

  def invoke_function(
      self, track, function_name, function_argv, depth=0, offset=0, memory={}):
    self.log('invoking function %s, args %s', function_name, function_argv,
        depth=depth)
    curried_argv = [
        x.curry(track) if hasattr(x, 'curry') else x
        for x in function_argv]
    return vinvoke(track, function_name, curried_argv, memory)

