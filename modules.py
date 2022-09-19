import os
import re
import shutil
from functools import cache
from uuid import uuid4

import numpy as np
from bs4 import BeautifulSoup
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage
from slugify import slugify

temp_dir = 'temp'

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# Generic format of temp files
temp_file = lambda filename='temp.tmp': f'{temp_dir}/{filename}'


class Module:
    """Generic file conversion module class. Subclasses will need to override `_run()` method."""

    INPUT_FORMAT = '~'
    OUTPUT_FORMAT = '~'

    @staticmethod
    def _get_temp_file(ext, filename='temp'):
        return temp_file(filename=f'{filename}.{ext}')

    @property
    def _input_source(self):
        return self._get_temp_file(ext=self.INPUT_FORMAT)

    @property
    def output(self):
        return self._get_temp_file(ext=self.OUTPUT_FORMAT)

    @property
    @cache  # so that its name is randomly generated once and then reused
    def input(self):
        """Internal file used in case input and output files are of same format"""
        return self._get_temp_file(ext=self.INPUT_FORMAT, filename=f"temp-{uuid4().hex}")

    def run(self):
        """Runs the module"""
        shutil.copyfile(self._input_source, self.input)  # copy
        self._run()
        os.remove(self.input)  # remove the temp input

    def _run(self):
        raise NotImplemented('This method needs to be override by child modules')


class MdToMdWithoutWikilinks(Module):
    INPUT_FORMAT = 'md'
    OUTPUT_FORMAT = 'md'

    def _run(self):
        with open(self.input, 'r') as f:
            md_data = f.read()

        wikilinks_pattern = re.compile(r'\[\[\s*(?P<target>[^][|]+?)(\s*\|\s*(?P<label>[^][]+))?\s*\]\]')
        new_md_data = ''
        prev_i = 0
        for match in wikilinks_pattern.finditer(md_data):
            target, label = match.group(1, 3)
            if label is None:
                label = target
            new_md_data = new_md_data + md_data[prev_i: match.span()[0]] + f"[{label}]({target})"
            prev_i = match.span()[1]

        new_md_data = new_md_data + md_data[prev_i:]

        with open(self.output, 'w') as f:
            f.write(new_md_data)


class SlugifyMdSectionLinks(Module):
    """This module processes the Markdown links to sections within the same document in a way
    that would allow them to be clickable after being converted to HTML

    [cool new section](#Section 33) -> [cool new section](#section-33)
    """
    INPUT_FORMAT = 'md'
    OUTPUT_FORMAT = 'md'

    def _run(self):
        with open(self.input, 'r') as f:
            md_data = f.read()

        md_links_pattern = re.compile(r'\[(?P<label>[^\[]+)\]\((?P<target>.*)\)')
        section_pattern = re.compile(r'^((?:.{0}|.*[^\\]))\#(.+)')
        new_md_data = ''
        prev_i = 0
        for match in md_links_pattern.finditer(md_data):
            label, target = match.group(1, 2)
            sections = section_pattern.findall(target)
            if len(sections) != 0:  # referencing a section in this link
                file, section = sections[0]
                slug = slugify(section)
                target = f'{file}#{slug}'
            new_md_data = new_md_data + md_data[prev_i: match.span()[0]] + f"[{label}]({target})"
            prev_i = match.span()[1]

        new_md_data = new_md_data + md_data[prev_i:]

        with open(self.output, 'w') as f:
            f.write(new_md_data)


class MdToHTML(Module):
    INPUT_FORMAT = 'md'
    OUTPUT_FORMAT = 'html'

    def __init__(self, title=None, workdir=None):
        """
        :param title: Title to be given to the HTML file
        :param workdir: directory from which the referenced files can be accessed (images, etc)
        """
        self.title = title
        self.wdir = workdir

    def _run(self):
        cmd = f"""pandoc --css=resources/pandoc.css --self-contained --mathml --quiet """ \
              f""" -f markdown -t html "{self.input}" -o "{self.output}" """

        # if given title will put it onto the HTML so better not
        if self.title is not None:
            cmd += f"""--title="{self.title}" """
        if self.wdir is not None:
            cmd += f"""--resource-path="{self.wdir}" """

        os.system(cmd)


class HTMLtoPDF(Module):
    """
    Step 0:
        Add dummy text to the end of the html so that it's the lowest text on the PDF
    Step 1:
        generate a PDF with maximum possible page length (10m+) to fit all the content
        to calculate how much it can be trimmed
    Step 2:
        read the max PDF generated on the previous step ant find where the lowest content item is (the dummy text
    Step 3:
        generate a new PDF with paper height exactly to fit the lowest item + margin
    """
    INPUT_FORMAT = 'html'
    OUTPUT_FORMAT = 'pdf'

    CMD = """prince "{input}" -o "{output}" """
    PTS_IN_MM = 1 / 25.4 * 72  # 72 points in inch, 1 inch = 22.4 mm

    def _run(self):
        self._style_tag_id = uuid4().hex  # id of style element specifying page dimensions
        self._dummy_text = uuid4().hex  # text to be put onto the bottom of the page to calculate its effective length

        for page_height_m in [10, 100, 1000]:  # -meter-long paper
            self._make_max_pdf(page_height_m=page_height_m)
            if self._get_output_page_count() == 1:  # content fit on one page, no need to try to increase paper size
                break

        page_height_mm = self._calculate_new_page_height_mm()

        self._make_fit_pdf(page_height_mm)

    def _get_output_page_count(self):
        if not os.path.exists(self.output):  # file doesn't exist
            return 0

        with open(self.output, 'rb') as f:
            return len(list(PDFPage.get_pages(f)))

    def _make_max_pdf(self, page_height_m=10):
        self._write_pdf(page_height_mm=page_height_m * 1000, add_dummy_text=True)

    def _make_fit_pdf(self, page_height_mm):
        self._write_pdf(page_height_mm=page_height_mm, add_dummy_text=False)

    def _calculate_new_page_height_mm(self):
        lowest_y = self._get_lowest_y_mm()
        new_height = np.ceil(lowest_y)
        return new_height

    def _get_lowest_y_mm(self):
        """Reads the input PDF and finds the lowest y value of an element if indexed from top right"""

        with open(self.output, 'rb') as f:
            pages = list(PDFPage.get_pages(f))

            rsrcmgr = PDFResourceManager()
            laparams = LAParams()
            device = PDFPageAggregator(rsrcmgr, laparams=laparams)
            interpreter = PDFPageInterpreter(rsrcmgr, device)

            if len(pages) > 1:
                print('More than one page found')

            bboxes = []
            for page in pages:
                interpreter.process_page(page)
                layout = device.get_result()
                for lobj in layout:
                    if isinstance(lobj, LTTextBox):
                        bboxes.append(lobj.bbox)
            page_height = page.mediabox[3]

        lowest_y = np.array(bboxes)[:, [1, 3]].min()  # coordinates begin from lower left
        return (page_height - lowest_y) / self.PTS_IN_MM  # convert points to mm

    def _write_pdf(self, add_dummy_text=False, **kwargs):
        bs = BeautifulSoup(open(self.input).read(), features="lxml")

        existing_style = bs.find('style', dict(id=self._style_tag_id))  # if added page style before
        if existing_style is not None:  # added this style on prev iteration, remove and add new one
            existing_style.extract()

        dummy_text_el = bs.find('span', dict(id=self._dummy_text))  # find if there is dummy text
        if dummy_text_el is not None:  # remove dummy text element (will add back if necessary)
            dummy_text_el.extract()
        if add_dummy_text:
            dummy_text_el = BeautifulSoup(
                f"""<span style="font-size: 1px;" id="{self._dummy_text}">{self._dummy_text}</span>""",
                features="lxml").span
            bs.body.append(dummy_text_el)

        style = self._get_page_style(**kwargs)
        bs.head.append(style)

        open(self.input, "w").write(str(bs))

        os.system(self.CMD.format(input=self.input, output=self.output))

    def _get_page_style(self, page_width_mm=210, page_height_mm=297, left_mm=15, right_mm=15, top_mm=15, bottom_mm=15):
        return BeautifulSoup(f"""<style id="{self._style_tag_id}">
        @page {{
        size: {page_width_mm}mm {page_height_mm + bottom_mm}mm;
          margin: {top_mm}mm {right_mm}mm 0mm {left_mm}mm;
        }}
        </style>""", features="lxml").style


class CopyFile(Module):
    """Parent class for copying a file"""

    def __init__(self, filepath):
        self._filepath = filepath
        self._ext = filepath.strip().split('.')[-1]  # extract extension

    def run(self):
        shutil.copyfile(self.input, self.output)


class FetchFile(CopyFile):
    """Copies a file from outside of temp folder"""

    @property
    def input(self):
        return self._filepath

    @property
    def output(self):
        return self._get_temp_file(ext=self._ext)


class ReturnFile(CopyFile):
    """Copies a file from temp environment to destination"""

    @property
    def input(self):
        return self._get_temp_file(ext=self._ext)

    @property
    def output(self):
        return self._filepath


class ProcessPDF(Module):
    """To avoid writing input and output format as pdf"""
    INPUT_FORMAT = 'pdf'
    OUTPUT_FORMAT = 'pdf'


class RemovePrinceWatermark(ProcessPDF):
    """
    Bonus module to remove PrinceXML watermark from the top right corner.
    This works only on Unix/Ma, only with installed qpdf and only for A4-width paper.
    Normally, this watermark can easily be removed manually anyway.
    """

    def _run(self):
        try:
            _UncompressPDF().run()
            _RemovePrinceWatermarkBox().run()
            _CompressPDF().run()
        except Exception:  # can't remove watermark, it's fine, generate the pdf anyway
            pass


class _RemovePrinceWatermarkBox(ProcessPDF):
    def _run(self):
        os.system(
            f"""LANG=C LC_ALL=C sed """
            f"""-e "s/555\.2756/-99\.9999/g" """
            f"""-e "s/580\.2756/-99\.9999/g" """
            f"""-e "s/265\.2756/-99\.9999/g" """
            f"""-e "s/515\.2756/-99\.9999/g" """
            f"""-e "s/This document was created with Prince, a great way of getting web content onto paper\./                                                                                     /g" """
            f"""-e "s/www\.princexml\.com/                 /g" """
            f"""-e "s/Prince - Non-commercial License/                               /g" """
            f""" < "{self.input}" > "{self.output}" """
        )


class _UncompressPDF(ProcessPDF):
    def _run(self):
        os.system(f"""qpdf --stream-data=uncompress "{self.input}" "{self.output}" """)


class _CompressPDF(ProcessPDF):
    def _run(self):
        os.system(f"""qpdf --stream-data=compress "{self.input}" "{self.output}" """)


class IPYNBtoMD(Module):
    INPUT_FORMAT = 'ipynb'
    OUTPUT_FORMAT = 'md'

    def _run(self):
        import nbformat
        from nbconvert import MarkdownExporter

        with open(self.input, 'r') as f:
            notebook = nbformat.reads(f.read(), as_version=4)

        (body, resources) = MarkdownExporter().from_notebook_node(notebook)

        with open(self.output, 'w') as f:
            f.write(body)

        for output, content in resources['outputs'].items():
            with open(temp_file(filename=output), 'wb') as f:
                f.write(content)
