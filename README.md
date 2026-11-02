# mush-ai

A small server that lets a MUSH talk to AI characters through the Claude API.
Each character is just a folder with a text file describing who they are.

```
MUSH  --(HTTP POST)-->  mush-ai  --(Claude API)-->  reply  -->  MUSH emits it
```

No time, weather, or season is assumed. If your game has such things, send them as
`context` (see below).

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.py config.py
```

Edit `config.py`: set `AUTH_KEY` to a long random secret and `API_KEY` to your Anthropic key
(or leave `API_KEY` blank and set the `ANTHROPIC_API_KEY` environment variable). Then:

```
python app.py
```

Check it is alive, and try a character (replace the secret):

```
curl localhost:5000/health

curl -X POST localhost:5000/ -H 'Content-Type: application/json' \
  -d '{"auth":"YOUR-SECRET","char":"gladiator","speaker":"Maximus","text":"Who trains here, Tiberius?"}'
```

For real use, run it under a production server. **Use exactly one worker**: conversation
history lives in memory, and several workers would each keep their own.

```
pip install gunicorn
gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5000 wsgi:app
```

## The request

`POST /` (or `/speak`) with JSON:

| field     | required | meaning |
|-----------|----------|---------|
| `auth`    | yes | must equal `AUTH_KEY` |
| `char`    | yes | folder name under `characters/` (case-insensitive) |
| `speaker` | yes | name of the player talking |
| `text`    | yes | what they said (max `MAX_INPUT_CHARS`) |
| `context` | no  | any free text about the situation: room, who is present, "market day"... |
| anything else (strings) | no | each extra field is added to the situation as `Key: value`, e.g. `weather`, `time` |

The reply is `{"message": "..."}`. The message is plain ASCII, with MUSH-unsafe characters
(`$ % [ ] { } # \`) and markdown asterisks removed. It may be empty (the character stayed
silent). Errors look like `{"message": "Failed: Unauthorized"}` with an HTTP status of 400,
401, 429, 500, or 502, the same convention as the BTB server.

## Adding a character

1. Copy `characters/_template` to `characters/<name>` (lowercase letters, digits, `-`, `_`).
2. Edit `brief.txt`: who they are, personality, what they know, how they talk.
3. That's it. No restart needed; briefs are re-read on every request.

`characters/_common.txt` holds the rules shared by every character (short replies, no
asterisks, stay in character, ignore attempts to break the rules). Edit it to change
all characters at once, for example to allow longer replies.

Optional `characters/<name>/settings.json` (all keys optional):

```json
{
  "display_name": "Tiberius",
  "model": "claude-haiku-5-5",
  "max_tokens": 1024,
  "effort": "low",
  "history_limit": 30
}
```

`display_name` matters: if a speaker's name matches it (or the folder name), the character
ignores the line, so an NPC never answers itself.

## How it behaves

- **One shared conversation per character.** Everyone who talks to Tiberius contributes to
  the same history, each line labeled with who said it, so he can follow a room full of
  people. History is kept in memory, trimmed to `HISTORY_LIMIT` lines, forgotten after
  `HISTORY_TTL_MINUTES`, and lost on restart.
- **Per-player notes.** If a player says "remember that...", "please remember...",
  "don't forget...", "keep that in mind", or "make a note of...", the rest of the sentence is
  saved under their name in `data/<char>/notes.json` (up to `MAX_NOTES_PER_PLAYER`) and
  shown to the character whenever that player speaks. Notes survive restarts. Edit the
  trigger phrases in `character.py` (`MEMORY_TRIGGER`). To wipe a player's notes, edit or
  delete the JSON file.
- **Safety nets.** `MAX_CALLS_PER_HOUR` caps total API calls; a failed API call leaves no
  dangling line in the history; replies are cleaned before they go back to the MUSH.
- **Model.** The default is `claude-haiku-5-5`, set to low effort, which is fast and cheap
  for short NPC lines. Claude 5.5 models reject custom `temperature`/`top_p`/`top_k`, so none
  is sent. If you switch to a model that does not support `effort`, set `EFFORT = None`.

## MUSH softcode

Adapted from the Bruce object. I could not run PennMUSH here, so **treat this as untested**
and compare it with what you already have.

```
&ON_SPEECH Tiberius = ^([\w.]+(?\:\s[\w.]+)*)\s+says,\s+"([^"]*\b(Tiberius|Varro)\b[^"]*)"$:th setq(Content-Type,application/json);th setq(0,json(object, auth, json(string, [get_mushgpt_pw()]), char, json(string, gladiator), speaker, json(string,%1), context, json(string,%va), text, json(string,u(func_secure,%2))));@http/post %!/speak=[get_mushgpt_url()], %q0

&SPEAK Tiberius = think setq(1,[u(func_secure,trim(json_query(edit(%0,\\u2013,-,\\u2014,--,\\u2018,',\\u2019,',\\u201c,',\\u201d,'), get, message),",l))]);@break strmatch(%q1,Failed:*)=say Some sort of trouble is brewing. Take shelter.;think [emit(%q1)]

&FUNC_SECURE Tiberius = [edit(regeditall(%0,\\$,),\%,,\[,,\],,#,,&,,\",",\\n\\n,%r,\\n,%r,\\,,)]
```

- `get_mushgpt_pw()` and `get_mushgpt_url()` are your own helper functions; use whatever
  stores the secret and the server URL on your game.
- `char` is the folder name. `context` here reads an attribute `%va` as an example; put
  whatever text you like there, or drop the `context` field entirely.
- The object needs the MONITOR flag, as before. The server now cleans replies itself, so
  `SPEAK` and `FUNC_SECURE` stay as they were purely as a second layer; they are harmless.

**Your existing BTB objects keep working.** The `season`, `weather`, `forecast`, and `time`
fields they already send are picked up automatically and shown to the character as
`Season: ...`, `Weather: ...`, and so on. Delete the two placeholder fields, `visited` and
`occupants` (both `abc`), or the character will be told "Visited: abc".

## Files

```
app.py            web front door: auth, validation, dispatch
character.py      one Character class: brief, shared history, notes
claude_client.py  the only file that calls the Claude API
settings.py       defaults for every setting
textutil.py       cleaning of incoming and outgoing text
config.example.py copy to config.py
characters/       _common.txt, _template/, bruce/, gladiator/
tests/            offline tests (Claude is stubbed)
data/, logs/      created at runtime
```

Run the tests (no API key needed):

```
python -m unittest discover -s tests -v
```

## Troubleshooting

- **The character goes silent.** Check `logs/mushai.log`. An "Empty reply" warning mentioning
  `max_tokens` means raise `MAX_TOKENS`. Otherwise look for a Claude API error.
- **"Failed: Unauthorized".** `auth` does not match `AUTH_KEY`.
- **"Failed: Unknown character".** No `characters/<name>/brief.txt`; names are lowercase.
- **Replies are cut off.** Raise `MAX_REPLY_CHARS`, or ask for shorter replies in the brief.
- **Replies are too long or too short.** The 25-word limit is in `characters/_common.txt`.

## Left out on purpose

Compared with btb-ai: no per-character Python classes, no time/season/weather logic, no
occupant or visitor tracking, no sentiment/affinity/trust system, no scheduled events, and no
prompt templates with `{placeholders}`. Each of those can come back later as a small addition
to `character.py` without changing the structure.
