#!/usr/bin/env python3
"""NKUST iAI client. Python 3.10+, standard library only. See references/cli.md."""
from __future__ import annotations

import argparse
import base64
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "https://www.iai.nkust.edu.tw/aihub"
PATHS = {
    "models": "/v1/models", "chat": "/v1/chat/completions",
    "transcribe": "/v1/audio/transcriptions", "speak": "/v1/audio/speech",
    "embed": "/v1/embeddings", "image": "/v1/images/generations",
    "rerank": "/v1/rerank", "edit": "/v1/images/edits",
}


class ClientError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def parse_value(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("operation", choices=PATHS)
    p.add_argument("--base-url", default=os.getenv("IAI_BASE_URL", BASE), help="API root without /v1")
    p.add_argument("--api-key-env", default="IAI_API_KEY", help="Environment variable NAME, never the key")
    p.add_argument("--auth", choices=["bearer", "litellm", "litellm-bearer"], default="bearer")
    p.add_argument("--timeout", type=float, default=os.getenv("IAI_TIMEOUT", "120"), help="Socket I/O timeout seconds, not a whole-request deadline")
    p.add_argument("--models-method", choices=["GET", "POST"], default="GET")
    p.add_argument("--model", help="Exact model ID; fallback IAI_MODEL then body")
    p.add_argument("--body", help="UTF-8 JSON object file; form fields for transcribe/edit")
    p.add_argument("--image", help="Local reference image for edit (one image)")
    p.add_argument("--param", action="append", default=[], metavar="KEY=JSON_OR_TEXT", help="Repeatable top-level API field override")
    for name, help_text in {
        "prompt": "chat/image prompt", "prompt-file": "UTF-8 prompt file",
        "system": "chat system message", "messages": "chat UTF-8 JSON messages array file",
        "input": "speak/embed text", "input-file": "UTF-8 speak/embed text file",
        "file": "Local audio file for transcribe", "language": "ASR language, e.g. zh",
        "response-format": "transcribe/speak response_format", "voice": "speak voice",
        "encoding-format": "embed encoding_format (default float)", "size": "Image size",
        "query": "rerank query", "documents": "rerank UTF-8 JSON string array file",
    }.items():
        p.add_argument("--" + name, help=help_text)
    p.add_argument("--temperature", type=float, help="chat, range depends on model")
    p.add_argument("--max-tokens", type=int, help="chat token limit if supported")
    p.add_argument("--stream", action="store_true", default=None, help="chat raw SSE")
    p.add_argument("--n", type=int, help="Image count")
    p.add_argument("--top-n", type=int, help="rerank result count")
    p.add_argument("--output", help="Save JSON, text, raw SSE, or binary speech")
    p.add_argument("--error-output", help="Save a redacted HTTP diagnostic JSON on error (no automatic retry)")
    p.add_argument("--text-only", action="store_true", help="Extract chat/transcribe text")
    p.add_argument("--save-images", help="Decode known base64 image fields to this directory")
    p.add_argument("--overwrite", action="store_true", help="Permit replacing targeted output files")
    p.add_argument("--dry-run", action="store_true", help="Validate/show request, no key or network")
    return p


def require(condition, message):
    if not condition:
        raise ClientError(message)


def build_request(a):
    url = a.base_url.rstrip("/")
    parts = urllib.parse.urlsplit(url)
    local = parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost", "::1"}
    require(parts.scheme == "https" or local, "base URL must be HTTPS (HTTP only on loopback for local tests)")
    require(parts.hostname and not parts.username and not parts.password and not parts.query and not parts.fragment,
            "base URL must not contain credentials, query parameters, or fragments")
    require(not parts.path.endswith("/v1"), "base URL must omit /v1; the client appends it")
    require(math.isfinite(a.timeout) and a.timeout > 0, "timeout must be a finite positive number")
    b = load_json(a.body) if a.body else {}
    require(isinstance(b, dict), "--body must contain a JSON object")
    require(not (a.prompt is not None and a.prompt_file), "choose --prompt or --prompt-file")
    require(not (a.input is not None and a.input_file), "choose --input or --input-file")
    prompt = Path(a.prompt_file).read_text(encoding="utf-8-sig") if a.prompt_file else a.prompt
    text_input = Path(a.input_file).read_text(encoding="utf-8-sig") if a.input_file else a.input
    allowed = {
        "prompt": {"chat", "image", "edit"}, "prompt_file": {"chat", "image", "edit"},
        "system": {"chat"}, "messages": {"chat"}, "input": {"speak", "embed"},
        "input_file": {"speak", "embed"}, "file": {"transcribe"}, "language": {"transcribe"},
        "response_format": {"transcribe", "speak", "image", "edit"}, "voice": {"speak"},
        "encoding_format": {"embed"}, "temperature": {"chat"}, "max_tokens": {"chat"},
        "stream": {"chat"}, "n": {"image", "edit"}, "size": {"image", "edit"},
        "image": {"edit"},
        "query": {"rerank"}, "documents": {"rerank"}, "top_n": {"rerank"},
    }
    for name, operations in allowed.items():
        require(getattr(a, name) is None or a.operation in operations,
                f"--{name.replace('_', '-')} is not applicable to {a.operation}; use --param for intentional API extensions")
    require(not a.text_only or a.operation in {"chat", "transcribe"}, "--text-only is for chat/transcribe")
    require(not a.save_images or a.operation in {"chat", "image", "edit"}, "--save-images is for chat/image/edit")
    if a.operation != "models":
        model = a.model or os.getenv("IAI_MODEL")
        if model:
            b["model"] = model
    else:
        require(not a.model, "models does not take --model")
    if a.operation == "chat":
        require(not (a.messages and prompt is not None), "choose --messages or --prompt/--prompt-file")
        if a.messages:
            b["messages"] = load_json(a.messages)
        elif prompt is not None:
            b["messages"] = [{"role": "user", "content": prompt}]
        if a.system is not None:
            require(isinstance(b.get("messages"), list), "--system requires messages or prompt")
            b["messages"] = [{"role": "system", "content": a.system}] + b["messages"]
    elif a.operation in {"image", "edit"} and prompt is not None:
        b["prompt"] = prompt
    if text_input is not None:
        b["input"] = text_input
    for name in ["language", "response_format", "voice", "encoding_format", "temperature", "max_tokens", "stream", "n", "size", "query", "top_n"]:
        if getattr(a, name) is not None:
            b[name] = getattr(a, name)
    if a.documents:
        b["documents"] = load_json(a.documents)
    for param in a.param:
        key, sep, value = param.partition("=")
        require(sep and key.strip(), "--param requires KEY=VALUE")
        require(key == key.strip(), "--param key must not have surrounding whitespace")
        require(key != "file" or a.operation != "transcribe", "use --file for audio upload")
        require(key != "image" or a.operation != "edit", "use --image for reference upload")
        b[key] = parse_value(value)
    if a.operation == "embed":
        b.setdefault("encoding_format", "float")
    if a.operation == "models":
        require(not b, "models sends no body; omit --body and --param")
    else:
        require(isinstance(b.get("model"), str) and b["model"].strip(), "model required: --model, IAI_MODEL, body or --param")
    required = {"chat": "messages", "speak": "input", "embed": "input", "image": "prompt", "edit": "prompt", "rerank": "query"}
    if a.operation in required:
        field = required[a.operation]
        require(b.get(field) is not None and b[field] != "" and b[field] != [], f"{field} is required")
    if a.operation == "chat":
        require(isinstance(b["messages"], list) and all(isinstance(m, dict) and isinstance(m.get("role"), str) for m in b["messages"]), "messages must be an array of objects with role")
        # Allow tool calls with absent content and multimodal content arrays.
    if a.operation in {"image", "edit"}:
        require(isinstance(b["prompt"], str), "image prompt must be a string")
    if a.operation == "speak":
        require(isinstance(b["input"], str), "speak input must be a string")
        require(a.output, "speak requires --output for binary audio")
    if a.operation == "embed":
        require(isinstance(b["input"], str) or (isinstance(b["input"], list) and all(isinstance(v, str) for v in b["input"])), "embed input must be text or an array of texts")
    if a.operation == "rerank":
        require(isinstance(b["query"], str), "query must be a string")
        require(isinstance(b.get("documents"), list) and b["documents"] and all(isinstance(d, str) for d in b["documents"]), "documents must be a nonempty JSON string array")
    for field in ["n", "top_n", "max_tokens"]:
        if field in b:
            require(type(b[field]) is int and b[field] > 0, f"{field} must be a positive integer")
    if "temperature" in b:
        require(type(b["temperature"]) in {int, float} and math.isfinite(b["temperature"]), "temperature must be finite")
    if "stream" in b:
        require(type(b["stream"]) is bool, "stream must be a JSON boolean")
    streaming = a.operation == "chat" and b.get("stream") is True
    require(not streaming or not (a.text_only or a.save_images), "stream returns raw SSE; omit --text-only/--save-images")
    audio = None
    reference = None
    if a.operation == "edit":
        require(a.image, "edit requires --image")
        reference = Path(a.image)
        require(reference.is_file(), "reference image does not exist")
        require("image" not in b, "image is reserved; specify reference with --image")
    if a.operation == "transcribe":
        require(a.file, "transcribe requires --file")
        audio = Path(a.file)
        require(audio.is_file(), "audio file does not exist")
        require("file" not in b, "file is reserved; specify audio with --file")
    # Serialization also validates non-finite numbers in custom/nested parameters.
    json.dumps(b, ensure_ascii=False, allow_nan=False)
    method = a.models_method if a.operation == "models" else "POST"
    if a.auth == "bearer":
        header, prefix = "Authorization", "Bearer "
    else:
        header, prefix = "x-litellm-api-key", "Bearer " if a.auth == "litellm-bearer" else ""
    return {"url": url + PATHS[a.operation], "method": method, "body": b,
            "audio": audio, "image": reference, "auth_header": header, "auth_prefix": prefix, "stream": streaming}


def multipart(fields, audio=None, image=None):
    boundary = "iai-" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        require(not re.search(r'[\r\n"\\]', name), "invalid multipart field name")
        value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False)
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + value.encode("utf-8") + b"\r\n")
    for field, path in [("file", audio), ("image", image)]:
        if path is None:
            continue
        filename = re.sub(r'[^A-Za-z0-9._-]', '_', path.name)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode() + path.read_bytes() + b"\r\n")
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b"".join(chunks), "multipart/form-data; boundary=" + boundary


def write_file(path, data, overwrite=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        with path.open("xb") as f:
            f.write(data)
        return
    fd, temp = tempfile.mkstemp(prefix=".iai-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def image_payloads(obj):
    """Only known image fields; never recursively decode arbitrary strings or URLs."""
    data = obj.get("data", [])
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and isinstance(item.get("b64_json"), str):
            yield item["b64_json"]
    choices = obj.get("choices", [])
    for choice in choices if isinstance(choices, list) else []:
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        if not isinstance(message, dict):
            continue
        content = message.get("content", [])
        blocks = list(content) if isinstance(content, list) else []
        images = message.get("images", [])
        blocks += images if isinstance(images, list) else []
        if isinstance(content, str) and content.startswith("data:image/"):
            blocks.append({"image_url": {"url": content}})
        for item in blocks:
            if not isinstance(item, dict):
                continue
            entry = item.get("image_url", {})
            value = entry.get("url") if isinstance(entry, dict) else entry
            if isinstance(value, str) and value.startswith("data:image/") and ";base64," in value:
                yield value.split(";base64,", 1)[1]


def decode_images(obj, directory, overwrite=False):
    require(isinstance(obj, dict), "image response must be a JSON object")
    decoded = []
    for value in image_payloads(obj):
        raw = base64.b64decode(value, validate=True)
        ext = ("png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else
               "jpg" if raw.startswith(b"\xff\xd8\xff") else
               "webp" if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP" else
               "gif" if raw.startswith((b"GIF87a", b"GIF89a")) else None)
        require(ext, "unrecognized image signature; preserve JSON and inspect response")
        decoded.append((Path(directory) / f"image-{len(decoded)+1:03d}.{ext}", raw))
    require(decoded, "no known base64 image fields; preserve JSON and inspect schema; remote URLs are not downloaded")
    require(overwrite or not any(p.exists() for p, _ in decoded), "image output exists; choose new directory or --overwrite")
    files = []
    for path, raw in decoded:
        write_file(path, raw, overwrite)
        files.append(str(path.resolve()))
    return files


def extract_text(obj, operation):
    if isinstance(obj, str):
        return obj
    require(isinstance(obj, dict), "response has no extractable text; use raw JSON")
    if operation == "transcribe" and isinstance(obj.get("text"), str):
        return obj["text"]
    choices = obj.get("choices", [])
    content = choices[0].get("message", {}).get("content") if choices else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [x["text"] for x in content if isinstance(x, dict) and isinstance(x.get("text"), str)]
        if texts:
            return "\n".join(texts)
    raise ClientError("no extractable text (possibly tool calls/images); use raw JSON")


def http_diagnostic(exc, a):
    """Opt-in, bounded diagnostics with credentials and known input text removed."""
    spec = build_request(a)
    secrets = [os.getenv(a.api_key_env, "").strip()]
    def collect(value):
        if isinstance(value, str) and len(value) >= 4:
            secrets.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"prompt", "input", "content", "documents", "query", "messages"}:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(spec["body"])
    def scrub(value):
        if isinstance(value, dict):
            return {k: ("<REDACTED>" if re.search(r"authorization|api.?key|token|secret|password|headers|request_body", k, re.I) else scrub(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        if isinstance(value, str):
            for secret in sorted(set(secrets), key=len, reverse=True):
                if secret:
                    value = value.replace(secret, "<REDACTED>")
            value = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer <REDACTED>", value)
            value = re.sub(r"(?i)([?&](?:key|api_key|token|access_token)=)[^&\s\"']+", r"\1<REDACTED>", value)
        return value
    # Some gateways echo multi-MiB generated images inside an exception traceback.
    # Remove data URIs before limiting the readable diagnostic, never print base64.
    limit = 8 * 1024 * 1024
    raw = exc.read(limit + 1)
    truncated = len(raw) > limit
    text = raw[:limit].decode("utf-8", errors="replace")
    text = re.sub(r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+", "<IMAGE_DATA_OMITTED>", text)
    truncated = truncated or len(text) > 65536
    text = text[:65536]
    try:
        detail = json.loads(text)
    except ValueError:
        detail = text
    return {"status": exc.code, "method": spec["method"], "endpoint": PATHS[a.operation],
            "model": spec["body"].get("model"), "truncated": truncated,
            "request_id": scrub(exc.headers.get("x-request-id", "")), "error": scrub(detail)}


def run(a):
    spec = build_request(a)
    if a.dry_run:
        preview = {"method": spec["method"], "url": spec["url"],
                   "headers": {spec["auth_header"]: spec["auth_prefix"] + "<REDACTED>"},
                   "body": spec["body"], "timeout": a.timeout}
        preview["content_type"] = "multipart/form-data; boundary=<generated>" if spec["audio"] or spec["image"] else (None if a.operation == "models" else "application/json")
        if spec["audio"]:
            preview["file"] = {"path": str(spec["audio"].resolve()), "size_bytes": spec["audio"].stat().st_size}
        if spec["image"]:
            preview["image"] = {"path": str(spec["image"].resolve()), "size_bytes": spec["image"].stat().st_size}
        print(json.dumps(preview, ensure_ascii=False, indent=2, allow_nan=False))
        return
    key = os.getenv(a.api_key_env, "").strip()
    require(key, f"environment variable {a.api_key_env} is missing; set it locally or use --dry-run")
    require("\r" not in key and "\n" not in key, "API key must not contain line breaks")
    if a.output:
        require(a.overwrite or not Path(a.output).exists(), "output exists; choose another path or --overwrite")
    headers = {spec["auth_header"]: spec["auth_prefix"] + key}
    if spec["audio"] or spec["image"]:
        body, headers["Content-Type"] = multipart(spec["body"], spec["audio"], spec["image"])
    elif a.operation == "models":
        body = None
    else:
        body = json.dumps(spec["body"], ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    headers["Accept"] = "text/event-stream" if spec["stream"] else ("*/*" if a.operation in {"speak", "transcribe", "embed"} else "application/json")
    req = urllib.request.Request(spec["url"], data=body, headers=headers, method=spec["method"])
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(req, timeout=a.timeout) as response:
        kind = response.headers.get_content_type()
        if spec["stream"]:
            require(kind == "text/event-stream", "expected SSE content type; retry explicitly without stream to inspect")
            sink = None
            try:
                if a.output:
                    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
                    sink = open(a.output, "wb" if a.overwrite else "xb")
                for line in response:
                    if sink:
                        sink.write(line)
                        sink.flush()
                    else:
                        sys.stdout.write(line.decode("utf-8", errors="replace"))
                        sys.stdout.flush()
            finally:
                if sink:
                    sink.close()
            if a.output:
                print(f"Saved SSE: {Path(a.output).resolve()}", file=sys.stderr)
            return
        raw = response.read()
    if a.operation == "speak":
        require(kind not in {"application/json", "text/html"} and not kind.endswith("+json") and not kind.startswith("text/"), "expected binary speech but received JSON/text; audio not saved")
        require(raw, "empty speech response")
        write_file(a.output, raw, a.overwrite)
        print(f"Saved audio: {Path(a.output).resolve()}")
        return
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        require(a.operation in {"transcribe", "embed"} and not kind.endswith("json") and kind != "text/html", "expected JSON; response format mismatch")
        if a.output:
            write_file(a.output, raw, a.overwrite)
            print(f"Saved response: {Path(a.output).resolve()}", file=sys.stderr)
        else:
            require(a.operation != "embed", "binary embedding response requires --output")
            print(raw.decode("utf-8"))
        return
    output = extract_text(obj, a.operation) if a.text_only else json.dumps(obj, ensure_ascii=False, indent=2)
    if a.output:
        write_file(a.output, (output + "\n").encode("utf-8"), a.overwrite)
        print(f"Saved response: {Path(a.output).resolve()}", file=sys.stderr)
    elif not a.save_images:
        print(output)
    if a.save_images:
        for path in decode_images(obj, a.save_images, a.overwrite):
            print(f"Saved image: {path}")


def main(argv=None):
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    a = parser().parse_args(argv)
    try:
        if a.error_output:
            require(a.overwrite or not Path(a.error_output).exists(), "error output exists; choose another path or --overwrite")
        run(a)
        return 0
    except urllib.error.HTTPError as exc:
        tips = {400: "check parameters/model capabilities", 401: "check key/auth mode",
                403: "check account/model permission", 404: "check base URL/endpoint", 405: "check models GET/POST method",
                413: "input too large; check service limits", 422: "check fields/types",
                429: "rate/quota limit; wait before explicit retry"}
        print(f"HTTP {exc.code}: {tips.get(exc.code, 'service error; inspect status before retry')}. No automatic retry. Server error body omitted to protect request data.", file=sys.stderr)
        if a.error_output:
            try:
                diagnostic = http_diagnostic(exc, a)
                write_file(a.error_output, (json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), a.overwrite)
                print(f"Saved redacted HTTP diagnostic: {Path(a.error_output).resolve()}", file=sys.stderr)
            except (OSError, ValueError, ClientError):
                print("Could not save HTTP diagnostic; original HTTP status retained.", file=sys.stderr)
        return 3
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        print(f"Network error ({type(exc).__name__}); request may have reached service. No automatic retry.", file=sys.stderr)
        return 4
    except (ClientError, OSError, ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ClientError) else f"{type(exc).__name__}: check input files, JSON, output path and response format"
        print(message, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted; no automatic retry. Streaming output may be partial.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
