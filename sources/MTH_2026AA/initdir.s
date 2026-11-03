#!/bin/tcsh -f
#
# after running this:
# - do the things in [brackets] below
# - do preinvert1.s, preinvert2.s, invert1.s, and invert2.s

set newrel=2026AA
set prevrel=2025AB

pushd /local/content/MEME/MEME5/mr/umls
mkdir $newrel
cd $newrel
# [copy DVDIMAGE.tar to $newrel from NLM host & extract it to make DVDIMAGE dir]

mkdir META
# [copy MRREL.RRF and MRSAB.RRF to META from NLM host]

mkdir /local/content/MEME/MEME5/inv/sources/MTH_$newrel
cd /local/content/MEME/MEME5/inv/sources/MTH_$newrel
ln -s ../MTH_$prevrel prev
# [make link from "old" to the last MTH_20xxAX dir that was actually inserted]

ln -s /local/content/MEME/MEME5/mr/umls/$newrel/META Meta
cp -p prev/*.{s,pl,csh} .
cp -p prev/{bigrange.spec,inv?.spec,ncimid.readme,range?.spec,sab.vsab.map,src_data} .
