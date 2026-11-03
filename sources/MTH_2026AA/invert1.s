#!/bin/tcsh -f
#
# BEFORE running this script, run preinvert{1,2}.s to do the Metamorphosys runs
# to make the correct subsets of concepts based on ncisources.spec.
#
# !! -> BEFORE running this, update the MTH SAB in the src_data file and the
# rel and prevrel settings below (and modify this script and inv3.spec like in
# the 2015AB & 2017AB versions if the previous release wasn't inserted), and
# update the rel setting in invert2.s.

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

set rel=2026AA
set prevrel=2025AB

source env.s

# part1 (MSH) is now combined into part3 in "src" folder
#echo MSH >rsabs1
#echo SNOMEDCT >rsabs2
if ("`grep '^SNOMEDCT_US' ncisources.spec |sort -t\| +1 -2 |tail -1 |cut -d\| -f3`" == "UPDATE") then
    awk -F\| '$3=="KEEP" || $3=="UPDATE" || $3=="NEW"{print $1}' ncisources.spec |grep -v '^SNOMEDCT_US$' >rsabs3
else
#    echo SCTSPA >! rsabs2
    awk -F\| '$3=="KEEP" || $3=="UPDATE" || $3=="NEW"{print $1}' ncisources.spec |grep -v '^SCTSPA$' >! rsabs3
endif

awk -F\| '{print $4 "|" $3}' old/Meta/MRSAB.RRF |sort -t\| +0 -1 -o vsabs.old
awk -F\| '{print $4 "|" $3}' Meta/MRSAB.RRF |sort -t\| +0 -1 |join -t\| -v2 -o 2.2 - vsabs.old >vsabs.deleted
rm -f vsabs.old

ln -s . bin
ln -s . etc

# make world-writable qa dir for MEME5 qa output
mkdir qa
chmod o+w qa

sort -t\| +0 -1 -o ncimid.sources{,}

#foreach subset (1 2 3)
# don't make parts 1&2 any more: SNOMED (part2) is now being inserted separately
# and part1 (MSH) is now combined into part3 in "src" folder (was "all")
foreach subset (3)

    set dir=src
    mkdir $dir
    #chgrp memegrp $dir
    cd $dir
    ln -s .. bin
    ln -s ../Meta$subset Meta

    awk -F\| '$3=="UPDATE" || $3=="KEEP" || $3=="NEW"{print $1 "|" $2 "|" $3}' ../ncisources.spec |join -t\| -o 1.1 1.2 1.3 - ../rsabs$subset |join -t\| -a1 -o 2.2 1.2 1.3 - ../ncimid.sources |awk -F\| '$3=="KEEP"{print "|" $2} $3=="UPDATE"{print $1 "|" $2} $3=="NEW"{print "New|" $2}' |grep -v '|SRC$' |sort -t\| +1 -o vsab.updates

    sed -n '/^[^|]/s/.*|//p' vsab.updates |sort -o sabs_updated_umls
    awk -F\| '{print $3 "|" $4}' Meta/MRSAB.RRF |sort -t\| +0 -1 |join -t\| -o 1.2 - sabs_updated_umls |sort -o rsabs-updated.umls
    sed 's/^/V-/' rsabs-updated.umls >vcodes_updated

    bin/make.sourcestermgroups.pl

    # NOTE: still have to manually update termgroups.src to fix the
    #       "low_termgroup" value for termgroups that didn't exist in the
    #       previous version of the source

    if ($subset == 3) then
	# Assign term_ids for SRC atoms for new MTH source
	set baseid=`grep '^SourceAtomIdBase|' ../bigrange.spec |sed 's/.*|//' |awk '{print $0-2}'`
	mv sources.src{,.save}
	grep '^MTH_20' sources.src.save |awk 'BEGIN{FS=OFS="|"}{$6=substr($1,4); print $0}' >sources.src
	ln -s ../src_data
	$INV_HOME_OLD/bin/SRCbuilder.pl -s $baseid >& SRCbuilder.log
	/bin/mv -f sources.src{.save,}

	sed '/^SourceDir|/s/MTHrelease\/*$/MTH_'$rel'\/'$dir'/; /^DefineConst|MTHSAB|/s/MTHrelease$/MTH_'$rel'/; /eq .prevrel/{; s/prevrel1/'$prevrel'/}' ../inv3.spec >inv3.spec
    else
	touch class_src attr_src rel_src merge_src
    endif

    ln -s Meta/MR{CONSO,SAT,STY,DEF,REL,CUI}.RRF .

    # make auis_nonupdatedSAB_moved
    awk -F\| '$9=="Y" && ($3=="'$rel'" || $3=="'$prevrel'"){print $1 "|" $8}' Meta/MRAUI.RRF |sort -t\| +0 -1 -o auis.moved
    awk -F\| '{print $8 "|" $12}' Meta/MRCONSO.RRF |sort -t\| +0 -1 |join -t\| -o 2.2 1.1 1.2 auis.moved - |sort -t\| +0 -1 |join -t\| -j1 2 -o 1.1 2.2 2.3 vsab.updates - |sed -n 's/^|//p' >auis_nonupdatedSAB_moved
    rm -f auis.moved

    # make cui_merges
    awk -F\| '$3=="SY" && $7=="Y" && $2=="'$prevrel'"{print $1 "|" $6}' Meta/MRCUI.RRF >cui_merges
    #awk -F\| '$3=="SY" && $7=="Y" && ($2=="'$prevrel'" || $2=="'$prevrel2'"){print $1 "|" $6}' Meta/MRCUI.RRF >cui_merges

    sed '/^SourceDir|/s/MTHrelease\/*$/MTH_'$rel'\/'$dir'/' ../inv1.spec >inv1.spec
    sed '/^SourceDir|/s/MTHrelease\/*$/MTH_'$rel'\/'$dir'/; /^DefineConst|MTHSAB|/s/MTHrelease$/MTH_'$rel'/' ../inv2.spec >inv2.spec

    # LANG must not be set to UTF-8, or autoinv.pl will fail in weird ways
    setenv LANG C
    echo "start `date`" >autoinv.log
    $INV_HOME_OLD/bin/autoinv.pl ../bigrange.spec inv1.spec >>& autoinv.log

    if (subset == 3) then
	mv classes_atoms.src{,.orig}
	bin/remove.oldsrcvsabs.pl classes_atoms.src.orig >classes_atoms.src
	rm -f classes_atoms.src.orig
	mv aui_said_map{,.orig}
	grep -v C1976636 aui_said_map.orig >aui_said_map
	rm -f aui_said_map.orig
    endif

    cd ..
end

cat src/classes_atoms.src |sed -n '/\/XM|/p' |cut -d\| -f2 |sed 's/^/modify ncisources.spec to exclude XM for source /; s/$/ and re-run from preinvert2.s/' |sort -u |tee xm.tofix
