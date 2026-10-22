---
id: SPEC-local-notes
package_schema: canonical-spec-package.v1
companions: []
sources:
  - path: docs/intent.md
    role: provenance
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability.

# Local Notes

## Why

Realize a desktop notes prototype where one user keeps named plain-text notes available between app sessions.

## Capabilities

- **CAP-1**
  - **intent:** Create a named plain-text note.
  - **success:** A note with a non-empty title can be created with plain-text content.
- **CAP-2**
  - **intent:** Edit a note and return to its saved content after closing the app.
  - **success:** After text is edited and successfully saved, closing and reopening the app lets the user reopen the note with its saved title and text intact.
- **CAP-3**
  - **intent:** Prevent saving a note with an empty title.
  - **success:** An empty title is rejected and no save occurs.
- **CAP-4**
  - **intent:** Recover from a failed save without losing unsaved edits.
  - **success:** The app reports the save failure, retains unsaved edits, and permits a retry with those edits.

## Constraints

- The prototype is a single-user offline desktop app.
- Note content is plain text.

## Non-goals

- Accounts, network sync, attachments, sharing and billing.

## Success signal

- Offline, create and edit a named note, successfully save it, close and reopen the app, and recover the saved text.
- Reject an empty-title save; induce a save failure, observe the failure report and retained edits, then successfully retry saving those edits.

## Open Questions

- Which desktop operating system or systems must the prototype support?
- What initiates saving, and how should closing with unsaved edits be handled?
- Does an empty title include whitespace-only input?
