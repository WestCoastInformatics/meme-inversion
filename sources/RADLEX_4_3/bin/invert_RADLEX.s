#!/bin/tcsh -f

#make src files; create relas & their inverses in one direction only
#verify relas current
makesrc.pl

#remove duplicate relationships & self-referential rel from relat*src
remove_dup_rels.pl
cp ../tmp/relationships_no_dups_no_self_refs.tmp ../src/relationships.src

#remove duplicates from classes and mergefacts
remove_dup_classes.pl
cp ../tmp/classes_unique.txt ../src/classes_atoms.src
cp ../tmp/mergefacts_new.txt ../src/mergefacts.src

#remove duplicates from attributes
remove_dup_attributes.pl
cp ../tmp/attributes_unique.txt ../src/attributes.src

#create MRDOC.RRF
echo "creating MRDOC.RRF"
$INV_HOME/bin/makeDoc.pl -i ../src

#QA
echo "QA'ing files"
cd ../src
$INV_HOME/bin/srcQa.pl -c ../etc/*cfg
$INV_HOME/bin/findQaStats.pl

echo "Inversion Done - `date`"
