#!/usr/bin/env python3
"""Stream tokens at a configurable rate to feel LLM speeds."""
import argparse
import random
import re
import select
import sys
import termios
import time
import tty

# ---------------------------------------------------------------------------
# Prose mode (lorem ipsum)
# ---------------------------------------------------------------------------

TEXT = '''
Intelligence

Intelligence refers to certain mental powers. There is no general agreement on which mental powers are intelligent or part of intelligence. The idea comes from a Latin word: "intelligo" meaning to "choose between different options". A part of intelligence allows people to solve problems. These problems may be easy to solve. They may also be difficult to solve, and involve abstract thought. For some, intelligence is a property, or characteristic of the mind. For others, it is simply the working of the brain, especially the cerebral cortex.

If an answer is found to a problem, it can be remembered. That way, the problem is solved more quickly when it comes up again. This is what is called learning.

There is disagreement about which has more influence on intelligence, genetics or environment. Also, intelligent behaviour is possibly learned when an organism (a living thing) reacts enough to a stimulus.

Scientists believe that intelligence can be measured or tested. A type of intelligence test would be solving many problems in a very short time. Most of the problems have to do with seeing things, or telling what a rotated shape would look like. Some are also related to mathematics: for example to tell what number would come next in a row. Other tests have to do with words or the understanding of language. After giving such a test to a person, a number would be calculated to give an approximation of the Intelligence Quotient (IQ).

Computer engineers try to build machines that act as if they were intelligent. This is related to computer science and is called Artificial intelligence (man-made "intelligence"). Artificial intelligence uses logic, and often combines it with machine learning. This means that similar to living organisms, the machine has to be trained to solve a problem. After training, it will solve the problem faster.

Intelligence is not limited to humans. Many animals also show signs of intelligence: animals also need to solve problems, and remembering how a problem is solved is useful to them. Many animals use tools to solve problems. These animals include the Great Apes, dogs, dolphins, elephants, rats and mice, and some birds. All these animals are vertebrates, but tool use isn't limited to these: Even cephalopods and arthropods show signs of intelligence. To be able to compare the behaviours of different species, scientists need to adapt the notion of intelligence. 

It has been argued that plants should also be classified as intelligent: they are able to sense and model external and internal environments and adjust their morphology, physiology and phenotype accordingly to ensure self-preservation and reproduction. A counter argument is that intelligence is commonly understood to involve the creation and use of persistent memories. 

Opposed to this are computations that only occur once, and that do not involve learning. If this is accepted as part of the definition, then it includes the artificial intelligence of robots capable of "machine learning", but excludes those purely autonomic sense-reaction responses that can be observed in many plants. Plants are not limited to automated sensory-motor responses, however, they are capable of discriminating positive and negative experiences and of 'learning' (registering memories) from their past experiences. They are also capable of communication, accurately computing their circumstances, using sophisticated cost–benefit analysis and taking tightly controlled actions to mitigate and control the diverse environmental stressors.
'''.split(' ')

def _bpe_split_plain_word(word):
    """BPE-ish: short words stay whole; longer words split more often."""
    n = len(word)
    if n <= 5:
        yield word
        return
    p_split = 0.3 if n <= 7 else 0.5 if n <= 10 else 0.75
    if random.random() >= p_split:
        yield word
        return
    cut = random.randint(2, n - 2)
    yield word[:cut]
    yield word[cut:]


def prose_tokens():
    i = 0
    while True:
        word = TEXT[i % len(TEXT)]
        i += 1
        yield from _emit_split_word(word)


# ---------------------------------------------------------------------------
# Code mode (syntax-highlighted pseudo-code)
# ---------------------------------------------------------------------------

KEYWORDS = {
    "def", "class", "if", "else", "elif", "for", "while", "return", "import",
    "from", "as", "in", "not", "and", "or", "is", "None", "True", "False",
    "try", "except", "with", "pass", "break", "continue", "lambda", "yield",
    "async", "await", "fn", "let", "const", "mut", "pub", "struct", "impl",
    "match", "self", "Self", "use", "function", "var", "new", "throw",
}

BUILTINS = {
    "print", "len", "range", "sum", "min", "max", "sorted", "enumerate",
    "map", "filter", "zip", "list", "dict", "set", "tuple", "int", "str",
    "float", "bool", "open", "isinstance", "type", "Vec", "String", "Some",
    "Ok", "Err", "Result", "Option", "Error", "fetch", "Date", "Config",
    "fs",
}

DECL_KEYWORDS = {"def", "fn", "function", "class", "struct", "impl"}

COLORS = {
    "kw":      "\x1b[1;35m",   # bold magenta
    "builtin": "\x1b[36m",     # cyan
    "fn":      "\x1b[1;33m",   # bold yellow
    "string":  "\x1b[32m",     # green
    "number":  "\x1b[33m",     # yellow
    "comment": "\x1b[2;37m",   # dim
}
RESET = "\x1b[0m"

TOKEN_RE = re.compile(
    r"""
      (?P<comment> \#[^\n]* | //[^\n]* )
    | (?P<string>  "(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*' | `(?:[^`\\]|\\.)*` )
    | (?P<number>  \d+(?:\.\d+)? )
    | (?P<word>    [A-Za-z_][A-Za-z_0-9]* )
    | (?P<ws>      \n[ \t]* | [ \t]+ )
    | (?P<op>      [^\w\s] )
    """,
    re.VERBOSE,
)

CODE_SNIPPETS = [
    '''def estimate_tokens(text, model="claude-opus"):
    # Rough heuristic: ~1 token per 4 chars of English
    chars = len(text)
    overhead = sum(1 for c in text if c in ".,;:!?")
    return (chars // 4) + overhead + 1
''',
    '''class TokenStream:
    def __init__(self, model, prompt, rate=30):
        self.model = model
        self.prompt = prompt
        self.rate = rate
        self._budget = 2048

    async def __aiter__(self):
        async for chunk in self.model.stream(self.prompt):
            yield chunk.text
            if chunk.stop_reason:
                return
''',
    '''fn parse_config(path: &str) -> Result<Config, Error> {
    let contents = fs::read_to_string(path)?;
    let mut config = Config::default();
    for line in contents.lines() {
        if line.starts_with('#') || line.is_empty() {
            continue;
        }
        config.apply(line)?;
    }
    Ok(config)
}
''',
    '''const fetchUser = async (id) => {
    const res = await fetch(`/api/users/${id}`);
    if (!res.ok) {
        throw new Error(`HTTP ${res.status}: failed to load user`);
    }
    const user = await res.json();
    return { ...user, fetchedAt: Date.now() };
};
''',
    '''def merge_sorted(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    return result + left[i:] + right[j:]
''',
    '''def retry(func, attempts=3, backoff=0.5):
    # Exponential backoff with jitter
    for n in range(attempts):
        try:
            return func()
        except Exception as err:
            if n == attempts - 1:
                raise
            time.sleep(backoff * (2 ** n))
''',
]


def _color(text, style):
    return f"{style}{text}{RESET}" if style else text


def _emit_split_word(word, style=""):
    """Yield BPE-split pieces of word; first piece prefixed with a space."""
    first = True
    for piece in _bpe_split_plain_word(word):
        yield _color((" " + piece) if first else piece, style)
        first = False


_IDENT_PARTS = re.compile(r"_+|[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]*|[a-z]+|\d+")


def _split_identifier(text):
    """BPE-ish: split identifiers at snake_case / camelCase / acronym boundaries."""
    if len(text) <= 5:
        yield text
        return

    chunks = _IDENT_PARTS.findall(text)
    # Single underscores cling to the following piece: `calculate_score` -> `calculate`, `_score`.
    # Runs of two or more (`__init__`) stand alone.
    merged = []
    i = 0
    while i < len(chunks):
        c = chunks[i]
        if c == "_" and i + 1 < len(chunks):
            merged.append("_" + chunks[i + 1])
            i += 2
        else:
            merged.append(c)
            i += 1

    if len(merged) > 1:
        yield from merged
        return

    if len(text) >= 10 and random.random() < 0.35:
        cut = random.randint(3, len(text) - 3)
        yield text[:cut]
        yield text[cut:]
    else:
        yield text


def _emit_snippet(snippet):
    """Yield colored tokens for one code snippet."""
    expecting_fn = False
    for m in TOKEN_RE.finditer(snippet):
        kind = m.lastgroup
        text = m.group()

        if kind == "ws":
            yield text
            continue

        split_ident = False
        if kind == "word":
            if text in KEYWORDS:
                style = COLORS["kw"]
                expecting_fn = text in DECL_KEYWORDS
            elif text in BUILTINS:
                style = COLORS["builtin"]
                expecting_fn = False
            elif expecting_fn:
                style = COLORS["fn"]
                expecting_fn = False
                split_ident = True
            else:
                style = ""
                split_ident = True
        elif kind in ("comment", "string", "number"):
            style = COLORS[kind]
        else:
            style = ""

        if split_ident:
            for piece in _split_identifier(text):
                yield _color(piece, style)
        else:
            yield _color(text, style)


def _snippet_cycle():
    while True:
        yield from random.sample(CODE_SNIPPETS, len(CODE_SNIPPETS))


def code_tokens():
    for snippet in _snippet_cycle():
        yield from _emit_snippet(snippet)
        yield "\n"


# ---------------------------------------------------------------------------
# Think mode (reasoning blended with code)
# ---------------------------------------------------------------------------

THINK_STYLE = "\x1b[2;3m"  # dim italic

THOUGHTS = [
    "Let me trace through this with a small example to make sure the indices line up.",
    "The function takes a path and returns a Result, so any IO error bubbles up via the ? operator.",
    "Wait — if the input list is empty, the loop never executes and we return a stale value.",
    "I think the cleanest approach is to extract this into its own helper and unit-test it in isolation.",
    "Actually, the existing utility already handles the retry logic, so I should just reuse it.",
    "Looking at the call sites, none of them pass None, so a non-optional type is fine here.",
    "Let me check whether the upstream library closes the connection on its own.",
    "First I'll validate the input, then run the main loop, then format the output for the caller.",
    "The hot path here is the inner loop, so I want to avoid allocations inside it if possible.",
    "I should add an early return when the cache is warm to skip the expensive recomputation.",
    "This is essentially a fold, so a reduce with an accumulator dictionary should work cleanly.",
    "If we're streaming, we can't materialize the whole list — switch to a generator that yields chunks.",
    "The error handling is duplicated across all three call sites, so let me factor it into a decorator.",
    "Hmm, the type annotation says str but the runtime value can be bytes when the encoding fails.",
    "I'll use a context manager so the file gets closed even if an exception is raised mid-iteration.",
    "Before writing the implementation, I want to sketch the public API to keep the surface minimal.",
    "The naming is a bit confusing here — result and response mean different things in this codebase.",
    "OK, I think I have a clear plan now. Let me write the function:",
    "That handles the happy path. Now I need to think about what happens on a partial failure.",
    "Reading the tests, the contract seems to be that empty input returns an empty list, not None.",
]


def _emit_thought():
    """Yield dim-italic tokens for a 3–7 sentence thought."""
    for _ in range(random.randint(3, 7)):
        sentence = random.choice(THOUGHTS)
        for word in sentence.split():
            base = word.rstrip(",.;:?!")
            tail = word[len(base):]
            if not base:
                base, tail = word, ""
            yield from _emit_split_word(base, THINK_STYLE)
            for ch in tail:
                yield _color(ch, THINK_STYLE)


def think_tokens():
    for snippet in _snippet_cycle():
        yield from _emit_thought()
        yield "\n\n"
        yield from _emit_snippet(snippet)
        if random.random() < 0.7:
            yield "\n"
            yield from _emit_thought()
            yield "\n\n"
        else:
            yield "\n"


# ---------------------------------------------------------------------------
# TUI loop
# ---------------------------------------------------------------------------

PRESETS = {
    "1": 5, "2": 10, "3": 20, "4": 30, "5": 60,
    "6": 100, "7": 200, "8": 400, "9": 800,
}

MIN_RATE = 0.05
MAX_RATE = 2000.0
RATE_STEP = 1.25
PAUSE_POLL = 0.05  # seconds between input polls while paused

GENERATORS = {"code": code_tokens, "text": prose_tokens, "think": think_tokens}


def status(rate, paused, mode):
    state = "PAUSED" if paused else f"{rate:>5.1f} tok/s"
    return (
        f"\n\n\x1b[2m[ {state} | mode: {mode} | "
        f"+/- adjust · 1-9 preset · space pause · q quit ]\x1b[0m\n"
    )


def prompt_mode():
    sys.stdout.write(
        "\n\x1b[1mChoose mode:\x1b[0m\n"
        "  \x1b[1;33m[c]\x1b[0m code   — syntax-highlighted pseudo-code\n"
        "  \x1b[1;33m[t]\x1b[0m text   — lorem ipsum prose\n"
        "  \x1b[1;33m[h]\x1b[0m think  — reasoning blended with code\n"
        "\n> "
    )
    sys.stdout.flush()
    keys = {"c": "code", "t": "text", "h": "think"}
    while True:
        ch = sys.stdin.read(1).lower()
        if ch in keys:
            sys.stdout.write(f"{keys[ch]}\n")
            return keys[ch]
        if ch in ("q", "\x03", "\x04"):  # q, Ctrl-C, Ctrl-D
            sys.stdout.write("\n")
            sys.exit(0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rate", type=float, nargs="?", default=30.0,
                   help="initial tokens per second (default: 30)")
    p.add_argument("--mode", choices=list(GENERATORS), default=None,
                   help="what to stream (prompts if omitted)")
    args = p.parse_args()

    rate = max(MIN_RATE, args.rate)
    paused = False

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)

        mode = args.mode or prompt_mode()
        gen = GENERATORS[mode]()

        sys.stdout.write(status(rate, paused, mode))
        sys.stdout.flush()

        next_tick = time.monotonic()
        while True:
            while select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch == "q":
                    sys.stdout.write(RESET + "\n\n")
                    return
                elif ch in ("+", "="):
                    rate = min(rate * RATE_STEP, MAX_RATE)
                elif ch in ("-", "_"):
                    rate = max(rate / RATE_STEP, MIN_RATE)
                elif ch == " ":
                    paused = not paused
                elif ch in PRESETS:
                    rate = float(PRESETS[ch])
                else:
                    continue
                sys.stdout.write(status(rate, paused, mode))
                sys.stdout.flush()
                next_tick = time.monotonic()

            if paused:
                time.sleep(PAUSE_POLL)
                continue

            sys.stdout.write(next(gen))
            sys.stdout.flush()

            next_tick += 1.0 / rate
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_tick = time.monotonic()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write(RESET + "\n")


if __name__ == "__main__":
    main()
