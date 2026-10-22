---
name: curator-agent
description: The agent that files things in Acervo - turning a chat message or a dropped PDF into a card, descending the folder tree with Jev, the create/append/conflict policy and the proposal it builds. Use when changing where or how anything gets filed.
---

# Curator

Input: a message in Capturar mode, or a PDF dropped in the chat or a folder. Output: one proposal (skill
`proposals`), or a question to the person, or "already written". The Curator never writes to a base.

| Step | Who | File |
|---|---|---|
| 1. card of the input | LLM `card` | `curator/card.py` |
| 2. options of the current level | code | `curator/options.py` |
| 3. descent, beam of 2 | Jev `Choice` per level | `curator/descent.py` |
| 4. page check (text only) | Jev, one call: `covered` `Noul`, `contradicts` `Noul`, `section` `Choice` | `curator/page_check.py` |
| 5. PDF version check (PDF only) | Jev `Noul` per PDF already in the folder | `curator/pdf_check.py` |
| 6. policy | code, `config.Thresholds` | `curator/policy.py` |
| 7. patch (text only) | LLM `patch` | `curator/build.py` |
| 8. proposal | code | `curator/build.py` |

## The descent

Start at the base's root. At each level, one `Choice` whose options are built in `options.py`:

| Input | Options at a level |
|---|---|
| PDF | the subfolders, **"save here"**, **"new folder here"** |
| text | the subfolders, the pages of this folder, **"stay at this level"**, **"new page here"**, **"new folder here"** |

PDFs are never options. A PDF input never lands on a page.

Keep the 2 best paths at each level (beam). Stop at a page, at "save here"/"stay at this level", or at a "new …"
option. Depth limit 6. The second path becomes the proposal's "Outro lugar".

If a folder has more than 255 children (Jev's `Choice` limit), the options are the 60 with the most recent activity
plus "none of these"; when "none of these" wins, the person is asked. There is no embedding pre-filter.

## The policy

| Condition | Result |
|---|---|
| best path below `place_min` | question in the chat with the top 3 paths; the input waits in "Sem lugar definido" |
| text, `covered` above `covered` | "already written", with a link to the section; no proposal |
| text, `contradicts` above `contradicts` | `conflict` proposal showing both versions |
| text, landed on a page | `append` (or `edit` when the section has a line about the same thing) to the chosen section |
| text, landed on a folder | `create_page` with a title from the card |
| PDF, an existing PDF above `pdf_new_version` | `replace_pdf` (the old file goes to the file's history) |
| PDF, otherwise | `save_pdf` to the folder, with the suggested name |
| best path below `place_show_second` | the proposal shows the 2nd path next to the 1st |

## Rules

- A dropped PDF gets a card from its first pages and its outline only. The Curator does not read the whole PDF.
- The suggested PDF name keeps the extension `.pdf` and is editable in the proposal; the bytes are never changed.
- A new folder is proposed, never created as a side effect; accepting the proposal creates it.
- Everything the Curator decided is in the decision log under one `run_id`, which the proposal stores.

## Tests

Policy: one test per row of the table with a `FakeDecider` (skill `testing`). Descent: a tree fixture and fixed
probabilities, asserting the path and the second path. Real placement quality is measured in `evals`, not in tests.
