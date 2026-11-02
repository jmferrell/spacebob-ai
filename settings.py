"""Settings: defaults live here; config.py only needs to override what you change."""
import os
from types import SimpleNamespace

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "API_KEY": "",               # or set the ANTHROPIC_API_KEY environment variable
    "AUTH_KEY": "",              # shared secret the MUSH sends as "auth" (required)
    "MODEL": "claude-haiku-5-5",
    "MAX_TOKENS": 1024,          # ceiling for one reply; leaves room for the model's thinking
    "EFFORT": "low",             # "low" = fastest/cheapest. Set None if your model rejects it.
    "TIMEOUT_SECONDS": 30,
    "HISTORY_LIMIT": 30,         # conversation messages remembered per character
    "HISTORY_TTL_MINUTES": 60,   # forget conversation lines older than this (0 = never)
    "MAX_NOTES_PER_PLAYER": 20,  # "remember that..." notes kept per player
    "MAX_INPUT_CHARS": 500,      # longest player message accepted
    "MAX_REPLY_CHARS": 1500,     # longest reply sent back to the MUSH
    "MAX_CALLS_PER_HOUR": 300,   # overall cap on Claude calls (0 = unlimited)
    "ASCII_ONLY": True,          # transliterate replies to plain ASCII for the MUSH
    "HOST": "127.0.0.1",         # use "0.0.0.0" only if the MUSH is on another machine
    "PORT": 5000,
    "DATA_DIR": "data",          # notes are stored here (relative to the project folder)
    "CHARACTERS_DIR": "characters",  # folder of character briefs; relative to the project folder, or an absolute path
    "LOG_FILE": "logs/mushai.log",  # None = log to the console only
}


def load_config(overrides=None):
    """Return settings as an object. With no argument, reads config.py."""
    if overrides is None:
        try:
            import config as user_config
        except ImportError:
            raise RuntimeError(
                "config.py not found. Copy config.example.py to config.py and edit it."
            )
        overrides = {k: v for k, v in vars(user_config).items() if k.isupper()}
    values = dict(DEFAULTS)
    values.update(overrides)
    return SimpleNamespace(**values)
