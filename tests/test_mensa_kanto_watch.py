import unittest

from mensa_kanto_watch import extract_entries, parse_region_section


class ParsingTest(unittest.TestCase):
    def test_parse_region_section_stops_at_next_region(self):
        html = """
        <h2>関東地方</h2><dl><dt>日時 ： 2026/10/18(日) 11:00</dt></dl>
        <h2>関西地方</h2><dl><dt>日時 ： 2026/10/19(月) 11:00</dt></dl>
        """

        section = parse_region_section(html, "関東地方")

        self.assertIn("2026/10/18", section)
        self.assertNotIn("2026/10/19", section)

    def test_extract_entries_reads_open_status_and_link(self):
        region_html = """
        <dl>
          <dt>日時 ： 2026/10/18(日) 11:00</dt>
          <dd><a href="/exam/apply"><img src="/images/entry_out.jpg"></a></dd>
        </dl>
        """

        entries = extract_entries(region_html)

        self.assertEqual(
            entries,
            [{
                "datetime": "日時 ： 2026/10/18(日) 11:00",
                "status": "申込可",
                "link": "/exam/apply",
            }],
        )


if __name__ == "__main__":
    unittest.main()
