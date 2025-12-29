#!/bin/csh -f

# prints the string along with the rel
# read this right to left

cat classes_atoms.src > classes.reltmp
if($#argv == 1)then
cat $1 >> classes.reltmp
endif
sort -t\| +0 -1 classes.reltmp -o classes.reltmp

sort -t\| +2 -3 relationships.src | join -t\| -j1 3 -j2 1 -o 1.3 2.8 1.4 1.5 1.6 - classes.reltmp > rels.tmp



sort -t\| +4 -5 rels.tmp | join -t\| -j1 5 -j2 1 -o 1.1 1.2 1.3 1.4 1.5 2.8 - classes.reltmp > rels.tocheck

/bin/rm -f rels.tmp classes.reltmp
