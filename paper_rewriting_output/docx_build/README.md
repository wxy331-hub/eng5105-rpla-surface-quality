# Word build for the paired proposal reports

This toolchain reconstructs the historical paired DOCX revision. The current
user-confirmed final report is [the supplied PDF](../final/Proposal_Design_Report.pdf);
these scripts neither generate nor replace that file.

The two Markdown reports one directory up are the hash-anchored source of this historical revision.
`ENG5105_Proposal_Design_Report_EN.docx` and `..._ZH.docx` are generated from them
for submission and carry no hash record of their own.

## Build

```bash
cd paper_rewriting_output/docx_build
npm install          # first run only
python build.py
```

That renders the four Mermaid diagrams, assembles an A4 reference document, runs
pandoc, post-processes the result, copies both `.docx` one directory up, and prints
a structural check. Everything it writes lands in `build/`, which is ignored by git.

## Visual check (optional, needs Word)

```powershell
powershell -File preview.ps1 -Docx build\out_en.docx -Pdf build\preview_en.pdf -From 1 -To 6
node pdfshot.mjs build/preview_en.pdf build/en 1 2 3
```

`preview.ps1` opens the file in Word, refreshes the table-of-contents field and
exports the page range to PDF. `pdfshot.mjs` turns PDF pages into PNGs so they can
be looked at without a PDF viewer.

## Things that will bite you

**Do not edit the `.md` sources from here.** The build reads them and writes a
working copy into `build/`. The sources are byte-anchored: Appendix A and
`final_artifact_manifest.md` record their SHA-256, and `.gitattributes` marks them
`-text` so Git stores their CRLF endings unchanged. Any script that touches them
must read and write with `newline=''`.

**System Chrome cannot render the diagrams on this machine.** `chrome.exe
--headless=new` and `--headless=old` both terminate the renderer before it requests
the page; `--dump-dom` returns nothing. `render.mjs` therefore uses the Chromium
that puppeteer installs. It also serves the build directory over local HTTP,
because a page loaded through `setContent` has an `about:blank` origin and cannot
import the Mermaid ES module from `file://`.

**Pandoc pins table column widths from the Markdown source**, which shreds a
six-column table into one word per line. `build.py` rewrites every table to
`autofit` so Word sizes columns by content.

**Pandoc's table-of-contents field is empty until fields are refreshed.**
`build.py` writes `<w:updateFields w:val="true"/>` into `word/settings.xml` so Word
populates it on open.

**`docStructureTags` makes PDF export hang** for more than twenty minutes on this
document. `build.py` strips it, and `preview.ps1` passes `$false` for it. If you
export a PDF from the Word interface instead, clear the "Document structure tags
for accessibility" checkbox.

**Dollar math is disabled** (`-tex_math_dollars`) so that Australian-dollar amounts
are never read as maths delimiters. The reports write maths as `\[...\]` and
`\(...\)`, which `+tex_math_single_backslash` covers.

**A semicolon inside an unquoted Mermaid label becomes a statement separator** and
invents phantom nodes. `extract.py` strips trailing semicolons; a semicolon in the
middle of a label has to be fixed in the source.

## Deliberate differences from the Markdown

Recorded in the delivery-boundary paragraph of `final_artifact_manifest.md`:

- Figure 1 is drawn top-to-bottom rather than left-to-right, and sits on its own
  landscape page, because an A4 text column renders its labels at about 4 pt.
- Table columns are sized by Word rather than by the Markdown source widths.
- The table of contents is a field the reader's Word populates on open.

No wording, number, table row or figure element differs.
