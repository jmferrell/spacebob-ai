# Writing a character brief

Every AI character is a folder with a plain-text file named `brief.txt`. The brief tells the
AI who the character is and how they talk. You don't need any programming to write one.

## How it works, in one minute

Each time a player speaks to a character, the AI is given, in this order:

1. The shared rules in `_common.txt` (reply length, no asterisks, stay in character...).
2. The character's `brief.txt`.
3. A short "current situation": who is talking, plus any context the game sends (such as the room).
4. Anything this player has asked the character to remember.
5. The recent conversation, shared by everyone talking to that character.

The AI reads all of that and writes the character's next line. It follows the brief closely,
and it also copies its wording, so the way you phrase things matters.

## Adding a character

1. Copy the `_template` folder and rename it. Use lowercase letters, digits, `-` or `_`
   (for example `innkeeper`).
2. Edit the new `brief.txt`.
3. Tell the MUSH object to use that folder name as its `char` value.

No restart is needed. The brief is read again on every message.

## Writing the brief

**Start with who, where, and what they're like.** One or two sentences of identity and
situation, then a handful of personality traits. Tie each trait to how it sounds:

- Weak: `Gruff.`
- Better: `Gruff: short sentences, grumbles before answering, never flatters.`

**Examples get copied, so choose them carefully.** If you include a sample line, expect its
wording to show up again and again. Label examples as tone only ("never repeat these lines"),
give two or three that differ in length and shape, and avoid any phrase or image you wouldn't
want to hear fifty times.

**Words you repeat get repeated.** A place, object, or catchphrase mentioned several times in
a brief will appear in nearly every reply. Mention each idea once, and add a line such as
`Vary your wording; don't lean on any one word or image.`

**Say what to do, not only what to avoid.** Describe the behavior you want.

- Weak: `Doesn't know about modern things.`
- Better: `If a player mentions anything modern (phones, cars), react with plain confusion and
  ask what it is. Never play along or claim to have one.`

**Decide the awkward cases in advance.** Players will try things: modern references, "are you
a bot?", insults, requests for items, quests, or rooms that don't exist, a one-word message
like "hi". Give each case that matters one line. If younger players use the game, or it's part
of a school project, add a line such as `Keep everything suitable for a school audience;
deflect anything inappropriate in character.`

**Fence what the character knows.** List the real places, people, and facts in your game, and
tell the AI that when it's unsure, it should stay vague or say so in character. Otherwise it
fills gaps with plausible inventions, such as a back room, a menu item, or a rack of weapons
by the door that players then go looking for. For historical or mythological characters, name
the details you want to get right and any popular myths you want avoided.

**Don't let rules fight each other.** The shared rules and the brief are read together. If
two rules could clash, say which wins ("you may still agree to remember what a player tells
you, even about things you don't understand"). If you want longer replies than the default,
say so plainly, for example `You may use up to 40 words.`

**Keep it short and organized.** Short sections with bullets, usually 300 to 500 words. Long
briefs dilute the important lines. Don't repeat what `_common.txt` already covers.

**State pronouns** for the character (`Pronouns: she/her`), so they don't drift mid-conversation.

## Testing and editing

**Test like a player.** Run through about ten lines:

- a greeting
- a question about the character's own world
- a question from outside it
- a rude remark
- a silly request
- "are you an AI?"
- a single word like "hi"
- "remember that..." followed later by a question about it

Change one thing at a time, so you know which edit helped.

**When a reply surprises you, ask which line caused it.** Fix the cause rather than adding a
"never do X" for every surprise. That bloats the brief and often creates new problems.

**Remember the history.** Edits apply on the next message, but the last hour of conversation
is still part of what the AI sees, so a character may keep old habits for a while. Reloading
the server gives a clean start.

**Save a copy of a working brief before a big rewrite**, somewhere outside the `characters`
folder, so you can go back if the new version is worse.
