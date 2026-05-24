# git history search

`git` is a search engine over *changes*, not just current contents. Use it to
answer "when/why did this appear or vanish?".

## Pickaxe: search the content of diffs

```bash
git log -S'MAX_RETRIES'             # commits that changed the COUNT of this string
git log -G'retry_.*count'           # commits whose diff matches this REGEX
git log -S'MAX_RETRIES' -p          # ...with the patch for each hit
```

`-S` is best for "added/removed this exact token"; `-G` for "any diff line
matching this regex" (including moves that don't change the count).

## Line-range and function history

```bash
git log -L :parseConfig:src/config.ts     # full history of one function
git log -L 40,80:src/config.ts            # history of a line range
```

## Per-path history

```bash
git log -p -- path/to/file.py             # full patch history of a path
git log --oneline -- path/to/file.py      # compact list of touching commits
git log -1 -S'MAX_RETRIES' -- src/        # the single most recent change to it
```

## Who and when (blame, deletions)

```bash
git blame -L 40,80 src/config.ts          # last author per line in a range
git log --diff-filter=D --oneline -- src/old.py   # commits that DELETED a path
git log --diff-filter=A --oneline -- src/new.py   # commits that ADDED a path
```

## Optional: structural diffs with difftastic

```bash
GIT_EXTERNAL_DIFF=difft git show <sha>    # syntax-aware diff for one commit
GIT_EXTERNAL_DIFF=difft git log -p -- f   # structural patches in log
```

`difft` highlights structural changes (moved/renamed nodes) instead of raw
line noise — useful when a reformat buries the real change.

## Recipes

```bash
# When was this constant introduced?
git log --reverse -S'MAX_RETRIES' --oneline | head -1

# Who removed this call, and in which commit?
git log -G'requests\.get\(' --diff-filter=M -p -- src/client.py
```
