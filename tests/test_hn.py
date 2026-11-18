import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests
import radar


class HackerNewsTests(unittest.TestCase):
    def test_rejects_prefix_and_other_repository_matches(self):
        cases = [
            ('Universal XSS', 'https://iter.ca/post/ubo-uxss/', False),
            ('Univer Clipsheet', 'https://github.com/dream-num/univer-clipsheet', False),
            ('Univer', 'https://github.com/other/univer', False),
            ('Univer', 'https://github.com/dream-num/univer/', True),
        ]
        for title, url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(radar.hn_hit_matches('dream-num/univer', {'title': title, 'url': url}), expected)

    def test_generic_name_requires_repository_or_owner(self):
        self.assertFalse(radar.hn_hit_matches('anthropics/skills', {'title': 'Improve your skills', 'url': 'https://example.com/skills'}))
        self.assertTrue(radar.hn_hit_matches('anthropics/skills', {'title': 'Skills', 'url': 'https://github.com/anthropics/skills'}))

    @patch('radar.time.time', return_value=1800000000)
    @patch('radar.requests.get')
    def test_archives_do_not_inflate_recent_score_and_stories_are_deduplicated(self, get, clock):
        now = int(clock.return_value)
        def hit(i, days, points):
            created = now - days * 86400
            return {'objectID': str(i), 'title': 'Univer release',
                    'url': 'https://github.com/dream-num/univer', 'points': points,
                    'num_comments': i, 'created_at_i': created,
                    'created_at': datetime.fromtimestamp(created, timezone.utc).isoformat()}
        recent, older = hit(1, 1, 7), hit(2, 365, 900)
        response = Mock()
        response.json.return_value = {'hits': [older, recent]}
        get.return_value = response
        result = radar.hn_lookup('dream-num/univer')
        self.assertEqual(result['mentions'], 1)
        self.assertEqual(result['points'], 7)
        self.assertEqual(result['comments'], 1)
        self.assertEqual([s['id'] for s in result['stories']], ['1', '2'])
        self.assertEqual(result['top']['id'], '1')
        self.assertEqual(result['stories'][1]['url'], 'https://news.ycombinator.com/item?id=2')
        self.assertEqual(result['discussion_count'], 2)

    @patch('radar.requests.get', side_effect=requests.Timeout)
    def test_unavailable_service_does_not_report_zero_discussions(self, get):
        self.assertIsNone(radar.hn_lookup('dream-num/univer'))


if __name__ == '__main__':
    unittest.main()
