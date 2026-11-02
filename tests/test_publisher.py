import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publisher', ROOT / 'scripts/publisher.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class FakeAPI:
    def __init__(self):
        self.items = {}
        self.calls = []
        self.uploads = 0
        self.fail_after_create = False

    def upload(self, endpoint, path, **kwargs):
        self.uploads += 1
        return {'media_id': 'fictional-cover', 'url': 'https://example.invalid/image-' + str(self.uploads)}

    def post(self, endpoint, payload):
        self.calls.append(endpoint)
        if endpoint == 'draft/add':
            self.items['fictional-draft'] = copy.deepcopy(payload['articles'][0])
            if self.fail_after_create:
                raise RuntimeError('Simulated response loss after server committed')
            return {'media_id': 'fictional-draft'}
        if endpoint == 'draft/update':
            self.items[payload['media_id']] = copy.deepcopy(payload['articles'])
            return {'errcode': 0}
        return {'news_item': [self.items[payload['media_id']]]}


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        shutil.copytree(ROOT / 'examples/demo', self.base, dirs_exist_ok=True)
        self.manifest = self.base / 'article.json'
        self.api = FakeAPI()

    def tearDown(self):
        self.tmp.cleanup()

    def article(self):
        return p.load_article(self.manifest)

    def test_create_retry_does_not_duplicate_and_update_keeps_id(self):
        p.run('create', self.article(), self.api)
        p.run('create', self.article(), self.api)
        self.assertEqual(self.api.calls.count('draft/add'), 1)
        src = self.base / 'article.html'
        src.write_text(src.read_text().replace('搜集、编辑和核验', '检索、编辑和核验'))
        with self.assertRaises(ValueError):
            p.run('create', self.article(), self.api)
        p.run('update', self.article(), self.api)
        state = json.loads(self.article()['receipt'].read_text())
        self.assertEqual(state['media_id'], 'fictional-draft')
        self.assertTrue(state['verified'])
        self.assertEqual(self.api.calls.count('draft/add'), 1)

    def test_uncertain_create_blocks_resubmit(self):
        self.api.fail_after_create = True
        with self.assertRaises(RuntimeError):
            p.run('create', self.article(), self.api)
        with self.assertRaises(ValueError):
            p.run('create', self.article(), self.api)
        self.assertEqual(self.api.calls.count('draft/add'), 1)
        self.assertEqual(json.loads(self.article()['receipt'].read_text())['in_flight'], 'create')

    def test_changed_body_image_changes_fingerprint(self):
        first = self.article()['fingerprint']
        img = self.base / 'body.png'
        img.write_bytes(img.read_bytes() + b'changed-test-asset')
        self.assertNotEqual(first, self.article()['fingerprint'])

    def test_path_escape_rejected(self):
        cfg = json.loads(self.manifest.read_text())
        cfg['receipt'] = '../escape.json'
        self.manifest.write_text(json.dumps(cfg))
        with self.assertRaises(ValueError):
            self.article()

    def test_readback_mismatch_is_not_marked_success(self):
        original_post = self.api.post
        def altered(endpoint, payload):
            result = original_post(endpoint, payload)
            if endpoint == 'draft/get':
                result['news_item'][0]['content'] = '<p>Wrong body</p>'
            return result
        self.api.post = altered
        with self.assertRaises(ValueError):
            p.run('create', self.article(), self.api)
        self.assertFalse(json.loads(self.article()['receipt'].read_text())['verified'])


if __name__ == '__main__':
    unittest.main()
