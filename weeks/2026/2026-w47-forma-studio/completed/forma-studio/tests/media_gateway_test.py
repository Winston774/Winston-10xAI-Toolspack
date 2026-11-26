"""Exercise the Colab gateway with the same Python packages as the installed Breeze API."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "media"))
from breeze_gateway import create_app


class GatewayTest(unittest.TestCase):
    def test_auth_and_private_cloud_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav, words = Path(tmp, "voice.wav"), Path(tmp, "words.txt")
            wav.write_bytes(b"mock-reference")
            words.write_text("測試文字", encoding="utf-8")
            client = TestClient(create_app("test-token", profiles={"guide": (wav, words)}))
            headers = {"Authorization": "Bearer test-token"}
            self.assertEqual(client.get("/studio/capabilities").status_code, 401)
            self.assertEqual(client.get("/studio/capabilities", headers=headers).json(), {"profiles": ["guide"]})
            reply = client.post("/v1/audio/speech", headers=headers, data={"text": "嗨", "voice_id": "missing"})
            self.assertEqual(reply.status_code, 404)
            with patch("breeze_gateway.requests.post") as post:
                def upstream(url, **kwargs):
                    self.assertEqual(url, "http://127.0.0.1:7860/v1/audio/speech")
                    self.assertEqual(kwargs["data"]["ref_text"], "測試文字")
                    self.assertEqual(kwargs["files"]["ref_audio"][1].read(), b"mock-reference")
                    from requests import Response
                    response = Response()
                    response.status_code = 200
                    response.headers["X-Sample-Rate"] = "24000"
                    response.headers["Content-Type"] = "audio/pcm"
                    response._content = bytes(96)
                    response._content_consumed = True
                    return response
                post.side_effect = upstream
                response = client.post("/v1/audio/speech", headers=headers, data={"text": "嗨", "voice_id": "guide"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, bytes(96))
                self.assertEqual(response.headers["X-Sample-Rate"], "24000")


if __name__ == "__main__":
    unittest.main()
