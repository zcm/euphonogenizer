#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import random
import sys

from common import dbg


# TODO(dremelofdeath): Actually finish these mapping functions.
def magic_map_filename(formatter, track):
  pass

def magic_map_filename_ext(formatter, track):
  pass

def magic_map_track_artist(formatter, track):
  artist = formatter.magic_resolve_variable(track, 'artist')
  album_artist = formatter.magic_resolve_variable(track, 'album artist')
  if artist != album_artist:
    return artist

def magic_map_tracknumber(formatter, track):
  return track.get('TRACKNUMBER').zfill(2)

def magic_map_track_number(formatter, track):
  return str(int(track.get('TRACKNUMBER')))


magic_mappings = {
    'album artist': ['ALBUM ARTIST', 'ARTIST', 'COMPOSER', 'PERFORMER'],
    'album': ['ALBUM', 'VENUE'],
    'artist': ['ARTIST', 'ALBUM ARTIST', 'COMPOSER', 'PERFORMER'],
    'discnumber': ['DISCNUMBER', 'DISC'],
    'filename': magic_map_filename,
    'filename_ext': magic_map_filename_ext,
    'track artist': magic_map_track_artist,
    'title': ['TITLE', '@'],
    'tracknumber': magic_map_tracknumber,
    'track number': magic_map_track_number,
}

def __foo_va_conv_n(n):
  if n:
    try:
      return int(n)
    except ValueError:
      try:
        start = 1 if n[0] == '-' else 0
        last_found_number = 0
        try:
          for i in range(start, len(n)):
            if int(n[i]) > 0:
              last_found_number = i
        except ValueError:
          if last_found_number:
            return int(n[0:last_found_number+1])
      except ValueError:
        pass
      except KeyError:
        pass
  return 0

def foo_false(track, va):
  pass

def foo_zero(track, va):
  return '0'

def foo_one(track, va):
  return '1'

def foo_nop(track, va):
  return va[0]

# TODO(dremelofdeath): Implement all these functions.
# TODO(dremelofdeath): These need some form of lazy-evaluation.
def foo_if_arity2(track, va_cond_then):
  if va_cond_then[0]:
    return va_cond_then[1]

def foo_if_arity3(track, va_cond_then_else):
  if va_cond_then_else[0]:
    return va_cond_then_else[1]
  return va_cond_then_else[2]

def foo_if2(track, va_a_else):
  return va_a_else[0] if va_a_else[0] else va_a_else[1]

def foo_if3(track, va_a1_a2_aN_else):
  for i in range(0, len(va_a1_a2_aN_else) - 1):
    if va_a1_a2_aN_else[i]:
      return va_a1_a2_aN_else[i]
  return va_a1_a2_aN_else[-1]

def foo_ifequal(track, va_n1_n2_then_else):
  n1 = __foo_va_conv_n(va_n1_n2_then_else[0])
  n2 = __foo_va_conv_n(va_n1_n2_then_else[1])
  if n1 == n2:
    return va_n1_n2_then_else[2]
  return va_n1_n2_then_else[3]

def foo_ifgreater(track, va_n1_n2_then_else):
  n1 = __foo_va_conv_n(va_n1_n2_then_else[0])
  n2 = __foo_va_conv_n(va_n1_n2_then_else[1])
  if n1 > n2:
    return va_n1_n2_then_else[2]
  return va_n1_n2_then_else[3]

def foo_iflonger(track, va_s_n_then_else):
  n = __foo_va_conv_n(va_s_n_then_else[1])
  if len(va_s_n_then_else[0]) > n:
    return va_s_n_then_else[2]
  return va_n1_n2_then_else[3]

def foo_select(track, va_n_a1_aN):
  n = __foo_va_conv_n(va_n_a1_aN[0])
  if n > 0 and n <= len(va_n_a1_aN) - 1:
    return va_n_a1_aN[n]

def foo_add(track, va_aN):
  return sum(map(__foo_va_conv_n, va_aN))

def foo_div(track, va_aN):
  return reduce(lambda x, y: x // y, map(__foo_va_conv_n, va_aN))

def foo_greater(track, va_a_b):
  a = __foo_va_conv_n(va_a_b[0])
  b = __foo_va_conv_n(va_a_b[1])
  if a > b:
    return True
  return False

def foo_max(track, va_a_b):
  return foo_ifgreater(track, *(va_a_b + va_a_b))

def foo_maxN(track, va_aN):
  return reduce(lambda x, y: foo_max(track, [x, y]), va_aN)

def foo_min(track, va_a_b):
  return foo_ifgreater(track, *(va_a_b + reverse(va_a_b)))

def foo_minN(track, va_aN):
  return reduce(lambda x, y: foo_min(track, [x, y]), va_aN)

def foo_mod(track, va_a_b):
  a = __foo_va_conv_n(va_a_b[0])
  b = __foo_va_conv_n(va_a_b[1])
  if not b:
    return a
  return a % b

def foo_modN(track, va_aN):
  return reduce(
      lambda x, y: foo_mod(track, [x, y]), map(__foo_va_conv_n, va_aN))

def foo_mul(track, va_aN):
  return reduce(lambda x, y: x * y, va_aN)

def foo_muldiv(track, va_a_b_c):
  c = __foo_va_conv_n(va_a_b_c[2])
  return (foo_mul(track, [a, b]) + c // 2) // c

def foo_rand(track, va):
  random.seed()
  return random.randint(0, sys.maxint)

def foo_sub(track, va_aN):
  return reduce(lambda x, y: x - y, map(__foo_va_conv_n, va_aN))

def foo_and(track, va_N):
  pass

def foo_or(track, va_N):
  pass

def foo_not(track, va_N):
  pass

def foo_xor(track, va_N):
  pass

def foo_abbr_arity1(track, va_x):
  pass

def foo_abbr_arity2(track, va_x_len):
  pass

def foo_ansi(track, va_x):
  pass

def foo_ascii(track, va_x):
  pass

def foo_caps(track, va_x):
  pass

def foo_caps2(track, va_x):
  pass

def foo_char(track, va_x):
  pass

def foo_crc32(track, va_x):
  pass

def foo_crlf(track, va):
  pass

def foo_cut(track, va_a_len):
  pass

def foo_directory_arity1(track, va_x):
  pass

def foo_directory_arity2(track, va_x_n):
  pass

def foo_directory_path(track, va_x):
  pass

def foo_ext(track, va_x):
  pass

def foo_filename(track, va_x):
  pass

def foo_fix_eol_arity1(track, va_x):
  pass

def foo_fix_eol_arity2(track, va_x_indicator):
  pass

def foo_hex_arity1(track, va_n):
  pass

def foo_hex_arity2(track, va_n_len):
  pass

def foo_insert(track, va_a_b_n):
  pass

def foo_left(track, va_a_len):
  pass

def foo_len(track, va_a):
  pass

def foo_len2(track, va_a):
  pass

def foo_longer(track, va_a_b):
  pass

def foo_lower(track, va_a):
  pass

def foo_longest(track, va_a1_aN):
  pass

def foo_num(track, va_n_len):
  pass

def foo_pad_arity2(track, va_x_len):
  pass

def foo_pad_arity3(track, va_x_len_char):
  pass

def foo_pad_right_arity2(track, va_x_len):
  pass

def foo_pad_right_arity3(track, va_x_len_char):
  pass

def foo_padcut(track, va_x_len):
  pass

def foo_padcut_right(track, va_x_len):
  pass

def foo_progress(track, va_pos_range_len_a_b):
  pass

def foo_progress2(track, va_pos_range_len_a_b):
  pass

def foo_repeat(track, va_a_n):
  pass

def foo_replace(track, va_a_n):
  pass

def foo_right(track, va_a_len):
  pass

def foo_roman(track, va_n):
  pass

def foo_rot13(track, va_a):
  pass

def foo_shortest(track, va_aN):
  pass

def foo_strchr(track, va_s_c):
  pass

def foo_strrchr(track, va_s_c):
  pass

def foo_strstr(track, va_s1_s2):
  pass

def foo_strcmp(track, va_s1_s2):
  pass

def foo_stricmp(track, va_s1_s2):
  pass

def foo_substr(track, va_s_m_n):
  pass

def foo_stripprefix_arity1(track, va_x):
  pass

def foo_stripprefix_arityN(track, va_x_prefix1_prefix2_prefixN):
  pass

def foo_swapprefix_arity1(track, va_x):
  pass

def foo_swapprefix_arityN(track, va_x_prefix1_prefix2_prefixN):
  pass

def foo_trim(track, va_s):
  pass

def foo_tab_arity0(track, va):
  pass

def foo_tab_arity1(track, va_n):
  pass

def foo_upper(track, va_s):
  pass

def foo_meta_arity1(track, va_name):
  pass

def foo_meta_arity2(track, va_name_n):
  pass

def foo_meta_sep_arity2(track, va_name_sep):
  pass

def foo_meta_sep_arity3(track, va_name_sep_lastsep):
  pass

def foo_meta_test(track, va_nameN):
  pass

def foo_meta_num(track, va_name):
  pass

def foo_year(track, va_time):
  pass

def foo_month(track, va_time):
  pass

def foo_day_of_month(track, va_time):
  pass

def foo_date(track, va_time):
  pass

def foo_time(track, va_time):
  pass

def foo_get(track, va_name):
  pass

def foo_put(track, va_name_value):
  pass

def foo_puts(track, va_name_value):
  pass


foo_function_vtable = {
    'if': {'2': foo_if_arity2, '3': foo_if_arity3},
    'if2': {'2': foo_if2},
    'if3': {'0': foo_false, '1': foo_nop, 'n': foo_if3},
    'ifequal': {'4': foo_ifequal},
    'ifgreater': {'4': foo_ifgreater},
    'iflonger': {'4': foo_iflonger},
    'select': {'0': foo_false, '1': foo_false, 'n': foo_select},
    'add': {'0': foo_zero, '1': foo_nop, 'n': foo_add},
    'div': {'0': foo_false, '1': foo_nop, 'n': foo_div},
    'greater': {'2': foo_greater},
    'max': {'0': foo_false, '1': foo_nop, '2': foo_max, 'n': foo_maxN},
    'min': {'0': foo_false, '1': foo_nop, '2': foo_min, 'n': foo_minN},
    'mod': {'0': foo_false, '1': foo_nop, '2': foo_mod, 'n': foo_modN},
    'mul': {'0': foo_one, '1': foo_nop, 'n': foo_mul},
    'muldiv': {'3': foo_muldiv},
    'rand': {'0': foo_rand},
    'sub': {'0': foo_false, 'n': foo_sub},
    # TODO(dremelofdeath): This is where I left off...
    'and': {'n': foo_and},
    'or': {'n': foo_or},
    'not': {'1': foo_not},
    'xor': {'n': foo_xor},
    'abbr': {'1': foo_abbr_arity1, '2': foo_abbr_arity2},
    'ansi': {'1': foo_ansi},
    'ascii': {'1': foo_ascii},
    'caps': {'1': foo_caps},
    'caps2': {'1': foo_caps2},
    'char': {'1': foo_char},
    'crc32': {'1': foo_crc32},
    'crlf': {'0': foo_crlf},
    'cut': {'2': foo_cut},
    'directory': {'1': foo_directory_arity1, '2': foo_directory_arity2},
    'directory_path': {'1': foo_directory_path},
    'ext': {'1': foo_ext},
    'filename': {'1': foo_filename},
    'fix_eol': {'1': foo_fix_eol_arity1, '2': foo_fix_eol_arity2},
    'hex': {'1': foo_hex_arity1, '2': foo_hex_arity2},
    'insert': {'3': foo_insert},
    'left': {'2': foo_left},
    'len': {'1': foo_len},
    'len2': {'1': foo_len2},
    'longer': {'2': foo_longer},
    'lower': {'1': foo_lower},
    'longest': {'n': foo_longest},
    'num': {'2': foo_num},
    'pad': {'2': foo_pad_arity2, '3': foo_pad_arity3},
    'pad_right': {'2': foo_pad_right_arity2, '3': foo_pad_right_arity3},
    'padcut': {'2': foo_padcut},
    'padcut_right': {'2': foo_padcut_right},
    'progress': {'5': foo_progress},
    'progress2': {'5': foo_progress2},
    'repeat': {'2': foo_repeat},
    'replace': {'3': foo_replace},
    'right': {'2': foo_right},
    'roman': {'1': foo_roman},
    'rot13': {'1': foo_rot13},
    'shortest': {'n': foo_shortest},
    'strchr': {'2': foo_strchr},
    'strrchr': {'2': foo_strrchr},
    'strstr': {'2': foo_strstr},
    'strcmp': {'2': foo_strcmp},
    'stricmp': {'2': foo_stricmp},
    'substr': {'3': foo_substr},
    'stripprefix': {'1': foo_stripprefix_arity1, 'n': foo_stripprefix_arityN},
    'swapprefix': {'1': foo_swapprefix_arity1, 'n': foo_swapprefix_arityN},
    'trim': {'1': foo_trim},
    'tab': {'0': foo_tab_arity0, '1': foo_tab_arity1},
    'upper': {'1': foo_upper},
    'meta': {'1': foo_meta_arity1, '2': foo_meta_arity2},
    'meta_sep': {'2': foo_meta_sep_arity2, '3': foo_meta_sep_arity3},
    'meta_test': {'n': foo_meta_test},
    'meta_num': {'1': foo_meta_num},
    'year': {'1': foo_year},
    'month': {'1': foo_month},
    'day_of_month': {'1': foo_day_of_month},
    'date': {'1': foo_date},
    'time': {'1': foo_time},
    'get': {'1': foo_get},
    'put': {'2': foo_put},
    'puts': {'2': foo_puts},
}


class FunctionVirtualInvocationException(Exception):
  pass


def vmarshal(value):
  if not value and value is not 0:
    return ''
  return str(value)

def vinvoke(track, function, argv):
  arity = str(len(argv))
  funcref = None
  try:
    funcref = foo_function_vtable[function][arity]
  except KeyError:
    try:
      funcref = foo_function_vtable[function]['n']
    except KeyError:
      message = 'No function with name %s and arity %s exists' % (
          function, arity)
      raise FunctionVirtualInvocationException(message)
  return vmarshal(funcref(track, argv))


class TitleFormatParseException(Exception):
  pass


class TitleFormatter:
  def __init__(self, case_sensitive=False, magic=True, debug=False):
    self.case_sensitive = case_sensitive
    self.magic = magic
    self.debug = debug

  def format(self, track, title_format, conditional=False, depth=0, offset=0):
    lookbehind = None
    outputting = True
    literal = False
    literal_chars_count = None
    parsing_variable = False
    parsing_function = False
    parsing_function_args = False
    parsing_conditional = False
    offset_start = 0
    fn_offset_start = 0
    bad_var_char = None
    conditional_parse_count = 0
    evaluation_count = 0
    output = ''
    current = ''
    current_fn = ''
    current_argv = []

    if self.debug:
      dbg('fresh call to parse(); format="%s" offset=%s' % (
        title_format, offset), depth)

    for i, c in enumerate(title_format):
      if outputting:
        if literal:
          next_output, literal, chars_parsed = self.parse_literal(
              c, i, lookbehind, literal_chars_count, False, depth, offset + i)
          output += next_output
          literal_chars_count += chars_parsed
        else:
          if c == "'":
            if self.debug:
              dbg('entering literal mode at char %s' % i, depth)
            literal = True
            literal_chars_count = 0
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
            raise TitleFormatParseException(message)
          else:
            output += c
      else:
        if literal and not parsing_function_args:
          raise TitleFormatParseException(
              'Invalid parse state: Cannot parse names while in literal mode')

        if parsing_variable:
          if c == '%':
            evaluated_value = self.resolve_variable(track, current, i, depth)

            if self.debug:
              dbg('value is: %s' % evaluated_value, depth)
            if evaluated_value:
              output += evaluated_value
              evaluation_count += 1
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
          if c == '(':
            if current == '':
              raise TitleFormatParseException(
                  "Can't call function with no name at char %s" % i)
            if self.debug:
              dbg('parsed function %s at char %s' % (current, i), depth)

            current_fn = current
            current = ''
            parsing_function = False
            parsing_function_args = True
            offset_start = i + 1
          elif c == ')':
            message = self.make_backwards_error(')', '(', offset, i)
            raise TitleFormatParseException(message)
          elif not c.isalnum():
            raise TitleFormatParseException(
                "Illegal token '%s' encountered at char %s" % (c, i))
          else:
            current += c
        elif parsing_function_args:
          if literal:
            next_current, literal, chars_parsed = self.parse_literal(
                c, i, lookbehind, literal_chars_count, True, depth, offset + i)
            current += next_current
            literal_chars_count += chars_parsed
          else:
            if c == ')':
              current, arg = self.parse_fn_arg(track, current_fn, current,
                  current_argv, c, i, depth, offset + offset_start)
              current_argv.append(arg)

              if self.debug:
                dbg('finished parsing function arglist at char %s' % i, depth)
              fn_result = self.invoke_function(
                  track, current_fn, current_argv,
                  depth, offset + fn_offset_start)
              if self.debug:
                dbg('finished invoking function %s, value: %s' % (
                    current_fn, fn_result), depth)
              if fn_result:
                output += fn_result
                evaluation_count += 1
              if self.debug:
                dbg('evaluation count is now %s' % evaluation_count, depth)

              current_argv = []
              outputting = True
              parsing_function_args = False
            elif c == "'":
              if self.debug:
                dbg('entering arglist literal mode at char %s' % i, depth)
              literal = True
              literal_chars_count = 0
              # Include the quotes because we reparse function arguments.
              current += c
            elif c == ',':
              current, arg = self.parse_fn_arg(track, current_fn, current,
                  current_argv, c, i, depth, offset + offset_start)
              current_argv.append(arg)
              offset_start = i + 1
            else:
              current += c
        elif parsing_conditional:
          if c == '[':
            if self.debug:
              dbg('found a pending conditional at char %s' % i, depth)
            conditional_parse_count += 1
            current += c
          elif c == ']':
            if conditional_parse_count > 0:
              if self.debug:
                dbg('found a terminating conditional at char %s' % i, depth)
              conditional_parse_count -= 1
              current += c
            else:
              if self.debug:
                dbg('finished parsing conditional at char %s' % i, depth)
              evaluated_value = self.format(
                  track, current, True, depth + 1, offset + offset_start)

              if self.debug:
                dbg('value is: %s' % evaluated_value, depth)
              if evaluated_value:
                output += evaluated_value
                evaluation_count += 1
              if self.debug:
                dbg('evaluation count is now %s' % evaluation_count, depth)

              current = ''
              conditional_parse_count = 0
              outputting = True
              parsing_conditional = False
          else:
            current += c
        else:
          # Whatever is happening is invalid.
          raise TitleFormatParseException(
              "Invalid title format parse state: Can't handle character " + c)
      lookbehind = c

    # At this point, we have reached the end of the input.
    if outputting:
      if literal:
        message = self.make_unterminated_error('literal', "'", offset, i)
        raise TitleFormatParseException(message)
    else:
      message = None
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

      raise TitleFormatParseException(message)

    if conditional and evaluation_count == 0:
      if self.debug:
        dbg('about to return nothing for output: %s' % output, depth)
      return None

    return output

  def is_valid_var_identifier(self, c):
    return c == ' ' or c == '@' or c == '_' or c == '-' or c.isalnum()

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

  def parse_literal(self, c, i, lookbehind, literal_chars_count, include_quote,
      depth=0, offset=0):
    next_output = ''
    next_literal_state = True
    literal_chars_parsed = 0

    if c == "'":
      if lookbehind == "'" and literal_chars_count == 0:
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

  def parse_fn_arg(
      self, track, current_fn, current, current_argv, c, i, depth=0, offset=0):
    next_current = ''

    if self.debug:
      dbg('finished argument %s for function "%s" at char %s' % (
          len(current_argv), current_fn, i), depth)
    # Now recursively subparse the argument.
    subparsed_argument = self.format(track, current, False, depth + 1, offset)
    return (next_current, subparsed_argument)

  def resolve_variable(self, track, field, i, depth):
    local_field = field
    if not self.case_sensitive:
      local_field = field.upper()
    if self.debug:
      dbg('parsed variable %s at char %s' % (local_field, i), depth)
    if not self.magic:
      return track.get(local_field)
    else:
      return self.magic_resolve_variable(track, local_field, depth)

  def magic_resolve_variable(self, track, field, depth):
    field_lower = field.lower()
    if field_lower in magic_mappings:
      mapping = magic_mappings[field_lower]
      if not mapping:
        dbg('mapping "%s" is not valid' % field_lower, depth)
        return track.get(field)
      else:
        # First try to call it -- the mapping can be a function.
        try:
          return mapping(self, track)
        except TypeError:
          # That didn't work. It's a list.
          dbg('mapping "%s" is not a function' % field_lower, depth)
          for each in mapping:
            dbg('attempting to map "%s"' % each, depth)
            if each in track:
              return track.get(each)
            if self.case_sensitive:
              each_lower = each.lower()
              dbg('attempting to map "%s"' % each_lower, depth)
              if each_lower in track:
                return track.get(each_lower)

          # Still couldn't find it.
          dbg('mapping %s failed to map magic variable' % field_lower, depth)
          return track.get(field)
    dbg('mapping %s not found in magic variables' % field_lower, depth)
    return track.get(field)

  def invoke_function(
      self, track, function_name, function_argv, depth=0, offset=0):
    if self.debug:
      dbg('invoking function %s, args %s' % (
          function_name, function_argv), depth)
    return vinvoke(track, function_name, function_argv)

