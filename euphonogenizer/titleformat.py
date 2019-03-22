#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from functools import reduce
from typing import Any, Callable, List, Tuple

import binascii
import codecs
import contextvars
import itertools
import os
import platform
import random
import re
import sys
import unicodedata


class EvaluatorAtom(object):
  __slots__ = 'value', 'truth'

  def __init__(self, value, truth=False):
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

  def __int__(self):
    return intify(self.value)

  def __str__(self):
    return str(self.value)

  def __bytes__(self):
    return bytes(self.value, 'utf-8')

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


_ctx_track = contextvars.ContextVar('track', default=None)
_ctx_memory = contextvars.ContextVar('memory', default=None)


class _TitleformatContextManager(object):
  __slots__ = 'track', 'memory', 'track_token', 'memory_token'

  def __init__(self, track, memory):
    self.track = track
    self.memory = memory
    self.track_token, self.memory_token = None, None

  def __enter__(self):
    self.track_token = _ctx_track.set(self.track)
    self.memory_token = _ctx_memory.set(self.memory)

  def __exit__(self, exc_type, exc_val, exc_tb):
    _ctx_track.reset(self.track_token)
    _ctx_memory.reset(self.memory_token)


def tfcontext(track=None, memory=None):
  return _TitleformatContextManager(track, memory)


def magic_map_filename(track):
  value = track.get('@')
  if value is not None and value is not False:
    return str(foo_filename(None, None, [value]))
  return None


def magic_map_filename_ext(track):
  value = track.get('@')
  if value is not None and value is not False:
    filename = str(foo_filename(None, None, [value]))
    ext = str(foo_ext(None, None, [value]))
    if ext:
      filename += '.' + ext
    return filename
  return None


def magic_map_track_artist(track):
  artist = resolve_magic_var(track, 'artist')
  album_artist = resolve_magic_var(track, 'album artist')
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


def magic_map_tracknumber(track):
  value = __find_tracknumber(track)
  if value is not None and value is not False:
    return value.zfill(2)
  return None


def magic_map_track_number(track):
  value = __find_tracknumber(track)
  if value is not None and value is not False:
    return str(int(value))
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


__sub_int_trailing = re.compile(r'(?<=[0-9])[^0-9].*$').sub


def intify(whatever: Any) -> int:
  if whatever in (None, ''):
    return 0
  if callable(whatever):
    try:
      return int(whatever())
    except:
      try:
        return int(__sub_int_trailing('', whatever()))
      except:
        pass
  else:
    try:
      return int(whatever)
    except:
      try:
        return int(__sub_int_trailing('', whatever))
      except:
        pass
  return 0


def atomize(obj):
  if isinstance(obj, EvaluatorAtom):
    return obj
  elif callable(obj):
    return atomize_noncallable(obj())
  elif isinstance(obj, bool):
    return EvaluatorAtom(None, obj)
  return EvaluatorAtom(obj)


def atomize_noncallable(obj):
  if isinstance(obj, EvaluatorAtom):
    return obj
  elif isinstance(obj, bool):
    return EvaluatorAtom(None, obj)
  return EvaluatorAtom(obj)


def atomize_int(obj):
  if isinstance(obj, EvaluatorAtom):
    obj.value = intify(obj.value)
    return obj
  elif isinstance(obj, int):
    return EvaluatorAtom(obj)
  elif callable(obj):
    return atomize_int_noncallable(obj())
  return EvaluatorAtom(intify(obj))


def atomize_int_noncallable(obj):
  if isinstance(obj, EvaluatorAtom):
    obj.value = intify(obj.value)
    return obj
  elif isinstance(obj, int):
    return EvaluatorAtom(obj)
  return EvaluatorAtom(intify(obj))


def boolify(obj):
  if isinstance(obj, (EvaluatorAtom, bool)):
    return bool(obj)
  elif callable(obj):
    return boolify_noncallable(obj())
  return False


def boolify_noncallable(obj):
  if isinstance(obj, (EvaluatorAtom, bool)):
    return bool(obj)
  return False


def stringify(obj):
  if isinstance(obj, (EvaluatorAtom, str, int)):
    return str(obj)
  elif callable(obj):
    return stringify_noncallable(obj())
  return ''


def stringify_noncallable(obj):
  if isinstance(obj, (EvaluatorAtom, str, int)):
    return str(obj)
  return ''


def foo_true(*unused_va):
  return True


def foo_false(*unused_va):
  pass


def foo_zero(*unused_va):
  return '0'


def foo_one(*unused_va):
  return '1'


def foo_nop(*va):
  return atomize(va[0])


def foo_unknown(*unused_va):
  return '[UNKNOWN FUNCTION]'


def foo_nnop(*va):
  val = atomize_int(va[0])
  val.value = str(val.value)
  return val


def foo_bnop(*va):
  return boolify(va[0])


def foo_invalid(fn):
  error_str = f'[INVALID ${fn.upper()} SYNTAX]'
  return lambda *args: error_str


def foo_if__2(cond, then_case):
  if boolify(cond):
    return atomize(then_case)


def foo_if__3(cond, then_case, else_case):
  return atomize(then_case) if boolify(cond) else atomize(else_case)


def foo_if2(a, else_case):
  return atomize(a) or atomize(else_case)


def foo_if3(*a1_a2_aN_else):
  for i in range(len(a1_a2_aN_else) - 1):
    aN = atomize(a1_a2_aN_else[i])
    if aN:
      return aN
  return atomize(a1_a2_aN_else[-1])


def foo_ifequal(n1, n2, then_case, else_case):
  if intify(n1) == intify(n2):
    return atomize(then_case)
  else:
    return atomize(else_case)


def foo_ifgreater(n1, n2, then_case, else_case):
  if intify(n1) > intify(n2):
    return atomize(then_case)
  else:
    return atomize(else_case)


def foo_iflonger(s, n, then_case, else_case):
  if len(atomize(s)) > intify(n):
    return atomize(then_case)
  return atomize(else_case)


def foo_select(*n_a1_aN):
  n = intify(n_a1_aN[0])
  if n > 0 and n <= len(n_a1_aN) - 1:
    return atomize(n_a1_aN[n])


def foo_select_2(n, a1):
  # This is just here as an optimization for poorly-written titleformats.
  if intify(n) == 1:
    return atomize(a1)


def foo_add(*aN):
  value = atomize_int(aN[0])
  for a in aN[1:]:
    value += atomize_int(a)
  return value


def foo_div(*aN):
  value = atomize_int(aN[0])
  for a in aN[1:]:
    value //= atomize_int(a)
  return value


def foo_greater(a, b):
  return intify(a) > intify(b)


def __foo_max_logic(a, b):
  if a > b:
    a |= b
    return a
  b |= a
  return b


def foo_max(a, b):
  return __foo_max_logic(atomize_int(a), atomize_int(b))


def foo_maxN(*aN):
  return reduce(__foo_max_logic, map(atomize_int, aN))


def __foo_min_logic(a, b):
  if a < b:
    a |= b
    return a
  b |= a
  return b


def foo_min(a, b):
  return __foo_min_logic(atomize_int(a), atomize_int(b))


def foo_minN(*aN):
  return reduce(__foo_min_logic, map(atomize_int, aN))


def foo_mod(a, b):
  a = atomize_int(a)
  a %= atomize_int(b)
  return a


def foo_modN(*aN):
  value = atomize_int(aN[0])
  for a in aN[1:]:
    value %= atomize_int(a)
  return value


def foo_mul(*aN):
  value = atomize_int(aN[0])
  for a in aN[1:]:
    value *= atomize_int(a)
  return value


def foo_muldiv(a, b, c):
  c = atomize_int(c)
  c.truth = True  # Truth behavior confirmed by experimentation.
  if c.value == 0:
    # This is real Foobar behavior for some reason, probably a bug.
    c.value = -1
    return c
  a = atomize_int(a)
  a *= atomize_int(b)
  a //= c
  return a


def foo_rand():
  random.seed()
  return random.randint(0, sys.maxint)


def foo_sub(*aN):
  value = atomize_int(aN[0])
  for a in aN[1:]:
    value -= atomize_int(a)
  return value


def foo_and(*expr):
  for each in expr:
    if not boolify(each):
      return False
  return True


def foo_or(*expr):
  for each in expr:
    if boolify(each):
      return True
  return False


def foo_not(expr):
  return not boolify(expr)


def foo_xor(*expr):
  r = False
  for each in expr:
    r ^= boolify(each)
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


def foo_abbr1(x):
  x = atomize(x)
  x.value = foo_abbr(str(x))
  return x


def foo_abbr2(x, length):
  x = atomize(x)
  length = intify(length)
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


def foo_ansi(x):
  x = atomize(x)
  # Doing the conversion this way will probably not produce the same output with
  # wide characters as Foobar, which produces two '??' instead of one. I don't
  # have a multibyte build of Python lying around right now, so I can't
  # confirm at the moment. But really, it probably doesn't matter.
  x.value = str(str(x)
      .encode('windows-1252', '__foo_ansi_replace'), 'windows-1252', 'replace')
  return x


def foo_ascii(x):
  x = atomize(x)
  x.value = (str(x)
      .encode('ascii', '__foo_ascii_replace')
      .decode('utf-8', 'replace'))
  return x


__caps_sep = r'^|[ /|(,)[\]\\]'
__caps_word = r'[^ /|(,)[\]\\]'
__caps_sub_pattern = re.compile(
    f'({__caps_sep})({__caps_word})({__caps_word}*)')
__caps2_sub_pattern = re.compile(
    f'({__caps_sep})({__caps_word})')

del __caps_sep
del __caps_word


def __caps_sub_repl(match):
  return f'{match.group(1)}{match.group(2).upper()}{match.group(3).lower()}'


def __caps2_sub_repl(match):
  return f'{match.group(1)}{match.group(2).upper()}'


def foo_caps(x):
  x = atomize(x)
  x.value = __caps_sub_pattern.sub(__caps_sub_repl, str(x))
  return x


def foo_caps2(x):
  x = atomize(x)
  x.value = __caps2_sub_pattern.sub(__caps2_sub_repl, str(x))
  return x


def foo_char(x):
  x = intify(x)
  if x <= 0:
    return ''
  if x > 1048575:
    # FB2k only supports doing this with 20-bit integers for some reason.
    # In the future, we might want a better, non-compliant implementation.
    return '?'
  try:
    return chr(x)
  except ValueError:
    # Also happens when using a narrow Python build
    return '?'
  except OverflowError:
    return ''


def foo_crc32(x):
  x = atomize(x)
  x.value = binascii.crc32(bytes(x))
  return x


def foo_crlf():
  return '\r\n'


# foo_cut is the same as foo_left; see definition for it below


def foo_directory_1(x):
  x = atomize(x)
  # RFC 8089 allows pipe characters to be used instead of the colons in the
  # drive construct, and Foobar obeys this. For more information, see:
  # https://tools.ietf.org/html/rfc8089#appendix-E.2.2
  parts = re.split('[\\\\/:|]', str(x))
  x.value = '' if len(parts) < 2 else parts[-2]
  return x


def foo_directory_2(x, n):
  x = atomize(x)
  n = intify(n)
  if n <= 0:
    x.value = ''
    return x
  parts = re.split('[\\\\/:|]', str(x))
  parts_len = len(parts)
  x.value = '' if n >= parts_len or parts_len < 2 else parts[parts_len - n - 1]
  return x


def foo_directory_path(x):
  x = atomize(x)
  parts = re.split('[\\\\/:|]', str(x)[::-1], 1)
  x.value = '' if len(parts) < 2 else parts[1][::-1]
  return x


def foo_ext(x):
  x = atomize(x)

  _, delimiter, ext = str(x).rpartition('.')

  if not delimiter or any(c in '/\\|:' for c in ext):
    return ''

  x.value = ext.partition('?')[0]
  return x


def foo_filename(x):
  x = atomize(x)
  parts = re.split('[\\\\/:|]', str(x))
  x.value = parts[-1].partition('?')[0].rsplit('.', 1)[0]
  return x


def foo_fix_eol(x, indicator=' (...)'):
  x = atomize(x)
  parts = re.split('[\r\n]', str(x), 1)

  if len(parts) > 1:
    x.value = parts[0] + stringify(indicator)

  return x


def foo_hex(n, length=0):
  # While technically in the documentation, $hex(n) doesn't actually do anything
  # as of foobar2000 1.4.2. This is probably a bug that no one has noticed. This
  # documentation-based implementation is provided for non-compliant uses.
  n = atomize_int(n)
  length = intify(length)

  n.value = hex(
      max(-0x8000000000000000, min(int(n), 0x7FFFFFFFFFFFFFFF)
        ) % 0x100000000)[2:].upper().zfill(max(0, min(length, 32)))

  return n


def foo_insert(a, b, n):
  a = atomize(a)
  b = stringify(b)
  n = intify(n)

  if n < 0:
    a.value += b
  else:
    a.value = ''.join([a.value[0:n], b, a.value[n:]])

  return a


def foo_left(a, length):
  a = atomize(a)
  length = intify(length)

  if length >= 0:
    a.value = a.value[0:length]

  return a


foo_cut = foo_left  # These are the same, so just alias for completeness


def foo_len(a):
  a = atomize(a)
  a.value = len(a)
  return a

foo_len2 = foo_len

# This function is not used anywhere, as since at least Foobar 1.4.2, $len2 does
# exactly the same thing as $len. This version of the function is implemented
# according to the HydrogenAudio titleformat documentation.
def _foo_len2_old(a):
  a = atomize(a)
  length = 0
  str_a = str(a)
  for c in str_a:
    width = unicodedata.east_asian_width(c)
    if width == 'N' or width == 'Na' or width == 'H':
      # Narrow / Halfwidth character
      length += 1
    elif width == 'W' or width == 'F' or width == 'A':
      # Wide / Fullwidth / Ambiguous character
      length += 2
  a.value = length
  return a


def foo_longer(a, b):
  return len(stringify(a)) > len(stringify(b))


def foo_lower(a):
  a = atomize(a)
  a.value = str(a).lower()
  return a


def foo_longest(*a1_aN):
  longest = None
  longest_len = -1
  for each in a1_aN:
    current = atomize(each)
    current_len = len(current)
    if current_len > longest_len:
      longest = current
      longest_len = current_len
  return longest


# A non-compatible version of this would be nice, where it could ignore the
# Foobar bugs and limits and just do its own thing in a simple way.
def foo_num(n, length):
  n = atomize(n)
  int_n = int(n)
  bugged_sign = int_n <= -9223372036854775808
  int_n = max(-9223372036854775808, min(9223372036854775807, int_n))
  length = intify(length)
  length = (min(32, length)
            if length >= 0 else
            max(0, min(32, length + 9223372036854775808)))
  if bugged_sign:
    ns = str(int_n)
    n.value = f"-{'0' * (length - len(ns) - 1)}{ns}"
  else:
    n.value = str(int_n).zfill(length)
  return n


def _do_foo_pad(x, length, char, pad):
  x = atomize(x)
  length = intify(length)
  char = stringify(char)[0]

  if not char:
    return x

  x_str = str(x)
  x_len = len(x_str)

  if x_len < length:
    x.value = pad(x_str, x_len, length, char)
  return x


def _padleft(x_str: str, x_len: int, length: int, char: str) -> str:
  return x_str + char * (length - x_len)


def _padright(x_str: str, x_len: int, length: int, char: str) -> str:
  return char * (length - x_len) + x_str


def foo_pad(x, length, char=' '):
  return _do_foo_pad(x, length, char, _padleft)


def foo_pad_right(x, length, char=' '):
  return _do_foo_pad(x, length, char, _padright)


def foo_padcut(x, length):
  return foo_pad(foo_cut(x, length), length)


def foo_padcut_right(x, length):
  return foo_pad_right(foo_cut(x, length), length)


def _foo_progress_for(pos, range_value, length, a, b, proc):
  pos = atomize_int(pos)
  range_value = atomize_int(range_value)
  length = intify(length)
  a = stringify(a)
  b = stringify(b)
  pos_int = int(pos)
  range_int = int(range_value)

  if range_int < 0:
    range_int = 0

  if pos_int > range_int:
    pos_int = max(range_int, 1)
  elif pos_int < 0:
    pos_int = 0

  pos.value = proc(pos_int, range_int, length, a, b)
  pos.truth = foo_and(pos, range_value)
  return pos


def _do_foo_progress(
    pos_int: int, range_int: int, length: int, a: str, b: str) -> str:
  if range_int == 0:
    if pos_int > 0:
      return b * (length - 1) + a
    else:
      return a + b * (length - 1)
  else:
    cursor_pos = (pos_int * length + range_int // 2) // range_int

    # This appears to be a foobar2000 bug. The cursor position is off by one.
    # Remove this line if the bug is ever fixed.
    cursor_pos += 1

    if cursor_pos <= 0:
      cursor_pos = 1
    elif cursor_pos >= length:
      cursor_pos = length

    return b * (cursor_pos - 1) + a + b * (length - cursor_pos)


def _do_foo_progress2(
    pos_int: int, range_int: int, length: int, a: str, b: str) -> str:
  if length < 1:
    length = 1

  if range_int == 0:
    if pos_int > 0:
      return a * length
    else:
      return b * length
  else:
    left_count = int(round(pos_int * length / range_int))

    return a * left_count + b * (length - left_count)


def foo_progress(pos, range_value, length, a, b):
  return _foo_progress_for(pos, range_value, length, a, b, _do_foo_progress)


def foo_progress2(pos, range_value, length, a, b):
  return _foo_progress_for(pos, range_value, length, a, b, _do_foo_progress2)


def foo_repeat(a, n):
  a = atomize(a)
  a.value = str(a) * intify(n)
  return a


def foo_replace_explode_recursive(a, a_bN_cN, i):
  if i + 1 < len(a_bN_cN):
    b = stringify(a_bN_cN[i])
    splits = a.split(b)
    current = []
    for each in splits:
      sub_splits = foo_replace_explode_recursive(each, a_bN_cN, i + 2)
      if sub_splits is not None:
        current.append(sub_splits)
    if not current:
      current = splits
    return current


def foo_replace_join_recursive(splits, a_bN_cN, i):
  if i < len(a_bN_cN):
    current = []
    for each in splits:
      sub_joined = foo_replace_join_recursive(each, a_bN_cN, i + 2)
      if sub_joined is not None:
        current.append(sub_joined)
    c = stringify(a_bN_cN[i])
    if not current:
      current = splits
    joined = c.join(current)
    return joined


def foo_replace(*a_bN_cN):
  a = atomize(a_bN_cN[0])
  splits = foo_replace_explode_recursive(str(a), a_bN_cN, 1)
  result = foo_replace_join_recursive(splits, a_bN_cN, 2)
  # Truthfully, I have no idea if this is actually right, but it's probably good
  # enough for what it does. The sample cases check out, at least.
  return EvaluatorAtom(result, bool(a))


def foo_right(a, length):
  a = atomize(a)
  length = intify(length)
  a_str = str(a)
  a_len = len(a_str)
  if a_len == 0 or length >= a_len:
    return a
  elif length <= 0:
    a.value = ''
  else:
    a.value = a_str[a_len-length:]
  return a


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


def foo_roman(n):
  n = atomize(n)
  n_int = int(n)
  result = ''
  if n_int > 0 and n_int <= 100000:
    for numeral, value in __roman_numerals:
      while n_int >= value:
        result += numeral
        n_int -= value
  n.value = result
  return n


def foo_rot13(a):
  a = atomize(a)
  a.value = codecs.encode(str(a), 'rot_13')
  return a


def foo_shortest(*aN):
  shortest = None
  shortest_len = -1
  for each in aN:
    current = atomize(each)
    current_len = len(current)
    if shortest_len == -1 or current_len < shortest_len:
      shortest = current
      shortest_len = current_len
  return shortest


def foo_strchr(s, c):
  # TODO: Need to check if 's' should be evaluated if not c; side effects?
  s = atomize(s)
  c = stringify(c)
  if c:
    c = c[0]
    # TODO: There is a far better implementation of this using str.index()
    for i, char in enumerate(str(s)):
      if c == char:
        s.value = i + 1
        s.truth = True
        return s
  s.value, s.truth = 0, False
  return s


def foo_strrchr(s, c):
  # TODO: Same here, should 's' be evaluated if not c?
  s = atomize(s)
  c = stringify(c)
  if c:
    c = c[0]
    sstr = str(s)
    for i, char in itertools.izip(reversed(xrange(len(sstr))), reversed(sstr)):
      if c == char:
        s.value = i + 1
        s.truth = True
        return s
  s.value, s.truth = 0, False
  return s


def foo_strstr(s1, s2):
  s1 = atomize(s1)
  s2 = stringify(s2)
  s1_str = str(s1)
  s1.value = s1_str.find(s2) + 1 if s1_str and s2 else 0
  s1.truth = bool(s1.value)
  return s1


def foo_strcmp(s1, s2):
  s1 = atomize(s1)
  s2 = stringify(s2)
  if str(s1) == s2:
    s1.value, s1.truth = 1, True
  else:
    s1.value, s1.truth = '', False
  return s1


def foo_stricmp(s1, s2):
  s1 = atomize(s1)
  s2 = stringify(s2)
  if str(s1).lower() == s2.lower():
    s1.value, s1.truth = 1, True
  else:
    s1.value, s1.truth = '', False
  return s1


def foo_substr(s, m, n):
  s = atomize(s)
  m = intify(m) - 1
  n = intify(n)
  if n < m:
    return EvaluatorAtom('', bool(s))
  if m < 0:
    m = 0
  s_str = str(s)
  s_len = len(s_str)
  if n > s_len:
    n = s_len
  if m == 0 and n == s_len:
    return s
  elif n == s_len:
    s.value = s_str[m:]
  else:
    s.value = s_str[m:n]
  return s


def _foo_strip_swap_prefix(x, prefixN, should_swap):
  x = atomize(x)
  x_str = str(x)
  x_str_lower = x_str.lower()

  for prefix in prefixN:
    prefix = stringify(prefix)

    if x_str_lower.startswith(prefix.lower() + ' '):
      prefix_len = len(prefix)
      x.value = x_str[prefix_len+1:]

      if should_swap:
        x.value = f'{x.value}, {x_str[0:prefix_len]}'

  return x


def foo_stripprefix__1(x):
  return _foo_strip_swap_prefix(x, ('A', 'The'), False)


def foo_stripprefix_arityN(x, *prefixN):
  return _foo_strip_swap_prefix(x, prefixN, False)


def foo_swapprefix__1(x):
  return _foo_strip_swap_prefix(x, ('A', 'The'), True)


def foo_swapprefix_arityN(x, *prefixN):
  return _foo_strip_swap_prefix(x, prefixN, True)


def foo_trim(s):
  s = atomize(s)
  s.value = str(s).strip()
  return s


def foo_tab__0():
  return '\t'


def foo_tab__1(n):
  n = intify(n)
  if n < 0 or n > 16:
    n = 16
  return '\t' * n


def foo_upper(s):
  s = atomize(s)
  s.value = str(s).upper()
  return s


def foo_meta__1(name, track=None):
  return foo_meta_sep__2(name, ', ', track=track)


def foo_meta__2(name, n, track=None):
  name = atomize(name)
  n = intify(n)
  if n < 0:
    return False
  if track is None:
    track = _ctx_track.get()
  name_str = str(name)
  value = track.get(name_str)
  if not value:
    value = track.get(name_str.upper())
    if not value:
      return False
  if isinstance(value, list):
    if n >= len(value):
      return False
    value = value[n]
  elif n != 0:
    return False
  name.value = value
  name.truth = True
  return name


def foo_meta_sep__2(name, sep, track=None):
  name = atomize(name)
  sep = stringify(sep)
  name_str = str(name)
  if track is None:
    track = _ctx_track.get()
  value = track.get(name_str)
  if not value:
    value = track.get(name_str.upper())
    if not value:
      return False
  if isinstance(value, list):
    value = sep.join(value)
  name.value = value
  name.truth = True
  return name


def foo_meta_sep__3(name, sep, lastsep, track=None):
  name = atomize(name)
  name_str = str(name)
  sep = stringify(sep)
  lastsep = stringify(lastsep)
  if track is None:
    track = _ctx_track.get()
  value = track.get(name_str)
  if not value:
    value = track.get(name_str.upper())
    if not value:
      return False
  if isinstance(value, list):
    if len(value) > 1:
      value = sep.join(value[:-1]) + lastsep + value[-1]
    else:
      value = value[0]
  name.value = value
  name.truth = True
  return name


def foo_meta_test(*nameN, track=None):
  if track is None:
    track = _ctx_track.get()
  for each in nameN:
    name = stringify(each)
    value = track.get(name)
    if not value:
      value = track.get(name.upper())
      if not value:
        return False
  return EvaluatorAtom(1, True)


def foo_meta_num(name, track=None):
  name = atomize(name)
  name_str = str(name)
  if track is None:
    track = _ctx_track.get()
  value = track.get(name_str)
  if not value:
    value = track.get(name_str.upper())
    if not value:
      return 0
  name.value = len(value) if isinstance(value, list) else 1
  name.truth = 1
  return name


def foo_get(name, memory=None):
  name = stringify(name)
  if name == '':
    return False
  if memory is None:
    memory = _ctx_memory.get()
  value = memory.get(name)
  if value is not None and value is not False and value != '':
    return EvaluatorAtom(value, True)
  return False


def foo_put(name, value, memory=None):
  name = stringify(name)
  value = atomize(value)
  if name != '':
    if memory is None:
      memory = _ctx_memory.get()
    memory[name] = str(value)
  return value


def foo_puts(name, value, memory=None):
  return bool(foo_put(name, value, memory))


foo_function_vtable = {
    '(default)' : {'n': foo_unknown},
    # TODO: With strict rules, $if 'n' should throw exception
    'if': {2: foo_if__2, 3: foo_if__3, 'n': foo_invalid('if')},
    'if2': {2: foo_if2, 'n': foo_invalid('if2')},
    'if3': {0: foo_false, 1: foo_false, 'n': foo_if3},
    'ifequal': {4: foo_ifequal, 'n': foo_invalid('ifequal')},
    'ifgreater': {4: foo_ifgreater, 'n': foo_invalid('ifgreater')},
    'iflonger': {4: foo_iflonger, 'n': foo_invalid('iflonger')},
    'select': {0: foo_false, 1: foo_false, 2: foo_select_2, 'n': foo_select},
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
    'fix_eol': {1: foo_fix_eol, 2: foo_fix_eol, 'n': foo_false},
    # NOTE: $hex 1 should be foo_hex_1, but foobar2000 actually does nothing
    'hex': {2: foo_hex, 'n': foo_false},
    'insert': {3: foo_insert, 'n': foo_false},
    'left': {2: foo_left, 'n': foo_false},
    'len': {1: foo_len, 'n': foo_false},
    # NOTE: Since at least 1.4.2, $len and $len2 are equivalent.
    'len2': {1: foo_len, 'n': foo_false},
    'longer': {2: foo_longer, 'n': foo_false},
    'lower': {1: foo_lower},
    'longest': {0: foo_false, 1: foo_nop, 'n': foo_longest},
    'num': {2: foo_num, 'n': foo_false},
    'pad': {2: foo_pad, 3: foo_pad},
    'pad_right': {2: foo_pad_right, 3: foo_pad_right},
    'padcut': {2: foo_padcut},
    'padcut_right': {2: foo_padcut_right},
    'progress': {5: foo_progress, 'n': foo_false},
    'progress2': {5: foo_progress2, 'n': foo_false},
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
        1: foo_stripprefix__1,
        'n': foo_stripprefix_arityN
    },
    'swapprefix': {
        0: foo_false,
        1: foo_swapprefix__1,
        'n': foo_swapprefix_arityN
    },
    'trim': {1: foo_trim},
    'tab': {0: foo_tab__0, 1: foo_tab__1},
    'upper': {1: foo_upper},
    'meta': {1: foo_meta__1, 2: foo_meta__2},
    'meta_sep': {2: foo_meta_sep__2, 3: foo_meta_sep__3},
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


def vinvoke(function, argv):
  arity = len(argv)
  funcref = vlookup(function, arity)
  return vmarshal(funcref(*argv))


def vcallmarshal(atom):
  if atom is None:
    return ('', 0)

  return (str(atom), 1 if atom else 0)


def vcondmarshal(atom):
  if not atom:
    return ('', 0)

  return (str(atom), 1)


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


class LazyExpression(object):
  __slots__ = (
      'fmt', 'conditional', 'depth', 'offset', 'case_sensitive', 'magic',
      'for_filename', 'compatible', 'ccache', 'value', 'evaluated')

  def __init__(self,
      fmt, conditional, depth, offset, case_sensitive, magic, for_filename,
      compatible, ccache):
    self.fmt = fmt
    self.conditional = conditional
    self.depth = depth
    self.offset = offset
    self.case_sensitive = case_sensitive
    self.magic = magic
    self.for_filename = for_filename
    self.compatible = compatible
    self.ccache = ccache
    self.value = None
    self.evaluated = False

  def __call__(self):
    if not self.evaluated:
      self.value = _eval(
          self.fmt, _interpreter_vtable, self.conditional, self.depth,
          self.offset)
      self.evaluated = True
    return self.value

  def __str__(self):
    return self.fmt

  def __repr__(self):
    return "lazy(%s)" % repr(self.fmt)


class TitleformatError(Exception):
  pass


class TitleformatRuntimeError(TitleformatError):
  pass


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
next_paren_token = re.compile(r"[(')]")
next_cond_token = re.compile(r"['\[\]]")


def flush_output(output, compiled):
  joined_output = ''.join(output)
  compiled.append(lambda: (joined_output, 0))
  output.clear()


def parse_literal(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  start = i
  i = fmt.index("'", i) + 1
  output.append(fmt[start:i-1])
  return i, offset, offstart, evals


def interpret_var(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  start = i
  i = fmt.index('%', i)

  val, edelta = resolve_var(fmt[start:i], case_sensitive, magic, for_filename)

  output.append(val)
  return i + 1, offset, offstart, evals + edelta


def compile_var(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  if output:
    flush_output(output, compiled)

  start = i
  i = fmt.index('%', i)
  current = current=fmt[start:i]

  compiled.append(
      lambda: resolve_var(current, case_sensitive, magic, for_filename))

  return i + 1, offset, offstart, None


def interpret_func(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  return construe_func(
    fmt, i, evals, output, depth, offset, offstart, case_sensitive, magic,
    for_filename, compatible, ccache, interpret_arg, interpret_arglist)


def compile_func(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  if output:
    flush_output(output, compiled)
  return construe_func(
    fmt, i, evals, compiled, depth, offset, offstart, case_sensitive, magic,
    for_filename, compatible, ccache, compile_arg, compile_arglist)


def interpret_arg(
    fmt, arglist, depth, offset, case_sensitive, magic, for_filename,
    compatible, ccache):
  arglist.append(
      LazyExpression(
          fmt, False, depth, offset, case_sensitive, magic, for_filename,
          compatible, ccache))


def compile_arg(
    fmt, arglist, depth, offset, case_sensitive, magic, for_filename,
    compatible, ccache):
  arglist.append(_eval(fmt, _compiler_vtable, depth=depth, offset=offset,
    case_sensitive=case_sensitive, magic=magic, for_filename=for_filename,
    compatible=compatible, ccache=ccache))


def interpret_arglist(evals, current_fn, arglist, output, depth, offset):
  val, edelta = vcallmarshal(vinvoke(current_fn, arglist))
  if val:
    output.append(val)
  return evals + edelta


def compile_arglist(evals, current_fn, arglist, compiled, depth, offset):
  compiled.append(compile_fn_call(current_fn, arglist))


def construe_func(
    fmt, i, evals, container, depth, offset, offstart, case_sensitive, magic,
    for_filename, compatible, ccache, do_arg, do_arglist):
  argparens, innerparens = 0, 0
  foffstart = i + 1
  start = i

  while True:
    c = fmt[i]
    i += 1
    if c == '(':
      current_fn = fmt[start:i-1]
      within_arglist = True
      offset = i + 1
      break
    elif not c.isalnum() and c != '_':
      if compatible:
        raise StopIteration()
      else:
        raise TitleformatError(f'Illegal token "{c}" encountered at char {i}')

  current = []
  arglist = []

  while True:
    c = fmt[i]
    i += 1
    if not argparens:
      if c == ')':
        if current or arglist:
          do_arg(''.join(current), arglist, depth + 1, offset + offstart,
              case_sensitive, magic, for_filename, compatible, ccache)

        return i, offset, offstart, do_arglist(
            evals, current_fn, arglist, container, depth, offset + foffstart)
        break
      elif c == ',':
        do_arg(''.join(current), arglist, depth + 1, offset + offstart,
            case_sensitive, magic, for_filename, compatible, ccache)
        current.clear()
        offstart = i + 1
        continue
    if c == "'":  # Literal within arglist
      start = i
      i = fmt.index("'", i) + 1
      current.append(fmt[start-1:i])
    elif c == '$':  # Nested function call
      start = i
      innerparens = 0
      it = next_paren_token.finditer(fmt[i:])
      while True:
        match = next(it)
        c = match.group()
        if c == '(':
          innerparens += 1
        elif c == "'":
          match = next(it)
          while match.group() != "'":
            match = next(it)
        elif c == ')':
          innerparens -= 1
          if not innerparens:  # Stop skipping evaluation.
            i += match.end()
            current.append(fmt[start-1:i])
            break
          elif innerparens < 0:
            if compatible:
              raise StopIteration()
            else:
              raise TitleformatError(backwards_error(')', '(', offset, i))
    elif c == '(':  # "Paren poisoning" -- due to weird foobar parsing logic
      argparens += 1
      while True:  # Skip to next arg or matching paren, whichever comes first
        c = fmt[i]
        if c == '(':
          argparens += 1
        elif not argparens:
          if c in ',)':
            # Resume normal execution
            break
        elif c == ')':
          argparens -= 1
        i += 1  # Only need to do this if we're not actually breaking
    else:
      # This is a critical section. I've tried the following approaches and
      # benchmarked them to find the fastest ones:
      #     1. Regular expression match groups (this one)
      #     2. Increment the index counter until you find it
      #     3. Use next() with a comprehension to assign the index counter
      #     4. Use min() and str.find() to find the lowest index
      #     5. Reduce min() over a map of a sliced fmt with a filter
      # #1 is overall very good and asymptotically the fastest. #2 is faster
      # for very short sequences by about 4%, making it better for the unit
      # tests, but overall not worth it. Everything else just performs worse
      # somehow in the formatter, even if it benchmarks well outside it.
      match = next_inner_token.search(fmt, i)
      i = match.start()  # Don't check, just let this raise AttributeError!
      current.append(fmt[match.pos-1:i])
  raise StopIteration()


def interpret_cond(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  return construe_cond(
    fmt, i, evals, output, depth, offset, offstart, case_sensitive, magic,
    for_filename, compatible, ccache, interpret_cond_contents)


def compile_cond(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  if output:
    flush_output(output, compiled)
  return construe_cond(
    fmt, i, evals, compiled, depth, offset, offstart, case_sensitive, magic,
    for_filename, compatible, ccache, compile_cond_contents)


def interpret_cond_contents(fmt, evals, output, depth, offset):
  evaluated_value = _eval(fmt, _interpreter_vtable, True, depth, offset)

  if evaluated_value:
    output.append(str(evaluated_value))
    return evals + 1
  return evals


def compile_cond_contents(fmt, evals, compiled, depth, offset):
  compiled_cond = _eval(fmt, _compiler_vtable, True, depth, offset)
  compiled.append(lambda: vcondmarshal(compiled_cond()))


def construe_cond(
    fmt, i, evals, container, depth, offset, offstart, case_sensitive, magic,
    for_filename, compatible, ccache, do_cond_contents):
  conds = 0
  start = i
  while True:
    c = fmt[i]
    i += 1
    if c == '[':
        conds += 1
    elif c == ']':
      if conds:
        conds -= 1
      else:
        return i, offset, offstart, do_cond_contents(
            fmt[start:i-1], evals, container, depth + 1, offset)
    elif c == "'":
      i = fmt.index("'", i) + 1
    else:
      match = next_cond_token.search(fmt, i)
      i = match.start()


def misplaced_cond(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  if compatible:
    raise StopIteration()
  else:
    raise TitleformatError(backwards_error(']', '[', offset, i))


def misplaced_paren(
    fmt, i, evals, output, compiled, depth, offset, offstart,
    case_sensitive, magic, for_filename, compatible, ccache):
  # This seems like a foobar bug; parens shouldn't do anything outside of a
  # function call, but foobar will just explode if it sees a lone paren floating
  # around in the input.
  if compatible:
    raise StopIteration()


_interpreter_vtable = {
    "'": parse_literal,
    '%': interpret_var,
    '$': interpret_func,
    '[': interpret_cond,
    ']': misplaced_cond,
    '(': misplaced_paren,
    ')': misplaced_paren,
}

_compiler_vtable = {
    "'": parse_literal,
    '%': compile_var,
    '$': compile_func,
    '[': compile_cond,
    ']': misplaced_cond,
    '(': misplaced_paren,
    ')': misplaced_paren,
}


def format(fmt, track=None, memory=None):
  with tfcontext(track, memory):
    return _eval(fmt, _interpreter_vtable)


def compile(fmt):
  return (lambda track=None, memory=None:
      enact_cascade(_eval(fmt, _compiler_vtable), track, memory))


def enact_cascade(cobj, track, memory):
  with tfcontext(track, memory):
    return cobj()


def _eval(fmt, vtable, conditional=False, depth=0, offset=0,
    case_sensitive=False, magic=True, for_filename=False, compatible=True,
    ccache=default_ccache):
  if fmt in ccache:
    if vtable is _compiler_vtable: return ccache[fmt]
    else: return ccache[fmt]()

  evals, i, soff, offstart = 0, 0, -1, 0
  output = []
  compiled = [] if vtable is _compiler_vtable else None

  try:
    while True:
      c = fmt[i]
      i += 1
      if c in vtable:
        if c not in '[]()' and c == fmt[i]:
          soff = 0
          i += 1  # Fall through
        else:
          i, offset, offstart, evals = vtable[c](
              fmt, i, evals, output, compiled, depth, offset, offstart,
              case_sensitive, magic, for_filename, compatible, ccache)
          continue

      match = next_token.search(fmt, i + soff)
      if match:
        output.append(fmt[i-1:match.start()])
        soff = -1
        i = match.start()
      else:
        output.append(fmt[i-1:])
        i = len(fmt)
        break
  except (IndexError, ValueError, AttributeError, StopIteration) as e:
    #print(f'Caught {e.__class__.__name__}, ignoring: {e}')
    pass

  # At this point, we have reached the end of the input.
  if i < len(fmt) and not compatible:
      raise TitleformatError(state_errors[c](offset, i))

  if vtable is _compiler_vtable:
    if output:
      # We need to flush the output buffer to a lambda once more
      compiled.append(lambda output=''.join(output): (output, 0))
    ccache[fmt] = lambda: run_compiled(compiled)
    return ccache[fmt]

  output = ''.join(output)

  if not depth and for_filename:
    output = foobar_filename_escape(output)

  result = EvaluatorAtom(output, bool(evals))

  return result


def run_compiled(compiled: Callable[..., Tuple[str, int]]) -> EvaluatorAtom:
  output = []
  eval_count = 0

  for c in compiled:
    c_output, c_count = c()
    output.append(c_output)
    eval_count += c_count

  return EvaluatorAtom(''.join(output), eval_count != 0)


def resolve_var(field, case_sensitive, magic, for_filename):
  try:
    track = _ctx_track.get()

    if track is None:
      return ('', 0)

    if not case_sensitive:
      field = field.upper()

    resolved = None

    if not magic:
      resolved = track.get(field)
    else:
      resolved = resolve_magic_var(track, field, case_sensitive)

    if resolved:
      if for_filename:
        resolved = re.sub('[\\\\/:|]', '-', resolved)
      resolved = EvaluatorAtom(resolved, True)
    elif resolved is False:
      resolved = None

    return ((str(resolved) if resolved is not True else '', 1)
            if resolved or resolved == ''
            # This is the case where no evaluation happened but there is still a
            # string value (that won't output conditionally).
            else (str(resolved), 0)
            if resolved is not None and resolved is not False
            else ('?', 0))
  except Exception as e:
    raise TitleformatError(
        f'Unexpected error while resolving variable "{field}".') from e


def resolve_magic_var(track, field, case_sensitive):
  field_lower = field.lower()
  if field_lower in magic_mappings:
    mapping = magic_mappings[field_lower]
    if mapping:
      try:  # First try to call it -- the mapping can be a function.
        return mapping(track)
      except TypeError:  # That didn't work. It's a list.
        for each in mapping:
          if each in track:
            return track.get(each)
          if case_sensitive:
            each_lower = each.lower()
            if each_lower in track:
              return track.get(each_lower)
  # Still couldn't find it.
  return track.get(field)


def compile_fn_call(current_fn, argv):
  fn = vlookup(current_fn, len(argv))
  return lambda: vcallmarshal(vmarshal(fn(*argv)))

