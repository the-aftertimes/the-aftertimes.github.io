# The Aftertimes - working notes for Claude

## `main` has a SECOND writer: the bot

`daily-dispatch` commits and pushes to `main` **twice a day** (20:13 and 22:13
UTC), writing `index.html`, `archive.html`, `d/`, `data/` and `assets/img/`. So
your local clone goes stale on its own, with nobody touching it.

**Always `git pull` before you commit or push.** A push that has worked all
session will be rejected the moment a cron lands, and on 17/08/2026 it was
rejected after the bot filed two days of dispatches mid-session.

`pull.rebase` and `rebase.autoStash` are set locally in this repo, so a plain
`git pull` rebases and stashes work-in-progress for you. That fixes the second
failure mode too: `git pull --rebase` with unstaged changes used to abort with
*"cannot pull with rebase: You have unstaged changes"*.

**Do not** rewrite pushed history or force-push. The bot will push again on the
next cron regardless, so a force-push only loses dispatches.

Watch for conflicts in `data/` specifically - it is the one tree both you and
the bot write to (`data/dispatches/`, `data/last_email.json`,
`data/send_hold.json`, `data/trials/`).

## The newsletter is HELD, not broken (as at 17/08/2026)

Brevo put the shared account under validation on 10/08. `send_email.py` latches
`data/send_hold.json` on a 402 and stops calling the API - that is deliberate, to
avoid hammering an account under manual review. Clear it only once the account is
resolved:

```bash
python send_email.py --clear-hold
```

Publishing is unaffected and has continued throughout. See `docs/TODO.md` for the
full diagnosis, including the separate and larger finding that campaigns have
been delivering to an effectively empty list.

## The deadpan rule governs EVERY channel, not just the prose

The whole conceit is that absurd events are reported completely straight. That is
settled for the writing - "report the facts, never state the joke". **It applies
just as hard to the pictures, and twice now I have broken it in a channel I was
not thinking of:**

- `letter` and `advice` styles wrote first-person council complaints, then `review`
  wrote a consumer review of a funeral venue. Charlie: "doesn't feel like a news
  story." All three are gone. `firstperson` followed on 18/08/2026 - "shouldn't be
  first person (e.g. i am)" - which makes four styles cut for one reason. Earlier
  that same day I had tried to SAVE it by telling it to state the news in sentence
  one and witness it second. Wrong repair: the fault was the narrator, not the
  lede. A reporter who says "I" is writing a column.
- **The picture must be of the story's SUBJECT, not just a true moment from it.**
  18/08/2026, on a dispatch about six nuns guarding a burst pipe, `depict.py`
  returned a lone station fitter at a cart and flux drew it faithfully. Every rule
  was obeyed - plain, real, one figure, the dull moment after the event - and the
  picture was unrecognisable as the story. The one-or-two-figures rule is settled
  house style, so the fix was WHICH figure, never how many.
- Porting photocopy's image brief, I copied an `anomaly` slot asking for "the one
  thing a generic illustration would NOT have" - an instruction to be bizarre - and
  got a surreal tableau. Charlie: "really Dali-esque, it doesn't look real."

Photocopy is a drifting art project where surreal is the point. This is a
newspaper. **Before adding or porting anything that shapes an output - a style, a
prompt slot, a few-shot pool - ask whether it pushes toward reporting the absurd
thing plainly or toward performing it.** Anything that amplifies the absurdity is
wrong here, however good it looks elsewhere.

House style is settled and is NOT to be re-pitched: Dore engraving, monochrome.
Four alternatives were rendered and rejected on 17/08/2026 - see `docs/TODO.md`
and `data/trials/img/style-*.jpg`.

**The figure rule changed on 20/08/2026 and this note used to say the opposite.**
It read "one or two figures", full stop, and that cap was the reason three
consecutive pictures failed to look like their stories: roughly half the
dispatches have a group as the joke, and the cap forced the picture editor to
throw the group away and pick one person, which it kept getting wrong. Charlie
reconfirmed the hard cap when asked, then saw the first picture that broke it - a
woman at a camera tripod with her family lined up behind her - and said "it
actually looks fine here with multiple figures". So:

**One or two people are the SUBJECT; the cap is on the subject, not on the
frame.** Others may stand behind them, smaller and plainer. What is still banned
is a picture with no focal subject - a dozen equal faces at equal weight, which
is what actually turns to mush in an engraving. If a future picture is criticised
for being crowded, the fix is to make the subject dominate, not to empty the
background again.

## Read docs/TODO.md before writing to it

It is edited by other sessions between turns. On 17/08/2026 I appended an item
about duotoning the newsletter image, having missed that the newsletter had been
retired four days earlier - the file said so, I just had not re-read it. Append
via an editor that reads first, never a blind script.

## Trial batches eat the cron's quota

`trial.py` and the daily run share one Gemini free tier. Ten trials is roughly
thirty calls and **it exhausted the daily allowance on 10/08/2026, degrading that
night's dispatch** - the judge and revise passes both 429'd. I had told Charlie the
cron was not at risk, reasoning from a reset time rather than measuring. Run
batches AFTER the day's dispatch has filed, and do not reassure anyone about
headroom without checking what was actually consumed.

## Measure the archive BEFORE you change a prompt

Charlie's quality complaints are reliable as **symptoms** and often wrong as
**causes**. He reads the paper; he does not read the pipeline. Take the symptom
seriously and go measure it across `data/dispatches/*.json` before touching a
single prompt line - the measurement has changed the fix every time it has been
run:

- 17/08/2026, "hard to read... really archaic words and it's very verbose."
  Verbosity was **already fixed** - late July ran 271-317 words at a 21-30 word
  mean sentence, that week ran ~205 at 12-16. He was reading the BACK CATALOGUE,
  which the archive page surfaces just as prominently as today's. Rewriting the
  prompt for verbosity would have fixed nothing and probably broken something.
  The archaic half WAS real and measurable, and the root cause was not the model
  drifting: plainness was the one quality dimension `critic.py` did not measure,
  so it lost to every rule that was measured.
- 18/08/2026, "little bit too absurd." The write prompt was asking for it in as
  many words - "follow its internal logic to increasingly ridiculous conclusions".
  Not drift, an instruction.
- 18/08/2026, "image doesn't really match what it's about." flux was fine. The
  brief was fine prose. `depict.py` had chosen the wrong PERSON.

So: reproduce the complaint as a number over the whole archive, find the line of
config or prompt that CAUSES it, and only then edit. "The model has drifted" has
been the wrong answer three times running.

## Before changing anything about prose quality

Read `config/funny_lines.yaml` and the `quality` block in `config/settings.yaml`
first. The critic's thresholds are evidence-derived and one of them was wrong in
the dangerous direction (a rhythm floor that penalised the only dispatch Charlie
found funny). Do not reintroduce a threshold set by taste rather than by a
verdict.
