#!/bin/tcsh

alias cutp 'cut -d\|'
alias joinp 'join -t\|'
alias sort '/bin/sort'
alias sortp 'sort -t\|'
alias perl '/usr/bin/perl'
alias tallyfield '$INV_HOME/bin/tallyfield.pl'
#alias tallyfield '$INV_HOME_OLD/bin/tallyfield.pl'
alias cat /bin/cat
alias mv /bin/mv
alias cp /bin/cp
alias wcl 'wc -l'
alias fawk 'awk -F\|'


# 1) create new directories for your data and link the .owl and .txt (output of exportrels)to the Orig-<ver> directory:

#    Orig-<ver>   (e.g. Orig-1601D; ln -s /local/content/MEME/MEME5/inv/sources/NCI_2023_11D/orig Orig-2311D)
#    <ver>        (e.g. 0510E; mkdir 0510E)

# 2) create the config_associations, config_properties, and config_roles files in the inversion's orig directory
#	a) cp orig/fromprovider/NCI<ver>.txt ../orig/config_associations
#	b) cp orig/fromprovider/NCI<ver>.txt ../orig/config_properties
#	c) cp orig/fromprovider/NCI<ver>.txt ../orig/config_roles
#	d) edit each file so that it contains the appropriate data. 
#	'config_associations' only contains the association data, 
#	'config_properties' only contains the properties data, etc.

# 3) update version in check.conflictingrels.s

# update the following variables.  Normally, this means
# setting the "prev*" values to what the "cur*" values were
# last time you ran the script, and then updating the "cur*" values
# to the directories you just created

# curdir/prevdir are the directories where the Original (.xml & .txt files) live
# curfiles/prevfiles are the directories where the interim files live

set ver = "2610D"
#set ver = "0606D-Q"
set prev = "2609D"

set curdir="Orig-$ver"
set curfiles=$ver
set curTREF="Orig-$ver"
#set curTREF="TREF-$ver"

set tmpdir="/local/content/MEME/MEME5/inv/sources/NCI_2026_10D/tmp"
set prevtmpdir="/local/content/MEME/MEME5/inv/sources/NCI_2026_09D/tmp"

set usr="nci"

set rpt="checklist-report-$ver.txt"
set newonly="checklist-report-$ver-newonly.txt"

set validstys=$INV_HOME/etc/valid_stys
#set validstys=$INV_HOME_OLD/etc/valid_stys

set prevdir="Orig-$prev"
set prevfiles=$prev
set prevusr="nci"
#set prevusr="MSDNCI"
#set prevusr="memeqa"

echo "ver: $ver"
echo ""

\rm $rpt
\rm $newonly

touch $rpt
touch $newonly

#awk -F\| '($2=="Preferred_Name"){print $3}' $curdir/$usr\_properties.txt >! \
#$curfiles/prefname.dups.tmp

echo "Test 1 - Preferred name not unique to single concept"
echo "1.  Preferred name not unique to single concept" >> $rpt
echo "1.  Preferred name not unique to single concept (new since last version)" >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "Preferred_Name property duplicates" >> $rpt

#fawk '($2=="Preferred_Name"){print $1"|"$2"|"$3}' $curdir/$usr\_properties.txt |\
#sortp +2 -3 >! $curfiles/prefnames.all

#cutp -f3 $curfiles/prefnames.all | sort | uniq -d |\
#joinp -j1 3 $curfiles/prefnames.all -  |\
#fawk '{print $2"|"$3"|"$1}' >! $curfiles/prefname.dups.txt

get_PrefName_dups.pl $curdir/$usr\_properties.txt |\
sort -u | sortp +1 -2 >! $curfiles/prefname.dups.txt

get_PrefName_dups.pl $prevdir/$prevusr\_properties.txt |\
sort -u | sortp +1 -2 >! $prevfiles/prefname.dups.txt

cat $curfiles/prefname.dups.txt | sort -u | sortp +1 -2 >> $rpt


#awk -F\| '$2=="Preferred_Name"' $curdir/$usr\_properties.txt |\
#sort -t\| +2 -3 |\
#join -t\| -j1 3 -j2 1 -o 1.1 1.2 1.3 - $curfiles/prefname.dups.tmp \
#>! $curfiles/prefname.dups.txt

# old style 
# grep 'FULL_SYN.*<term-group>PT</term-group><term-source>NCI</term-source>' \
# $curdir/$usr\_properties.txt \
# | cut -f3 -d\| | sort | uniq -d > $curfiles/dupncipts.tmp

#fawk '($2=="Preferred_Name")' $curdir/$usr\_properties.txt | sortp +2 -3 \
#>! pref_name.all.tmp

# not correct
#joinp -j1 3 -o 1.1 1.2 1.3 $curfiles/pref_name.all.tmp $curfiles/dup_pref_name.tmp \
#> $curfiles/fspt.dups.txt

#fawk '($2=="FULL_SYN"){print $1$4}' $curdir/$usr\_properties.txt

echo "Preferred_Name property duplicates"
echo "" >> $rpt
echo "Preferred_Name property duplicates (new only)" >> $newonly
echo "" >> $rpt
echo "" >> $newonly

echo `comm -23 $curfiles/prefname.dups.txt $prevfiles/prefname.dups.txt | wc -l` >> $newonly
comm -23 $curfiles/prefname.dups.txt $prevfiles/prefname.dups.txt >> $newonly

# these are FULL_SYN records where there are multiple NCI/PTs
# 
#echo "1a. FULL_SYN NCI/PT duplicates across concepts"
#echo "1a. FULL_SYN NCI/PT duplicates across concepts" >> $rpt
#echo "" >> $rpt

# fawk '($2=="FULL_SYN"){split($4,q,"\\");print $1"|"$3"|"q[2]"|"q[4]}' \
# $curdir/$usr\_properties.txt | sort | uniq -d >! fspt.dups.txt |\
# sort | uniq -d >! $curfiles/nci_FS-PT_dup.txt

#wc -l $curfiles/nci_FS-PT_dup.txt >> $rpt

get_FULL_SYN-PT_dups.pl $curdir/$usr\_properties.txt |\
sortp +1 -2 >! $curfiles/fspt.dups.txt 

cat $curfiles/fspt.dups.txt >> $rpt

echo "" >> $rpt 

#cat $curfiles/nci_FS-PT_dup.txt >> $rpt

echo "" >> $rpt
echo "" >> $rpt

sort $curfiles/prefname.dups.txt -o $curfiles/prefname.dups.txt
sort $prevfiles/prefname.dups.txt -o $prevfiles/prefname.dups.txt

comm -23 $curfiles/prefname.dups.txt $prevfiles/prefname.dups.txt | sort -t\| +2 -3 > $curfiles/newprefnamedups.txt

sort $curfiles/fspt.dups.txt -o $curfiles/fspt.dups.txt
sort $prevfiles/fspt.dups.txt -o $prevfiles/fspt.dups.txt
comm -23 $curfiles/fspt.dups.txt $prevfiles/fspt.dups.txt | sort -t\| +2 -3 > $curfiles/newfspt.dups.txt

wc -l $curfiles/newprefnamedups.txt >> $newonly
echo "" >> $newonly
cat $curfiles/newprefnamedups.txt >> $newonly
echo "" >> $newonly

echo "FULL_SYN NCI/PT duplicates (new only)"
echo "FULL_SYN NCI/PT duplicates (new only)" >> $newonly
echo "" >> $newonly
wc -l  $curfiles/newfspt.dups.txt >> $newonly
echo "" >> $newonly
cat  $curfiles/newfspt.dups.txt >> $newonly

echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt
echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "Test 2 "
echo "Duplicate roles"
echo "2a.  Duplicate roles within concepts" >> $rpt
echo "2a.  Duplicate roles within concepts" >> $newonly

echo "" >> $rpt
echo "" >> $newonly

sort $tmpdir/nci_roles3.tmp | uniq -d | wc -l >> $rpt
#sort $curdir/$usr\_defroles.txt | uniq -d | wc -l >> $rpt
#sort $curdir/$usr\_defroles.txt | uniq -d | wc -l >> $newonly

echo "" >> $rpt
echo "" >> $newonly

sort $tmpdir/nci_roles3.tmp | uniq -d >> $rpt
#sort $curdir/$usr\_defroles.txt | uniq -d >> $rpt
#sort $curdir/$usr\_defroles.txt | uniq -d >> $newonly
#
#echo "" >> $rpt
#echo "" >> $newonly
#
#echo "2b.  Duplicate properties within concepts (includes definitions, stys, etc.)" >> $rpt
#echo "2b.  Duplicate properties within concepts (includes definitions, stys, etc.)" >> $newonly
#
#echo "" >> $rpt
#echo "" >> $newonly
#
#sort $curdir/$usr\_properties.txt | uniq -d | wc -l >> $rpt
#sort $curdir/$usr\_properties.txt | uniq -d | wc -l >> $newonly
#
#echo "" >> $rpt
#echo "" >> $newonly
#
#sort $curdir/$usr\_properties.txt | uniq -d >> $rpt
#sort $curdir/$usr\_properties.txt | uniq -d >> $newonly
#
#echo "" >> $rpt
#echo "" >> $rpt
#
#echo "----------------------------------------------------------" >> $rpt
#echo "" >> $rpt
#
#echo "" >> $newonly
#echo "" >> $newonly
#
echo "----------------------------------------------------------" >> $newonly

echo "3.  Structure/format of fields is non-standard" >> $rpt
echo "3.  Structure/format of fields is non-standard" >> $newonly

echo "" >> $rpt
echo "NOT YET CHECKED" >> $rpt
echo "" >> $rpt

echo "" >> $newonly
echo "NOT YET CHECKED" >> $newonly
echo "" >> $newonly

echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "4.  Invalid semantic types" >> $rpt
echo "4.  Invalid semantic types" >> $newonly

echo "" >> $rpt
echo "" >> $newonly

fawk '$2=="Semantic_Type" {print($3)}'  $curdir/$usr\_properties.txt \
| sort -u >! stys.tmp

sort $validstys >! validstys.sorted
join -t\| -j1 1 -j2 1 -v 1 stys.tmp validstys.sorted >> $rpt
join -t\| -j1 1 -j2 1 -v 1 stys.tmp validstys.sorted >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "5.  Verify exactly one NCI PT per concept" >> $rpt
echo "5.  Verify exactly one NCI PT per concept (new only)" >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "" >> $rpt
echo "" >> $rpt

echo "" >> $newonly
echo "" >> $newonly

echo "Calling check.pts_qual"
check.pts_qual.pl $ver $curdir/$usr\_properties.txt

echo "5a. Multiple NCI/PT in FULL_SYN:" >> $rpt
echo "5a. Multiple NCI/PT in FULL_SYN (new only):" >> $newonly

echo "" >> $rpt
echo "" >> $newonly

wc -l $curfiles/duppts.tmp >> $rpt

echo "" >> $rpt
echo "" >> $newonly

cat $curfiles/duppts.tmp >> $rpt

sort $curfiles/duppts.tmp -o $curfiles/duppts.tmp
sort $prevfiles/duppts.tmp -o $prevfiles/duppts.tmp

comm -23  $curfiles/duppts.tmp $prevfiles/duppts.tmp > $curfiles/newonlyduppts.tmp
wc -l $curfiles/newonlyduppts.tmp >> $newonly

cat $curfiles/newonlyduppts.tmp >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "5b. Duplicate Preferred_Name Properties within a concepts" >> $rpt
echo "" >> $rpt

wc -l $curfiles/duppref.tmp >> $rpt
echo "" >> $rpt
cat $curfiles/duppref.tmp >> $rpt
echo "" >> $rpt


echo "5b. Duplicate Preferred_Name Properties (new only)" >> $newonly
echo "" >> $newonly

sort $curfiles/duppref.tmp -o $curfiles/duppref.tmp
sort $prevfiles/duppref.tmp -o $prevfiles/duppref.tmp
comm -23  $curfiles/duppref.tmp $prevfiles/duppref.tmp > $curfiles/newonlyduppref.tmp

wc -l $curfiles/newonlyduppref.tmp >> $newonly
echo "" >> $newonly
cat $curfiles/newonlyduppref.tmp >> $newonly
echo "" >> $newonly

#echo "5c. Mismatch between NCI/PT in FULL_SYN and Preferred_Name" >> $rpt

#echo "" >> $rpt
#cat $curfiles/mismatch.tmp >> $rpt
#echo "" >> $rpt

#echo "5c. Mismatch between NCI/PT in FULL_SYN and Preferred_Name (all)" >> $newonly

#echo "" >> $newonly
#cat $curfiles/mismatch.tmp >> $newonly
#echo "" >> $newonly

#echo "" >> $newonly

#echo "" >> $newonly

#echo "Test 5d"
#echo "5d. No NCI/PT in FULL_SYN" >> $rpt
#echo "" >> $rpt
#wc -l $curfiles/nofullsyn.tmp >> $rpt
#echo "" >> $rpt
#cat $curfiles/nofullsyn.tmp >> $rpt
#echo "" >> $rpt

#sort -u $curfiles/nofullsyn.tmp -o $curfiles/nofullsyn.tmp
#sort -u $prevfiles/nofullsyn.tmp -o $prevfiles/nofullsyn.tmp

#comm -23 $curfiles/nofullsyn.tmp $prevfiles/nofullsyn.tmp > $curfiles/newnofullsyn.tmp

#echo "5d. No NCI/PT in FULL_SYN (new only)" >> $newonly
#echo "" >> $newonly
#wc -l $curfiles/newnofullsyn.tmp >> $newonly
#echo "" >> $newonly
#cat $curfiles/newnofullsyn.tmp >> $newonly
echo "" >> $newonly

echo "5e. No Preferred_Name property or problem with value " >> $rpt
echo "" >> $rpt
wc -l $curfiles/noprefname.tmp >> $rpt
echo "" >> $rpt
cat $curfiles/noprefname.tmp >> $rpt
echo "" >> $rpt

echo "5e. No Preferred_Name property or problem with value (all)" >> $newonly
echo "" >> $newonly
wc -l $curfiles/noprefname.tmp >> $newonly
echo "" >> $newonly
cat $curfiles/noprefname.tmp >> $newonly
echo "" >> $newonly

echo "----------------------------------------------------------" >> $rpt

echo "" >> $rpt

echo "----------------------------------------------------------" >> $newonly

echo "" >> $newonly

echo "6. New Roles:  Need rel, rela, inverse rela" >> $rpt
echo "6. New Roles:  Need rel, rela, inverse rela" >> $newonly

cut -f3 -d\| $tmpdir/nci_roles3.tmp >! curroles.tmp
#cut -f3 -d\| $curdir/$usr\_defroles.txt > curroles.tmp
#cut -f3 -d\| $curdir/$usr\_infroles.txt >> curroles.tmp
sort -u curroles.tmp -o curroles.tmp

cut -f3 -d\| $prevtmpdir/nci_roles3.tmp >! prevroles.tmp
#cut -f3 -d\| $prevdir/$prevusr\_defroles.txt > prevroles.tmp
#cut -f3 -d\| $prevdir/$prevusr\_infroles.txt >> prevroles.tmp
sort -u prevroles.tmp -o prevroles.tmp

echo "new roles:" >> $rpt
echo "new roles:" >> $newonly

join curroles.tmp prevroles.tmp -v 1 >> $rpt
join curroles.tmp prevroles.tmp -v 1 >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "disappearing roles" >> $rpt
join curroles.tmp prevroles.tmp -v 2 >> $rpt

echo "disappearing roles" >> $newonly
join curroles.tmp prevroles.tmp -v 2 >> $newonly


echo "" >> $rpt
echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "" >> $newonly
echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "7.  New Properties:  Need ATN" >> $rpt
echo "" >> $rpt
echo "7.  New Properties:  Need ATN" >> $newonly
echo "" >> $newonly

#longcut.pl '$2' $curdir/$usr\_properties.txt | sort -u > curprops.tmp
#longcut.pl '$2' $prevdir/$prevusr\_properties.txt | sort -u > prevprops.tmp
cutp -f2 -d\| $curdir/$usr\_properties.txt | sort -u >! curprops.tmp
cutp -f2 -d\| $prevdir/$prevusr\_properties.txt | sort -u >! prevprops.tmp

echo "new properties:" >> $rpt
join curprops.tmp prevprops.tmp -v 1 >> $rpt
echo "new properties:" >> $newonly
join curprops.tmp prevprops.tmp -v 1 >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "disapearing properties" >> $rpt
join curprops.tmp prevprops.tmp -v 2 >> $rpt

echo "" >> $rpt
echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "disapearing properties" >> $newonly
join curprops.tmp prevprops.tmp -v 2 >> $newonly

echo "Test 8"
echo "" >> $newonly
echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "8.  New subsources; need citation, SAB, precedence, etc." >> $rpt
echo "8.  New subsources; need citation, SAB, precedence, etc." >> $newonly

echo "" >> $rpt
echo "" >> $newonly

get-prevsubsources-qual.pl $prevdir/$prevusr\_properties.txt

echo "1"

# output is now sort -u already
#sort -u prevsubsources.tmp -o prevsubsources.tmp
sort -u subsources.tmp -o subsources.tmp

echo "2"

join subsources.tmp prevsubsources.tmp -v 1>> $rpt
join subsources.tmp prevsubsources.tmp -v 1>> $newonly

echo "3"

echo "" >> $rpt

echo "4"

echo "Disappearing subsources" >> $rpt

echo "5"
join subsources.tmp prevsubsources.tmp -v 2>> $rpt

echo "6"

echo "" >> $rpt
echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "" >> $newonly
echo "Disappearing subsources" >> $newonly
join subsources.tmp prevsubsources.tmp -v 2>> $newonly

echo "" >> $newonly
echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "9.  Which subsources are updated?  NCI to provide" >> $rpt
echo "" >> $rpt
echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "9.  Which subsources are updated?  NCI to provide" >> $newonly
echo "" >> $newonly
echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "10. Pipe characters in data" >> $rpt
echo "In TDE, select all properties except "OLD_ROLE" and search for *|* to find these" >> $rpt
echo "" >> $rpt

#grep '|' $curdir/*xml >> $rpt

awk -F\| '$2!="OLD_ROLE" && NF!=4' $curdir/$usr\_properties.txt >> $rpt

echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "10. Pipe characters in data" >> $newonly
echo "In TDE, select all properties except "OLD_ROLE" and search for *|* to find these" >> $newonly
echo "" >> $newonly

#grep '|' $curdir/*xml >> $newonly
awk -F\| '$2!="OLD_ROLE" && NF!=4' $curdir/$usr\_properties.txt >> $newonly

echo "" >> $newonly

echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "11. Review hi-bit characters" >> $rpt

echo "" >> $rpt

echo "NOT CHECKING" >> $rpt
#\rm 8.out

#touch 8.out

#foreach x ( `ls $curdir/$usr\_*txt` )
#echo $x >> 8.out
#/site/umls/unicode/charfreq.pl -8 $x >> 8.out
#echo "" >> 8.out
#/site/umls/unicode/grep8.pl $x >> 8.out
#echo "" >> 8.out
#echo "" >> 8.out
#end

#cat 8.out >> $rpt


#echo "" >> $rpt

echo "Test 11"
echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "11. Review hi-bit characters" >> $newonly

echo "" >> $newonly

echo "NOT CHECKING" >> $newonly
#
#cat 8.out >> $newonly


echo "" >> $rpt


echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt
echo "" >> $newonly


#echo "----------------------------------------------------------" >> $newonly
#echo "" >> $newonly

echo "12. @ characters in Definition or FULL_SYN fields" >> $rpt
echo "" >> $rpt

grep 'DEFINITION.*\@' $curdir/$usr\_properties.txt >> $rpt

echo "" >> $rpt

grep 'FULL_SYN.*\@' $curdir/$usr\_properties.txt >> $rpt

echo "" >> $rpt


echo "Test 12"
echo "----------------------------------------------------------" >> $rpt
echo "12. @ characters in Definition or FULL_SYN fields" >> $newonly
echo "" >> $newonly

grep 'DEFINITION.*\@' $curdir/$usr\_properties.txt >> $newonly

echo "" >> $newonly

grep 'FULL_SYN.*\@' $curdir/$usr\_properties.txt >> $newonly

echo "" >> $newonly


echo "Test 13"
# test for dups in different concepts
echo "----------------------------------------------------------" >> $newonly

echo "13. Check for duplicate atoms -- same name, code, term type, and sab appearing in DIFFERENT concepts" >> $rpt

get_dup_atoms.pl $curdir/$usr\_properties.txt >> $rpt

echo "" >> $rpt
echo "13. Check for identical atoms -- same name, code, term type in different concepts" >> $newonly

echo "" >> $newonly

cut -f2 -d\| $curfiles/syns.tmp | grep -v '@$' | sort | uniq -d >! $curfiles/syns.duptmp

# added an intermediate step to create the sort file because of a 
# broken pipe warning. Didn't seem to affect the results, but the warning
# was troublesome.
sort -t\| +1 -2 $curfiles/syns.tmp >! $curfiles/synsort.tmp
join -t\| -j1 2 -j2 1 -o 1.1 1.2 $curfiles/synsort.tmp $curfiles/syns.duptmp \
>! $curfiles/syns.dups

#wc -l $curfiles/syns.dups >> $rpt 
#echo "" >> $rpt
#wc -l $curfiles/syns.dups >> $newonly 
#echo "" >> $newonly
#cat $curfiles/syns.dups >> $rpt
#cat $curfiles/syns.dups >> $newonly


echo "Test 14"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "----------------------------------------------------------" >> $newonly

echo "" >> $rpt

echo "14. Check for NCI-GLOSS definitions in concepts with no NCI-GLOSS PT atoms" >> $rpt

echo "" >> $rpt
echo "14. Check for NCI-GLOSS definitions in concepts with no NCI-GLOSS atoms" >> $newonly

echo "" >> $newonly

check-nci-gloss.pl $curdir/$usr\_properties.txt | sort -u > $curfiles/nci-gloss.tmp

cat $curfiles/nci-gloss.tmp >> $rpt
cat $curfiles/nci-gloss.tmp >> $newonly


echo "Test 15- OBSOLETE"
#Test 15 OBSOLETE: USE TEST #20; SLQ 1/11/2011
#echo "" >> $rpt
#
#echo "----------------------------------------------------------" >> $rpt
#echo "----------------------------------------------------------" >> $newonly
#
#echo "" >> $rpt
#
#echo "15. Check for concepts that have a (association) self-referential relationship" >> $rpt
#
#echo "" >> $rpt
#echo "15. Check for concepts that have a (association) self-referential relationship" >> $newonly
#
#echo "" >> $newonly
#
#awk -F\| '$1==$3' $curdir/$usr\_associations.txt > $curfiles/self-ref_rels
#
#cat $curfiles/self-ref_rels >> $rpt
#cat $curfiles/self-ref_rels >> $newonly


echo "Test 16"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "----------------------------------------------------------" >> $newonly

echo "" >> $rpt

echo "16. Roles that appear in the data but not in the configuration file" >> $rpt

echo "" >> $rpt
echo "16. Roles that appear in the data but not in the configuration file" >> $newonly

echo "" >> $newonly

cutp -f3 $tmpdir/nci_roles3.tmp > $curfiles/roles
#cutp -f3 $curdir/$usr\_defroles.txt > $curfiles/roles
#cutp -f3 $curdir/$usr\_infroles.txt >> $curfiles/roles
sort -u $curfiles/roles > $curfiles/uniq_roles.txt

cutp -f1 $curdir/config_roles > $curfiles/config_roles
cutp -f2 $curdir/config_roles >> $curfiles/config_roles
perl -pe 's///' $curfiles/config_roles > $curfiles/config_roles.tmp
sort -u $curfiles/config_roles.tmp > $curfiles/config_roles.txt

comm -23 $curfiles/uniq_roles.txt $curfiles/config_roles.txt > $curfiles/unused_roles.txt 

cat $curfiles/unused_roles.txt >> $rpt
cat $curfiles/unused_roles.txt >> $newonly


echo "Test 17"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "----------------------------------------------------------" >> $newonly

echo "" >> $rpt

echo "17. Property names that appear in the data but not in the configuration file" >> $rpt

echo "" >> $rpt
echo "17. Property names that appear in the data but not in the configuration file" >> $newonly

echo "" >> $newonly

cutp -f2 $curdir/$usr\_properties.txt | sort -u > $curfiles/property_names

cutp -f1 $curdir/config_properties > $curfiles/config_properties
cutp -f2 $curdir/config_properties >> $curfiles/config_properties
perl -pe 's///' $curfiles/config_properties > $curfiles/config_properties.tmp
sort -u $curfiles/config_properties.tmp > $curfiles/config_properties.txt

comm -23 $curfiles/property_names $curfiles/config_properties.txt > $curfiles/unused_properties.txt 

cat $curfiles/unused_properties.txt >> $rpt
cat $curfiles/unused_properties.txt >> $newonly


echo "Test 18"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "----------------------------------------------------------" >> $newonly

echo "" >> $rpt

echo "18. Association names that appear in the data but not in the configuration file" >> $rpt

echo "" >> $rpt
echo "18. Association names that appear in the data but not in the configuration file" >> $newonly

echo "" >> $newonly

cutp -f2 $curdir/$usr\_associations.txt | sort -u > $curfiles/association_names

cutp -f1 $curdir/config_associations > $curfiles/config_associations
#cutp -f2 $curdir/config_associations >> $curfiles/config_associations
perl -pe 's///' $curfiles/config_associations > $curfiles/config_associations.tmp 
sort -u $curfiles/config_associations.tmp > $curfiles/config_associations.txt

comm -23 $curfiles/association_names $curfiles/config_associations.txt > $curfiles/unused_associations.txt 

cat $curfiles/unused_associations.txt >> $rpt
cat $curfiles/unused_associations.txt >> $newonly


echo "Test 19"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "----------------------------------------------------------" >> $newonly

echo "" >> $rpt

echo "19. Check for duplicate atoms -- same name, term type, and sab but with different codes appearing in the SAME concept" >> $rpt

echo "" >> $rpt
echo "19. Duplicate terms with the same sab, tty but with different codes" >> $newonly

echo "" >> $newonly

grep '|FULL_SYN|' $curdir/$usr\_properties.txt > $curfiles/full_syns
perl -pe 's/\\/|/g' $curfiles/full_syns > $curfiles/full_syns.tmp

cutp -f1,2,3,4,5,6,7 $curfiles/full_syns.tmp | sort | uniq -d > $curfiles/dup_full_syns

cat $curfiles/dup_full_syns >> $rpt

echo "Test 20"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt

echo "" >> $rpt

echo "20. Check for concepts that have a self-referential relationship" >> $rpt

echo "" >> $rpt

get_self_refs.pl $curTREF/MRREL.TREF | sortp +0 -1 +2 -3 > $curfiles/self_ref_rels

cat $curfiles/self_ref_rels>> $rpt

echo "Test 21"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt

echo "" >> $rpt

echo "21. Check for conflicting RELAs between same concept pairs" >> $rpt

echo "" >> $rpt

check.conflictingrels.s 

cat $curfiles/disr1.txt >> $rpt
cat $curfiles/disr2.txt >> $rpt
cat $curfiles/disr3.txt >> $rpt
cat $curfiles/disr4.txt >> $rpt
cat $curfiles/disr5.txt >> $rpt
cat $curfiles/disr6.txt >> $rpt
cat $curfiles/disr7.txt >> $rpt
cat $curfiles/disr8.txt >> $rpt
#cat $curfiles/disr9.txt >> $rpt
cat $curfiles/disr10.txt >> $rpt

echo "Test 22"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt

echo "" >> $rpt

echo "22. Check for ALT-DEFS with a source of NCI" >> $rpt

echo "" >> $rpt

awk -F\| '$2=="ALT_DEFINITION" && $4=="Definition_Source\NCI"' $curdir/nci_properties.txt > $curfiles/nci_alt_defs.txt

cat $curfiles/nci_alt_defs.txt >> $rpt

#echo "Test 23"
#echo "" >> $rpt

#echo "----------------------------------------------------------" >> $rpt

#echo "" >> $rpt

#echo "23. Check for invalid external codes (e.g., ICD10CM, ICD9CM, etc)" >> $rpt

#echo "" >> $rpt

#confirm_mapping_codes.pl >! invalid_mapping_codes
#grep 'ICD10' invalid_mapping_codes >> $rpt
#grep 'ICD9' invalid_mapping_codes >> $rpt
#grep 'MedDRA' invalid_mapping_codes >> $rpt
#grep 'ICDO3' invalid_mapping_codes >> $rpt
