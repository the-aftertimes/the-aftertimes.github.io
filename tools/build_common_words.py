"""Regenerate config/common_words.txt, the critic's plain-English vocabulary.

    pip install wordfreq && python tools/build_common_words.py

Run by hand, never in CI. `wordfreq` carries about 30MB of corpus data and the
daily job has no business installing it - the point of freezing the list to a
committed file is that the daily run needs no dependency and the vocabulary
cannot shift underneath the critic between runs.

The 3.0 Zipf cut-off is the readability line, so it is the one number here worth
arguing about. It admits roughly 28,000 words: 'girder' (2.7), 'apothecary' (2.7)
and 'thorax' (2.9) fall outside, while 'spoon' (3.9) and 'drill' (4.1) fall
inside. Raising it makes the critic stricter and starts flagging ordinary
concrete nouns; lowering it lets the archaic register back in.
"""
from __future__ import annotations

import os

from wordfreq import top_n_list, zipf_frequency

ZIPF_FLOOR = 3.0
MIN_LEN = 3
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "config", "common_words.txt")

HEADER = """\
# Words an ordinary reader knows without stopping. Anything NOT in
# here is flagged by critic.check_plainness as a word the reader has
# to decode, which is what makes a dispatch read archaic or clinical.
#
# Provenance: every English word with a Zipf frequency of 3.0 or above
# (roughly one occurrence per million words or commoner) in the
# `wordfreq` corpus, alphabetic, three letters or longer. Frozen to a
# file on purpose: the daily job must not grow a 30MB dependency, and a
# committed list is reviewable and cannot shift under the critic's feet.
# Regenerate with tools/build_common_words.py (needs wordfreq installed).
"""


def main() -> None:
    words = sorted(w for w in top_n_list("en", 200_000)
                   if zipf_frequency(w, "en") >= ZIPF_FLOOR
                   and w.isalpha() and len(w) >= MIN_LEN)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEADER)
        fh.write("\n".join(words) + "\n")
    print(f"{len(words)} words -> {OUT}")


if __name__ == "__main__":
    main()
