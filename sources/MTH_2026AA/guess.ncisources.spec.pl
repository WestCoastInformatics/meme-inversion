#!/usr/bin/perl
#
# preinvert1.s publishes a complete proposal while preserving failed evidence.
# Direct use should write to a separate review file, not the existing plan.

die "Missing or unreadable old/ncisources.spec\n" unless -f 'old/ncisources.spec' && -r 'old/ncisources.spec';
die "Missing or unreadable Meta/MRSAB.RRF\n" unless -f 'Meta/MRSAB.RRF' && -r 'Meta/MRSAB.RRF';
open(OLD, 'sort -t\| +0 -1 +1 -2r old/ncisources.spec |sort -m -u -t\| +0 -1|') || die "Can't open old/ncisources.spec producer: $!\n";
open(NEW, q[awk -F\| '{print $4 "|" $3 "|" $22}' Meta/MRSAB.RRF |sort -t\| +0 -1 |]) || die "Can't open Meta/MRSAB.RRF producer: $!\n";

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
	} elsif ($oTYPE eq 'SPECIAL') {
	    $TYPE = $oTYPE;
	} else {
	    die "Unknown prior disposition $oTYPE for $RSAB\n";
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
