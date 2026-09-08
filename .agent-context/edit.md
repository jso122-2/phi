# /edit — Surgical fix

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- Touch only the shape / type / logic bug named in the ask.
- No drive-by refactors. No new files unless the bug is "the file is missing".
- Read the failing test or traceback first, then patch, then re-run that test.

If the fix needs a design choice, switch to `/talk` instead of guessing.
