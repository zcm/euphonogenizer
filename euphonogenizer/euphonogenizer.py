#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import glob
import os
import re
import shutil
import sys

import mtags
import titleformat

from args import parser
from common import dbg, err, unicwd, uniprint, unistr

escape_glob_dict = {
    '[': '[[]',
    ']': '[]]',
}

escape_glob_rc = re.compile('|'.join(map(re.escape, escape_glob_dict)))


def escape_glob(path):
  return escape_glob_rc.sub(lambda m: escape_glob_dict[m.group(0)], path)


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


class LimitReachedException(Exception):
  def __init__(self, message="Limit reached", visited_dirs=None):
    super(LimitReachedException, self).__init__(message)
    self.visited_dirs = visited_dirs


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


class CopyCommand(CoverArtConfigurableCommand):
  def create_dirs_and_copy(self, dirname, src, dst):
    if os.path.isfile(dst):
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

  def handle_cover(self, dirpath, track, dirname):
    cover = self.cover_finder.find_cover_art(dirpath, track, dirname)

    if cover:
      coversrc = cover[0]
      coverdst = cover[1]
      self.create_dirs_and_copy(dirname, coversrc, coverdst)

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

    if self.args.write_mtags:
      if dirname not in visited_dirs:
        visited_dirs[dirname] = []
      visited_dirs[dirname].append((basename, track))

    self.create_dirs_and_copy(dirname, src, dst)

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

