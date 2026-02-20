#!/bin/tcsh

alias cutp 'cut -d\|'
alias joinp 'join -t\|'
alias sortp 'sort -t\|'
alias fawk 'awk -F\|'

if (! $?INV_HOME_OLD) then
    set INV_HOME_OLD = `pwd`/INV
endif


# 1) NOTE: this is now handled programmatically - do not edit the config files manually
# create new directories for your data and link the .owl and .txt (output of exportrels)to the Orig-<ver> directory:
#    Orig-<ver>   (e.g. Orig-1601D; ln -s /local/content/MEME/MEME5/inv/sources/NCI_2023_11D/orig Orig-2311D)
#    <ver>        (e.g. 0510E; mkdir 0510E)

# 2) NOTE: this is now handled programmatically - do not edit the config files manually
# create the config_associations, config_properties, and config_roles files in the inversion's orig directory
#	a) cp orig/fromprovider/NCI<ver>.txt ../orig/config_associations
#	b) cp orig/fromprovider/NCI<ver>.txt ../orig/config_properties
#	c) cp orig/fromprovider/NCI<ver>.txt ../orig/config_roles
#	d) edit each file so that it contains the appropriate data. 
#	'config_associations' only contains the association data, 
#	'config_properties' only contains the properties data, etc.

# 3) NOTE: this is now handled programmatically - do not edit the config files manually
# update version in check.conflictingrels.s

# 4) NOTE: this is now handled programmatically - do not edit the config files manually
# update the following variables.  Normally, this means
# setting the "prev*" values to what the "cur*" values were
# last time you ran the script, and then updating the "cur*" values
# to the directories you just created

# curdir/prevdir are the directories where the Original (.xml & .txt files) live
# curfiles/prevfiles are the directories where the interim files live

set ver=$1
set prev=$2

set curdir="archive/checkall/Orig-$ver"
set working_tmp="archive/checkall"
set curfiles="$working_tmp/$ver"
set curTREF="archive/checkall/Orig-$ver"

set srcdir="sources/NCI_20`echo $ver | cut -c1-2`_`echo $ver | cut -c3-5`"
set prevsrcdir="sources/NCI_20`echo $prev | cut -c1-2`_`echo $prev | cut -c3-5`"

set usr="nci"
set rpt="archive/checkall/checklist-report-$ver.txt"
set newonly="archive/checkall/checklist-report-$ver-newonly.txt"

set validstys=$INV_HOME_OLD/etc/valid_stys

set prevdir="archive/checkall/Orig-$prev"
set prevfiles="$working_tmp/$prev"
set prevusr="nci"

echo "ver: $ver"
echo ""

if (! -d "archive/checkall") then
    mkdir -p archive/checkall
endif
if (! -d "$curfiles") then
    mkdir -p $curfiles
endif
if (! -d "$prevfiles") then
    mkdir -p $prevfiles
endif

if (! -d "$curdir") then
    # e.g., ln -s ../../sources/NCI_2025_12E/orig archive/checkall/Orig-2512E
    ln -s ../../$srcdir/orig $curdir
endif
if (! -d "$prevdir") then
    ln -s ../../$prevsrcdir/orig $prevdir
endif

rm -f $rpt
rm -f $newonly

touch $rpt
touch $newonly

foreach prev_file ("prefname.dups.txt" "fspt.dups.txt" "duppts.tmp" "duppref.tmp" "noprefname.tmp")
    if (! -f "$prevfiles/$prev_file") then
        touch "$prevfiles/$prev_file"
    endif
end

if (! -f "$working_tmp/prevsubsources.tmp") then
    touch "$working_tmp/prevsubsources.tmp"
endif

set full_ver="20`echo $ver | cut -c1-2`_`echo $ver | cut -c3-5`"
set nci_file="NCI${full_ver}.txt"

echo "Setup Steps - Prepare the configuration files"


echo "Setup Step 1 - Prepare the config_association file"
cp $srcdir/orig/fromprovider/$nci_file $srcdir/orig/config_associations
awk '/\*\*\* ASSOCIATIONS \*\*\*/{f=1} f' $srcdir/orig/config_associations > $srcdir/orig/config_associations.tmp
mv $srcdir/orig/config_associations.tmp $srcdir/orig/config_associations

echo "Setup Step 2 - Prepare the config_properties file"
cp $srcdir/orig/fromprovider/$nci_file $srcdir/orig/config_properties
awk '/\*\*\* ATTRIBUTES \*\*\*/,/\*\*\*\*\* END \*\*\*\*\*/' $srcdir/orig/config_properties > $srcdir/orig/config_properties.tmp
mv $srcdir/orig/config_properties.tmp $srcdir/orig/config_properties

echo "Setup Step 3 - Prepare the config_roles file"
cp $srcdir/orig/fromprovider/$nci_file $srcdir/orig/config_roles
awk '/\*\*\* ROLES \*\*\*/,/\*\*\*\*\* END \*\*\*\*\*/' $srcdir/orig/config_roles > $srcdir/orig/config_roles.tmp
mv $srcdir/orig/config_roles.tmp $srcdir/orig/config_roles

echo "Test 1 - Preferred name not unique to single concept"
echo "1.  Preferred name not unique to single concept" >> $rpt
echo "1.  Preferred name not unique to single concept (new since last version)" >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "Preferred_Name property duplicates" >> $rpt

$INV_HOME_OLD/bin/get_PrefName_dups.pl $curdir/$usr\_properties.txt |\
sort -u | sortp -k2,2 >! $curfiles/prefname.dups.txt

$INV_HOME_OLD/bin/get_PrefName_dups.pl $prevdir/$prevusr\_properties.txt |\
sort -u | sortp -k2,2 >! $prevfiles/prefname.dups.txt

cat $curfiles/prefname.dups.txt | sort -u | sortp -k2,2 >> $rpt


# echo "Preferred_Name property duplicates"
echo "" >> $rpt
echo "Preferred_Name property duplicates (new only)" >> $newonly
echo "" >> $rpt
echo "" >> $newonly

echo `comm -23 $curfiles/prefname.dups.txt $prevfiles/prefname.dups.txt | wc -l` >> $newonly
comm -23 $curfiles/prefname.dups.txt $prevfiles/prefname.dups.txt >> $newonly


$INV_HOME_OLD/bin/get_FULL_SYN-PT_dups.pl $curdir/$usr\_properties.txt |\
sortp -k2,2 >! $curfiles/fspt.dups.txt 

cat $curfiles/fspt.dups.txt >> $rpt

echo "" >> $rpt 
echo "" >> $rpt
echo "" >> $rpt

sort $curfiles/prefname.dups.txt -o $curfiles/prefname.dups.txt
sort $prevfiles/prefname.dups.txt -o $prevfiles/prefname.dups.txt

comm -23 $curfiles/prefname.dups.txt $prevfiles/prefname.dups.txt | sort -t\| -k3,3 > $curfiles/newprefnamedups.txt

sort $curfiles/fspt.dups.txt -o $curfiles/fspt.dups.txt
sort $prevfiles/fspt.dups.txt -o $prevfiles/fspt.dups.txt
comm -23 $curfiles/fspt.dups.txt $prevfiles/fspt.dups.txt | sort -t\| -k3,3 > $curfiles/newfspt.dups.txt

wc -l $curfiles/newprefnamedups.txt >> $newonly
echo "" >> $newonly
cat $curfiles/newprefnamedups.txt >> $newonly
echo "" >> $newonly

# echo "FULL_SYN NCI/PT duplicates (new only)"
echo "FULL_SYN NCI/PT duplicates (new only)" >> $newonly
echo "" >> $newonly
wc -l  $curfiles/newfspt.dups.txt >> $newonly
echo "" >> $newonly
cat  $curfiles/newfspt.dups.txt >> $newonly

echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt
echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "Test 2 - Duplicate roles"
echo "2a.  Duplicate roles within concepts" >> $rpt
echo "2a.  Duplicate roles within concepts" >> $newonly

echo "" >> $rpt
echo "" >> $newonly

sort $srcdir/tmp/nci_roles3.tmp | uniq -d | wc -l >> $rpt
#sort $curdir/$usr\_defroles.txt | uniq -d | wc -l >> $rpt
#sort $curdir/$usr\_defroles.txt | uniq -d | wc -l >> $newonly

echo "" >> $rpt
echo "" >> $newonly

sort $srcdir/tmp/nci_roles3.tmp | uniq -d >> $rpt

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
| sort -u >! $working_tmp/stys.tmp

sort $validstys >! $working_tmp/validstys.sorted
join -t\| -1 1 -2 1 -v 1 $working_tmp/stys.tmp $working_tmp/validstys.sorted >> $rpt
join -t\| -1 1 -2 1 -v 1 $working_tmp/stys.tmp $working_tmp/validstys.sorted >> $newonly

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

# echo "Calling check.pts_qual"
$INV_HOME_OLD/bin/check.pts_qual.pl $curfiles $curdir/$usr\_properties.txt > /dev/null

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

cut -f3 -d\| $srcdir/tmp/nci_roles3.tmp >! $working_tmp/curroles.tmp
sort -u $working_tmp/curroles.tmp -o $working_tmp/curroles.tmp

cut -f3 -d\| $prevsrcdir/tmp/nci_roles3.tmp >! $working_tmp/prevroles.tmp
sort -u $working_tmp/prevroles.tmp -o $working_tmp/prevroles.tmp

echo "new roles:" >> $rpt
echo "new roles:" >> $newonly

join -v 1 $working_tmp/curroles.tmp $working_tmp/prevroles.tmp >> $rpt
join -v 1 $working_tmp/curroles.tmp $working_tmp/prevroles.tmp >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "disappearing roles:" >> $rpt
join -v 2 $working_tmp/curroles.tmp $working_tmp/prevroles.tmp >> $rpt

echo "disappearing roles:" >> $newonly
join -v 2 $working_tmp/curroles.tmp $working_tmp/prevroles.tmp >> $newonly


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

cutp -f2 -d\| $curdir/$usr\_properties.txt | sort -u >! $working_tmp/curprops.tmp
cutp -f2 -d\| $prevdir/$prevusr\_properties.txt | sort -u >! $working_tmp/prevprops.tmp

echo "new properties:" >> $rpt
join -v 1 $working_tmp/curprops.tmp $working_tmp/prevprops.tmp >> $rpt
echo "new properties:" >> $newonly
join -v 1 $working_tmp/curprops.tmp $working_tmp/prevprops.tmp >> $newonly

echo "" >> $rpt
echo "" >> $newonly

echo "disapearing properties:" >> $rpt
join -v 2 $working_tmp/curprops.tmp $working_tmp/prevprops.tmp >> $rpt

echo "" >> $rpt
echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "disapearing properties:" >> $newonly
join -v 2 $working_tmp/curprops.tmp $working_tmp/prevprops.tmp >> $newonly

echo "Test 8 - New subsources"
echo "" >> $newonly
echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "8.  New subsources; need citation, SAB, precedence, etc." >> $rpt
echo "8.  New subsources; need citation, SAB, precedence, etc." >> $newonly

echo "" >> $rpt
echo "" >> $newonly

$INV_HOME_OLD/bin/get-prevsubsources-qual.pl $working_tmp $prevdir/$prevusr\_properties.txt

# echo "1"

# output is now sort -u already
#sort -u $working_tmp/prevsubsources.tmp -o $working_tmp/prevsubsources.tmp
sort -u $curfiles/subsources.tmp -o $curfiles/subsources.tmp

# echo "2"

join -v 1 $curfiles/subsources.tmp $working_tmp/prevsubsources.tmp >> $rpt
join -v 1 $curfiles/subsources.tmp $working_tmp/prevsubsources.tmp >> $newonly

# echo "3"

echo "" >> $rpt

# echo "4"

echo "disappearing subsources:" >> $rpt

# echo "5"
join -v 2 $curfiles/subsources.tmp $working_tmp/prevsubsources.tmp >> $rpt

# echo "6"

echo "" >> $rpt
echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "" >> $newonly
echo "disappearing subsources:" >> $newonly
join -v 2 $curfiles/subsources.tmp $working_tmp/prevsubsources.tmp >> $newonly

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
echo "In TDE, select all properties except 'OLD_ROLE' and search for *|* to find these" >> $rpt
echo "" >> $rpt

#grep '|' $curdir/*xml >> $rpt

awk -F\| '$2!="OLD_ROLE" && NF!=4' $curdir/$usr\_properties.txt >> $rpt

echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "" >> $rpt

echo "10. Pipe characters in data" >> $newonly
echo "In TDE, select all properties except 'OLD_ROLE' and search for *|* to find these" >> $newonly
echo "" >> $newonly

#grep '|' $curdir/*xml >> $newonly
awk -F\| '$2!="OLD_ROLE" && NF!=4' $curdir/$usr\_properties.txt >> $newonly

echo "" >> $newonly

echo "----------------------------------------------------------" >> $newonly
echo "" >> $newonly

echo "11. Review hi-bit characters" >> $rpt

echo "" >> $rpt

echo "NOT CHECKING" >> $rpt

echo "Test 11 - Review hi-bit characters"
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


echo "Test 12 - @ characters in Definition or FULL_SYN fields"
echo "----------------------------------------------------------" >> $rpt
echo "12. @ characters in Definition or FULL_SYN fields" >> $newonly
echo "" >> $newonly

grep 'DEFINITION.*\@' $curdir/$usr\_properties.txt >> $newonly

echo "" >> $newonly

grep 'FULL_SYN.*\@' $curdir/$usr\_properties.txt >> $newonly

echo "" >> $newonly


echo "Test 13 - Duplicate atoms in different concepts"
# test for dups in different concepts
echo "----------------------------------------------------------" >> $newonly

echo "13. Check for duplicate atoms -- same name, code, term type, and sab appearing in DIFFERENT concepts" >> $rpt

$INV_HOME_OLD/bin/get_dup_atoms.pl $curdir/$usr\_properties.txt >> $rpt

echo "" >> $rpt
echo "13. Check for identical atoms -- same name, code, term type in different concepts" >> $newonly

echo "" >> $newonly

cut -f2 -d\| $curfiles/syns.tmp | grep -v '@$' | sort | uniq -d >! $curfiles/syns.duptmp

# added an intermediate step to create the sort file because of a 
# broken pipe warning. Didn't seem to affect the results, but the warning
# was troublesome.
sort -t\| -k2,2 $curfiles/syns.tmp >! $curfiles/synsort.tmp
join -t\| -1 2 -2 1 -o 1.1,1.2 $curfiles/synsort.tmp $curfiles/syns.duptmp \
>! $curfiles/syns.dups


echo "Test 14 - NCI-GLOSS definitions without PT atoms"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "----------------------------------------------------------" >> $newonly

echo "" >> $rpt

echo "14. Check for NCI-GLOSS definitions in concepts with no NCI-GLOSS PT atoms" >> $rpt

echo "" >> $rpt
echo "14. Check for NCI-GLOSS definitions in concepts with no NCI-GLOSS atoms" >> $newonly

echo "" >> $newonly

$INV_HOME_OLD/bin/check-nci-gloss.pl $curdir/$usr\_properties.txt | sort -u > $curfiles/nci-gloss.tmp

cat $curfiles/nci-gloss.tmp >> $rpt
cat $curfiles/nci-gloss.tmp >> $newonly

echo "Test 16 - Roles in data but not in configuration"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt
echo "----------------------------------------------------------" >> $newonly

echo "" >> $rpt

echo "16. Roles that appear in the data but not in the configuration file" >> $rpt

echo "" >> $rpt
echo "16. Roles that appear in the data but not in the configuration file" >> $newonly

echo "" >> $newonly

cutp -f3 $srcdir/tmp/nci_roles3.tmp > $curfiles/roles
#cutp -f3 $curdir/$usr\_defroles.txt > $curfiles/roles
#cutp -f3 $curdir/$usr\_infroles.txt >> $curfiles/roles
sort -u $curfiles/roles > $curfiles/uniq_roles.txt

cutp -f1 $curdir/config_roles > $curfiles/config_roles
cutp -f2 $curdir/config_roles >> $curfiles/config_roles
perl -pe 's/\r//' $curfiles/config_roles > $curfiles/config_roles.tmp
sort -u $curfiles/config_roles.tmp > $curfiles/config_roles.txt

comm -23 $curfiles/uniq_roles.txt $curfiles/config_roles.txt > $curfiles/unused_roles.txt 

cat $curfiles/unused_roles.txt >> $rpt
cat $curfiles/unused_roles.txt >> $newonly


echo "Test 17 - Property names in data but not in configuration"
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
perl -pe 's/\r//' $curfiles/config_properties > $curfiles/config_properties.tmp
sort -u $curfiles/config_properties.tmp > $curfiles/config_properties.txt

comm -23 $curfiles/property_names $curfiles/config_properties.txt > $curfiles/unused_properties.txt 

cat $curfiles/unused_properties.txt >> $rpt
cat $curfiles/unused_properties.txt >> $newonly


echo "Test 18 - Association names in data but not in configuration"
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
perl -pe 's/\r//' $curfiles/config_associations > $curfiles/config_associations.tmp 
sort -u $curfiles/config_associations.tmp > $curfiles/config_associations.txt

comm -23 $curfiles/association_names $curfiles/config_associations.txt > $curfiles/unused_associations.txt 

cat $curfiles/unused_associations.txt >> $rpt
cat $curfiles/unused_associations.txt >> $newonly


echo "Test 19 - Duplicate atoms within the same concept"
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

echo "Test 20 - Self-referential relationships"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt

echo "" >> $rpt

echo "20. Check for concepts that have a self-referential relationship" >> $rpt

echo "" >> $rpt

$INV_HOME_OLD/bin/get_self_refs.pl $curTREF/MRREL.TREF | sortp -k1,1 -k3,3 > $curfiles/self_ref_rels

cat $curfiles/self_ref_rels>> $rpt

echo "Test 21 - Conflicting RELAs between concept pairs"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt

echo "" >> $rpt

echo "21. Check for conflicting RELAs between same concept pairs" >> $rpt

echo "" >> $rpt

$INV_HOME_OLD/bin/check.conflictingrels.s $curTREF $curfiles 

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

echo "Test 22 - ALT-DEFS with a source of NCI"
echo "" >> $rpt

echo "----------------------------------------------------------" >> $rpt

echo "" >> $rpt

echo "22. Check for ALT-DEFS with a source of NCI" >> $rpt

echo "" >> $rpt

awk -F\| '$2=="ALT_DEFINITION" && $4=="Definition_Source\\NCI"' $curdir/nci_properties.txt > $curfiles/nci_alt_defs.txt

cat $curfiles/nci_alt_defs.txt >> $rpt

