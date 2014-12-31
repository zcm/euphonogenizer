#!/usr/bin/python
# -*- coding: utf-8 -*-

class TitleFormatParseException(Exception):
  pass


class TitleFormatter:
  def __init__(self, case_sensitive=False, debug=False):
    self.case_sensitive = case_sensitive
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
            if not self.case_sensitive:
              current = current.upper()

            if self.debug:
              dbg('parsed variable %s at char %s' % (current, i), depth)
            evaluated_value = track.get(current)

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
                  current_fn, current_argv, depth, offset + fn_offset_start)
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

  def invoke_function(self, function_name, function_argv, depth=0, offset=0):
    if self.debug:
      dbg('invoking function %s, args %s' % (
          function_name, function_argv), depth)
    # TODO(dremelofdeath): Now invoke the function.


