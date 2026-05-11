# tokenspeed

**How fast is 30 tokens per second, really?**

Every local-LLM benchmark reports throughput: "47 tok/s on an M3," "180 tok/s on a 4090," "500 tok/s on Groq." But unless you've actually watched tokens stream at those speeds, the numbers are hard to internalize.

`tokenspeed` is a tiny terminal toy that streams fake tokens at any rate you set, so you can see what those numbers actually look like.

Three modes:

- **`code`** — syntax-highlighted pseudo-code (Python/Rust/JS), the most common thing you watch stream out of an LLM
- **`text`** — Wikipedia prose, for the chat/answer case
- **`think`** — dim-italic reasoning sentences alternating with code, mimicking a reasoning model thinking out loud

If you don't pick a mode on the command line, it'll ask.

## Run it

```bash
python3 tokenspeed.py                  # 30 tok/s, prompts for mode
python3 tokenspeed.py 60               # 60 tok/s, prompts for mode
python3 tokenspeed.py --mode code      # skip the prompt
python3 tokenspeed.py 120 --mode think # both at once
```

No dependencies — just Python 3 and a real terminal.

## What to try

Start at the default `30` and read along. Then hit `1` (5 tok/s) — Raspberry-Pi-class local model. Then `5` (60 tok/s) — typical hosted Claude or GPT. Then `7` (200 tok/s) — Groq territory. Then `9` (800 tok/s) — Cerebras-class, where the bottleneck is your eyeballs.

Now switch between `--mode code` and `--mode text` at the same rate. The difference is striking and intentional — see below.

## Controls

| Key      | Action                                                              |
| -------- | ------------------------------------------------------------------- |
| `+` / `-`| Nudge the rate by ×1.25                                             |
| `1`–`9`  | Jump to a preset: 5, 10, 20, 30, 60, 100, 200, 400, 800 tok/s       |
| `space`  | Pause / resume                                                      |
| `q`      | Quit                                                                |

## What counts as a token

`tokenspeed` approximates BPE-style tokenization. It is **not** trying to exactly reproduce `tiktoken`, Claude's tokenizer, or any vendor-specific encoder — those disagree with each other in the details anyway.

Roughly: short words are often one token; longer identifiers frequently split into multiple chunks (e.g., `processUserInput` → `process` + `User` + `Input`, `calculate_score` → `calculate` + `_score`); and punctuation and operators usually count as tokens too.

The point worth internalizing: code is more token-dense than prose, so the same tok/s can feel very different depending on what's streaming. 30 tok/s of code lands far less visible content per second than 30 tok/s of English. The benchmark number is honest; the perceptual effect just varies a lot by content type, which is exactly the gap this tool exists to expose.

(English prose averages ~1.3 tokens per word, so 30 tok/s ≈ 23 words/s.)
