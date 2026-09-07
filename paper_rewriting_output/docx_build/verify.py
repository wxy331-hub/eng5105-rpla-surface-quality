# -*- coding: utf-8 -*-
"""Check each produced .docx against what its Markdown source says it should hold."""
import io
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, 'build')
DEST = os.path.dirname(HERE)
# the checks run against what is actually delivered, not the intermediate
DELIVERED = {'en': 'ENG5105_Proposal_Design_Report_EN.docx',
             'zh': 'ENG5105_Proposal_Design_Report_ZH.docx'}

# the Windows console is code-page bound; probe names carry ¥ and Chinese
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# text that must be present, and text that must not have survived an earlier design
PROBES = (('IMX415', True), ('A$142.00', True), ('A$360.00', True),
          ('Global Shutter', False), ('CN¥688', False), ('encoder', False))


def plain_text(document_xml):
    return re.sub(r'<[^>]+>', '', document_xml.replace('</w:p>', '\n'))


def check(language):
    path = os.path.join(DEST, DELIVERED[language])
    archive = zipfile.ZipFile(path)
    names = archive.namelist()
    doc = archive.read('word/document.xml').decode('utf-8')
    body = plain_text(doc)
    settings = archive.read('word/settings.xml').decode('utf-8')

    source = io.open(os.path.join(BUILD, 'body_%s.md' % language),
                     encoding='utf-8', newline='').read()

    results = [
        ('diagrams embedded', len([n for n in names if n.startswith('word/media/')]) == 4),
        ('tables match source', doc.count('<w:tbl>') == len(re.findall(r'(?m)^\|---', source))),
        ('equations converted', doc.count('<m:oMath') > 40 and '\\frac' not in body),
        ('A4 page setup', 'w:w="11906"' in doc and 'w:h="16838"' in doc),
        ('page-number footer', any(n.startswith('word/footer') for n in names)),
        # a baked field carries its entries between fldChar separate and end
        ('contents filled in', 'TOC' in doc
                               and doc.count('PAGEREF') >= 20),
        ('APA hanging indent', 'w:hanging="720"' in doc),
        ('table columns sized', '<w:tblLayout w:type="fixed"/>' in doc
                                 and 'w:type="pct"' in doc),
        ('contents after cover', doc.index('Table of Contents') > doc.index('</w:tbl>')),
        ('no accessibility tags', 'docStructureTags' not in settings),
    ]
    for probe, expected in PROBES:
        # source paths inside reference entries are intentional, body prose is not
        found = probe in body if probe != 'encoder' else bool(re.search(r'\bencoder', body))
        results.append(('%s %s' % ('holds' if expected else 'drops', probe), found == expected))

    failed = [name for name, ok in results if not ok]
    for name, ok in results:
        sys.stdout.write('  %s %s\n' % ('ok  ' if ok else 'FAIL', name))
    return failed


def main():
    problems = {}
    for language in ('en', 'zh'):
        sys.stdout.write('%s\n' % language.upper())
        failed = check(language)
        if failed:
            problems[language] = failed
    if problems:
        raise SystemExit('verification failed: %s' % problems)
    sys.stdout.write('both documents pass every structural check\n')


if __name__ == '__main__':
    main()
