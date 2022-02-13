# MDtoLongPDF

**Table of Contents**

- [About The Project](#about-the-project)
- [Getting Started](#getting-started)
	- [Prerequisites](#prerequisites)
	- [Installation](#installation)
- [Usage](#usage)
    -  [Default Parameters](#default-parameters)
- [Known Issues](#known-issues)
	- [Wikilinks](#wikilinks)

## About The Project  

Pagination in PDF sucks. The vast majority of PDF documents nowadays were never intended to be nor will ever be printed. Yet, page breaks continue to split sections, break tables, move figures around leaving huge chunks of empty space, etc, all to serve a function that is no longer needed. 

So, this script aims to provide a workaround when converting from inherently unpaginated formats, namely, Markdown and HTML into PDF by putting all of their rendered content onto a single very long PDF page. See [README.pdf](resources/README.pdf) for an example.

## Getting Started  
  
### Prerequisites  
  
* Python 3.x (tested on Python 3.9.7)
    * `numpy`
    * `pdfminer`
* `pandoc` for md -> html
* `Prince XML` for html -> pdf
  
### Installation  
  
_Below is an example of how you can instruct your audience on installing and setting up your app. This template doesn't rely on any external dependencies or services._  
  
1. Install [`pandoc`](https://pandoc.org/installing.html), [`Prince XML`](https://www.princexml.com/), and [`qpdf`](https://formulae.brew.sh/formula/qpdf)
2. Clone the repo  
    ```sh  
    git clone https://github.com/Breedoon/MDtoLongPDF.git
    ```  
3. Install `requirements.txt`:
   ```sh  
    pip install -r requirements.txt
   ```  

## Usage  
  
1. To use the script, run:

```sh
python md2longpdf.py
```

2. Then you will be prompted to enter path to you `.md` or `.html` file, for example:

```
Enter location of your md/html file (e.g.: /Users/breedoon/Drive/CS166/Assignment 1.md)
>? README.md
```

3. Then you will be asked where the PDF should be generated (or leave empty to use the same folder and name as the input file):

```
Paste path to the output pdf file (will be overridden if exists)
or leave blank to generate in the same folder with the same name
>? resources/README.pdf
```
4. Done! Find your PDF: [resources/README.pdf](resources/README.pdf)

### Default Parameters

The stylesheet used to generate HTML is [resources/pandoc.css](resources/pandoc.css) based on [this stylesheet](https://gist.github.com/killercup/5917178). The simplest way to change scale is to modify `html { font-size: 120%; ... }` and `.math {  zoom: 120%; }`.

The default PDF margins used are 15mm from each side, and can be changed in [modules.py](modules.py) in the parameters of `HTMLtoPDF` class.

## Known Issues

### Wikilinks

At the moment of writing, pandoc still does not have support for markdown \[\[wikilinks\]\] so I had to write a short script of my own to preprocess my markdown files containing wikilinks, which might not work in some edge cases (e.g., double \[\[\]\] inside of code blocks, etc), though it has worked well for most of my use cases. 

`pandoc`  will likely soon [implement wikilinks](https://github.com/jgm/pandoc/issues/2923), after which the entire `MdToMdWithoutWikilinks` part of the script will be unnecessary and the pandoc command will need to be modified to include `pandoc ... -f markdown+wikilinks_title_after_pipe ...`.
