#!/bin/tcsh -f

# file|VSAB_field#
# MRCONSO.RRF|12
# MRDEF.RRF|5
# MRRANK.RRF|2
# MRREL.RRF|11
# MRSAB.RRF|3
# MRSAT.RRF|10

set rel=2021AA

#foreach i (Meta1 Meta2 Meta3)
foreach i (Meta1 Meta3)

    mv $i/MRCONSO.RRF{,.orig}
    awk 'BEGIN{FS=OFS="|"} $12=="MTH"{$12="MTH'$rel'"}{print $0}' $i/MRCONSO.RRF.orig >$i/MRCONSO.RRF

    mv $i/MRDEF.RRF{,.orig}
    awk 'BEGIN{FS=OFS="|"} $5=="MTH"{$5="MTH'$rel'"}{print $0}' $i/MRDEF.RRF.orig >$i/MRDEF.RRF

    mv $i/MRRANK.RRF{,.orig}
    awk 'BEGIN{FS=OFS="|"} $2=="MTH"{$2="MTH'$rel'"}{print $0}' $i/MRRANK.RRF.orig >$i/MRRANK.RRF

    mv $i/MRREL.RRF{,.orig}
    awk 'BEGIN{FS=OFS="|"} $11=="MTH"{$11="MTH'$rel'"}$12=="MTH"{$12="MTH'$rel'"}{print $0}' $i/MRREL.RRF.orig >$i/MRREL.RRF

    mv $i/MRSAB.RRF{,.orig}
    awk 'BEGIN{FS=OFS="|"} $3=="MTH"{$3="MTH'$rel'"}{print $0}' $i/MRSAB.RRF.orig >$i/MRSAB.RRF

    mv $i/MRSAT.RRF{,.orig}
    awk 'BEGIN{FS=OFS="|"} $10=="MTH"{$10="MTH'$rel'"}{print $0}' $i/MRSAT.RRF.orig >$i/MRSAT.RRF

    rm -f $i/MR*.RRF.orig

end
