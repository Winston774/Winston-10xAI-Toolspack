"""Real HTTP + decoded known-amplitude stereo, including cache and chunk edges."""
import array
import json
import math
import sys
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

from local_editor.media_engine import doctor
from local_editor.server import make_server


@unittest.skipUnless(doctor()["ready"], "需要 FFmpeg 與 FFprobe")
class WaveformHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="waveform-http-")
        cls.server = make_server(cls.directory.name, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.opener = build_opener(ProxyHandler({}))
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.path = cls.server.service.assets / "known-stereo.wav"
        samples = array.array('h')
        for i in range(48000 * 31 + 3360):
            t = i / 48000
            amplitude = 0 if t < 1 else .1 if t < 2 else .8 if t < 3 else .25
            value = round(32767 * amplitude * math.sin(2 * math.pi * 2000 * t))
            samples.extend((value, -value))
        if sys.byteorder != 'little':
            samples.byteswap()
        with wave.open(str(cls.path), 'wb') as output:
            output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            output.writeframes(samples.tobytes())
        project = cls.server.service.create_project({"name": "波形 HTTP 驗收"})
        cls.project = cls.server.service.import_media(project['id'], {
            "expected_version": project['version'], "path": str(cls.path)})
        media = cls.project['media'][0]
        cls.endpoint = f"/api/projects/{cls.project['id']}/media/{media['id']}/peaks"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server.service.close()
        cls.thread.join()
        cls.directory.cleanup()

    def request(self, path):
        try:
            response = self.opener.open(self.base + path, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, json.loads(response.read())

    def test_real_stereo_peaks_distinguish_silence_soft_and_loud_without_phase_cancellation(self):
        status, data = self.request(self.endpoint + '?chunk=0')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['peaks']), 3000)
        self.assertEqual(data['bucket_seconds'], .01)
        self.assertEqual(max(data['peaks'][5:95]), 0)
        self.assertAlmostEqual(data['peaks'][150], .1, delta=.002)
        self.assertAlmostEqual(data['peaks'][250], .8, delta=.002)
        self.assertEqual(self.server.service.get_project(self.project['id'])['version'], self.project['version'])

    def test_last_chunk_has_actual_coverage_and_cached_reads_do_not_rewrite(self):
        status, data = self.request(self.endpoint + '?chunk=1')
        self.assertEqual(status, 200)
        self.assertEqual(data['start'], 30)
        self.assertAlmostEqual(data['end'], 31.07, places=3)
        self.assertEqual(len(data['peaks']), 107)
        cache = self.server.service.work / 'waveforms'
        before = {p.name:p.stat().st_mtime_ns for p in cache.glob('*.json')}
        self.assertEqual(self.request(self.endpoint + '?chunk=1')[1], data)
        self.assertEqual({p.name:p.stat().st_mtime_ns for p in cache.glob('*.json')}, before)

    def test_invalid_intervals_and_unknown_media_are_rejected(self):
        for chunk in ('-1', '1.5', 'NaN', '99999999', '2'):
            self.assertEqual(self.request(self.endpoint + '?chunk=' + chunk)[0], 400)
        self.assertEqual(self.request(f"/api/projects/{self.project['id']}/media/missing/peaks")[0], 404)


if __name__ == '__main__':
    unittest.main()
