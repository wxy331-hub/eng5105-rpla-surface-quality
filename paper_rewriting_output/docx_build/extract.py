# -*- coding: utf-8 -*-
"""Prepare a Word-only working copy of each report.

Pulls the Mermaid blocks out into `.mmd` files and leaves an image reference
behind. The `.md` sources are read byte-for-byte and never written.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
BUILD = os.path.join(HERE, 'build')

BLOCK = re.compile(r'```mermaid\r?\n(.*?)```', re.S)

# Placed width per figure, against the 6.69 in A4 text column and each diagram's
# aspect ratio. Figure 1 takes the full column; Figure 2 is portrait-shaped and has
# to be held back so it fits the page height.
#
# A landscape page for Figure 1 was measured and rejected: once the flowchart is
# drawn top-to-bottom it is close to square, so a landscape page is limited by
# height rather than width and buys 0.2 pt of label size for an orientation break.
WIDTH = {'fig1': '6.6in', 'fig2': '4.0in', 'fig3': '5.5in', 'fig4': '6.3in'}


def prepare(lang):
    src = os.path.join(SRC, 'ENG5105_Proposal_Design_Report_%s.md' % lang.upper())
    text = io.open(src, encoding='utf-8', newline='').read()

    blocks = BLOCK.findall(text)
    if len(blocks) != 4:
        raise SystemExit('%s: expected 4 Mermaid blocks, found %d' % (lang, len(blocks)))

    for index, block in enumerate(blocks, 1):
        lines = block.replace('\r\n', '\n').split('\n')
        # a trailing semicolon is a statement separator, not punctuation
        cleaned = '\n'.join(line.rstrip().rstrip(';') if line.strip().endswith(';')
                            else line.rstrip() for line in lines)
        io.open(os.path.join(BUILD, 'fig%d_%s.mmd' % (index, lang)), 'w',
                encoding='utf-8', newline='\n').write(cleaned.strip() + '\n')

    counter = {'n': 0}

    def to_image(_match):
        counter['n'] += 1
        name = 'fig%d' % counter['n']
        return '![](%s_%s.png){width=%s}' % (name, lang, WIDTH[name])

    body = BLOCK.sub(to_image, text)

    out = os.path.join(BUILD, 'body_%s.md' % lang)
    io.open(out, 'w', encoding='utf-8', newline='\n').write(body)
    sys.stdout.write('%s: 4 diagrams extracted\n' % lang.upper())


if __name__ == '__main__':
    os.makedirs(BUILD, exist_ok=True)
    for language in ('en', 'zh'):
        prepare(language)
