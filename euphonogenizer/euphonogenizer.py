#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from __future__ import print_function

import glob
import os
import re
import shutil
import stat
import sys

import colorama
import colorama.ansi

from . import albumart
from . import mtags
from . import terminalsize
from . import titleformat

from .args import parser, EmbedCoversArg
from .common import (compat_iteritems, dbg, err, progname, unicwd, uniprint,
                     unistr, write_with_override)
from .tagext import is_mutagen_file

from mutagen import File
from mutagen.flac import FLAC
from mutagen.id3 import ID3FileType
from mutagen.easyid3 import EasyID3FileType
from mutagen.easymp4 import EasyMP4
from mutagen.mp3 import EasyMP3, MP3
from mutagen.mp4 import MP4
from mutagen.trueaudio import EasyTrueAudio
from mutagen.trueaudio import TrueAudio
from mutagen._compat import iteritems

escape_glob_dict = {
    '[': '[[]',
    ']': '[]]',
}

escape_glob_rc = re.compile('|'.join(map(re.escape, escape_glob_dict)))


def escape_glob(path):
  return escape_glob_rc.sub(lambda m: escape_glob_dict[m.group(0)], path)

def retry_if_ioerror(exception):
  return isinstance(exception, IOError)


class LimitReachedException(Exception):
  def __init__(self, message='Limit reached', visited_dirs=None):
    super(LimitReachedException, self).__init__(message)
    self.visited_dirs = visited_dirs


class UnwritableMetadataException(Exception):
  pass


class InvalidProcessorStateException(Exception):
  pass


class FileAccessException(Exception):
  pass


class DefaultConfigurable(object):
  def __init__(self, args, titleformatter, fileformatter):
    self._args = args
    self._titleformatter = titleformatter
    self._fileformatter = fileformatter

  @property
  def args(self):
    return self._args

  @property
  def titleformatter(self):
    return self._titleformatter

  @property
  def fileformatter(self):
    return self._fileformatter


class PrintHandler(DefaultConfigurable):
  def __init__(self, args, titleformatter, fileformatter):
    super(PrintHandler, self).__init__(args, titleformatter, fileformatter)
    self._unique_output = set()
    self._groupby_output = {}
    self.progress = args and hasattr(args, 'progress') and args.progress
    self.unique = args and hasattr(args, 'unique') and args.unique

    self.last_jump = 0
    self.init_ansi()

  @property
  def unique_output(self):
    return self._unique_output

  @property
  def groupby_output(self):
    return self._groupby_output

  def init_ansi(self):
    if self.progress:
      colorama.init()

      uniprint('== ' + progname + ' ==')
      uniprint('Progress:')
      uniprint('Current tag:')
      uniprint('Last file:')
      uniprint('Status:')
      uniprint('Track:')
      uniprint('Album:')
      uniprint('')

  def handle_group_uniprint(self, output, group):
    if group:
      if group not in self.groupby_output:
        self.groupby_output[group] = [output]
      else:
        self.groupby_output[group].append(output)
    else:
      uniprint(output)

  def print_or_defer_output(self, output, group=None):
    if self.unique:
      unique_key = output
      if group is not None:
        # Unique only applies within groups -- this is to prevent unexpected
        # behavior when output lines have the same output but are in different
        # groups (for example, when two tracks have the same name but are on
        # differently named albums).
        unique_key = group + output
      if unique_key not in self.unique_output:
        self.unique_output.add(unique_key)
        self.handle_group_uniprint(output, group)
    else:
      self.handle_group_uniprint(output, group)

  def print_deferred_output(self):
    if self.args and hasattr(self.args, 'groupby') and self.args.groupby:
      first = True
      for key in self.groupby_output:
        if not first:
          uniprint('')
        uniprint(key + ':')
        for each in self.groupby_output[key]:
          uniprint(' ' * self.args.groupby_indent + each)
        first = False

  def debug(self, text):
    if not self.progress:
      dbg(text)
    else:
      s = self.jump_to_and_clear_debug()
      s = s + text + os.linesep
      self.last_jump = self.last_jump - 1
      s = s + self.undo_last_jump()
      uniprint(s, end='')

  def on_before_update(self):
    pass

  def on_after_update(self):
    pass

  def update_progress(self, done, total, plural_noun):
    if self.progress:
      self.on_before_update()
      s = self.jump_to_and_clear_progress()
      s = s + self.get_completion_output(done, total, plural_noun) + os.linesep
      self.last_jump = self.last_jump - 1
      s = s + self.undo_last_jump()
      uniprint(s, end='')
      self.on_after_update()

  def update_current(self, done, total, plural_noun, sumtotal):
    if self.progress:
      self.on_before_update()
      s = self.jump_to_and_clear_current()
      s = s + self.get_completion_output(done, total, plural_noun, sumtotal)
      s = s + os.linesep
      self.last_jump = self.last_jump - 1
      s = s + self.undo_last_jump()
      uniprint(s, end='')
      self.on_after_update()

  def update_last_file(self, last_result, long_form=None):
    self.on_before_update()

    if not self.progress:
      if long_form is None:
        uniprint(last_result)
      else:
        uniprint(last_result + long_form)
    else:
      s = self.jump_to_and_clear_last_file()
      s = s + last_result + os.linesep
      self.last_jump = self.last_jump - 1
      s = s + self.undo_last_jump()
      uniprint(s, end='')

    self.on_after_update()

  def get_completion_output(self, done, total, plural_noun, sumtotal=None):
    s = '%d of %d %s processed (%d%%' % (
        done, total, plural_noun, done * 100 // total)

    if sumtotal is None:
      s = s + ')'
    else:
      s = s + ' - %d total)' % (sumtotal)

    return s

  def update_status(self, status=None, long_form=None):
    self.on_before_update()

    if not self.progress:
      if long_form is None:
        uniprint(status)
      else:
        uniprint(status + long_form)
    else:
      # Ignore the long form and just set the status.
      s = self.jump_to_and_clear_status()
      s = s + status + os.linesep
      self.last_jump = self.last_jump - 1
      s = s + self.undo_last_jump()
      uniprint(s, end='')

    self.on_after_update()

  def limit_to_width(self, text, width):
    if len(text) > width:
      # TODO(dremelofdeath): Consider printing an ellipsis character if the
      # terminal that we're on supports it (meaning supports Unicode).
      return text[:width-3] + '...'
    return text

  def update_track_and_album(self, track):
    if self.progress:
      self.on_before_update()
      t_pattern = '%album artist% - %title%'
      a_pattern = '%album% (%date%)'
      s = self.jump_to_and_clear_track()
      term_w, term_h = terminalsize.get_terminal_size()
      widthlimit = term_w - 14
      tracktext = self.titleformatter.format(track, t_pattern)
      tracktext = self.limit_to_width(tracktext, widthlimit)
      s = s + tracktext + os.linesep
      self.last_jump = self.last_jump - 1
      s = s + self.undo_last_jump()
      s = s + self.jump_to_and_clear_album()
      albumtext = self.titleformatter.format(track, a_pattern)
      albumtext = self.limit_to_width(albumtext, widthlimit)
      s = s + albumtext + os.linesep
      self.last_jump = self.last_jump - 1
      s = s + self.undo_last_jump()
      uniprint(s, end='')
      self.on_after_update()

  def jump_to_and_clear_field(self, n):
    s = self.jump_up_lines(n) + self.forward_to_field() + self.clear_to_end()
    return s

  def jump_to_and_clear_debug(self):
    return self.jump_to_and_clear_field(8);

  def jump_to_and_clear_progress(self):
    return self.jump_to_and_clear_field(7);

  def jump_to_and_clear_current(self):
    return self.jump_to_and_clear_field(6);

  def jump_to_and_clear_last_file(self):
    return self.jump_to_and_clear_field(5);

  def jump_to_and_clear_status(self):
    return self.jump_to_and_clear_field(4)

  def jump_to_and_clear_track(self):
    return self.jump_to_and_clear_field(3)

  def jump_to_and_clear_album(self):
    return self.jump_to_and_clear_field(2)

  def jump_up_lines(self, n):
    self.last_jump = n
    return colorama.ansi.Cursor.UP(n)

  def jump_down_lines(self, n):
    self.last_jump = -n
    return colorama.ansi.Cursor.DOWN(n)

  def undo_last_jump(self):
    if self.last_jump > 0:
      return self.jump_down_lines(self.last_jump)
    elif self.last_jump < 0:
      return self.jump_up_lines(-self.last_jump)

  def forward_to_field(self):
    return colorama.ansi.Cursor.FORWARD(13)

  def clear_to_end(self):
    return colorama.ansi.clear_line(0)


class DefaultPrintingConfigurable(DefaultConfigurable):
  def __init__(self, args, titleformatter, fileformatter, printer=None):
    super(DefaultPrintingConfigurable, self).__init__(
        args, titleformatter, fileformatter)

    if printer is None:
      printer = PrintHandler(self.args, self.titleformatter, self.fileformatter)

    self._printer = printer

  @property
  def printer(self):
    return self._printer


class CoverArtFinder(DefaultPrintingConfigurable):
  def __init__(self, args, titleformatter, fileformatter, printer=None):
    super(CoverArtFinder, self).__init__(
        args, titleformatter, fileformatter, printer)
    self._cover_dirs = set()

    self.include = hasattr(self.args, 'include_covers') and args.include_covers
    self.progress = hasattr(args, 'progress') and args.progress

  @property
  def cover_dirs(self):
    return self._cover_dirs

  def find_cover_art(self, dirname, track, dstpath=None, silent=False):
    if not self.include:
      # Just don't even bother.
      return

    retval = None
    explain = hasattr(self.args, 'explain') and self.args.explain

    if dirname not in self.cover_dirs:
      if explain or self.progress:
        if not silent:
          self.printer.update_status(
              'Finding cover art', ' for directory: ' + dirname)
      for each in self.args.include_covers:
        cover_file = os.path.join(
            dirname, self.titleformatter.format(track, each))
        cover_glob = glob.glob(escape_glob(cover_file))
        if explain and not silent:
          uniprint("  attempting pattern '" + each + "'")
          uniprint('    ==> ' + cover_file)
          if len(cover_glob) > 0:
            uniprint('    possible matches:')
            for n, each_glob in enumerate(cover_glob):
              uniprint('      %d: %s' % (n, each_glob))
          else:
            uniprint('    no matches')
        if cover_glob and os.path.isfile(cover_glob[0]):
          found_cover = cover_glob[0]
          if not dstpath:
            retval = found_cover
            break
          else:
            # Perhaps a bit of a hack to get the metadata formated properly...
            cover_track = track.copy()
            cover_track['@'] = found_cover
            ext = found_cover.split('.')[-1]
            dst = self.fileformatter.format(
                cover_track, self.args.cover_name) + '.' + ext
            dst = os.path.join(dstpath, dst)
            retval = (found_cover, dst)
            break
      if self.should_track_searched_cover_dir(dirname):
        self.cover_dirs.add(dirname)

    return retval

  def should_track_searched_cover_dir(self, dirname):
    return not self.args.per_track_cover_search


class EmbeddedCoverArtFinder(CoverArtFinder):
  def __init__(self, args, titleformatter, fileformatter, printer=None):
    super(EmbeddedCoverArtFinder, self).__init__(
        args, titleformatter, fileformatter, printer)

  def should_track_searched_cover_dir(self, dirname):
    return (self.args.embed_covers != EmbedCoversArg.EMBED_ONLY
            and not self.args.per_track_cover_search)


class FoobarMetadataHandler:
  known_mutagen_keys = {
      'albumartist': 'ALBUM ARTIST',
      'organization': 'PUBLISHER',
      'disctotal': 'TOTALDISCS',
      'tracktotal': 'TOTALTRACKS',
  }

  @classmethod
  def marshal_foobar_key(cls, key):
    if key in cls.known_mutagen_keys:
      return cls.known_mutagen_keys[key]

    return key.upper()


class MutagenFileMetadataHandler(DefaultPrintingConfigurable):
  # TODO(dremelofdeath): See if Foobar does this with filetypes other than FLAC
  # as well.
  known_foobar_keys = {
      # Foobar, I'm guessing, treats these fields as 'comment'-ish fields and
      # writes them first. From what I can gather, the comment-ish fields that
      # appear first are determined to be the 'real' fields, and if there are
      # others that have the same name as Foobar's internal name, they will come
      # afterwards.
      'ALBUM ARTIST': 'ALBUMARTIST',
      # Foobar writes these fields right before ReplayGain fields, and uses its
      # proximity to them in order to determine which one is the "real" field,
      # in the event that there are multiple as far as I can tell. This is
      # basically the complete opposite of the previous group of fields, since
      # the ReplayGain fields are written last. Emulating this behavior is going
      # to be a nightmare...
      'PUBLISHER': 'ORGANIZATION',
      'TOTALDISCS': 'DISCTOTAL',
      'TOTALTRACKS': 'TRACKTOTAL',
  }

  def __init__(
      self, args=None, titleformatter=None, fileformatter=None, printer=None):
    super(MutagenFileMetadataHandler, self).__init__(
        args, titleformatter, fileformatter, printer)
    # I know this looks stupid, but we really only need this submodule if we are
    # going to be processing file metadata. Same with the ID3 configuration.
    from . import tagext

    tagext.configure_id3_ext()

    self.progress = hasattr(args, 'progress') and args.progress

  def handle_metadata(self, filename, mutagen_file, track, is_new_file, silent):
    if self.args.write_file_metadata:
      if self.progress and not silent:
        self.printer.update_status('Checking metadata')
      return self.really_handle_metadata(
          mutagen_file, track, is_new_file, silent)

  def really_handle_metadata(
      self, filename, mutagen_file, track, is_new_file, silent):
    is_new_instance = False

    if mutagen_file is None or not is_mutagen_file(mutagen_file):
      is_new_instance = True
      mutagen_file = File(filename, easy=True)

    is_complex_type = isinstance(mutagen_file, (
        ID3FileType, EasyID3FileType, EasyMP4, EasyMP3, MP3, MP4,
        EasyTrueAudio, TrueAudio))

    changed = is_new_file or self.has_metadata_changed(
        mutagen_file, track, is_complex_type)

    if is_new_file or changed:
      if self.progress and not silent:
        self.printer.update_status('Updating metadata')

      try:
        if not self.args.dry_run:
          self.maybe_clear_existing_metadata(
              filename, mutagen_file, is_new_file)

        complex_discnumber = None
        complex_totaldiscs = None
        complex_tracknumber = None
        complex_totaltracks = None

        for key, value in iteritems(track):
          if key == '@':
            continue

          mutagen_key = self.marshal_mutagen_key(
              mutagen_file, key, is_complex_type)

          if is_complex_type:
            if mutagen_key == 'discnumber':
              complex_discnumber = value
              continue
            elif mutagen_key == 'totaldiscs':
              complex_totaldiscs = value
              continue
            elif mutagen_key == 'tracknumber':
              complex_tracknumber = value
              continue
            elif mutagen_key == 'totaltracks':
              complex_totaltracks = value
              continue

          mutagen_file[mutagen_key] = value

        if is_complex_type:
          if complex_totaldiscs:
            if complex_discnumber:
              complex_value = complex_discnumber + '/' + complex_totaldiscs
              mutagen_file['discnumber'] = complex_value
            else:
              mutagen_file['totaldiscs'] = complex_totaldiscs
          elif complex_discnumber:
            mutagen_file['discnumber'] = complex_discnumber

          if complex_totaltracks:
            if complex_tracknumber:
              complex_value = complex_tracknumber + '/' + complex_totaltracks
              mutagen_file['tracknumber'] = complex_value
            else:
              mutagen_file['totaltracks'] = complex_totaltracks
          elif complex_tracknumber:
            mutagen_file['tracknumber'] = complex_tracknumber

        if not self.args.dry_run and not is_new_instance:
          self.handle_metadata_write(filename, mutagen_file, is_new_file)
      except UnwritableMetadataException:
        self.on_unwritable_metadata(filename)

    return changed

  def on_unwritable_metadata(self, filename):
    if not self.args.quiet:
      if self.args.even_if_readonly:
        # We shouldn't be throwing this exception if we're forcing the
        # write with --even-if-readonly.
        raise InvalidProcessorStateException(
            'Failed to write metadata for ' + filename)
      else:
        if self.progress:
          self.printer.update_last_file(
              "Couldn't write metadata -- readonly file"
              + " (force with --even-if-readonly)")
        else:
          uniprint("Can't write metadata for readonly file " + filename)
          uniprint('  (use --even-if-readonly to force writing readonly files)')

  def handle_metadata_write(self, filename, mutagen_file, is_new_file):
    did_write = self.write_metadata(filename, mutagen_file, is_new_file)
    if did_write and self.progress:
      # TODO(dremelofdeath): Gah, I know this shouldn't be here. I'll fix
      # it later...
      # Don't check silent. If the metadata has changed, we will stop
      # fast-forwarding here.
      self.printer.update_last_file('Success!')

  def safe_handle_metadata_write(self, filename, mutagen_file, is_new_file):
    try:
      self.handle_metadata_write(filename, mutagen_file, is_new_file)
    except UnwritableMetadataException:
      self.on_unwritable_metadata(filename)

  @classmethod
  def marshal_mutagen_key(cls, mutagen_file, key, is_complex_type):
    """
    Translates from Foobar2000's label of the metadata frame to Mutagen's
    expected format. This varies based on the type of the file that you are
    trying to write (in particular, ID3 is complicated).
    """
    if is_complex_type:
      # These types are weird, so we're just going to return a lowercased key.
      return key.lower()

    # We will temporarily deal with uppercase IDs. We might marshal back to
    # lowercase if we need to. (This is probably not the case...)
    upperkey = key.upper()

    # If this is just a known thing (known to me, at least) that Foobar does to
    # metadata strings in the way it handles them, return that thing.
    if upperkey in cls.known_foobar_keys:
      # TODO(dremelofdeath): Determine if the considered field would be
      # considered a 'real' field by Foobar in the event there are duplicates of
      # the internal IDs.
      return cls.known_foobar_keys[upperkey]

    if upperkey.startswith('REPLAYGAIN_'):
      return upperkey.lower()

    return upperkey

  def safe_clear_metadata(self, mutagen_file):
    # It might be the case that Mutagen fails to correctly initialize the file
    # object; if this is the case, we'll correct that for them (it's probably a
    # bug) and then erase the metadata anyway. This might be a Python 3 thing.
    if isinstance(mutagen_file, FLAC) and mutagen_file.tags is not None:
      if mutagen_file.tags not in mutagen_file.metadata_blocks:
        mutagen_file.metadata_blocks.append(mutagen_file.tags)
    mutagen_file.delete()

  def maybe_clear_existing_metadata(self, filename, mutagen_file, is_new_file):
    self.maybe_force_write(
        filename, is_new_file, lambda: self.safe_clear_metadata(mutagen_file))

  def has_metadata_changed(self, mutagen_file, track, is_complex_type):
    if is_complex_type:
      # If you're dealing with any of these complex types, it's wayyyy easier to
      # simply just rewrite the metadata every single time. Just go to the disk.
      return True

    left_keys = mutagen_file.keys()
    right_keys = track.keys()

    left_keys_len = len(left_keys)
    # Note that the '@' field is virtual, so we won't count that.
    right_keys_len = len(right_keys) - 1

    # If the number of metadata fields if different, the metadata has changed.
    if left_keys_len != right_keys_len:
      return True

    marshalled_right_keys = [self.marshal_mutagen_key(
                                 mutagen_file, key, is_complex_type)
                             for key in right_keys if key != '@']

    # If any of the fields in the right are not in the left, it's changed.
    for each in marshalled_right_keys:
      # Mutagen can lowercase the data and Foobar can still read it.
      if each not in left_keys and each.lower() not in left_keys:
        return True

    # If any of the field values have changed (or changed types), it's changed.
    for key, value in iteritems(track):
      if key != '@':
        marshalled_key = self.marshal_mutagen_key(
            mutagen_file, key, is_complex_type)

        before = mutagen_file[marshalled_key]

        if isinstance(before, (list, tuple)):
          # Mutagen usually gives us a singleton list.
          if len(before) == 1:
            before = before[0]
            if before != value:
              # This single field has changed.
              return True
          else:
            if isinstance(value, (list, tuple)):
              if len(before) == len(value):
                for i, each in enumerate(before):
                  if each != value[i]:
                    # The values or order of values have changed.
                    return True
              else:
                # This field has changed types or length.
                return True
        else:
          if before != value:
            return True

    return False

  def on_existing_file_skipped(self):
    if not self.args.quiet:
      if hasattr(self.args, 'progress') and self.args.progress:
        self.printer.update_last_file(
            'File exists (use --update-metadata to write newer metadata)')
      else:
        uniprint('Not writing newer metadata because file exists')
        uniprint('  (use --update-metadata to write metadata anyway)')

  def write_metadata(self, filename, mutagen_file, is_new_file):
    if not is_new_file:
      if not self.args.update_metadata:
        self.on_existing_file_skipped()
        return False
      if not self.args.quiet:
        self.printer.update_status('Writing metadata', ' for: ' + filename)

    self.maybe_force_write(
        filename, is_new_file, lambda: mutagen_file.save(filename))

    return True

  def maybe_force_write(self, filename, is_new_file, forced_write_closure):
    try:
      write_with_override(filename, forced_write_closure,
          override = is_new_file or self.args.even_if_readonly)
    except IOError:
      # Can't force it for some reason. We will skip it.
      raise UnwritableMetadataException('Metadata unwritable for ' + filename)


class AutomaticConfiguringCommand(DefaultPrintingConfigurable):
  def __init__(
      self, args=None, titleformatter=None, fileformatter=None, printer=None):
    # Set defaults for these in case the package is being imported.
    case_sensitive = False
    magic = False

    if args is not None:
      if hasattr(args, 'case_sensitive'):
        case_sensitive = args.case_sensitive
      if hasattr(args, 'magic'):
        magic = args.magic

    if titleformatter is None:
      titleformatter = titleformat.TitleFormatter(
          case_sensitive, magic, for_filename=False)

    if fileformatter is None:
      fileformatter = titleformat.TitleFormatter(
          case_sensitive, magic, for_filename=True)

    super(AutomaticConfiguringCommand, self).__init__(
        args, titleformatter, fileformatter, printer)


class TrackCommand(AutomaticConfiguringCommand):
  def __init__(
      self, args=None, titleformatter=None, fileformatter=None, printer=None):
    super(TrackCommand, self).__init__(
        args, titleformatter, fileformatter, printer)
    self._records_processed = None
    self.quiet = hasattr(args, 'quiet') and args.quiet
    self.progress = hasattr(args, 'progress') and args.progress
    self.total_tags = 0
    self.tags_done = 0

  @property
  def records_processed(self):
    return self._records_processed

  def is_static_pattern(self, pattern):
    formatted = self.titleformatter.format({}, pattern)
    return pattern == formatted

  def static_format(self, track, field, **kwargs):
    if field in kwargs:
      value = kwargs[field]
      staticfield = field + 'static'
      if staticfield not in kwargs or not kwargs[staticfield]:
        value = self.titleformatter.format(track, value)
      return value

  def precompute_static_pattern(self, track_params, attr):
    argsattr = getattr(self.args, attr)
    if argsattr:
      track_params[attr] = argsattr
      if self.is_static_pattern(argsattr):
        track_params[attr + 'static'] = True

  def precompute_static_filter_patterns(self, track_params):
    self.precompute_static_pattern(track_params, 'startswith')
    self.precompute_static_pattern(track_params, 'equals')
    self.precompute_static_pattern(track_params, 'contains')

  def precompute_static_group_filter_patterns(self, track_params):
    self.precompute_static_pattern(track_params, 'group_startswith')

  def should_filter_include(self, formatted, track, **kwargs):
    if 'startswith' in kwargs:
      startswith = self.static_format(track, 'startswith', **kwargs)
      return formatted.startswith(startswith)
    elif 'equals' in kwargs:
      equals = self.static_format(track, 'equals', **kwargs)
      return formatted == equals
    elif 'contains' in kwargs:
      contains = self.static_format(track, 'contains', **kwargs)
      return contains in formatted
    return True

  def should_group_filter_include(self, formattedgroup, track, **kwargs):
    if 'group_startswith' in kwargs:
      group_startswith = self.static_format(track, 'group_startswith', **kwargs)
      return formattedgroup.startswith(group_startswith)
    return True

  def handle_tags(self, dirpath, tags):
    pass

  def run(self):
    visited_dirs = None

    try:
      visited_dirs = self.do_run()
    except LimitReachedException as e:
      visited_dirs = e.visited_dirs

    self.printer.print_deferred_output()
    return visited_dirs

  def do_run(self):
    self._records_processed = 0
    visited_dirs = {}
    tagsname = self.args.tagsfile

    if self.progress:
      v = {'s': 0}
      self.handle_all_tags(
          tagsname,
          lambda dirpath, dirnames, filenames, all_tags:
              self._setd(v, 's', v['s'] + len(all_tags)))
      self.total_tags = v['s']
      self.on_progress_count_complete()

    self.handle_all_tags(
        tagsname,
        lambda dirpath, dirnames, filenames, all_tags:
            self.handle_each_tag(dirpath, all_tags, visited_dirs))

    return visited_dirs

  def _setd(self, d, key, value):
    d[key] = value

  def on_progress_count_complete(self):
    pass

  def on_progress_tag_done(self):
    pass

  def handle_all_tags(self, tagsname, on_tags_found):
    for dirpath, dirnames, filenames in os.walk(unicwd()):
      all_tags = [each for each in filenames if each == tagsname]
      on_tags_found(dirpath, dirnames, filenames, all_tags)

  def handle_each_tag(self, dirpath, all_tags, visited_dirs):
    self.on_progress_tag_done()
    for tagsfile in all_tags:
      tags = mtags.TagsFile(os.path.join(dirpath, tagsfile))
      self.handle_tags(dirpath, tags, visited_dirs)
      self.tags_done = self.tags_done + 1
      self.on_progress_tag_done()

  def process_record(self, visited_dirs, on_accounting_done):
    if self.args and self.records_processed == self.args.limit:
      raise LimitReachedException(visited_dirs=visited_dirs)
    on_accounting_done()
    self._records_processed += 1


class CoverArtConfigurableCommand(TrackCommand):
  def __init__(self, args=None, titleformatter=None, fileformatter=None,
      printer=None, cover_finder=None):
    super(CoverArtConfigurableCommand, self).__init__(
        args, titleformatter, fileformatter, printer)

    if cover_finder is None:
      if hasattr(self.args, 'embed_covers') and self.args.embed_covers:
        cover_finder = EmbeddedCoverArtFinder(
            self.args, self.titleformatter, self.fileformatter, self.printer)
      else:
        cover_finder = CoverArtFinder(
            self.args, self.titleformatter, self.fileformatter, self.printer)

    self._cover_finder = cover_finder

  @property
  def cover_finder(self):
    return self._cover_finder


class CoverArtFileMetadataConfigurableCommand(CoverArtConfigurableCommand):
  def __init__(self, args=None, titleformatter=None, fileformatter=None,
      printer=None, cover_finder=None, metadata_handler=None):
    super(CoverArtFileMetadataConfigurableCommand, self).__init__(
        args, titleformatter, fileformatter, printer, cover_finder)

    if metadata_handler is None:
      metadata_handler = MutagenFileMetadataHandler(
          self.args, self.titleformatter, self.fileformatter, self.printer)

    self._metadata_handler = metadata_handler

  @property
  def metadata_handler(self):
      return self._metadata_handler


class ListCommand(TrackCommand):
  def __init__(
      self, args=None, titleformatter=None, fileformatter=None, printer=None):
    super(ListCommand, self).__init__(
        args, titleformatter, fileformatter, printer)
    self.groupby = args and hasattr(args, 'groupby') and args.groupby

  def on_formatted_track_included(self, track, formatted, group, **kwargs):
    self.printer.print_or_defer_output(formatted, group)

  def handle_formatted_track(self, track, formatted, **kwargs):
    group = None
    if self.groupby:
      group = self.titleformatter.format(track, self.groupby)
      if not self.should_group_filter_include(group, track, **kwargs):
        return
    if self.should_filter_include(formatted, track, **kwargs):
      self.on_formatted_track_included(track, formatted, group, **kwargs)

  def handle_track(self, track, **kwargs):
    formatted = self.titleformatter.format(track, self.args.display)
    self.handle_formatted_track(track, formatted, **kwargs)

  def handle_tags(self, dirpath, tags, visited_dirs):
    track_params = {}
    self.precompute_static_filter_patterns(track_params)
    if self.groupby:
      self.precompute_static_group_filter_patterns(track_params)
    for track in tags.tracks:
      self.process_record(
          visited_dirs, lambda: self.handle_track(track, **track_params))


class CountCommand(ListCommand):
  def __init__(
      self, args=None, titleformatter=None, fileformatter=None, printer=None):
    super(CountCommand, self).__init__(
        args, titleformatter, fileformatter, printer)
    self.totalcount = 0

  def on_formatted_track_included(self, track, formatted, group, **kwargs):
    self.totalcount = self.totalcount + 1

  def run(self):
    visited_dirs = super(CountCommand, self).run()
    uniprint(unistr(self.totalcount))
    return visited_dirs


class CopyCommand(CoverArtFileMetadataConfigurableCommand):
  def __init__(self, args=None, titleformatter=None, fileformatter=None,
      printer=None, cover_finder=None, metadata_handler=None):
    super(CopyCommand, self).__init__(args, titleformatter, fileformatter,
        printer, cover_finder, metadata_handler)

    self.is_fast_forwarding = self.progress

  def on_progress_count_complete(self):
    super(CopyCommand, self).on_progress_count_complete()
    if self.is_fast_forwarding:
      self.printer.update_status('Fast forwarding...')

  def on_progress_tag_done(self):
    super(CopyCommand, self).on_progress_tag_done()
    self.printer.update_progress(
        self.tags_done, self.total_tags, 'tags')

  def check_new_file(self, dst):
    if os.path.isfile(dst):
      if not self.args.quiet:
        if not self.is_fast_forwarding:
          self.printer.update_last_file('File already exists', ': ' + dst)
      return False
    return True

  def create_dirs(self, dirname):
    if self.progress:
      self.printer.update_status('Creating target directory')
    try:
      os.makedirs(dirname)
    except OSError:
      pass

  def create_dirs_and_copy(self, dirname, src, dst, noun):
    is_new_file = self.check_new_file(dst)

    if is_new_file:
      if not self.quiet and not self.progress:
        uniprint(dst)
      if os.path.isfile(src):
        if not self.args.dry_run:
          self.create_dirs(dirname)

          if self.progress:
            self.printer.update_status('Copying ' + noun)

          shutil.copy2(src, dst)
      else:
        if self.progress:
          uniprint(dst)
        raise FileAccessException('cannot access file ' + src)

    return is_new_file

  def create_dirs_and_copy_if_size_changed(self, dirname, src, dst, noun):
    srcsize = os.path.getsize(src)
    dstsize = -1

    try:
      dstsize = os.path.getsize(dst)
    except OSError:
      pass

    if srcsize != dstsize:
      self.create_dirs_and_copy(dirname, src, dst, noun)

  def handle_cover(self, dirpath, track, dirname, dst_file, mutagen_file):
    cover = self.cover_finder.find_cover_art(
        dirpath, track, dirname, silent=self.is_fast_forwarding)

    if cover:
      coversrc = cover[0]
      coverdst = cover[1]
      if (not self.args.embed_covers
          or self.args.embed_covers == EmbedCoversArg.EMBED_AND_COPY):
        if self.is_fast_forwarding:
          self.create_dirs_and_copy_if_size_changed(
              dirname, coversrc, coverdst, 'cover art')
        else:
          self.create_dirs_and_copy(dirname, coversrc, coverdst, 'cover art')
      if self.args.embed_covers:
        albumart.embed(coversrc, mutagen_file)

  def handle_file_metadata(self, filename, track, is_new_file, mutagen_file):
    changed = self.metadata_handler.handle_metadata(
        filename, mutagen_file, track, is_new_file, self.is_fast_forwarding)
    if self.is_fast_forwarding and changed:
      self.is_fast_forwarding = False

  def handle_track(self, dirpath, track, visited_dirs, **kwargs):
    track_filename = unistr(track.get('@'))

    if self.args.skip_cue:
      if '.cue|' in track_filename:
        return

    u_dirpath = unistr(dirpath)
    u_track_filename = unistr(track_filename)
    src = os.path.join(u_dirpath, u_track_filename)
    dst = self.fileformatter.format(
        track, self.args.to + '.$ext(%filename_ext%)')
    dirname, basename = os.path.split(dst)

    is_new_file = self.create_dirs_and_copy(dirname, src, dst, 'track')

    if not is_new_file and not self.args.update_metadata:
      # Check this up here to keep us from opening the file, which is faster.
      self.metadata_handler.on_existing_file_skipped()
    else:
      mutagen_file = File(dst, easy=True)

      if self.is_fast_forwarding and is_new_file:
        self.is_fast_forwarding = False

      # Passing a mutagen file prevents this method from autosaving it.
      self.handle_file_metadata(dst, track, is_new_file, mutagen_file)
      self.handle_cover(dirpath, track, dirname, dst, mutagen_file)
      self.metadata_handler.safe_handle_metadata_write(
          dst, mutagen_file, is_new_file)

    if self.args.write_mtags:
      if dirname not in visited_dirs:
        visited_dirs[dirname] = []
      visited_dirs[dirname].append((basename, track))

  def handle_tags(self, dirpath, tags, visited_dirs):
    totaltracks = len(tags.tracks)
    done = 0
    for track in tags.tracks:
      if not self.is_fast_forwarding:
        self.printer.update_track_and_album(track)
        self.printer.update_current(
            done, totaltracks, 'tracks', self._records_processed)

      self.process_record(
          visited_dirs, lambda: self.handle_track(dirpath, track, visited_dirs))

      done = done + 1

      if not self.is_fast_forwarding:
        self.printer.update_current(
            done, totaltracks, 'tracks', self._records_processed)

  def run(self):
    if self.progress:
      self.printer.update_status('Initializing...')
    visited_dirs = super(CopyCommand, self).run()
    if self.args.write_mtags:
      for dirname, trackfiles in compat_iteritems(visited_dirs):
        pending_mtags = []
        for trackfile in trackfiles:
          basename = trackfile[0]
          trackinfo = trackfile[1].copy()
          trackinfo['@'] = basename
          pending_mtags.append(trackinfo)
        mtagsfile = mtags.TagsFile(pending_mtags)
        mtags_dst = os.path.join(dirname, self.args.tagsfile)
        if not self.args.quiet:
          uniprint(mtags_dst)
        if not self.args.dry_run:
          mtagsfile.write(mtags_dst)
    return visited_dirs


class FindCoversCommand(CoverArtConfigurableCommand):
  def handle_cover(self, dirpath, track):
    cover = self.cover_finder.find_cover_art(dirpath, track)
    if cover:
      uniprint(dirpath)
      uniprint('  ==> ' + cover)
      uniprint('')

  def handle_track(self, dirpath, track, **kwargs):
    if self.args and self.args.filter_value:
      formatted = self.titleformatter.format(track, self.args.filter_value)
      if self.should_filter_include(formatted, track, **kwargs):
        self.handle_cover(dirpath, track)
    else:
      self.handle_cover(dirpath, track)

  def handle_tags(self, dirpath, tags, visited_dirs):
    track_params = {}
    self.precompute_static_filter_patterns(track_params)
    for track in tags.tracks:
      self.process_record(
          visited_dirs,
          lambda: self.handle_track(dirpath, track, **track_params))

  def run(self):
    if not self.args or not self.args.include_covers:
      sep = '\n    '
      parser.error(
          'you must specify one of the following options:%s%s' % (
              sep,
              sep.join([
                '--include-covers',
                '--include-covers-default',
                '--include-covers-aggressive',
              ])
          )
      )
    if hasattr(self.args, 'progress') and self.args.progress:
      if hasattr(self.args, 'explain') and self.args.explain:
        parser.error('you cannot specify both --progress and --explain')
    return super(FindCoversCommand, self).run()


class GenerateCommand(AutomaticConfiguringCommand):
  def __init__(
      self, args=None, titleformatter=None, fileformatter=None, printer=None):
    super(GenerateCommand, self).__init__(
        args, titleformatter, fileformatter, printer)

  def process_single_media(self, filename, mutagen_file, taglist):
    track = {}

    track['@'] = filename

    for key in mutagen_file.keys():
      metadata_field = mutagen_file[key]

      if isinstance(metadata_field, list) and len(metadata_field) == 1:
        metadata_field = metadata_field[0]

      lower_key = key.lower()
      if lower_key in ('tracknumber', 'discnumber') and '/' in metadata_field:
        complex_key_1 = FoobarMetadataHandler.marshal_foobar_key(
            'tracknumber' if lower_key == 'tracknumber' else 'discnumber')
        complex_key_2 = FoobarMetadataHandler.marshal_foobar_key(
            'totaltracks' if lower_key == 'tracknumber' else 'totaldiscs')
        complex_value_1, complex_value_2 = metadata_field.split('/')
        track[complex_key_1] = complex_value_1
        track[complex_key_2] = complex_value_2
      else:
        track[FoobarMetadataHandler.marshal_foobar_key(key)] = metadata_field

    taglist.append(track)

  def handle_all_media(self):
    all_tags = {}

    for dirpath, dirnames, filenames in os.walk(unicwd()):
      for each in filenames:
        mutagen_file = File(os.path.join(dirpath, each), easy=True)
        if mutagen_file is not None:
          if dirpath not in all_tags:
            all_tags[dirpath] = {
                'file': os.path.join(dirpath, self.args.tagsfile),
                'tracks': [],
            }

          self.process_single_media(
              each, mutagen_file, all_tags[dirpath]['tracks'])

    tags_written = 0

    for each in sorted(all_tags.keys()):
      tracks = all_tags[each]['tracks']

      if len(tracks) == 0:
        continue

      filename = all_tags[each]['file']

      if not self.args.quiet:
        self.printer.print_or_defer_output(
            'writing tags file: %s (%d tracks)' % (filename, len(tracks)))

      mtags.TagsFile(tracks).write(filename)

      tags_written = tags_written + 1

    if tags_written == 0:
      self.printer.print_or_defer_output(
          "couldn't find any tags to write -- are you in the right directory?")
    elif tags_written > 1:
      self.printer.print_or_defer_output(
          "%d tag files written" % (tags_written))

  def run(self):
    self.handle_all_media()


def provide_configured_command(args):
  if args.cmd == 'list':
    return ListCommand(args)
  elif args.cmd == 'count':
    return CountCommand(args)
  elif args.cmd == 'copy':
    return CopyCommand(args)
  elif args.cmd == 'findcovers':
    return FindCoversCommand(args)
  elif args.cmd == 'generate':
    return GenerateCommand(args)
  else:
    parser.error("can't understand command '%s' -- this is a bug!" % (args.cmd))

def main():
  args = parser.parse_args()
  command = provide_configured_command(args)
  command.run()

if __name__ == '__main__':
  main()

