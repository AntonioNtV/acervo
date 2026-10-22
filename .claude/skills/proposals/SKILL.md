---
name: proposals
description: The proposal lifecycle in Acervo - kinds, states, accept with rebase, edit, reject with a reason, and the rule that only an accepted proposal changes a base. Use when adding a proposal kind or touching accept, reject or apply.
---

# Proposals

Agents never write to a base. They create proposals; the person accepts, edits or rejects them in the chat or in
"Propostas". `services/proposal_service.py` is the only code path that changes pages, files or folders on an
agent's behalf.

The person's own actions (create, edit, rename, drag, upload, trash, restore) are not proposals: their action is
their approval, and they write directly through `TreeService`, `PageService` and `FileService` with author `user`. The proposal
service calls those same services for an accepted proposal, with author `agent` and the proposal's id.

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
| `create_page` | folder, title, Markdown | new page, version 1 |
| `append`, `edit` | `Patch` (skill `markdown-pages`) | rebase, new page version |
| `conflict` | page, anchor, current text, new text | the person's choice: use new, keep current, keep both with a note |
| `save_pdf` | staged file, folder, name | moves the file from staging to the folder |
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
- An edited proposal keeps the original payload and stores the edited one; both go to `evals` as data.
- "Outro lugar" swaps the target for the second path the Curator logged; it does not run the Curator again.
- Undo after accept is a restore of the previous version (pages) or of the previous location (files).
- Auto-apply does not exist in the MVP. When it comes, it is a threshold in `Thresholds` and a per-base switch,
  and the proposal still exists with `accepted_by = auto`.
