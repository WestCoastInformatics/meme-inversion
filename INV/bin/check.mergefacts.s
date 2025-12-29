#!/bin/tcsh -f

# check to make sure all mergefacts are same code
# this is true for strongly coded sources.

sort -t\| +0 -1 classes_atoms.src > me.tmp1

if($#argv == 1)then
cat $1 >> me.tmp1
sort -t\| +0 -1 me.tmp1 -o me.tmp1
endif

echo "different code warning:"
echo ""

sort -t\| +0 -1 mergefacts.src | join -t\| -j1 1 -j2 1 -o 1.1 2.4 1.3 - me.tmp1 | sort -t\| +2 -3 | join -t\| -j1 3 -j2 1 -o 1.1 1.2 1.3 2.4 - me.tmp1 | awk -F\| '$2!=$4'

#/bin/rm -f me.tmp1
