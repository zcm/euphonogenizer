#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import os
import simplejson
import sys


parser = argparse.ArgumentParser(
    description = 'Manages music libraries with metadata in M-TAGS format.',
    epilog = 'Written by Zachary Murray (dremelofdeath). Loved by you, I hope.',
)

parser.add_argument('--mode',
    choices = ['copy', 'move', 'rename'],
    default = 'copy',
    help = 'operating mode for transformations',
)

parser.add_argument('--tagsfile',
    default = '!.tags',
    help = 'internal: the filename of the target tags files in subdirectories',
)

parser.add_argument('--pattern',
    default = "'  $$$' [[''%ISRC%'' -] %TRACKNUMBER% - ] %TITLE%",
    help = 'the pattern used for output filenames in transformations',
)

parser.add_argument('--coversearchpatterns',
    default = [
      '../override.png',
      '../override.jpg',
      '../front.png',
      '../cover.png',
      '../%@%.png',
      '../%ALBUM%.png',
      '../folder.png',
      '../%ARTIST% - %ALBUM%.png',
      '../front.jpg',
      '../cover.jpg',
      '../%@%.jpg',
      '../%ALBUM%.jpg',
      '../folder.jpg',
      '../front.jpeg',
      '../cover.jpeg',
      '../folder.jpeg',
      '../%ARTIST% - %ALBUM%.jpg',
      '../%ARTIST% - %ALBUM%.jpeg',
      'override.png',
      'override.jpg',
      'override.jpeg',
      'front.png',
      'front.jpg',
      'cover.png',
      'cover.jpg',
      '%@%.png',
      '%@%.jpg',
      '%ALBUM%.png',
      '%ALBUM%.jpg',
      'folder.png',
      'folder.jpg',
      'artwork/front.png',
      'artwork/front.jpg',
      '00 %ALBUM%.png',
      '00 %ALBUM%.jpg',
      '%ALBUM% - front.png',
      '%ALBUM% - front.jpg',
      '%ALBUM% - cover.png',
      '%ALBUM% - cover.jpg',
      '%ARTIST% - %ALBUM% - front.png',
      '%ARTIST% - %ALBUM% - front.jpg',
      '%ARTIST% - %ALBUM% - cover.png',
      '%ARTIST% - %ALBUM% - cover.jpg',
      'front.jpeg',
      'cover.jpeg',
      'folder.jpeg',
      'artwork/front.jpeg',
      '00 %ALBUM%.jpeg',
      '%ALBUM% - front.jpeg',
      '%ALBUM% - cover.jpeg',
      '%ARTIST% - %ALBUM% - front.jpeg',
      '%ARTIST% - %ALBUM% - cover.jpeg',
      '%ARTIST% - %ALBUM%.jpg',
      '%ARTIST% - %ALBUM%.jpeg',
      '%ARTIST% - %ALBUM%.png',
      'folder*.jpg',
      'FOLDER*.jpg',
    ],
    nargs = '+',
)

args = parser.parse_args()


class TitleFormattingParser:
  def __init__(self, debug=False):
    self.debug = debug

  def parse(self, track, title_format, conditional=False):
    lookbehind = None
    outputting = True
    literal = False
    literal_chars_count = None
    parsing_variable = False
    parsing_function = False
    parsing_function_args = False
    parsing_conditional = False
    subconditional_parse_count = 0
    evaluation_count = 0
    output = ''
    current = ''
    current_fn = ''
    current_argv = []

    if self.debug:
      print('fresh call to parse() - format is "%s"' % title_format)

    for i, c in enumerate(title_format):
      if outputting:
        if literal:
          next_output, literal, chars_parsed = self.parse_literal(
              c, i, lookbehind, literal_chars_count, False)
          output += next_output
          literal_chars_count += chars_parsed
        else:
          if c == "'":
            if self.debug:
              print('entering literal mode at char %s' % i)
            literal = True
            literal_chars_count = 0
          elif c == '%':
            if self.debug:
              print('begin parsing variable at char %s' % i)
            if parsing_variable or parsing_function or parsing_conditional:
              raise "Something went horribly wrong while parsing token '%'!"
            outputting = False
            parsing_variable = True
          elif c == '$':
            if self.debug:
              print('begin parsing function at char %s' % i)
            if parsing_variable or parsing_function or parsing_conditional:
              raise "Something went horribly wrong while parsing token '$'!"
            outputting = False
            parsing_function = True
          elif c == '[':
            if self.debug:
              print('begin parsing conditional at char %s' % i)
            if parsing_variable or parsing_function or parsing_conditional:
              raise "Something went horribly wrong while parsing token '['!"
            outputting = False
            parsing_conditional = True
          elif c == ']':
            raise "Found ']' with no matching token '['!"
          else:
            output += c
      else:
        if literal and not parsing_function_args:
          raise 'Invalid parse state: Cannot parse names while in literal mode'

        if parsing_variable:
          if c == '%':
            if self.debug:
              print('finished parsing variable %s at char %s' % (current, i))
            evaluated_value = track.get(current)

            if self.debug:
              print('value is: %s' % evaluated_value)
            if evaluated_value:
              output += evaluated_value
              evaluation_count += 1
            if self.debug:
              print('evaluation count is now %s' % evaluation_count)

            current = ''
            outputting = True
            parsing_variable = False
          else:
            current += c
        elif parsing_function:
          if c == '(':
            if current == '':
              raise ("Can't call function with no name at char %s" % i)
            if self.debug:
              print('finished parsing function %s at char %s' % (current, i))

            current_fn = current
            current = ''
            parsing_function = False
            parsing_function_args = True
          elif c == ')':
            raise ('Encountered close paren before open paren at char %s' % i)
          elif not c.isalnum():
            raise ("Illegal token '%s' encountered at char %s" % (c, i))
          else:
            current += c
        elif parsing_function_args:
          if literal:
            next_current, literal, chars_parsed = self.parse_literal(
                c, i, lookbehind, literal_chars_count, True)
            current += next_current
            literal_chars_count += chars_parsed
          else:
            if c == ')':
              current, arg = self.parse_fn_arg(
                  track, current_fn, current, current_argv, c, i)
              current_argv.append(arg)

              if self.debug:
                print('finished parsing function arglist at char %s' % i)
              fn_result = self.invoke_function(current_fn, current_argv)
              if self.debug:
                print('finished invoking function %s, value: %s' % (
                    current_fn, fn_result))
              if fn_result:
                output += fn_result
                evaluation_count += 1
              if self.debug:
                print('evaluation count is now %s' % evaluation_count)

              current_argv = []
              outputting = True
              parsing_function_args = False
            elif c == "'":
              if self.debug:
                print('entering arglist literal mode at char %s' % i)
              literal = True
              literal_chars_count = 0
              # Include the quotes because we reparse function arguments.
              current += c
            elif c == ',':
              current, arg = self.parse_fn_arg(
                  track, current_fn, current, current_argv, c, i)
              current_argv.append(arg)
            else:
              current += c
        elif parsing_conditional:
          if c == '[':
            if self.debug:
              print('found a pending subconditional at char %s' % i)
            subconditional_parse_count += 1
            current += c
          elif c == ']':
            if subconditional_parse_count > 0:
              if self.debug:
                print('found a terminating subconditional at char %s' % i)
              subconditional_parse_count -= 1
              current += c
            else:
              if self.debug:
                print('finished parsing conditional at char %s' % i)
              evaluated_value = self.parse(track, current, True)

              if self.debug:
                print('value is: %s' % evaluated_value)
              if evaluated_value:
                output += evaluated_value
                evaluation_count += 1
              if self.debug:
                print('evaluation count is now %s' % evaluation_count)

              current = ''
              subconditional_parse_count = 0
              outputting = True
              parsing_conditional = False
          else:
            current += c
        else:
          # Whatever is happening is invalid.
          raise "Invalid title format parse state: Can't handle character " + c
      lookbehind = c

    # At this point, we have reached the end of the input.
    if outputting:
      if literal:
        raise 'Unterminated literal; reached end of input, expected "\'"'
    else:
      if parsing_variable:
        raise "Unterminated variable; reached end of input, expected '%'"
      elif parsing_function:
        raise "Unterminated function call; reached end of input, expected ')'"
      elif parsing_conditional:
        raise "Unterminated subconditional; reached end of input, expected ']'"
      else:
        raise "Invalid title format parse state: Unknown error"

    if conditional and evaluation_count == 0:
      if self.debug:
        print('about to return an empty string for output: %s' % output)
      return ''

    return output

  def parse_literal(self, c, i, lookbehind, literal_chars_count, include_quote):
    next_output = ''
    next_literal_state = True
    literal_chars_parsed = 0

    if c == "'":
      if lookbehind == "'" and literal_chars_count == 0:
        if self.debug:
          print('output of single quote due to lookbehind at char %s' % i)
        next_output += c
      elif include_quote:
        next_output += c
      if self.debug:
        print('leaving literal mode at char %s' % i)
      next_literal_state = False
    else:
      next_output += c
      literal_chars_parsed += 1

    return (next_output, next_literal_state, literal_chars_parsed)

  def parse_fn_arg(self, track, current_fn, current, current_argv, c, i):
    next_current = ''

    if self.debug:
      print('finished argument %s for function "%s" at char %s' % (
          len(current_argv), current_fn, i))
    # Now recursively subparse the argument.
    subparsed_argument = self.parse(track, current, False)
    return (next_current, subparsed_argument)

  def invoke_function(self, function_name, function_argv):
    if self.debug:
      print('invoking function %s, args %s' % (function_name, function_argv))
    # TODO(dremelofdeath): Now invoke the function.


class TrackListing:
  def __init__(self, dict_obj):
    self._dict_obj = dict_obj

  def __contains__(self, key):
    return key in self._dict_obj

  def get(self, key):
    return self._dict_obj.get(key)


class PrintableTrackListing:
  def __init__(self, track_listing):
    self.track_listing = track_listing

  def __contains__(self, key):
    return key in self.track_listing

  def get(self, key):
    track_string = self.track_listing.get(key)
    if track_string is None:
      return None
    return track_string.encode(sys.stdout.encoding, errors='replace')


class TagsFile:
  def __init__(self, filename):
    with open(filename) as tags:
      tagsjson = simplejson.load(tags)
      self._process_saturated_tags(tagsjson)

  def _process_saturated_tags(self, tagsjson):
    self._tracks = []
    saturated_tags = {}

    for track in tagsjson:
      for tag_field, value in track.iteritems():
        if value == []:
          # This is, strangely, how the M-TAGS format erases values
          del saturated_tags[tag_field]
        else:
          saturated_tags[tag_field] = value

      self._tracks.append(saturated_tags.copy())

  def tracks(self):
    for each in self._tracks:
      yield TrackListing(each)

  def printable_tracks(self):
    for each in self.tracks():
      yield PrintableTrackListing(each)

  def both_tracks(self):
    for each in self._tracks:
      current_track = TrackListing(each)
      yield (current_track, PrintableTrackListing(current_track))


# TODO(dremelofdeath): Make this whole block a single class.
titleparser = TitleFormattingParser()


def handle_track(track, printtrack):
  if 'ARTIST' in track and 'TITLE' in track:
    print titleparser.parse(printtrack, args.pattern)


def handle_tags(dirpath, tags):
  print dirpath + ':'
  for track, printable_track in tags.both_tracks():
    handle_track(track, printable_track)


def main():
  for dirpath, dirnames, filenames in os.walk(os.getcwd()):
    for tagsfile in [each for each in filenames if each == args.tagsfile]:
      tags = TagsFile(os.path.join(dirpath, tagsfile))
      handle_tags(dirpath, tags)


# vim:ts=2:sw=2:et:ai
