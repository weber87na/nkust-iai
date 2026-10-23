"""Offline behavioral checks. Never contacts the real iAI service."""
import base64
from contextlib import redirect_stdout, redirect_stderr
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import iai

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1cAAAAASUVORK5CYII=")
KEY = "offline-test-key-only"


class Handler(BaseHTTPRequestHandler):
    records = []
    status = 200
    mode = "normal"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.records.append((self.command, self.path, self.headers, raw))
        if self.status != 200:
            self.send_response(self.status)
            if self.status == 307:
                self.send_header("Location", self.server.base + "/redirect-target")
            self.end_headers()
            if self.mode == "error-secrets":
                self.wfile.write(json.dumps({"error": {"message": "upstream unavailable; " + KEY + " private prompt text data:image/png;base64," + base64.b64encode(PNG).decode(), "type": "upstream_error", "code": "unavailable", "api_key": KEY}}).encode())
            else:
                self.wfile.write(b"private-error-body-not-for-logs")
            return
        kind = "application/json"
        endpoint = self.path.rsplit("/", 1)[-1]
        body = json.loads(raw) if raw and self.headers.get_content_type() == "application/json" else {}
        if endpoint == "models":
            data = {"object": "list", "data": [{"id": "test-model"}]}
        elif endpoint == "transcriptions":
            data = {"text": "測試逐字稿"}
        elif endpoint == "speech":
            if self.mode == "json-audio-error":
                data = {"error": "not audio"}
            else:
                kind, data = "audio/mpeg", b"ID3-test-audio"
        elif endpoint == "embeddings":
            if self.mode == "binary-embedding":
                kind, data = "application/octet-stream", b"\x00\x00\x80?"
            else:
                data = {"data": [{"index": 0, "embedding": [0.2, 0.5]}]}
        elif endpoint in {"generations", "edits"}:
            data = {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}
        elif endpoint == "rerank":
            data = {"results": [{"index": 1, "relevance_score": 0.9}]}
        elif body.get("stream"):
            kind, data = "text/event-stream", b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'
        elif self.mode == "chat-image":
            data = {"choices": [{"message": {"images": [{"image_url": {"url": "data:image/png;base64," + base64.b64encode(PNG).decode()}}]}}]}
        else:
            data = {"choices": [{"message": {"content": "繁體中文回答"}}], "usage": {"total_tokens": 7}}
        raw_response = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(raw_response)))
        self.end_headers()
        self.wfile.write(raw_response)


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/aihub"
        cls.server.base = cls.base
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="iai-test-")
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"IAI_API_KEY": KEY, "IAI_MODEL": "", "IAI_BASE_URL": self.base, "IAI_TIMEOUT": "3"})
        self.env.start()
        Handler.records = []
        Handler.mode, Handler.status = "normal", 200

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = iai.main(list(args))
        self.assertNotIn(KEY, out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def data_file(self, name, obj):
        path = self.root / name
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8-sig")
        return str(path)

    def test_models_both_methods_without_payload_or_model(self):
        for method in ["GET", "POST"]:
            code, out, _ = self.invoke("models", "--models-method", method)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["data"][0]["id"], "test-model")
            command, path, headers, raw = Handler.records[-1]
            self.assertEqual((command, path, raw), (method, "/aihub/v1/models", b""))
            self.assertEqual(headers["Authorization"], "Bearer " + KEY)

    def test_dry_run_requires_no_key_and_sends_nothing(self):
        with patch.dict(os.environ, {"IAI_API_KEY": ""}):
            code, out, _ = self.invoke("chat", "--model", "test-model", "--prompt", "你好", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["body"]["messages"][0]["content"], "你好")
        self.assertEqual(Handler.records, [])

    def test_precedence_preserves_unknown_nested_fields(self):
        path = self.data_file("body.json", {"model": "body", "messages": [{"role": "user", "content": "body"}], "temperature": 0.8, "tools": [{"custom": [1, 2]}]})
        with patch.dict(os.environ, {"IAI_MODEL": "env"}):
            code, out, _ = self.invoke("chat", "--body", path, "--model", "flag", "--temperature", "0.4", "--param", "model=last", "--param", "temperature=0.2", "--dry-run")
        self.assertEqual(code, 0)
        b = json.loads(out)["body"]
        self.assertEqual((b["model"], b["temperature"], b["tools"]), ("last", 0.2, [{"custom": [1, 2]}]))

    def test_chat_history_and_system_and_text_save(self):
        messages = self.data_file("messages.json", [{"role": "user", "content": "你好"}])
        output = self.root / "answer.txt"
        code, _, _ = self.invoke("chat", "--model", "m", "--messages", messages, "--system", "繁體中文", "--text-only", "--output", str(output))
        self.assertEqual(code, 0)
        self.assertEqual(output.read_text(encoding="utf-8").strip(), "繁體中文回答")
        b = json.loads(Handler.records[-1][3])
        self.assertEqual([x["role"] for x in b["messages"]], ["system", "user"])

    def test_multipart_contains_audio_fields_and_generated_boundary(self):
        path = self.root / "中文錄音.mp3"
        path.write_bytes(b"test-audio\x00\xff")
        code, out, _ = self.invoke("transcribe", "--model", "Asr", "--file", str(path), "--language", "zh", "--response-format", "json", "--text-only")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "測試逐字稿")
        _, url, headers, raw = Handler.records[-1]
        self.assertEqual(url, "/aihub/v1/audio/transcriptions")
        msg = BytesParser(policy=policy.default).parsebytes(("Content-Type: " + headers["Content-Type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + raw)
        fields = {part.get_param("name", header="content-disposition"): part.get_payload(decode=True) for part in msg.iter_parts()}
        self.assertEqual(fields, {"model": b"Asr", "language": b"zh", "response_format": b"json", "file": path.read_bytes()})

    def test_binary_audio_saved_and_json_not_mislabeled(self):
        path = self.root / "audio.mp3"
        args = ("speak", "--model", "Speaker", "--input", "你好", "--output", str(path))
        self.assertEqual(self.invoke(*args)[0], 0)
        self.assertEqual(path.read_bytes(), b"ID3-test-audio")
        Handler.mode = "json-audio-error"
        path2 = self.root / "bad.mp3"
        self.assertEqual(self.invoke(*args[:-1], str(path2))[0], 2)
        self.assertFalse(path2.exists())

    def test_edit_uploads_image_field_and_decodes_result(self):
        source = self.root / "參考圖.png"
        source.write_bytes(PNG)
        output = self.root / "edited"
        for model in ["Pic-small", "Pic-large"]:
            code, _, _ = self.invoke("edit", "--model", model, "--image", str(source), "--prompt", "只改布料顏色", "--n", "1", "--size", "1024x1024", "--save-images", str(output / model))
            self.assertEqual(code, 0)
            method, endpoint, headers, raw = Handler.records[-1]
            self.assertEqual((method, endpoint), ("POST", "/aihub/v1/images/edits"))
            msg = BytesParser(policy=policy.default).parsebytes(("Content-Type: " + headers["Content-Type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + raw)
            fields = {part.get_param("name", header="content-disposition"): part.get_payload(decode=True) for part in msg.iter_parts()}
            self.assertEqual(fields, {"model": model.encode(), "prompt": "只改布料顏色".encode(), "n": b"1", "size": b"1024x1024", "image": PNG})
            self.assertEqual((output / model / "image-001.png").read_bytes(), PNG)

    def test_edit_dry_run_lists_image_without_upload_or_output(self):
        source = self.root / "reference.png"
        source.write_bytes(PNG)
        body = self.data_file("edit.json", {"model": "Pic-large", "prompt": "change color", "seed": 123})
        output = self.root / "unused"
        code, out, _ = self.invoke("edit", "--body", body, "--image", str(source), "--save-images", str(output), "--dry-run")
        self.assertEqual(code, 0)
        preview = json.loads(out)
        self.assertEqual(preview["image"]["size_bytes"], len(PNG))
        self.assertEqual(preview["body"]["seed"], 123)
        self.assertIn("multipart/form-data", preview["content_type"])
        self.assertEqual(Handler.records, [])
        self.assertFalse(output.exists())

    def test_edit_rejects_missing_or_reserved_reference_before_network(self):
        source = self.root / "reference.png"
        source.write_bytes(PNG)
        bad_cases = [
            ["edit", "--model", "m", "--prompt", "x"],
            ["edit", "--model", "m", "--prompt", "x", "--image", str(self.root / "missing.png")],
            ["edit", "--model", "m", "--image", str(source)],
            ["edit", "--model", "m", "--prompt", "x", "--image", str(source), "--param", "image=not-a-file"],
            ["image", "--model", "m", "--prompt", "x", "--image", str(source)],
        ]
        for args in bad_cases:
            self.assertEqual(self.invoke(*args)[0], 2)
        self.assertEqual(Handler.records, [])

    def test_existing_output_prevents_api_call_and_explicit_overwrite_works(self):
        path = self.root / "answer.json"
        path.write_bytes(b"existing")
        args = ("chat", "--model", "m", "--prompt", "hello", "--output", str(path))
        self.assertEqual(self.invoke(*args)[0], 2)
        self.assertEqual(Handler.records, [])
        self.assertEqual(path.read_bytes(), b"existing")
        self.assertEqual(self.invoke(*args, "--overwrite")[0], 0)
        self.assertIn("choices", json.loads(path.read_bytes()))

    def test_embedding_batch_and_default_format(self):
        path = self.data_file("batch.json", {"model": "Embedding", "input": ["甲", "乙"]})
        self.assertEqual(self.invoke("embed", "--body", path)[0], 0)
        self.assertEqual(json.loads(Handler.records[-1][3])["encoding_format"], "float")
        Handler.mode = "binary-embedding"
        output = self.root / "vector.bin"
        self.assertEqual(self.invoke("embed", "--model", "Embedding", "--input", "甲", "--encoding-format", "bytes_only", "--output", str(output))[0], 0)
        self.assertEqual(output.read_bytes(), b"\x00\x00\x80?")

    def test_images_and_chat_images_decode_exact_bytes(self):
        for op, model in [("image", "z-image"), ("chat", "Pic-small")]:
            Handler.mode = "chat-image"
            directory = self.root / op
            response = self.root / (op + ".json")
            code, _, _ = self.invoke(op, "--model", model, "--prompt", "campus", "--save-images", str(directory), "--output", str(response))
            self.assertEqual(code, 0)
            self.assertEqual((directory / "image-001.png").read_bytes(), PNG)
            self.assertIsInstance(json.loads(response.read_bytes()), dict)

    def test_remote_image_url_not_downloaded(self):
        with self.assertRaises(iai.ClientError):
            iai.decode_images({"data": [{"url": "https://example.invalid/image.png"}]}, self.root)
        self.assertEqual(Handler.records, [])

    def test_sse_preserved_including_done_marker(self):
        path = self.root / "stream.sse"
        code, _, _ = self.invoke("chat", "--model", "m", "--prompt", "hi", "--stream", "--output", str(path))
        self.assertEqual(code, 0)
        self.assertIn(b"data: [DONE]\n\n", path.read_bytes())

    def test_rerank_auth_modes_and_candidate_order(self):
        docs = self.data_file("docs.json", ["a", "b"])
        for auth, header, prefix in [("bearer", "Authorization", "Bearer "), ("litellm", "x-litellm-api-key", ""), ("litellm-bearer", "x-litellm-api-key", "Bearer ")]:
            code, _, _ = self.invoke("rerank", "--model", "Furen-reranker", "--query", "q", "--documents", docs, "--top-n", "1", "--auth", auth)
            self.assertEqual(code, 0)
            _, path, headers, raw = Handler.records[-1]
            self.assertEqual(path, "/aihub/v1/rerank")
            self.assertEqual(headers[header], prefix + KEY)
            self.assertEqual(json.loads(raw)["documents"], ["a", "b"])

    def test_http_error_is_single_request_and_redacted(self):
        for status in [401, 429, 500]:
            Handler.status = status
            previous = len(Handler.records)
            code, out, err = self.invoke("models")
            self.assertEqual(code, 3)
            self.assertEqual(len(Handler.records), previous + 1)
            self.assertIn(str(status), err)
            self.assertNotIn("private-error-body", out + err)

    def test_redirect_is_not_followed(self):
        Handler.status = 307
        code, _, _ = self.invoke("models")
        self.assertEqual(code, 3)
        self.assertEqual(len(Handler.records), 1)

    def test_opt_in_diagnostic_preserves_cause_and_redacts_secrets(self):
        Handler.status, Handler.mode = 500, "error-secrets"
        diagnostic = self.root / "error.json"
        code, _, _ = self.invoke("chat", "--model", "m", "--prompt", "private prompt text", "--error-output", str(diagnostic))
        self.assertEqual(code, 3)
        raw = diagnostic.read_text(encoding="utf-8")
        self.assertNotIn(KEY, raw)
        self.assertNotIn("private prompt text", raw)
        self.assertNotIn(base64.b64encode(PNG).decode(), raw)
        self.assertIn("<IMAGE_DATA_OMITTED>", raw)
        obj = json.loads(raw)
        self.assertEqual(obj["status"], 500)
        self.assertEqual(obj["error"]["error"]["code"], "unavailable")
        self.assertEqual(obj["error"]["error"]["api_key"], "<REDACTED>")
        self.assertEqual(len(Handler.records), 1)

    def test_existing_diagnostic_prevents_api_call(self):
        path = self.root / "error.json"
        path.write_text("previous", encoding="utf-8")
        self.assertEqual(self.invoke("models", "--error-output", str(path))[0], 2)
        self.assertEqual(Handler.records, [])

    def test_invalid_requests_do_not_touch_network(self):
        bad_cases = [
            ["chat", "--prompt", "missing model"],
            ["chat", "--model", "m", "--prompt", "x", "--stream", "--text-only"],
            ["image", "--model", "m", "--prompt", "x", "--n", "0"],
            ["speak", "--model", "m", "--input", "x"],
            ["models", "--model", "m"],
            ["models", "--base-url", "https://example.invalid/aihub/v1"],
            ["models", "--base-url", "https://user:secret@example.invalid/aihub"],
            ["models", "--base-url", "http://example.invalid/aihub"],
            ["models", "--timeout", "nan"],
            ["embed", "--model", "m", "--input", "x", "--voice", "wrong"],
            ["transcribe", "--model", "m", "--file", str(self.root / "missing.mp3")],
            ["chat", "--model", "m", "--prompt", "x", "--param", "stream=yes"],
        ]
        for args in bad_cases:
            with self.subTest(args=args):
                self.assertEqual(self.invoke(*args)[0], 2)
        self.assertEqual(Handler.records, [])

    def test_custom_key_env_and_missing_key(self):
        with patch.dict(os.environ, {"CUSTOM_IAI_KEY": KEY, "IAI_API_KEY": ""}):
            self.assertEqual(self.invoke("models", "--api-key-env", "CUSTOM_IAI_KEY")[0], 0)
            self.assertEqual(self.invoke("models")[0], 2)
        self.assertEqual(len(Handler.records), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
