"""A complete station result with stray trailing characters is still that result (run 8d4cac94, job 3614879f)."""
import json
import unittest

import station_results
from providers_engine.production_host import embedded_json


class ResultParsingTests(unittest.TestCase):
    def test_trailing_brace_fenced_and_prose_wrapped_objects_parse(self):
        good={'summary':'pass','production':{'phase':'goldfish_review','outcome':'complete'}}
        text=json.dumps(good)
        self.assertEqual(embedded_json(text+'}'),good)
        self.assertEqual(embedded_json(text+'\n}\n'),good)
        self.assertEqual(embedded_json('```json\n'+text+'\n```'),good)
        self.assertEqual(embedded_json('Result follows: '+text+' done.'),good)
    def test_non_objects_and_truncated_objects_are_rejected(self):
        for bad in ('', 'no json', '[1,2]', '{"summary":"cut', None, 5):
            self.assertIsNone(embedded_json(bad), bad)
    def test_decode_prefers_host_validated_object(self):
        good={'summary':'pass'}
        self.assertEqual(station_results.decode({'structured_result':good,'text':json.dumps(good)+'}'}),good)
        with self.assertRaises(ValueError):station_results.decode({'text':json.dumps(good)+'}'})


if __name__=='__main__':unittest.main()
