#!/bin/zsh
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
cd $( dirname -- "$0"; )
source venv/bin/activate
out=`python md2longpdf.py $@`
pdf=`echo $out | tail -1 | sed -r -e "s/(PDF generated into )//g"`
open "$pdf"
