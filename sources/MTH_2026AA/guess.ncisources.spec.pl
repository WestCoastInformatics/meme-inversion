#!/usr/bin/perl
#
# e.g. "guess.ncisources.spec.pl >ncisources.spec"

open(OLD, 'sort -t\| +0 -1 +1 -2r old/ncisources.spec |sort -m -u -t\| +0 -1|');
open(NEW, q[awk -F\| '{print $4 "|" $3 "|" $22}' Meta/MRSAB.RRF |sort -t\| +0 -1 |]);

&getOLD;

# TYPEs: NEW, UPDATE, KEEP, EXCLUDE, REMOVE, SPECIAL
while (<NEW>) {
    ($RSAB, $VSAB, $CURVER) = split(/[|\n]/);
    while ($oRSAB lt $RSAB && $oRSAB ne '') {
	if ($oTYPE =~ /^(KEEP|UPDATE|NEW)$/) {
	    print "$oRSAB|$oVSAB|REMOVE|\n";
	}
	&getOLD;
    }
    if ($CURVER eq 'N') {
	print "$RSAB|$VSAB|EXCLUDE|\n";
	next;
    }
    $NOTES = '';
    if ($RSAB eq $oRSAB) {
	$NOTES = $oNOTES;
	if ($oTYPE =~ /^(KEEP|UPDATE|NEW)$/) {
	    $TYPE = ($VSAB eq $oVSAB) ? 'KEEP' : 'UPDATE';
	    $TYPE = 'UPDATE' if $RSAB eq 'MTH';
	} elsif ($oTYPE =~ /^(EXCLUDE|REMOVE)$/) {
	    $TYPE = 'EXCLUDE';
	} elsif ($oTYPE = 'SPECIAL') {
	    $TYPE = $oTYPE;
	}
	&getOLD;
    } else {
	$TYPE = '--NEW?--';
    }
    print "$RSAB|$VSAB|$TYPE|$NOTES\n";
}

sub getOLD {
    local($_);
    $_ = <OLD>;
    ($oRSAB, $oVSAB, $oTYPE, $oNOTES) = split(/[|\n]/);
}
