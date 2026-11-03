#!/bin/csh -f

echo "run the inversion twice:"
echo "After the first run, grep  for ‘XX-‘ in relationships.src." 
echo "If it appears this is an indication of a new/changed RELA and"
echo "it needs to be added to the RELMAP list in the *cfg file. "

#source env.s

# REMOVE the following two Association refset lines from the SAMEAS refset that
# just merge a description with its concept (instead of merging 2 concepts):
#  0969184a-d05f-4224-b0ae-1df6639b14af 900000000000527005 138210017 83330001
#  8b46ba55-944d-41d4-b730-b5b7e11f3dd4 900000000000527005 505551013 83330001

# ALSO REMOVE the following Association refset lines from the REFERS TO refset
# that refer to a definition rather than a term:
#  a822bb55-9fc4-421e-8318-9cca615f2e9e 900000000000531004 2884896013 410016009
#  91d30eef-90dc-49c3-bae5-e30eb8bb99b6 900000000000531004 3028154015 14560005
#  8f5d9b54-9497-4390-b5fb-a6f9a2705648 900000000000531004 3711689019 14363008
#  2546bb28-5b4f-4a23-8731-b7cc96c8bbbd 900000000000531004 3711690011 14363008
#  6026f2be-4620-42f3-9be0-9e1619a78908 9...00531004 2884821012 331171000009105

echo 'Review invert_rf2.pl lines 1151-1156.'
echo ' these might not be the right lines'
# Steph note:  these lines are from the NLM inversion; changes at NCI mean the line numbers are different
# 1151 refers to the line "The "2016" below is from section 2 of the documentation at"

# MRCONSO from last Meta, for checking which ICD code targets are in Meta
set conso=/local/content/MEME/MEME5/mr/ncim/202608/META/MRCONSO.RRF
#set icd10cm=/local/content/MEME/MEME5/inv/sources/MTH_2025AA/src/classes_atoms.src

#grep ICD9CM $conso |awk -F\| '$12=="ICD9CM"{print $14}' |sort -u >../etc/icd9cm.inmeta
awk -F\| '$12=="ICD10"{print $14}' $conso |sort -u >../etc/icd10.inmeta
awk -F\| '$12=="ICD10CM"{print $14}' $conso |sort -u >../etc/icd10cm.inmeta

./invert_rf2.pl
mv ../src/attributes.src{,.old}
./rmdanglingattrs.pl ../src/attributes.src.old >../src/attributes.src
rm ../src/attributes.src.old

#stys.pl

###COMMENT THIS OUT AFTER MAKING AND EDITING MRDOC.RRF (if running inversion multiple times)
cd ../src
rm -f MRDOC.RRF
$INV_HOME/bin/makeDoc.pl
mv MRDOC.RRF ../tmp
perl -pe '@f = split(/\|/); if ($f[0] eq "RELA" && $f[2] eq "expanded_form" && ($f[3] =~ /^####*$/)){($f[3] = $f[1]) =~ tr/_/ /; substr($f[3],0,1) =~ tr/a-z/A-Z/; $_ = join("|", @f)}' ../tmp/MRDOC.RRF >../src/MRDOC.RRF
grep '|UMLSRELA*|' ../src/attributes.src |awk -F\| '{f1="RELA"; f3="snomedct_rela_mapping"; if ($4 == "UMLSREL") {f1="REL"; f3="snomedct_rel_mapping"}; print f1 "|" $2 "|" f3 "|" $5}' >>../src/MRDOC.RRF
#OBSOLETE: awk -F\| '{print "ATN|" $1 "|expanded_form|" $2}' ../etc/subsetmember.atns >> ../src/MRDOC.RRF
#### END MRDOC section

awk -F\| '$2=="SRC"' classes_atoms.src >../etc/class_src
$INV_HOME/bin/check_sources.pl sources.src >../etc/check_sources.src.out

$INV_HOME/bin/findQaStats.pl
$INV_HOME/bin/srcQa.pl -c ../etc/sct.cfg
