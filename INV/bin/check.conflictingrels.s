#!/bin/tcsh

#1/13/2011 SSL
# Finds conflicting RELAs between the same pair of concepts.
# Conflicting RELAs not necessarily inverses of each other.

######update version########

set curTREF=$1
set curfiles=$2

############################

awk -F\| '{print($2"_"$6"|"$5)}' $curTREF/MRREL.TREF | sort -t\| -k1,1 >! $curfiles/rels.tmp

#Disease_May_Have_Finding + Disease_Has_Finding
#Diseases_May_Have_Finding + Disease_Excludes_Finding
#Disease_Has_Finding + Disease_Excludes_Finding

grep Disease_Has_Finding $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_May_Have_Finding $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

grep Disease_Excludes_Finding $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dexf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp
join $curfiles/dmhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp
join $curfiles/dhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp

join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr1.txt

#Disease_Excludes_Abnormal_Cell
#Disease_Has_Abnormal_Cell
#Disease_May_Have_Abnormal_Cell

grep Disease_Excludes_Abnormal_Cell $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_Has_Abnormal_Cell $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

grep Disease_May_Have_Abnormal_Cell $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dexf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp
join $curfiles/dmhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp
join $curfiles/dhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp
join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr2.txt

#Disease_Excludes_Normal_Cell_Origin
#Disease_Has_Normal_Cell_Origin
#Disease_May_Have_Normal_Cell_Origin

grep Disease_Excludes_Normal_Cell_Origin $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_Has_Normal_Cell_Origin $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

grep Disease_May_Have_Normal_Cell_Origin $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dexf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp
join $curfiles/dmhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp
join $curfiles/dhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp
join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr3.txt

#Disease_Excludes_Cytogenetic_Abnormality
#Disease_Has_Cytogenetic_Abnormality
#Disease_May_Have_Cytogenetic_Abnormality

grep Disease_Excludes_Cytogenetic_Abnormality $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_Has_Cytogenetic_Abnormality $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

grep Disease_May_Have_Cytogenetic_Abnormality $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dexf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp
join $curfiles/dmhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp
join $curfiles/dhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp
join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr4.txt

# Disease_Excludes_Molecular_Abnormality
# Disease_Has_Molecular_Abnormality
# Disease_May_Have_Molecular_Abnormality

grep Disease_Excludes_Molecular_Abnormality $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_Has_Molecular_Abnormality $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

grep Disease_May_Have_Molecular_Abnormality $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dexf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp
join $curfiles/dmhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp
join $curfiles/dhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp
join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr5.txt

#Disease_Excludes_Normal_Tissue_Origin
#Disease_May_Have_Normal_Tissue_Origin
#Disease_Has_Normal_Tissue_Origin

grep Disease_Excludes_Normal_Tissue_Origin $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_May_Have_Normal_Tissue_Origin $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

grep Disease_Has_Normal_Tissue_Origin $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dexf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp
join $curfiles/dmhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp
join $curfiles/dhf.tmp $curfiles/dexf.tmp >> $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp
join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr6.txt


#Disease_Excludes_Primary_Anatomic_Site
#Disease_Has_Primary_Anatomic_Site

grep Disease_Excludes_Primary_Anatomic_Site $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_Has_Primary_Anatomic_Site $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp
join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr7.txt

#Allele_Associated_With_Disease
#Allele_Not_Associated_With_Disease

grep Allele_Associated_With_Disease $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Allele_Not_Associated_With_Disease $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp
join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr8.txt


#Disease_Has_Associated_Anatomic_Site
#Disease_Has_Metastatic_Anatomic_Site

#grep Disease_Has_Associated_Anatomic_Site $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

#grep Disease_Has_Metastatic_Anatomic_Site $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

#join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp

#sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

#grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

#grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

#awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp

#join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr9.txt


#Disease_Has_Associated_Disease
#Disease_May_Have_Associated_Disease

grep Disease_Has_Associated_Disease $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dhf.tmp

grep Disease_May_Have_Associated_Disease $curTREF/MRREL.TREF | cut -f2,6 -d\| | sort -u >! $curfiles/dmhf.tmp

join $curfiles/dhf.tmp $curfiles/dmhf.tmp >! $curfiles/conflicts1.tmp

sort -u $curfiles/conflicts1.tmp | sort -t\| -k1,1 >! $curfiles/conflicts2.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 1 -o 1.3,1.2,2.2 - $curfiles/conflicts2.tmp | sort -t\| -k3,3 >! $curfiles/conflicts3.tmp

grep NCIPT $curTREF/MRCONSO.TREF | sort -t\| -k3,3 | join -t\| -1 3 -2 3 -o 2.1,2.2,2.3,1.2 - $curfiles/conflicts3.tmp >! $curfiles/conflicts4.tmp

awk -F\| '{print($1"_"$3"|"$1"|"$2"|"$3"|"$4)}' $curfiles/conflicts4.tmp | sort -t\| -k1,1 >! $curfiles/conflicts5.tmp

join -t\| -1 1 -2 1 -o 2.2,2.3,1.2,2.4,2.5 $curfiles/rels.tmp $curfiles/conflicts5.tmp >! $curfiles/disr10.txt

