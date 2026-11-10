#!/bin/tcsh -f
#
# BEFORE running this, update range3.spec to use a new range of atom ids from:
# https://meme-edit.semantics.cancer.gov/ncim-server-rest/index.html#/login
# (login: <credentials supplied separately>, click Inversion tab, enter terminology "MTH_20##XX", click
# "Request Range") with enough ids to handle 2 more than
# `wc -l src/classes_atoms.src`.
#   Note: add 2 to SourceItemIdBase in range3.spec to make room
#   for the MTH_20##XX SRC atoms.
# update the rel version below e.g.:  
#         set rel=2024AA
#
# AFTER this script, do Q/A using:
#   https://meme-edit.semantics.cancer.gov/ncim-server-rest/index.html#/login
#   (or maybe use meme-release)
#   (see documentation at https://wiki.nci.nih.gov/pages/viewpage.action?spaceKey=EVSproj&title=Inversion+QA+Processes):
#   Log in as NEO; click Process tab; choose Role: Administrator; click Config
#   sub-tab; choose Type: Inversion; on the previous release's "QA MTH_20##XX"
#   row click 'Clone process' icon; click the Edit icon on the new row; rename
#   it to "QA MTH_20##XX" (the current release); update its description, input
#   path, log path, and "feedback email" address; Save; click Admin tab; under
#   Application Administration, click Projects; click the Edit icon by the
#   NCI-Meta Editing project; ensure "Automations enabled" is unchecked; click
#   Save; click Process tab again; select the new process; click Prepare button
#   (middle of right section); [now in Execution sub-tab] click Execute button
#   (further down in right section) and confirm "OK" to begin.
# AFTER the Q/A completes, go back to the Admin tab, under Projects click Edit
#   by the "NCI-Meta Editing" project, re-select "Automations enabled", and
#   click Save.
# Then review the Q/A output in qa/process*.log
#   Expect "FAILED" for steps 0, 1, and 4 (atoms, attrs, and rels).
#   Expected errors (output from: grep 'error count' qa/process*.log):
#    - hundreds of ATOMS_18 errors and the same number of ATOMS_5 errors
#      ("invalid" termgroups in classes_atoms)
#    - ~2.8M (was ~200K) ATTRS_7 errors (whitespace in ATVs)
#    - 2 RELS_3 errors (self-ref rels from HPO)
#    - ~13K RELS_4 errors (RT with RELA=has_part)
#
# AFTER inversion and Q/A are completed do:
# % set rel=`grep 'set rel=' invert1.s |sed 's/.*=//'`
# % /local/content/MEME/MEME5/ncim/bin/push_s3.csh inv MTH_$rel --update
# % /local/content/MEME/MEME5/ncim/bin/push_s3.csh umls $rel
#
# AFTER inversion & Q/A, send any sources in vsabs.deleted that were NOT
# previously EXCLUDEd (and src/*.src) to the inserter AND use the template at:
#  https://wiki.nci.nih.gov/display/EVSproj/NCI+Source+Tracking
# to notify Lori&DSS&SSL&SLQ&RW&Lyubov&Joshua Liu (NOT the nci-meta list)
# "Inversion Completed" and "inversion files pushed to AWS".
#
# AFTER *insertion* is completed do (again, to upload insertion logs):
# % set rel=`grep 'set rel=' invert1.s |sed 's/.*=//'`
# % /local/content/MEME/MEME5/ncim/bin/push_s3.csh inv MTH_$rel --update
# and also:
# % set prevrel=`grep 'set prevrel=' invert1.s |sed 's/.*=//'`
# % rm -rf /local/content/MEME/MEME5/inv/sources/MTH_$prevrel
# % rm -f /local/content/MEME/MEME5/inv/sources/MTH_$prevrel.tgz
# % rm -rf /local/content/MEME/MEME5/mr/umls/$prevrel

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

set rel=2026AA

set lcrel = `echo $rel | tr '[A-Z]' '[a-z]'`

source env.s

if (`wc -l <xm.tofix` != 0) then
   echo "Fix XM problems (and re-run from preinvert2.s on) first:"
   cat xm.tofix
endif

#foreach subset (1 2 3)
# don't make parts 1&2 any more: SNOMED is now being inserted separately and
# MSH is now included in part3 in the "src" folder
foreach subset (3)

    set dir=src
    cd $dir

    if ($subset == 3) then
	# Assign term_ids for SRC atoms for new MTH source
	set baseid=`grep '^SourceAtomIdBase|' ../range$subset.spec |sed 's/.*|//' |awk '{print $0-2}'`
	mv sources.src{,.save}
	grep '^MTH_20' sources.src.save |awk 'BEGIN{FS=OFS="|"}{$6=substr($1,5); print $0}' >sources.src
	ln -s ../src_data
	$INV_HOME_OLD/bin/SRCbuilder.pl -s $baseid >& SRCbuilder.log
	/bin/mv -f sources.src{.save,}
    endif

    # LANG must not be set to UTF-8, or autoinv.pl will fail in weird ways
    setenv LANG C
    echo "start `date`" >autoinv.log
    $INV_HOME_OLD/bin/autoinv.pl ../range$subset.spec inv1.spec >>& autoinv.log
    # Every retained atom keeps its AUI mapping, including LOINCPARTS.
    # Atom exclusions are applied consistently by inv1.spec before this step.
    awk -F\| '$3=="Y"{print $2}' aui_said_map |sort -u -o cuis.withmovedaui
    awk -F\| '$3=="N"{print $2}' aui_said_map |sort -u |comm -23 cuis.withmovedaui - >cui.splitonly
    cut -d\| -f1 ../old/src/cui_said_map |sort |comm -23 cui.splitonly - >cui.splitonly.new
    rm -f cuis.withmovedaui cui.splitonly
    cut -d\| -f2,4 aui_said_map |sort -u -t\| +0 -1 |join -t\| - cui.splitonly.new >cui_splitonly_said_map
    awk -F\| '$3=="Y"{print $1 "|" $2 "|" $4}' aui_said_map >moved_aui_said_map
    awk -F\| '$3=="N"{print $1 "|" $2 "|" $4}' aui_said_map >asm2
    /bin/mv -f asm2 aui_said_map
    cut -d\| -f2,3 aui_said_map |sort -u -t\| +0 -1 -o cui_said_map - cui_splitonly_said_map
    if ($subset == 3) then
	sort -u ../src/cui_said_map -o rel_cui_said_map
    else
	ln -s cui_said_map rel_cui_said_map
    endif
    ln -s aui_said_map aui_said_map2
    ln -s rel_cui_said_map rel_cui_said_map2
    $INV_HOME_OLD/bin/autoinv.pl inv2.spec >>& autoinv.log
    if ($subset == 3) then
	$INV_HOME_OLD/bin/autoinv.pl inv3.spec >>& autoinv.log
    endif
    echo "done  `date`" >>autoinv.log

    if (subset == 3) then
	mv classes_atoms.src{,.orig}
	bin/remove.oldsrcvsabs.pl classes_atoms.src.orig >classes_atoms.src
	rm -f classes_atoms.src.orig
    endif

    (cut -d\| -f7 relationships.src; cut -d\| -f6 attributes.src |sed 's/^E-//') |sort -u |grep -v '^SRC$' >used.vsabs
    cut -d\| -f1 sources.src |sort -u |comm -23 used.vsabs - >missing.vsabs

    if (`wc -l <missing.vsabs` != 0) then
       echo '-> *** Add lines for rel/attr-only sources to sources.src ***:'
       echo '-> *** DO NOT copy the VSAB format from NDFRT - in the second date'
       echo '-> *** of each VSAB, use the "18" rather than "2018" format.'
       echo '(Note: make their LAT and CXTY blank)'
       cat missing.vsabs
       echo '**************************************************************'
    endif

    grep -v '^RELEASE|' Meta/MRDOC.RRF >MRDOC.RRF

    # make missing.tgs file; if anything appears there, need to manually add a
    # line in termgroups.src for it
    awk -F\| '$15=="Y"{print $3}' classes_atoms.src |sort -u -o cy.tgs
    grep -v '^ ' ../ncimid.termgroups |sed 's/|.*//' |sort |comm -23 cy.tgs - >missing.tgs
    rm -f cy.tgs

    if (`wc -l <missing.tgs` != 0) then
       echo '-> *** Add lines for moved-AUI-in-nonupdated-SAB termgroups ***'
       echo '-> *** to the termgroups.src file:                          ***'
       cat missing.tgs
       echo '***************************************************************'
    endif

    # map relationship names to BT/NT/RT/RT?
    mv relationships{,1}.src
    awk 'BEGIN{FS=OFS="|"; map["RB"]="BT"; map["RN"]="NT"; map["RO"]="RT"; map["RQ"]="RT?"} map[$4]!=""{$4=map[$4]} $17=="~DA:"{$17=""} {print $0}' relationships1.src >relationships.src
    rm -f relationships1.src

    cp -p attributes.src attributes.src.nocxts
    rm attributes.src.nocxts.gz
    gzip attributes.src.nocxts

    mkdir raw3
    #chgrp memegrp raw3

    awk -F\| '$12=="SRC" && $13=="RPT"{print substr($14,3) "|" $1}' Meta/MRCONSO.RRF |sort -t\| +0 -1 |join -t\| -o 1.2 - rsabs-updated.umls |sort -o src-root.cuis.updated

    bin/mrcxt2raw3.pl >>& autoinv.log

    # make attributes.contexts-all.src
    if (`wc -l <raw3/newsources.raw3` != 0) then
        # print.raw3.to.attributes.pl doesn't work on an empty input file
	$INV_HOME_OLD/bin/print.raw3.to.attributes.pl raw3/newsources.raw3 
	cat attributes.contexts-all.src >>attributes.src
    endif

    bin/runQA.s

    setenv PATH_TO_PERL /usr/bin/perl
    #$INV_HOME_OLD/bin/raw_to_contexts.csh raw3 >>& autoinv.log
    bin/raw_to_contexts.csh raw3 >>& autoinv.log
    mv contexts.src contexts.src.orig
    sed 's/$/||/' contexts.src.orig >contexts.src
    rm -f contexts.src.orig
    rm -f raw3/newsources.raw3

    grep 'write failed' autoinv.log
    if (`grep -c 'write failed' autoinv.log` != 0) then
	echo "DISK FULL, stopped"
	exit 1
    endif

    bin/make.meme4classes.s

    cd ..
end

# copy MTH sources.src entry from part3 to part1 so MTH attributes in parts
# 1 and 2 will work (and leave the MTH sources.src entry in part3 too so that
# the insertion process for marking old sources will work)
#grep '^MTH_20' part3/sources.src >>part1/sources.src

# make umlscui.txt file
/usr/bin/unzip -p Meta/../DVDIMAGE/$lcrel-1-meta.nlm "$rel/META/MRCONSO.RRF*.gz" | gunzip -c - |./fix.vsrc.atoms.pl |perl -ne '@_ = split /\|/; print "$_[0]||$_[8]|$_[9]|$_[10]|$_[11]|$_[12]|$_[13]|$_[14]|SUI|\n" if $_[1] eq "ENG";' >src/umlscui.txt
