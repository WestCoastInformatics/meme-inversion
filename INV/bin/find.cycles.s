#!/bin/csh -f

# script to find cases where A is both an ancestor of B and also a descendent

# get list of ancestors from contexts (treepos.dat)

$INV_HOME/bin/print.ancestors.pl treepos.dat

awk -F\| '$1!=$2' ancestors.tmp > ancestor.list

# Add BTs to ancestor list (for some sources we may want to skip this step)

awk -F\| '($4=="BT") {print($6"|"$3)}' ../relationships.src >> ancestor.list

awk -F\| '($4=="NT") {print($3"|"$6)}' ../relationships.src >> ancestor.list

sort -u ancestor.list -o ancestor.list

# print the ancestor list backwards, i.e. X|ancestor-of|Y -->
# Y|descendent-of|X

# compare the files to see if there is any overlap

awk -F\| '{print($2"|"$1)}' ancestor.list | sort > descendent.list

comm -12 ancestor.list descendent.list > overlap.list

