# -*- coding: utf-8 -*-
"""Assemble the reference document pandoc styles the output from.

Starts from pandoc's own default and changes four things: A4 page setup, a centred
page-number footer, Times New Roman throughout, and an East Asian face on every run
so the Chinese report does not fall back to a substitute font.

On the font choice: APA 7th does not mandate Times New Roman. Its setup guide says
"Many fonts are acceptable, including 12-point Aptos, 11-point Calibri, 11-point
Arial, 12-point Times New Roman, and 11-point Georgia", and pandoc's default theme
already used 12-point Aptos, which is on that list. Times New Roman is chosen for
portability rather than compliance: Aptos ships only with current Microsoft 365, so
a marker on Office 2019, LibreOffice or macOS would see a silently substituted face
that need not be on APA's list at all. Setting both the major and minor theme fonts
also satisfies APA's "use the same font throughout the entire paper", which the
Aptos Display headings did not.
"""
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, 'build')
BASE = os.path.join(BUILD, 'ref_base.docx')
OUT = os.path.join(BUILD, 'ref_a4.docx')

FOOTER = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr><w:jc w:val="center"/><w:rPr><w:sz w:val="18"/></w:rPr></w:pPr>
    <w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>
    <w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
    <w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r>
    <w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r>
    <w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r>
  </w:p>
</w:ftr>'''

SECTPR = (
    '<w:sectPr>'
    '<w:footerReference w:type="default" r:id="rIdFtr1"/>'
    '<w:footnotePr><w:numRestart w:val="eachSect"/></w:footnotePr>'
    '<w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
    'w:header="708" w:footer="708" w:gutter="0"/>'
    '<w:cols w:space="708"/>'
    '<w:docGrid w:linePitch="360"/>'
    '</w:sectPr>'
)


LATIN = 'Times New Roman'
EAST_ASIAN = 'SimSun'          # the conventional serif partner for Times New Roman


def east_asian(match):
    """w:eastAsiaTheme wins over w:eastAsia, and the default theme leaves it empty."""
    tag = match.group(0)
    if not tag.endswith('/>'):
        return tag
    tag = re.sub(r'\s*w:eastAsiaTheme="[^"]*"', '', tag)
    tag = re.sub(r'\s*w:eastAsia="[^"]*"', '', tag)
    return tag[:-2] + ' w:eastAsia="%s"/>' % EAST_ASIAN


def latin_theme(theme_xml):
    """Point both theme fonts at one face, so headings and body agree."""
    return re.sub(r'(<a:(?:major|minor)Font>\s*<a:latin typeface=")[^"]*"',
                  lambda m: m.group(1) + LATIN + '"', theme_xml)


def main():
    os.makedirs(BUILD, exist_ok=True)
    with open(BASE, 'wb') as handle:
        subprocess.run(['pandoc', '--print-default-data-file', 'reference.docx'],
                       stdout=handle, check=True)

    source = zipfile.ZipFile(BASE)
    names = source.namelist()
    parts = {name: source.read(name) for name in names}
    source.close()

    document = parts['word/document.xml'].decode('utf-8')
    document = re.sub(r'<w:sectPr>.*?</w:sectPr>', SECTPR, document, flags=re.S)
    if 'pgSz' not in document:
        raise SystemExit('sectPr not replaced')
    parts['word/document.xml'] = document.encode('utf-8')

    rels = parts['word/_rels/document.xml.rels'].decode('utf-8')
    rels = rels.replace('</Relationships>',
                        '<Relationship Id="rIdFtr1" Type="http://schemas.openxmlformats.org'
                        '/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
                        '</Relationships>')
    parts['word/_rels/document.xml.rels'] = rels.encode('utf-8')

    types = parts['[Content_Types].xml'].decode('utf-8')
    types = types.replace('</Types>',
                          '<Override PartName="/word/footer1.xml" ContentType="application/vnd'
                          '.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>')
    parts['[Content_Types].xml'] = types.encode('utf-8')

    styles = parts['word/styles.xml'].decode('utf-8')
    parts['word/styles.xml'] = re.sub(r'<w:rFonts\b[^>]*/>', east_asian, styles,
                                      flags=re.S).encode('utf-8')

    theme = parts['word/theme/theme1.xml'].decode('utf-8')
    parts['word/theme/theme1.xml'] = latin_theme(theme).encode('utf-8')

    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in names:
            target.writestr(name, parts[name])
        target.writestr('word/footer1.xml', FOOTER.encode('utf-8'))

    sys.stdout.write('reference document: A4, page-number footer, CJK fallback\n')


if __name__ == '__main__':
    main()
