# Edit references

Every reel you saved because the edit was good, measured with the same ruler as
your own videos. A cut you like becomes a named style you can repeat, instead of
a reel you saved and forgot.

## How it fills

1. Get your Instagram data export (Messages, and Saved if you use it, format JSON).
2. `python scripts/ig-refs.py pull <the zip> --saved` keeps every reel, TikTok and
   YouTube link you sent to yourself, plus whose video it is. Never the text you
   typed.
3. `python scripts/teardown.py --urls .teardown/ig-refs.txt --label refs --sheets --cookies ig-cookies.txt`
   downloads each one, measures every cut, reads the first spoken words and the
   loudness, and saves two frame grids per reel in `.teardown/sheets/refs/`.
4. `python scripts/ig-refs.py merge` writes the numbers into the table below.

Then group rows that share a cut, open their frame grids, and write the style
down: font, size, position, words per caption, how often it cuts. Put its name in
the Style column so the next merge keeps it.

Measure and learn the cut. Never reuse someone else's footage, audio or captions.

## References

<!-- refs:start -->
_Empty until the first pull._
<!-- refs:end -->
