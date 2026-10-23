---
name: proposals
description: The proposal lifecycle in Acervo - kinds, states, accept with rebase, edit, reject with a reason, and the rule that only an accepted proposal changes a base. Use when adding a proposal kind or touching accept, reject or apply.
---

# Proposals

Agents never write to a base. They create proposals; the person accepts, edits or rejects them in the chat or in
"Propostas". `services/proposal_service.py` is the only code path that changes pages, files or folders on an
agent's behalf.

The person's own actions (create, edit, rename, drag, upload, trash, restore) are not proposals: their action is
their approval, and they write directly through `TreeService`, `PageService` (the autosaved working text, skill
`markdown-pages`) and `FileService` with author `user`. The proposal service calls those same services for an
accepted proposal, with author `agent` and the proposal's id.

| Piece | File |
|---|---|
| models and kinds | `schemas/proposal.py` |
| states and transitions (pure) | `domain/proposals.py` |
| storage | `repositories/proposal.py` (on the `UnitOfWork`) |
| accept, reject, apply per kind | `services/proposal_service.py` |
| events | `proposal.created`, `proposal.updated` on the websocket |

## Kinds

| Kind | Payload | Apply |
|---|---|---|
| `create_page` | parent (folder or page), title, Markdown | new page, version 1 |
| `append`, `edit` | `Patch` (skill `markdown-pages`) | cut the working text, rebase, new page version |
| `conflict` | page, anchor, current text, new text | the person's choice: use new, keep current, keep both with a note |
| `save_pdf` | staged file, parent (folder or page), name | moves the file from staging under the parent |
| `replace_pdf` | staged file, existing PDF | new file version, old one in history |
| `move`, `rename` | node, destination or name | updates paths and wiki links |
| `new_folder` | parent, name | only as part of another proposal that needs it |

## States

```
pending → accepted → applied
pending → editing → pending
pending → rejected (reason)
pending → stale (the page moved on and the rebase failed) → pending (new diff)
```

Reject reasons are fixed: `wrong_place`, `already_there`, `wrong_info`, `not_worth_keeping`. They are labels for
calibration (skill `evals`), so the UI always asks for one.

## Rules

- Accept is idempotent and runs in one transaction: apply, new version, link the version to the proposal, refresh
  the descriptions of the ancestors (as a job, after commit).
- An agent patches the newest version, never the working text: the working text is cut as a version first, when the
  agent reads the page and again at accept, so the rebase sees what the person typed. The applied version also becomes
  the working text with a new `revision`, so an open editor reloads instead of overwriting it.
- An edited proposal keeps the original payload and stores the edited one; both go to `evals` as data.
- "Outro lugar" swaps the target for the second path the Curator logged; it does not run the Curator again.
- Undo after accept is a restore of the previous version (pages) or of the previous location (files).
- Every agent connection (the web chat, each MCP client) has a mode set by the person: **ask** (proposals wait) or
  **auto-approve** (accepted on creation, `accepted_by = auto`). Even in auto-approve, a `conflict` and an input with
  no place above `place_min` wait for the person. An auto-approved proposal still exists, is in the decision log with
  its connection, and is undone like any other.
