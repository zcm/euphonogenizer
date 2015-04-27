#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import glob
import os
import re
import shutil
import stat
import sys

import mtags
import titleformat

from args import parser
from common import dbg, err, unicwd, uniprint, unistr
from mutagen import File
from mutagen.id3 import ID3FileType
from mutagen.easyid3 import EasyID3FileType
from mutagen.easymp4 import EasyMP4
from mutagen.mp3 import EasyMP3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.trueaudio import EasyTrueAudio
from mutagen.trueaudio import TrueAudio
from mutagen._compat import iteritems
from retrying import retry

escape_glob_dict = {
    '[': '[[]',
    ']': '[]]',
}

escape_glob_rc = re.compile('|'.join(map(re.escape, escape_glob_dict)))


def escape_glob(path):
  return escape_glob_rc.sub(lambda m: escape_glob_dict[m.group(0)], path)

def retry_if_ioerror(exception):
  return isinstance(exception, IOError)


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

  @property
  def unique_output(self):
    return self._unique_output

  @property
  def groupby_output(self):
    return self._groupby_output

  def handle_group_uniprint(self, output, group):
    if group:
      if group not in self.groupby_output:
        self.groupby_output[group] = [output]
      else:
        self.groupby_output[group].append(output)
    else:
      uniprint(output)

  def print_or_defer_output(self, output, group=None):
    if self.args and hasattr(self.args, 'unique') and self.args.unique:
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


class CoverArtFinder(DefaultConfigurable):
  def __init__(self, args, titleformatter, fileformatter):
    super(CoverArtFinder, self).__init__(args, titleformatter, fileformatter)
    self._cover_dirs = set()

  @property
  def cover_dirs(self):
    return self._cover_dirs

  def find_cover_art(self, dirname, track, dstpath=None):
    if not self.args or not hasattr(self.args, 'include_covers'):
      # Just don't even bother.
      return
    if not self.args.include_covers:
      # Same here.
      return

    retval = None
    explain = hasattr(self.args, 'explain') and self.args.explain

    if dirname not in self.cover_dirs:
      if explain:
        uniprint('attempting to find cover art for directory:')
        uniprint('  ' + dirname)
      for each in self.args.include_covers:
        cover_file = os.path.join(
            dirname, self.titleformatter.format(track, each))
        cover_glob = glob.glob(escape_glob(cover_file))
        if explain:
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
            self.cover_dirs.add(dirname)
            retval = (found_cover, dst)
            break
      if not self.args.per_track_cover_search:
        self.cover_dirs.add(dirname)

    return retval


class MutagenFileMetadataHandler(DefaultConfigurable):
  # TODO(dremelofdeath): See if Foobar does this with filetypes other than FLAC
  # as well.
  known_foobar_keys = {
      # Foobar, I'm guessing, treats these fields as 'comment'-ish fields and
      # writes them first. From what I can gather, the comment-ish fields that
      # appear first are determined to be the 'real' fields, and if there are
      # others that have the same name as Foobar's internal name, they will come
      # afterwards.
      "ALBUM ARTIST": "ALBUMARTIST",
      # Foobar writes these fields right before ReplayGain fields, and uses its
      # proximity to them in order to determine which one is the "real" field,
      # in the event that there are multiple as far as I can tell. This is
      # basically the complete opposite of the previous group of fields, since
      # the ReplayGain fields are written last. Emulating this behavior is going
      # to be a nightmare...
      "PUBLISHER": "ORGANIZATION",
      "TOTALDISCS": "DISCTOTAL",
      "TOTALTRACKS": "TRACKTOTAL",
  }

  def __init__(self, args=None, titleformatter=None, fileformatter=None):
    super(MutagenFileMetadataHandler, self).__init__(
        args, titleformatter, fileformatter)
    # I know this looks stupid, but we really only need this submodule if we are
    # going to be processing file metadata. Same with the ID3 configuration.
    import tagext

    tagext.configure_id3_ext()

  def handle_metadata(self, filename, track, is_new_file):
    if self.args.write_file_metadata:
      self.really_handle_metadata(filename, track, is_new_file)

  def really_handle_metadata(self, filename, track, is_new_file):
    mutagen_file = File(filename, easy=True)
    changed = is_new_file or self.has_metadata_changed(mutagen_file, track)

    if is_new_file or changed:
      try:
        if not self.args.dry_run:
          self.maybe_clear_existing_metadata(
              filename, mutagen_file, is_new_file)

        for key, value in iteritems(track):
          if key == '@':
            continue
          mutagen_file[self.marshal_mutagen_key(mutagen_file, key)] = value

        if not self.args.dry_run:
          self.write_metadata(filename, mutagen_file, is_new_file)
      except UnwritableMetadataException:
        if not self.args.quiet:
          if self.args.even_if_readonly:
            # We shouldn't be throwing this exception if we're forcing the
            # write with --even-if-readonly.
            raise InvalidProcessorStateException(
                'Failed to write metadata for ' + filename)
          else:
            uniprint("can't write metadata for readonly file " + filename)
            uniprint(
                '  (use --even-if-readonly to force writing readonly files)')


  @classmethod
  def marshal_mutagen_key(cls, mutagen_file, key):
    """
    Translates from Foobar2000's label of the metadata frame to Mutagen's
    expected format. This varies based on the type of the file that you are
    trying to write (in particular, ID3 is complicated).
    """
    if isinstance(mutagen_file, (
        ID3FileType, EasyID3FileType, EasyMP4, EasyMP3, MP3, MP4,
        EasyTrueAudio, TrueAudio)):
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

  def maybe_clear_existing_metadata(self, filename, mutagen_file, is_new_file):
    self.maybe_force_write(filename, is_new_file, lambda: mutagen_file.delete())

  def has_metadata_changed(self, mutagen_file, track):
    left_keys = mutagen_file.keys()
    right_keys = track.keys()

    left_keys_len = len(left_keys)
    # Note that the '@' field is virtual, so we won't count that.
    right_keys_len = len(right_keys) - 1

    # If the number of metadata fields if different, the metadata has changed.
    if left_keys_len != right_keys_len:
      return True

    marshalled_right_keys = [self.marshal_mutagen_key(mutagen_file, key)
                             for key in right_keys if key != '@']

    # If any of the fields in the right are not in the left, it's changed.
    for each in marshalled_right_keys:
      # Mutagen can lowercase the data and Foobar can still read it.
      if each not in left_keys and each.lower() not in left_keys:
        return True

    # If any of the field values have changed (or changed types), it's changed.
    for key, value in iteritems(track):
      if key != '@':
        marshalled_key = self.marshal_mutagen_key(mutagen_file, key)
        before = mutagen_file[marshalled_key]

        if isinstance(before, (list, tuple)):
          # Mutagen usually gives us a singleton list.
          if len(before) == 1:
            before = before[0]
            if before != value:
              # This single field has changed.
              uniprint('diff: ' + before + ' ==> ' + value)
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

  def write_metadata(self, filename, mutagen_file, is_new_file):
    if not is_new_file and not self.args.update_metadata:
      if not self.args.quiet:
        uniprint('not writing newer metadata because file exists')
        uniprint('  (use --update-metadata to write metadata anyway)')
      return

    self.really_write_metadata(filename, mutagen_file, is_new_file)

  def really_write_metadata(self, filename, mutagen_file, is_new_file):
    if not is_new_file:
      if not self.args.quiet:
        uniprint('updating metadata for: ' + filename)

    self.maybe_force_write(
        filename, is_new_file, lambda: mutagen_file.save(filename))

  def maybe_force_write(self, filename, is_new_file, forced_write_closure):
    try:
      forced_write_closure()
    except IOError:
      # This is probably due to the read-only flag being set, so check it.
      if is_new_file or self.args.even_if_readonly:
        if not os.access(filename, os.W_OK):
          # We will just clear the flag temporarily and then set it back.
          mode = os.stat(filename)[stat.ST_MODE]
          os.chmod(filename, stat.S_IWRITE)
          forced_write_closure()
          os.chmod(filename, mode)
        else:
          # Something else bad is happening then.
          raise
      else:
        # We're not going to force it. The file isn't writable, so skip it.
        raise UnwritableMetadataException(
            'Metadata unwritable for ' + filename)


class LimitReachedException(Exception):
  def __init__(self, message="Limit reached", visited_dirs=None):
    super(LimitReachedException, self).__init__(message)
    self.visited_dirs = visited_dirs


class UnwritableMetadataException(Exception):
  pass


class InvalidProcessorStateException(Exception):
  pass


class AutomaticConfiguringCommand(DefaultConfigurable):
  def __init__(self, args=None, titleformatter=None, fileformatter=None,
      printer=None, cover_finder=None):
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
        args, titleformatter, fileformatter)

    if printer is None:
      printer = PrintHandler(self.args, self.titleformatter, self.fileformatter)

    self._printer = printer

  @property
  def printer(self):
    return self._printer


class TrackCommand(AutomaticConfiguringCommand):
  def __init__(
      self, args=None, titleformatter=None, fileformatter=None, printer=None):
    super(TrackCommand, self).__init__(
        args, titleformatter, fileformatter, printer)
    self._records_processed = None

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

    for dirpath, dirnames, filenames in os.walk(unicwd()):
      for tagsfile in [each for each in filenames if each == tagsname]:
        tags = mtags.TagsFile(os.path.join(dirpath, tagsfile))
        self.handle_tags(dirpath, tags, visited_dirs)

    return visited_dirs

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
      cover_finder = CoverArtFinder(
          self.args, self.titleformatter, self.fileformatter)

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
          self.args, self.titleformatter, self.fileformatter)

    self._metadata_handler = metadata_handler

  @property
  def metadata_handler(self):
      return self._metadata_handler


class ListCommand(TrackCommand):
  def handle_track(self, track, **kwargs):
    formatted = self.titleformatter.format(track, self.args.display)
    group = None
    if self.args and self.args.groupby:
      group = self.titleformatter.format(track, self.args.groupby)
      if not self.should_group_filter_include(group, track, **kwargs):
        return
    if self.should_filter_include(formatted, track, **kwargs):
      self.printer.print_or_defer_output(formatted, group)

  def handle_tags(self, dirpath, tags, visited_dirs):
    track_params = {}
    self.precompute_static_filter_patterns(track_params)
    self.precompute_static_group_filter_patterns(track_params)
    for track in tags.tracks:
      self.process_record(
          visited_dirs, lambda: self.handle_track(track, **track_params))


class CopyCommand(CoverArtFileMetadataConfigurableCommand):
  def create_dirs_and_copy(self, dirname, src, dst):
    is_new_file = True

    if os.path.isfile(dst):
      is_new_file = False
      if not self.args.quiet:
        uniprint('file already exists: ' + dst)
    else:
      if not self.args.quiet:
        uniprint(dst)
      if os.path.isfile(src):
        if not self.args.dry_run:
          try:
            os.makedirs(dirname)
          except OSError:
            pass

          shutil.copy2(src, dst)

    return is_new_file

  def handle_cover(self, dirpath, track, dirname):
    cover = self.cover_finder.find_cover_art(dirpath, track, dirname)

    if cover:
      coversrc = cover[0]
      coverdst = cover[1]
      self.create_dirs_and_copy(dirname, coversrc, coverdst)

  def handle_file_metadata(self, filename, track, is_new_file):
    self.metadata_handler.handle_metadata(filename, track, is_new_file)

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

    self.handle_cover(dirpath, track, dirname)

    is_new_file = self.create_dirs_and_copy(dirname, src, dst)

    self.handle_file_metadata(dst, track, is_new_file)

    if self.args.write_mtags:
      if dirname not in visited_dirs:
        visited_dirs[dirname] = []
      visited_dirs[dirname].append((basename, track))

  def handle_tags(self, dirpath, tags, visited_dirs):
    for track in tags.tracks:
      self.process_record(
          visited_dirs, lambda: self.handle_track(dirpath, track, visited_dirs))

  def run(self):
    visited_dirs = super(CopyCommand, self).run()
    if self.args.write_mtags:
      for dirname, trackfiles in visited_dirs.iteritems():
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
    return super(FindCoversCommand, self).run()

def provide_configured_command(args):
  if args.cmd == 'list':
    return ListCommand(args)
  elif args.cmd == 'copy':
    return CopyCommand(args)
  elif args.cmd == 'findcovers':
    return FindCoversCommand(args)
  else:
    parser.error("can't understand command '%s' -- this is a bug!" % (args.cmd))

def main():
  args = parser.parse_args()
  command = provide_configured_command(args)
  command.run()

if __name__ == '__main__':
  main()

