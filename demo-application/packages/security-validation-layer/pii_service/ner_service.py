"""
NER side service for the Security & Validation Layer's PII pipeline.

Regex (src/pii-detectors.js) finds structured PII; this service finds what
regex cannot: people's names inside free text, using Microsoft Presidio on a
spaCy model. The Node layer sends a batch of cell values and gets back the
PERSON spans in each.

    POST /analyze   {"texts": ["...", ...], "entities": ["PERSON"]}
                 -> {"results": [[{"type", "start", "end", "score"}], ...]}
    GET  /health -> {"status": "ok", "model": ..., "entities": [...]}

Binds to 127.0.0.1 only: cell values are personal data and must not leave
the host. Loading the model takes a few seconds, so this runs as a
long-lived process rather than per request.

    From demo-application on Windows:
    .ner-venv\\Scripts\\python packages\\security-validation-layer\\pii_service\\ner_service.py
                                                        (port 5002)
    NER_PORT=5003 NER_MODEL=en_core_web_sm ...      (overrides)
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from presidio_analyzer import AnalyzerEngine, BatchAnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

HOST = "127.0.0.1"
PORT = int(os.environ.get("NER_PORT", "5002"))
MODEL = os.environ.get("NER_MODEL", "en_core_web_lg")
MIN_SCORE = float(os.environ.get("NER_MIN_SCORE", "0.5"))
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_TEXTS = 5000
MAX_TEXT_LEN = 2000
# Entities this service will report. Structured types (email, phone, cards...)
# are left to the regex detectors, which validate checksums.
ALLOWED_ENTITIES = {"PERSON", "LOCATION", "NRP"}

print(f"Loading {MODEL} ...", flush=True)
_started = time.time()
_nlp_engine = NlpEngineProvider(
    nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": MODEL}]}
).create_engine()
_batch = BatchAnalyzerEngine(analyzer_engine=AnalyzerEngine(nlp_engine=_nlp_engine, supported_languages=["en"]))
# spaCy pipelines are not guaranteed thread-safe; one analysis at a time.
_lock = threading.Lock()
print(f"Model ready in {time.time() - _started:.1f}s", flush=True)


def analyze(texts, entities):
    clean = [str(t)[:MAX_TEXT_LEN] if t is not None else "" for t in texts]
    with _lock:
        batches = list(_batch.analyze_iterator(clean, language="en", entities=entities, score_threshold=MIN_SCORE))
    return [
        sorted(
            ({"type": r.entity_type, "start": r.start, "end": r.end, "score": round(r.score, 3)} for r in found),
            key=lambda s: s["start"],
        )
        for found in batches
    ]


class Handler(BaseHTTPRequestHandler):
    server_version = "svl-ner/1.0"

    def _send(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok", "model": MODEL, "entities": sorted(ALLOWED_ENTITIES)})
        self._send(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/analyze":
            return self._send(404, {"error": "not_found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._send(413, {"error": "body_too_large_or_empty"})
        try:
            body = json.loads(self.rfile.read(length))
            texts = body["texts"]
            entities = [e for e in body.get("entities", ["PERSON"]) if e in ALLOWED_ENTITIES]
            if not isinstance(texts, list) or len(texts) > MAX_TEXTS or not entities:
                raise ValueError("texts must be a list of at most %d items" % MAX_TEXTS)
        except (ValueError, KeyError, TypeError) as e:
            return self._send(400, {"error": "bad_request", "detail": str(e)})
        started = time.time()
        results = analyze(texts, entities)
        self._send(200, {"results": results, "elapsedMs": round((time.time() - started) * 1000, 1)})

    def log_message(self, fmt, *args):
        # Never log request bodies (they are personal data); a one-line access log is enough.
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"NER service listening on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
