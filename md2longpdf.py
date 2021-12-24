import os

from modules import MdToMdWithoutWikilinks, MdToHTML, HTMLtoPDF, RemoveBlankPDFPages

temp_dir = 'temp'

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

temp_files = {
    'md': f'{temp_dir}/temp.md',
    'html': f'{temp_dir}/temp.html',
    'htex': f'{temp_dir}/temp.htex',
    'pdf': f'{temp_dir}/temp.pdf',
}


def main(in_filepath, out_pdf=None):
    # Parse out location of md file and its name
    dir_path, filename, _ = _get_path_name_ext(in_filepath)

    if out_pdf is None:  # output pdf is not given, put it next to the input file
        out_pdf = dir_path + filename + '.pdf'

    # Get executables: (1) MdToHTML (2) HTMLtoPDF, etc
    modules = _get_modules_to_execute(in_filepath, out_pdf)

    try:

        for module in modules:
            print(f'Running {type(module).__name__}...')  # e.g.: 'Running MdToHTML...'
            module.run()

        print(f'PDF generated into {out_pdf}')

    finally:
        # Delete temp files
        for ext in temp_files:
            if os.path.exists(temp_files[ext]):
                os.remove(temp_files[ext])


def _get_path_name_ext(filepath: str):
    """Parses out path, filename and extension of the given file"""
    import re
    dir_path, f1, f2, ext = re.compile(r'(?:(.*[\/])(.+)|^(.+))\.((?:md|html))').findall(filepath)[0]
    filename = f1 + f2  # alternative groups, one will be empty one with filename
    return dir_path, filename, ext


def _get_modules_to_execute(in_filepath, out_pdf):
    # For now, use given file to convert to PDF (if .md will be sorted out later)
    html = in_filepath
    dir_path, filename, ext = _get_path_name_ext(in_filepath)

    modules = []

    if ext == 'md':  # given MD, need to preprocess MD to be HTML
        modules += [
            MdToMdWithoutWikilinks(in_filepath, temp_files['md']),
            MdToHTML(temp_files['md'], temp_files['html'], title=filename, workdir=dir_path),
        ]
        # Make a temp HTML file our target file for PDF conversion
        html = temp_files['html']

    modules += [
        HTMLtoPDF(html, temp_files['pdf']),
        RemoveBlankPDFPages(temp_files['pdf'], out_pdf),
    ]

    return modules


if __name__ == '__main__':
    in_md = input('Enter location of your md/html file (e.g.: /Users/breedoon/Drive/CS166/Assignment 1.md)\n')
    out_pdf = input('Enter location to the output pdf file (will be overridden if exists)\n'
                    'or leave blank to generate in the same folder with the same name\n')
    if len(out_pdf.strip()) == 0:  # blank
        out_pdf = None

    main(in_md, out_pdf)
