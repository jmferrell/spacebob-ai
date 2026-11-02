"""Flask front door: check the request, hand it to the right character, return JSON."""
import hmac
import logging
import os
import re
import sys
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request

from character import Character
from claude_client import ClaudeClient, ClaudeError
from settings import BASE_DIR, load_config
from textutil import clean_input

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
RESERVED_FIELDS = {"auth", "char", "speaker", "text", "context", "type"}
log = logging.getLogger("mushai")


class HourlyLimiter:
    """Cap on Claude calls per rolling hour, so a runaway loop can't run up a bill."""

    def __init__(self, limit):
        self.limit, self.hits, self._lock = limit, deque(), threading.Lock()

    def allow(self):
        if not self.limit:
            return True
        now = time.time()
        with self._lock:
            while self.hits and now - self.hits[0] > 3600:
                self.hits.popleft()
            if len(self.hits) >= self.limit:
                return False
            self.hits.append(now)
            return True


def _setup_logging(cfg, base_dir):
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers = [logging.StreamHandler()]
    if cfg.LOG_FILE:
        path = os.path.join(base_dir, cfg.LOG_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handlers.append(RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3))
    for handler in handlers:
        handler.setFormatter(fmt)
        log.addHandler(handler)


def build_situation(data):
    """Free-text 'context' plus any extra string fields (time, weather, room...) as plain lines."""
    lines = []
    context = clean_input(data.get("context", ""))[:1000]
    if context:
        lines.append(context)
    for key, value in data.items():
        if key in RESERVED_FIELDS or not isinstance(value, (str, int, float)):
            continue
        label = re.sub(r"[^A-Za-z0-9 _-]", "", str(key))[:30].replace("_", " ").strip().capitalize()
        value = clean_input(value)[:200]
        if label and value:
            lines.append(f"{label}: {value}")
        if len(lines) >= 11:
            break
    return "\n".join(lines)


def create_app(overrides=None, claude=None, base_dir=BASE_DIR):
    cfg = load_config(overrides)
    if cfg.AUTH_KEY in ("", "change-me"):
        raise RuntimeError("Set AUTH_KEY in config.py to a long random secret.")
    if claude is None:
        if not (cfg.API_KEY or os.environ.get("ANTHROPIC_API_KEY")):
            raise RuntimeError("No API key: set API_KEY in config.py or ANTHROPIC_API_KEY.")
        claude = ClaudeClient(cfg.API_KEY, cfg.TIMEOUT_SECONDS)
    _setup_logging(cfg, base_dir)

    chars_dir = os.path.join(base_dir, cfg.CHARACTERS_DIR)
    data_dir = os.path.join(base_dir, cfg.DATA_DIR)
    limiter = HourlyLimiter(cfg.MAX_CALLS_PER_HOUR)
    characters, characters_lock = {}, threading.Lock()

    def get_character(name):
        if not NAME_RE.match(name):
            return None
        with characters_lock:
            if name not in characters:
                if not os.path.isfile(os.path.join(chars_dir, name, "brief.txt")):
                    return None
                characters[name] = Character(name, chars_dir, data_dir, cfg, claude)
            return characters[name]

    def fail(message, status):
        return jsonify({"message": f"Failed: {message}"}), status

    app = Flask(__name__)
    app.config["MUSHAI_HOST"], app.config["MUSHAI_PORT"] = cfg.HOST, cfg.PORT

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.post("/")
    @app.post("/speak")
    def speak():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return fail("No JSON data provided", 400)
        if not hmac.compare_digest(str(data.get("auth", "")), str(cfg.AUTH_KEY)):
            return fail("Unauthorized", 401)

        speaker = clean_input(data.get("speaker", "")).replace('"', "")[:60]
        text = clean_input(data.get("text", ""))
        if not speaker or not text:
            return fail("Missing speaker or text", 400)
        if len(text) > cfg.MAX_INPUT_CHARS:
            return fail("Input exceeds maximum length", 400)
        character = get_character(str(data.get("char", "")).strip().lower())
        if character is None:
            return fail("Unknown character", 400)
        if not limiter.allow():
            return fail("Too many requests, try again later", 429)

        try:
            reply = character.respond(speaker, text, build_situation(data))
        except ClaudeError as exc:
            log.error("Claude API error: %s", exc)
            return fail("Claude API error", 502)
        except Exception:
            log.exception("Unexpected error")
            return fail("Internal error", 500)
        return jsonify({"message": reply})

    return app


if __name__ == "__main__":
    try:
        application = create_app()
    except RuntimeError as exc:
        sys.exit(str(exc))
    application.run(host=application.config["MUSHAI_HOST"], port=application.config["MUSHAI_PORT"])
