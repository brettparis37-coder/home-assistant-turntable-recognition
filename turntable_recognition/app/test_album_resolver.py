import unittest
from album_resolver import parse_timecode, normalized_name, standard_release_rank


class ResolverTests(unittest.TestCase):
    def test_timecode(self):
        self.assertEqual(parse_timecode("02:32"), 152)
        self.assertIsNone(parse_timecode("bad"))

    def test_normalizes_edition_suffix(self):
        self.assertEqual(normalized_name("Songs From the Big Chair (Super Deluxe Version)"),
                         "songs from the big chair")

    def test_standard_original_release_beats_deluxe(self):
        standard = {"id":"a", "title":"Album", "date":"1985-02-17",
                    "cover-art-archive":{"front":True}}
        deluxe = {"id":"b", "title":"Album (Super Deluxe Edition)", "date":"1985-02-01",
                  "cover-art-archive":{"front":True}}
        self.assertLess(standard_release_rank(standard, "1985-02-01"),
                        standard_release_rank(deluxe, "1985-02-01"))


if __name__ == "__main__": unittest.main()
