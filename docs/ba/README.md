# MediSync — Business Analysis Artifacts

This folder holds the **Business Analyst deliverables** for every MediSync feature. It exists alongside the engineering work so the project doubles as a BA portfolio.

For each feature or system enhancement, we produce three standard artifacts:

| Artifact | File | Purpose |
|---|---|---|
| Business Requirements Document | `brd.md` | The **why** — problem, stakeholders, goals, scope, success metrics |
| Functional Specification | `fsd.md` | The **what** — use cases, user stories, acceptance criteria |
| Flows & Diagrams | `flows.md` | The **how it moves** — context, process, sequence diagrams (Mermaid) |

---

## Folder convention

```
docs/ba/
├── README.md                ← this file (index)
├── _templates/              ← copy-paste starting points
│   ├── brd-template.md
│   ├── fsd-template.md
│   └── flows-template.md
└── NN-feature-slug/         ← one folder per feature, numbered in build order
    ├── brd.md
    ├── fsd.md
    └── flows.md
```

- **Numbering** mirrors `docs/runbooks/` so features stay browsable in build order.
- **Mermaid** is the diagramming standard — renders natively on GitHub, diffs cleanly, no external tools.
- Each feature's code/service `README.md` should link back to its `docs/ba/NN-feature-slug/` folder.

---

## Feature index

| # | Feature | Status | Folder |
|---|---|---|---|
| _none yet — first feature lands here_ | | | |

Status values: `Draft` · `Approved` · `Implemented` · `Superseded`

---

## How to add a new feature

1. Pick the next number (`NN`) and a short kebab-case slug.
2. Create `docs/ba/NN-feature-slug/`.
3. Copy the three templates from `_templates/` into it.
4. Fill in BRD first → review with stakeholders (or self) → FSD → flows.
5. After editing `flows.md`, regenerate the SVGs (see below).
6. Add a row to the feature index above.
7. Link from the feature's code README back to this folder.

---

## Diagram rendering

`flows.md` files contain Mermaid source blocks. GitHub renders them inline natively, but we **also** commit standalone `.svg` exports so diagrams open in a browser, scale cleanly, and can be dropped into slide decks or PDFs.

**One-time setup** (Node 18+ required, pnpm preferred):

```powershell
pnpm install                # installs @mermaid-js/mermaid-cli + Chromium (~170 MB)
```

**After editing any `flows.md`:**

```powershell
pnpm render:diagrams        # walks docs/ba/**/flows.md and rewrites the sibling flows/*.svg
```

This script:
- Finds every `docs/ba/<feature>/flows.md`.
- Extracts each ```` ```mermaid ```` block.
- Names each SVG `NN-<slug>.svg` (NN = block index; slug derived from the nearest preceding `##`/`###` heading).
- Writes them to `docs/ba/<feature>/flows/`.
- Theme: **neutral** (clean, readable in GitHub light/dark modes).

**Convention in `flows.md`:** every Mermaid block is followed by an image embed of its rendered SVG, e.g.

````markdown
```mermaid
graph LR
  A --> B
```

![Context diagram](./flows/01-context.svg)
````

The Mermaid block is the source of truth; the SVG is a generated artifact. Re-run `pnpm render:diagrams` after edits so they stay in sync.
