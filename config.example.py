# Copy this file to config.py and edit. Anything you leave out uses the default in settings.py.

AUTH_KEY = "change-me"        # REQUIRED: a long random secret; the MUSH sends it as "auth"
API_KEY = ""                  # your Anthropic API key (or set ANTHROPIC_API_KEY instead)

MODEL = "claude-haiku-5-5"    # small and fast is plenty for NPC chatter
EFFORT = "low"                # None if you switch to a model that doesn't support effort
MAX_CALLS_PER_HOUR = 300      # safety cap on API usage (0 = unlimited)
# CHARACTERS_DIR = "/home/spacebob/files/characters"  # absolute path; leave out to use ./characters
# HOST = "0.0.0.0"            # only if the MUSH runs on a different machine (then firewall port 5000)
# PORT = 5000
