#!/bin/tcsh

# make comparable ExportRels files from *.TREF output
# update SAB version

# ExportRels:	Correlation|48834|C48834|PRIMITIVE|NCI_Kind
# TREF:		|Correlation|C48834||NCIPT|| 

awk -F\| '$5=="NCIPT" {print($2"||"$3"|PRIMITIVE|")}' /local/content/MEME/MEME5/inv/sources/NCI_2026_10D/orig/MRCONSO.TREF | sort > ../tmp/nci_concepts.tmp

awk -F\| '{print($2"|"$6"|"$7"|"$1"|")}' /local/content/MEME/MEME5/inv/sources/NCI_2026_10D/orig/MRREL.TREF | sort > ../tmp/nci_rels.tmp

awk -F\| '$5=="isa" {print($7"|"$2)}' /local/content/MEME/MEME5/inv/sources/NCI_2026_10D/orig/MRREL.TREF | sort -u > ../orig/nci_definfconcepts.txt
