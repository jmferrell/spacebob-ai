"""Offline tests: Claude is replaced by a stub, so no API key or network is needed.
Run from the project folder:  python -m unittest discover -s tests -v
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import build_situation, create_app          # noqa: E402
from character import extract_note                    # noqa: E402
from claude_client import ClaudeError                 # noqa: E402
from textutil import clean_input, clean_reply         # noqa: E402


class FakeClaude:
    def __init__(self):
        self.calls, self.replies, self.fail = [], [], False

    def reply(self, system, messages, *, model, max_tokens, effort=None):
        self.calls.append(dict(system=system, messages=copy.deepcopy(messages),
                               model=model, max_tokens=max_tokens, effort=effort))
        if self.fail:
            raise ClaudeError("boom")
        return self.replies.pop(0) if self.replies else 'Bruce nods.'


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        chars = os.path.join(self.tmp, "characters")
        for name, text in (("bruce", "You are Bruce."), ("gladiator", "You are Tiberius.")):
            os.makedirs(os.path.join(chars, name))
            with open(os.path.join(chars, name, "brief.txt"), "w") as fh:
                fh.write(text)
        with open(os.path.join(chars, "_common.txt"), "w") as fh:
            fh.write("COMMON RULES")
        self.claude = FakeClaude()
        self.make_app()

    def make_app(self, **overrides):
        cfg = dict(AUTH_KEY="k", LOG_FILE=None, MAX_CALLS_PER_HOUR=0)
        cfg.update(overrides)
        self.app = create_app(cfg, claude=self.claude, base_dir=self.tmp)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, **fields):
        body = dict(auth="k", char="bruce", speaker="Maximus", text="Hello Bruce")
        body.update(fields)
        return self.client.post("/", json=body)

    # ---- request validation ----------------------------------------------------------------
    def test_bad_auth(self):
        r = self.post(auth="nope")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["message"], "Failed: Unauthorized")
        self.assertEqual(self.claude.calls, [])

    def test_no_json(self):
        r = self.client.post("/", data="hello")
        self.assertEqual(r.status_code, 400)

    def test_unknown_and_malicious_character(self):
        for name in ("nobody", "../x", "_template", "BRUCE/../bruce", ""):
            r = self.post(char=name)
            self.assertEqual(r.status_code, 400, name)

    def test_too_long_and_missing(self):
        self.assertEqual(self.post(text="x" * 501).status_code, 400)
        self.assertEqual(self.post(speaker="").status_code, 400)
        self.assertEqual(self.post(text="   ").status_code, 400)

    def test_speak_route_and_case_insensitive_char(self):
        r = self.client.post("/speak", json=dict(auth="k", char="BRUCE", speaker="Max", text="hi"))
        self.assertEqual(r.status_code, 200)

    def test_refuses_to_start_without_auth_key(self):
        with self.assertRaises(RuntimeError):
            create_app(dict(AUTH_KEY="change-me", LOG_FILE=None), claude=self.claude, base_dir=self.tmp)

    # ---- happy path and cleaning -----------------------------------------------------------
    def test_reply_is_cleaned(self):
        self.claude.replies = ['Bruce says, \u201cMind the [gap] \u2014 it\u2019s 100% *dangerous* & #1.\u201d\n\n\n\nHe grunts.']
        msg = self.post().get_json()["message"]
        self.assertEqual(msg, 'Bruce says, "Mind the gap -- it\'s 100 dangerous and 1."\n\nHe grunts.')
        self.assertTrue(msg.isascii())

    def test_prompt_contents(self):
        self.post(context="It is dusk.", weather="foggy")
        call = self.claude.calls[0]
        self.assertIn("COMMON RULES", call["system"])
        self.assertIn("You are Bruce.", call["system"])
        self.assertIn("You are speaking with Maximus.", call["system"])
        self.assertIn("It is dusk.", call["system"])
        self.assertIn("Weather: foggy", call["system"])
        self.assertEqual(call["model"], "claude-haiku-5-5")
        self.assertEqual(call["effort"], "low")
        self.assertEqual(call["messages"], [{"role": "user", "content": 'Maximus says, "Hello Bruce"'}])

    def test_never_replies_to_itself(self):
        self.assertEqual(self.post(speaker="Bruce").get_json()["message"], "")
        self.assertEqual(self.claude.calls, [])

    # ---- shared history --------------------------------------------------------------------
    def test_history_is_shared_alternates_and_ends_with_user(self):
        self.post(speaker="Ann", text="Hi Bruce")
        self.post(speaker="Bob", text="Bruce, who was that?")
        msgs = self.claude.calls[1]["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertIn("Ann says", msgs[0]["content"])
        self.assertIn("Bob says", msgs[2]["content"])

    def test_history_trim_never_starts_with_assistant(self):
        self.make_app(HISTORY_LIMIT=2)
        for i in range(6):
            self.post(text=f"Bruce, message {i}")
        for call in self.claude.calls:
            self.assertEqual(call["messages"][0]["role"], "user")
            self.assertEqual(call["messages"][-1]["role"], "user")

    def test_history_is_per_character(self):
        self.post()
        self.post(char="gladiator", text="Tiberius?")
        self.assertEqual(len(self.claude.calls[1]["messages"]), 1)

    def test_history_expires(self):
        self.make_app(HISTORY_TTL_MINUTES=1)
        self.post()
        # age every stored line by two minutes
        for c in list(self._characters().values()):
            for h in c.history:
                h["ts"] -= 120
        self.post(text="Bruce again")
        self.assertEqual(len(self.claude.calls[-1]["messages"]), 1)

    def _characters(self):
        # reach the cached Character objects through the closure of the route function
        fn = self.app.view_functions["speak"]
        cell = {n: c for n, c in zip(fn.__code__.co_freevars, fn.__closure__)}
        get_character = cell["get_character"].cell_contents
        cl = {n: c for n, c in zip(get_character.__code__.co_freevars, get_character.__closure__)}
        return cl["characters"].cell_contents

    # ---- failures --------------------------------------------------------------------------
    def test_claude_error_returns_502_and_rolls_back_history(self):
        self.claude.fail = True
        r = self.post()
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json()["message"], "Failed: Claude API error")
        self.claude.fail = False
        self.post(text="Bruce, try again")
        self.assertEqual(len(self.claude.calls[-1]["messages"]), 1)

    def test_rate_limit(self):
        self.make_app(MAX_CALLS_PER_HOUR=2)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 200)
        r = self.post()
        self.assertEqual(r.status_code, 429)
        self.assertTrue(r.get_json()["message"].startswith("Failed:"))

    # ---- per-player notes ------------------------------------------------------------------
    def test_notes_saved_scoped_to_player_and_persisted(self):
        self.post(speaker="Ann", text="Bruce, please remember that I'm allergic to nuts.")
        self.assertIn("I'm allergic to nuts", self.claude.calls[0]["system"])  # available immediately
        self.post(speaker="Bob", text="Bruce, hello")
        self.assertNotIn("allergic", self.claude.calls[1]["system"])
        self.post(speaker="ann", text="Bruce, hello again")  # names match case-insensitively
        self.assertIn("allergic to nuts", self.claude.calls[2]["system"])
        path = os.path.join(self.tmp, "data", "bruce", "notes.json")
        with open(path) as fh:
            self.assertEqual(json.load(fh), {"ann": ["I'm allergic to nuts"]})
        # a restart (new app, same data dir) still knows
        self.make_app()
        self.post(speaker="Ann", text="Bruce, remember me?")
        self.assertIn("allergic to nuts", self.claude.calls[-1]["system"])

    def test_note_cap_and_dedupe(self):
        self.make_app(MAX_NOTES_PER_PLAYER=2)
        for n in ("one one", "two two", "two two", "three three"):
            self.post(text=f"Bruce, remember that {n}")
        with open(os.path.join(self.tmp, "data", "bruce", "notes.json")) as fh:
            notes = json.load(fh)["maximus"]
        self.assertEqual(notes, ["two two", "three three"])

    def test_per_character_settings_override(self):
        with open(os.path.join(self.tmp, "characters", "bruce", "settings.json"), "w") as fh:
            json.dump({"model": "other-model", "max_tokens": 50, "effort": None}, fh)
        self.post()
        call = self.claude.calls[0]
        self.assertEqual((call["model"], call["max_tokens"], call["effort"]), ("other-model", 50, None))


class HelperTests(unittest.TestCase):
    def test_extract_note(self):
        cases = {
            "Bruce, remember that my sister is Julia": "my sister is Julia",
            "please remember: I owe you 5 coins.": "I owe you 5 coins",
            "Don't forget I paid you": "I paid you",
            "Make a note of that I owe Tim": "I owe Tim",
            "would you remember this: my name is Max": "my name is Max",
            "do you remember that guy?": None,
            "I remember that": None,
            "Hello there": None,
        }
        for text, expected in cases.items():
            self.assertEqual(extract_note(clean_input(text)), expected, text)

    def test_build_situation(self):
        s = build_situation({"auth": "x", "char": "b", "text": "t", "context": "Dusk.",
                             "time_of_day": "evening", "nested": {"a": 1}})
        self.assertEqual(s, "Dusk.\nTime of day: evening")

    def test_clean_reply_truncates_on_word_boundary(self):
        out = clean_reply("word " * 100, max_chars=22)
        self.assertTrue(out.endswith("...") and len(out) <= 25)

    def test_clean_reply_unsafe_chars(self):
        self.assertEqual(clean_reply("a$b%c[d]e{f}g\\h"), "abcdefgh")


if __name__ == "__main__":
    unittest.main()
