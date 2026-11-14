import json
import os
from pathlib import Path
import tempfile
import unittest

from review_library import CA02, LEGACY, ReviewLibrary


class ReviewLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'NEURAL_STUDIO_2'
        self.root.mkdir()
        self.lib = ReviewLibrary(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def video(self, relative, data=b'fixture-video'):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def listing(self, pid='alpha'):
        return self.lib.list(pid, {'id': pid})

    def test_new_latest_dedup_and_restart(self):
        older = self.video('data/projects/alpha/renders/v1.mp4')
        os.utime(older, (100, 100))
        first = self.listing()
        newer = self.video('data/projects/alpha/renders/v2.mp4')
        result = self.lib.list('alpha', {'id': 'alpha', 'links': [{'kind': 'render', 'path': str(newer)}]})
        self.assertEqual(len(result['versions']), 2)
        self.assertEqual(result['latest'], result['versions'][0]['id'])
        self.assertEqual(result['versions'][0]['path'], str(newer.resolve()))
        restarted = ReviewLibrary(self.root)
        self.assertEqual(restarted.media_path('alpha', first['latest']), older.resolve())

    def test_isolation_arbitrary_path_and_source_footage(self):
        self.video('data/projects/alpha/renders/a.mp4')
        foreign = self.video('data/projects/beta/renders/b.mp4')
        self.video('data/projects/alpha/media/episode.mp4')
        result = self.lib.list('alpha', {'links': [{'kind': 'review', 'path': str(foreign)}]})
        self.assertEqual(len(result['versions']), 1)
        with self.assertRaises(FileNotFoundError):
            self.lib.media_path('beta', result['latest'])
        with self.assertRaises(FileNotFoundError):
            self.lib.media_path('alpha', str(foreign))
        with self.assertRaises(ValueError):
            self.listing('../alpha')

    def test_deleted_and_replaced_files_fail_until_refresh(self):
        file = self.video('data/projects/alpha/renders/a.mp4')
        result = self.listing()
        file.write_bytes(b'new version is longer')
        with self.assertRaises(FileNotFoundError):
            self.lib.media_path('alpha', result['latest'])
        self.listing()
        file.unlink()
        with self.assertRaises(FileNotFoundError):
            self.lib.media_path('alpha', result['latest'])
        self.assertEqual(self.listing()['versions'], [])

    def test_manifest_completed_steps_and_proxy(self):
        folder = self.root / 'data/local-ops/jobs/job1'
        native = self.video('data/local-ops/jobs/job1/native/native.mov')
        proxy = self.video('data/local-ops/jobs/job1/review/review.mp4')
        self.video('data/local-ops/jobs/job1/scout/source.mp4')
        self.video('data/local-ops/jobs/job1/unready/half.mp4')
        manifest = {'project': 'alpha', 'title': 'Version 3', 'status': 'FAILED', 'steps': [
            {'id': 'native', 'operation': 'native_render', 'status': 'COMPLETED', 'outputs': ['native.mov']},
            {'id': 'review', 'operation': 'review_copy', 'status': 'COMPLETED', 'outputs': ['review.mp4']},
            {'id': 'scout', 'operation': 'frames', 'status': 'COMPLETED', 'outputs': ['source.mp4']},
            {'id': 'unready', 'operation': 'review_copy', 'status': 'RUNNING', 'outputs': ['half.mp4']}]}
        (folder / 'JOB.json').write_text(json.dumps(manifest))
        result = self.listing()
        self.assertEqual(len(result['versions']), 2)
        self.assertEqual(self.lib.media_path('alpha', result['latest']), proxy.resolve())
        self.assertTrue(next(r for r in result['versions'] if r['path'] == str(native.resolve()))['needsProxy'])
        self.assertEqual(self.listing('beta')['versions'], [])

    def test_legacy_source_proofs_are_not_current_renders(self):
        legacy = '3046a40e2ef045bbbe5b94b6d608209a'
        file = self.root.parent / 'NEURAL_STUDIO/data/projects' / legacy / 'renders/proof.mp4'
        file.parent.mkdir(parents=True)
        file.write_bytes(b'legacy proof')
        self.assertEqual(self.listing('alpha')['versions'], [])
        result = self.listing(CA02)
        self.assertEqual(result['versions'], [])

    def test_app_media_notification_owner_and_stale_metadata(self):
        proxy = self.video('data/local-ops/jobs/job1/review/review.mp4')
        manifest = proxy.parent.parent / 'JOB.json'
        manifest.write_text(json.dumps({'project_id': None, 'notification_project': 'alpha',
            'steps': [{'id': 'review', 'operation': 'review_copy', 'status': 'COMPLETED',
                       'outputs': ['review.mp4']}]}))
        st = manifest.stat()
        self.lib.folder.mkdir(parents=True)
        self.lib._index('alpha').write_text(json.dumps({'metadata': {str(manifest): {
            'stamp': [st.st_size, st.st_mtime_ns], 'owner': None, 'steps': []}}}))
        result = self.listing()
        self.assertEqual(self.lib.media_path('alpha', result['latest']), proxy.resolve())
        self.assertEqual(self.listing('beta')['versions'], [])

    def test_production_singular_render_directory(self):
        video = self.video('data/projects/alpha/render/full.mp4')
        self.assertEqual(self.lib.media_path('alpha', self.listing()['latest']), video.resolve())

    def test_symlink_escape(self):
        outside = self.video('outside/secret.mp4')
        directory = self.root / 'data/projects/alpha/renders'
        directory.mkdir(parents=True)
        try:
            (directory / 'secret.mp4').symlink_to(outside)
            (directory / 'elsewhere').symlink_to(outside.parent, target_is_directory=True)
        except OSError:
            self.skipTest('Host does not allow symlink creation')
        self.assertEqual(self.listing()['versions'], [])

    def test_manual_export_registration(self):
        p = self.video('data/editor/exports/job1/output.mp4')
        (p.parent / 'job.json').write_text(json.dumps({'project': 'alpha', 'status': 'completed', 'title': 'Manual export'}))
        result = self.listing()
        self.assertEqual(len(result['versions']), 1)
        self.assertEqual(self.lib.media_path('alpha', result['latest']), p.resolve())


if __name__ == '__main__':
    unittest.main()
