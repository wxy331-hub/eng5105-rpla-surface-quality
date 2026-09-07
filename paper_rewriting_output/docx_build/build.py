# -*- coding: utf-8 -*-
"""Build both submission .docx files from the Markdown sources.

Runs the whole chain: extract diagrams, render them, assemble the reference
document, convert with pandoc, post-process the result, copy it up, and check it.
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

import extract
import make_ref
import verify

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, 'build')
DEST = os.path.dirname(HERE)

TOC_TITLE = {'en': 'Contents', 'zh': '目录'}
OUTPUT_NAME = {'en': 'ENG5105_Proposal_Design_Report_EN.docx',
               'zh': 'ENG5105_Proposal_Design_Report_ZH.docx'}

# APA 7th: reference entries carry a 0.5 in hanging indent
HANGING = '<w:ind w:left="720" w:hanging="720"/>'
REFERENCES = re.compile(r'<w:p\b[^>]*>(?:(?!</w:p>).)*?'
                        r'<w:pStyle w:val="Heading1"\s*/>(?:(?!</w:p>).)*?'
                        r'<w:t[^>]*>(?:References|参考文献)</w:t>(?:(?!</w:p>).)*?</w:p>', re.S)


CELL = re.compile(r'<w:tc>.*?</w:tc>', re.S)
ROW = re.compile(r'<w:tr\b.*?</w:tr>', re.S)
# the tag must end right after "t" or carry attributes, so <w:tcPr> is not a match
RUN_TEXT = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', re.S)

# Narrowest share of the table a single column may take, in percent. Proportional
# allocation alone does not guarantee an absolute minimum, so a short label column
# such as the risk register's "RSK-06" needs this floor to stay on one line. There
# is no fixed ceiling: a two-column table is entitled to a 77% prose column, and the
# weight cap below already stops any one column running away in a busy table.
NARROWEST = 10
# a column's weight stops growing past this many display units
WEIGHT_CAP, WEIGHT_FLOOR = 40, 6
# cells carry a left and right margin, so a column needs more than its text width
CELL_PADDING = 3
# Table text is set smaller than body text. A seven-column register does not fit an
# A4 text column at 12 pt without breaking short cells such as "RSK-01" across two
# lines, and a denser table face is the usual answer to that in a report.
TABLE_POINTS = 9


def display_width(text):
    """Rough printed width in half-widths: CJK and full-width punctuation take two."""
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in text)


def size_tables(doc):
    """Give every table explicit column widths.

    Pandoc pins column widths from the Markdown source, which shreds a six-column
    table into one word per line, so those have to go. Word's own auto layout is not
    a safe replacement here: it gives a column its minimum content width and shares
    the rest out by maximum content width, and because Chinese breaks between any two
    characters, the minimum width of a Chinese column is one character. Short label
    and rating columns therefore collapse into vertical stacks of single characters.

    Instead the widths are computed from the content: each column is weighted by its
    widest cell, weights are clamped so that neither a long prose column nor a short
    label column takes over, and the layout is fixed so Word honours the result."""
    doc = re.sub(r'<w:tblW\b[^/]*/>', '<w:tblW w:w="5000" w:type="pct"/>', doc)
    doc = re.sub(r'<w:tblLayout\b[^/]*/>', '<w:tblLayout w:type="fixed"/>', doc)
    doc = doc.replace('<w:tblPr>', '<w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
                                   '<w:tblLayout w:type="fixed"/>')
    doc = re.sub(r'(<w:tblW w:w="5000" w:type="pct"/>)(?:\s*<w:tblW\b[^/]*/>)+', r'\1', doc)
    doc = re.sub(r'(<w:tblLayout w:type="fixed"/>)(?:\s*<w:tblLayout\b[^/]*/>)+', r'\1', doc)

    def one_table(match):
        block = match.group(0)
        rows = ROW.findall(block)
        if not rows:
            return block
        columns = max(len(CELL.findall(row)) for row in rows)
        if columns < 2:
            return block

        weights = [WEIGHT_FLOOR] * columns
        for row in rows:
            for index, cell in enumerate(CELL.findall(row)[:columns]):
                text = ''.join(RUN_TEXT.findall(cell))
                needed = display_width(text) + CELL_PADDING if text else 0
                weights[index] = max(weights[index], min(WEIGHT_CAP, needed))

        total = float(sum(weights))
        widest = 100 - NARROWEST * (columns - 1)
        shares = [max(NARROWEST, min(widest, w / total * 100)) for w in weights]
        scale = 100.0 / sum(shares)
        # w:tcW in pct counts fiftieths of a percent, so 5000 is the full width
        fiftieths = [int(round(s * scale * 50)) for s in shares]
        fiftieths[-1] += 5000 - sum(fiftieths)

        grid = ''.join('<w:gridCol w:w="%d"/>' % f for f in fiftieths)
        block = re.sub(r'<w:tblGrid>.*?</w:tblGrid>', '<w:tblGrid>' + grid + '</w:tblGrid>',
                       block, count=1, flags=re.S)

        def one_row(row_match):
            row = row_match.group(0)
            index = {'n': 0}

            def one_cell(cell_match):
                cell = cell_match.group(0)
                position = min(index['n'], columns - 1)
                index['n'] += 1
                width = '<w:tcW w:w="%d" w:type="pct"/>' % fiftieths[position]
                patched, count = re.subn(r'<w:tcPr\s*/>',
                                         '<w:tcPr>' + width + '</w:tcPr>', cell, count=1)
                if count:
                    return patched
                return re.sub(r'<w:tcPr>', '<w:tcPr>' + width, cell, count=1)

            return CELL.sub(one_cell, row)

        return shrink_text(ROW.sub(one_row, block))

    return re.sub(r'<w:tbl>.*?</w:tbl>', one_table, doc, flags=re.S)


def shrink_text(table):
    """Set every run in the table at the table point size."""
    size = '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (TABLE_POINTS * 2, TABLE_POINTS * 2)

    def run(match):
        text = match.group(0)
        if '<w:sz ' in text:
            return text
        patched, count = re.subn(r'<w:rPr\s*/>', '<w:rPr>' + size + '</w:rPr>', text, count=1)
        if count:
            return patched
        patched, count = re.subn(r'<w:rPr>', '<w:rPr>' + size, text, count=1)
        if count:
            return patched
        return re.sub(r'^(<w:r\b[^>]*>)', r'\1<w:rPr>' + size + '</w:rPr>', text)

    return re.sub(r'<w:r\b[^>]*>.*?</w:r>', run, table, flags=re.S)


def toc_after_cover(doc):
    """Pandoc puts its table of contents at the very top, ahead of the report title.
    A submitted report reads cover, then contents, then body."""
    toc = re.search(r'<w:sdt>.*?docPartGallery w:val="Table of Contents".*?</w:sdt>',
                    doc, re.S)
    if not toc:
        raise SystemExit('table of contents block not found')
    block = toc.group(0)
    doc = doc[:toc.start()] + doc[toc.end():]

    # the cover is the title, the subtitle and the document-field table
    end_of_cover = doc.find('</w:tbl>')
    if end_of_cover < 0:
        raise SystemExit('front-matter table not found')
    end_of_cover += len('</w:tbl>')

    page_break = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    return doc[:end_of_cover] + page_break + block + page_break + doc[end_of_cover:]


def hanging_references(doc):
    """Apply the APA hanging indent to every paragraph after the References
    heading. That section is last, so the tail needs no further boundary."""
    heading = REFERENCES.search(doc)
    if not heading:
        raise SystemExit('References heading not found in the produced document')
    head, tail = doc[:heading.end()], doc[heading.end():]

    def indent(match):
        block = match.group(0)
        if '<w:pPr>' in block:
            return block.replace('<w:pPr>', '<w:pPr>' + HANGING, 1)
        return re.sub(r'^(<w:p\b[^>]*>)', r'\1<w:pPr>' + HANGING + '</w:pPr>', block)

    tail = re.sub(r'<w:p\b[^>]*>.*?</w:p>', indent, tail, flags=re.S)
    return head + tail


def check_writable(*paths):
    """Word and WPS keep an open document locked, and pandoc's failure on a locked
    output is an unhelpful non-zero exit. Say which file to close instead."""
    held = []
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            open(path, 'ab').close()
        except PermissionError:
            held.append(path)
    if held:
        raise SystemExit('close these in Word or WPS and run build.py again:\n  '
                         + '\n  '.join(held))


def bake_fields(path):
    """Fill the table-of-contents field in, so a reader sees it without refreshing.

    Word may prompt instead of refreshing on open, and WPS Office ignores the
    instruction, which leaves the contents page blank. Needs Word; if it is not
    available the build still produces a valid file, just one whose contents page
    depends on the reader."""
    script = os.path.join(HERE, 'bake_fields.ps1')
    try:
        done = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', script, '-Docx', path],
                              capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as problem:
        sys.stdout.write('  contents left as an unfilled field: %s\n' % problem)
        return
    if done.returncode:
        complaint = (done.stderr or done.stdout).strip().splitlines()
        sys.stdout.write('  contents left as an unfilled field: %s\n'
                         % (complaint[-1] if complaint else 'Word did not run'))
        return
    sys.stdout.write('  contents filled in (%s)\n' % done.stdout.strip())


def post_process(path):
    temp = path + '.tmp'
    source = zipfile.ZipFile(path)
    items = [(name, source.read(name)) for name in source.namelist()]
    source.close()
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as target:
        for name, data in items:
            if name == 'word/document.xml':
                doc = data.decode('utf-8')
                doc = size_tables(doc)
                doc = toc_after_cover(doc)
                doc = hanging_references(doc)
                data = doc.encode('utf-8')
            elif name == 'word/settings.xml':
                text = data.decode('utf-8')
                # Word leaves a pandoc TOC field empty until fields are refreshed,
                # and docStructureTags is what makes PDF export hang.
                text = re.sub(r'<w:docStructureTags\s*/>', '', text)
                if 'updateFields' not in text:
                    text = re.sub(r'(<w:settings\b[^>]*>)',
                                  r'\1<w:updateFields w:val="true"/>', text, count=1)
                data = text.encode('utf-8')
            target.writestr(name, data)
    os.replace(temp, path)


def discard(path):
    """Best-effort delete. A stale reader's handle is not worth failing the build."""
    try:
        os.remove(path)
    except OSError:
        pass


def main():
    os.makedirs(BUILD, exist_ok=True)
    for language in ('en', 'zh'):
        extract.prepare(language)

    subprocess.run(['node', 'render.mjs'], cwd=HERE, check=True)
    make_ref.main()

    # Only the delivered files have to be writable. Each conversion goes to a name of
    # its own, so a reader that is still holding a previous run's intermediate cannot
    # block this one.
    check_writable(*[os.path.join(DEST, name) for name in OUTPUT_NAME.values()])

    for stale in os.listdir(BUILD):
        if stale.startswith('stage_') and stale.endswith('.docx'):
            discard(os.path.join(BUILD, stale))

    for language in ('en', 'zh'):
        stage = 'stage_%s_%d.docx' % (language, os.getpid())
        staged = os.path.join(BUILD, stage)
        subprocess.run(
            ['pandoc', 'body_%s.md' % language, '-o', stage,
             '--reference-doc=ref_a4.docx', '--toc', '--toc-depth=2',
             '--resource-path=.', '-f', 'markdown-tex_math_dollars+tex_math_single_backslash',
             '--metadata', 'toc-title=%s' % TOC_TITLE[language]],
            cwd=BUILD, check=True)
        post_process(staged)
        bake_fields(staged)
        shutil.copyfile(staged, os.path.join(DEST, OUTPUT_NAME[language]))
        sys.stdout.write('built and copied %s\n' % OUTPUT_NAME[language])
        # a stable copy to open while reviewing; never load-bearing
        try:
            shutil.copyfile(staged, os.path.join(BUILD, 'out_%s.docx' % language))
        except OSError:
            pass
        discard(staged)

    verify.main()


if __name__ == '__main__':
    main()
