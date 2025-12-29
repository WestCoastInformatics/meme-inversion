#!/bin/csh -f

# joins attributes.src and classes_atoms.src so you can read
# term|default_sty, which makes it easier to review/QA defaults

awk -F\| '{if($3=="SEMANTIC_TYPE") {print($1"|"$4)}}' attributes.src | sort > stys.tmp

join -t\| -j 1 -o 1.1 2.3 2.9 1.2 stys.tmp classes_atoms.src > stys.readable


