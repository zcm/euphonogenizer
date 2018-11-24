#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from euphonogenizer import titleformat

collective_soul_01 = {
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

class TestTitleFormatter:
    f = titleformat.TitleFormatter()

    def do_integration_test(
            self, fmt, expected, expected_truth=None, track=collective_soul_01):
        interpreted = self.f.eval(track, fmt)
        compiled = self.f.eval(None, fmt, compiling=True)(track)

        assert interpreted.string_value == expected

        if expected_truth is not None:
            assert interpreted.truth_value is expected_truth

        assert interpreted == compiled

    def test_eval_integration_add_arity0(self):
        self.do_integration_test('$add()', '0', False)

    def test_eval_integration_add_arity1(self):
        self.do_integration_test('$add(123)', '123', False)

    def test_eval_integration_add_arity2(self):
        self.do_integration_test('$add(12,34)', '46', False)

    def test_eval_integration_add_arity3(self):
        self.do_integration_test('$add(1,2,3)', '6', False)

    def test_eval_integration_add_arity4(self):
        self.do_integration_test('$add(1,2,3,4)', '10', False)

    def test_eval_integration_add_arity2_nested(self):
        self.do_integration_test('$add(1,$add(1,$add(1,$add(1))))', '4', False)
