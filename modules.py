import os

import numpy as np
from pdfminer.layout import LAParams, LTTextBox
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator


class Module:
    def __init__(self, in_filepath, out_filepath):
        self.input = in_filepath
        self.output = out_filepath

        # Delete output file if already exists
        if os.path.exists(self.output):
            os.remove(self.output)

    def run(self):
        pass


class MdToMdWithoutWikilinks(Module):
    def run(self):
        import re

        with open(self.input, 'r') as f:
            md_data = f.read()

        wikilinks_pattern = re.compile(r'\[\[\s*(?P<target>[^][|]+?)(\s*\|\s*(?P<label>[^][]+))?\s*\]\]')
        section_pattern = re.compile(r'^((?:.{0}|.*[^\\]))\#(.+)')
        new_md_data = ''
        prev_i = 0
        for match in wikilinks_pattern.finditer(md_data):
            target, label = match.group(1, 3)
            if label is None:
                label = target
            sections = section_pattern.findall(target)
            if len(sections) != 0:  # referencing a section in this link
                file, section = sections[0]
                section = re.compile(r'\ +').sub('-', re.compile(r'[^a-zA-Z\ ]').sub(' ', section)).lower()
                target = file + '#' + section
            new_md_data = new_md_data + md_data[prev_i: match.span()[0]] + f"[{label}]({target})"
            prev_i = match.span()[1]

        new_md_data = new_md_data + md_data[prev_i:]

        with open(self.output, 'w+') as f:
            f.write(new_md_data)


class MdToHTML(Module):
    def __init__(self, in_filepath, out_filepath, title=None, workdir=None):
        """
        :param title: Title to be given to the HTML file
        :param workdir: directory from which the referenced files can be accessed (images, etc)
        """
        super().__init__(in_filepath, out_filepath)
        self.title = title
        self.wdir = workdir

    def run(self):
        cmd = f"""pandoc --css=resources/pandoc.css --self-contained --webtex=https://latex.codecogs.com/svg.latex?""" \
              f""" -f markdown -t html "{self.input}" -o "{self.output}" """

        # if given title will put it onto the HTML so better not
        # if self.title is not None:
        #     cmd += f"""--metadata title="{self.title}" """
        if self.title is not None:
            cmd += f"""--resource-path="{self.wdir}" """

        os.system(cmd)


class HTMLtoPDF(Module):
    """
    Step 1:
        generate a PDF with maximum possible page length (10m+) to fit all the content
        to calculate how much it can be trimmed
    Step 2:
        read the max PDF generated on the previous step ant find where the lowest content item is;
        then generate a new PDF with paper height exactly to fit the lowest item + margin
    """

    # margins and dimensions of paper (margins must be in mm)
    DEFAULT_PARAMS = dict(ml='15mm', mr='15mm', mt='15mm', mb='15mm', page_width='210mm', page_height='297mm')
    CMD = """wkhtmltopdf -L {ml} -R {mr} -T {mt} -B {mb} --enable-javascript --no-stop-slow-scripts --page-width {page_width} --page-height {page_height} --enable-local-file-access "{input}" "{output}" """
    PTS_IN_MM = 1 / 25.4 * 72

    def run(self):
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
        params = self.DEFAULT_PARAMS.copy()
        params['mb'] = '0mm'  # remove bottom margin to make a super long pdf
        params['page_height'] = f'{page_height_m}m'

        os.system(self.CMD.format(**params, input=self.input, output=self.output))

    def _make_fit_pdf(self, page_height_mm):
        params = self.DEFAULT_PARAMS.copy()
        params['page_height'] = f'{page_height_mm}mm'

        os.system(self.CMD.format(**params, input=self.input, output=self.output))

    def _calculate_new_page_height_mm(self):
        lowest_y = self._get_lowest_y_mm()
        new_height = np.ceil(lowest_y) + float(self.DEFAULT_PARAMS['mb'][:-2])
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
        return (page_height - lowest_y) / self.PTS_IN_MM  # convert points to m


class RemoveBlankPDFPages(Module):
    """Removes all pages from the PDF except for page 1 (to remove accidentally created blank second page"""

    def run(self):
        os.system(f"""qpdf --pages "{self.input}" 1  -- "{self.input}" "{self.output}" """)
