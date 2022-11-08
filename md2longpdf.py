from modules import *
import argparse


def to_pdf(in_filepath, out_filepath_pdf, **kwargs):
    """
    Converts `in_filepath` to PDF created in `out_filepath_pdf`

    :param str in_filepath: Path to the input file, eg: '/Users/breedoon/CS166/Assignment 1.md'
        Must be one of: md, html, ipynb
    :param str out_filepath_pdf: Path to the output file (will be overridden if exists),
        eg: '/Users/breedoon/CS166/PDF/Assignment 1.pdf'
    """

    # Get executables: (1) MdToHTML (2) HTMLtoPDF, etc
    modules = _get_modules_to_execute(in_filepath, out_filepath_pdf, **kwargs)

    for module in modules:
        print(f'Running {type(module).__name__}...')  # e.g.: 'Running MdToHTML...'
        module.run()

    print(f'PDF generated into {out_filepath_pdf}')


def _preprocess_inputs(in_file, out_path):
    # Get exact
    # Parse out location of md file and its name
    dir_path, filename, _ = _get_path_name_ext(in_file)

    if out_path is None or len(out_path.strip()) == 0:  # output path is not given, put it next to the input file
        out_path = dir_path
    else:
        out_path = os.path.realpath(out_path.strip()) + '/'  # ensure has / at the end

    return out_path + filename + '.pdf'


def _get_path_name_ext(filepath: str):
    """Parses out path, filename and extension of the given file"""
    dir_path, f1, f2, ext = re.compile(r'(?:(.*[\/])(.+)|^(.+))\.((?:md|html|ipynb))').findall(filepath)[0]
    filename = f1 + f2  # alternative groups, one will be empty one with filename
    return dir_path, filename, ext


def _get_modules_to_execute(in_filepath, out_pdf, **kwargs):
    # For now, use given file to convert to PDF (if .md will be sorted out later)
    kwargs['workdir'], kwargs['title'], ext = _get_path_name_ext(in_filepath)

    modules = [FetchFile(filepath=in_filepath, **kwargs)]

    # IPYNB -> MD
    if ext == 'ipynb':
        modules += [IPYNBtoMD(**kwargs)]
        kwargs['workdir'] = temp_dir  # path to output images, if converting from ipynb, they will be in the temp folder

    # MD -> HTML
    if ext in ('ipynb', 'md'):  # given MD, need to preprocess MD to be HTML
        modules += [
            MdToMdWithoutWikilinks(**kwargs),
            SlugifyMdSectionLinks(**kwargs),
            MdToHTML(**kwargs),
        ]

    # HTML -> PDF
    modules += [
        HTMLtoPDF(**kwargs),
        RemovePrinceWatermark(**kwargs),
        ReturnFile(filepath=out_pdf, **kwargs)
    ]

    return modules


def main(in_file, out_path, **kwargs):
    out_pdf = _preprocess_inputs(in_file, out_path)
    to_pdf(in_file, out_pdf, **kwargs)


def _get_args_from_input():
    in_file = input('Enter location of your md/html/ipynb file (e.g.: /Users/breedoon/CS166/Assignment 1.md)\n')
    out_path = input('Enter location to store the produced PDF file (e.g.: /Users/breedoon/CS166/PDF/)\n'
                     'or leave blank to generate in the same folder\n')

    return in_file, out_path


def _get_args_from_command():
    parser = argparse.ArgumentParser(description='Process some integers.', argument_default='')
    parser.add_argument('--input-file', '-i', dest='in_file', required=False,
                        help='absolute path to the md/html/ipynb file')
    parser.add_argument('--output-path', '-o', dest='out_path', required=False,
                        help='absolute path to directory where to put the produced PDF file')
    args, raw_kwargs = parser.parse_known_args()
    kwargs = {k.strip('-'): v for k, v in map(lambda x: x.split("=")[:2], raw_kwargs)}
    return args.in_file, args.out_path, kwargs


if __name__ == '__main__':
    in_file, out_path, kwargs = _get_args_from_command()

    if in_file is None:  # args weren't passed via command line, ask to input
        in_file, out_path = _get_args_from_input()

    main(in_file, out_path, **kwargs)
