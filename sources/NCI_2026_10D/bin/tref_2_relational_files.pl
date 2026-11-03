#!/bin/tcsh

#Change *.TREF files to ExportRels formatted files


#owl_concepts (MRCONSO.TREF)
#update SAB in script
echo "Building relational files"
compare_exportrels2tref.s

#get_cn.pl --obsolete step,no concept name avail.

sort ../tmp/nci_concepts.tmp -o ../orig/nci_concepts.txt

#owl_associations (MRREL.TREF)
#get_rel_name.pl --obsolete step 
echo "Building associations file"
get_nci_assoc.pl 
sort -u ../orig/nci_associations.txt -o ../orig/nci_associations.txt


#owl_properties(MRSAT.TREF) (except FULL_SYN, Preferred_Name)
echo "Building property files"
cut -f2,4,5 -d\| ../orig/MRSAT.TREF | sort -u > ../tmp/nci_properties.tmp

get_prop_name.pl
sort -u ../tmp/nci_properties2.tmp -o ../tmp/nci_properties2.tmp


#owl_properties (MRCONSO.TREF) (for FULL_SYN, Preferred_Name)

cut -f2,3,5,6 -d\| ../orig/MRCONSO.TREF >! ../tmp/nci_sy_pt_properties.tmp

get_sy_pt_name.pl

cat ../tmp/nci_properties2.tmp ../tmp/nci_sy_pt_properties2.tmp | sort -t\| +0 -1 +1 -2 > ../orig/nci_properties.txt 


#owl_roles (MRREL.TREF) isa are included in compare_exportrels2tref.s
echo "Building roles file"
get_owl_roles.pl
sort -u ../tmp/nci_roles.tmp -o ../tmp/nci_roles.tmp
assign_rolegroups.pl
delete_dup_roles.pl

#create file of defined concepts
#awk -F\| '($2=="isa"){print($1"|"$3)}' ../tmp/nci_rels.tmp | sort -u > ! ../orig/nci_defconcepts.txt


#flip.rels.pl

#sort -u ex_definfroles.txt -o ex_definfroles.txt
#sort -u owl_definfroles.txt -o owl_definfroles.txt
