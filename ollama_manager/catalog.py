"""A short, opinionated list of models to offer in the Install dropdown.

Any Ollama tag can still be typed by hand — this exists so a user who does not
follow model releases has somewhere sensible to start, with the download size
stated up front. Sizes are the approximate download for the listed tag; they
matter more than benchmark scores when you are on a metered tier-2/3 connection.

Ordered smallest-first, because the most common mistake is pulling a 40 GB
model onto a laptop that cannot run it.
"""

# (tag, approx download, one-line note)
MODELS = [
    ('qwen2.5:0.5b', '~0.4 GB', 'Tiny. Runs on almost anything; basic answers.'),
    ('llama3.2:1b', '~1.3 GB', 'Very small, quick. Light Q&A and summarising.'),
    ('gemma2:2b', '~1.6 GB', 'Small Google model; tidy short answers.'),
    ('llama3.2:3b', '~2.0 GB', 'Good balance for an ordinary office PC.'),
    ('phi3:mini', '~2.3 GB', 'Strong reasoning for its size; 4 GB RAM is enough.'),
    ('qwen2.5:3b', '~1.9 GB', 'Solid all-rounder, good with structured text.'),
    ('mistral:7b', '~4.1 GB', 'Popular general model; needs ~8 GB RAM.'),
    ('llama3.1:8b', '~4.7 GB', 'The common default. Needs ~8 GB RAM.'),
    ('qwen2.5-coder:7b', '~4.7 GB', 'Tuned for code and SQL.'),
    ('gemma2:9b', '~5.4 GB', 'Bigger Google model; needs ~12 GB RAM.'),
    ('deepseek-r1:8b', '~4.9 GB', 'Shows its reasoning; slower to answer.'),
    ('nomic-embed-text', '~0.3 GB', 'Embeddings only — not a chat model.'),
]

# Chosen when nothing is installed yet: small enough to finish downloading and
# actually run on a modest machine, rather than the biggest thing available.
SUGGESTED = 'llama3.2:3b'


def choices():
    """Dropdown labels: 'tag  —  size  —  note'."""
    return ['{}   —   {}   —   {}'.format(tag, size, note)
            for tag, size, note in MODELS]


def tag_from_choice(choice):
    """Pull the bare tag back out of a dropdown label (or a hand-typed tag)."""
    text = (choice or '').strip()
    if not text:
        return ''
    return text.split('—')[0].strip()
