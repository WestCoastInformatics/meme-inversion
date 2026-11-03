#!/usr/bin/perl
#
# This must be run from a part# subdirectory

use Digest::MD5 qw(md5_hex);

$RRFDIR='Meta';

# make termgroups, sources

open (MRRANK, "sort -t\\| +0 -1nr $RRFDIR/MRRANK.RRF |") || die "can't open MRRANK\n";
open (HIGH, ">highranks.txt");

while (<MRRANK>) {
    chomp;
    ($rank,$sab,$tty,$suppress)=split(/\|/);
    if (!$highrank{$sab}) {
	if ($sab eq "SRC") {
	    $rank = '9999';
	}
	$highrank{$sab}=$rank;
	push (@highranks,$rank);
	$sab{$rank}=$sab;
    }
    $tty{$rank} = "$tty";
}

foreach $r (sort @highranks) {
    print HIGH "$sab{$r}|$r\n";
}

close (HIGH);

open (UPDATES, "vsab.updates");
while (<UPDATES>) {
    ($old, $new) = split(/[|\n]/);
    if ($old ne '') {
	$updated{$new} = 1;
	$oldvsab{$new} = $old unless $old eq 'New';
    }
}

open (HIGH, 'sort -t\| +1 -2n highranks.txt |') || die "can't open HIGH\n";

while (<HIGH>) {
    chomp;
    ($sab,$rank)=split(/\|/);
    if (!$lowsrc) {$lowsrc="SRC";}
    $lowsrc{$sab}=$lowsrc;
    $lowsrc=$sab;
}

## (old): when multiple tgs have the same rank, pick the alphabetically largest
## open(TGS, "sort -t\\| +1 -2 +0 -1r ../ncimid.termgroups |sort -m -u -t\\| +1 |sort -t\\| +1 -2nr |");
# (now - Mar'15): mark all existing termgroups as "exists"
open(TGS, "sort -t\\| +1 -2n +0 -1 ../ncimid.termgroups |");
while (<TGS>) {
    next if /^ /;
    ($tg, $rank) = split(/[|\n]/);
    $exists{$tg} = 1;
    ($sab, $tty) = split(m@/@, $tg);
    if ($sab ne $psab) {
	if ($psab ne '') {
	    $defaultlowtg{$psab} = $tg;
	}
	$psab = $sab;
    }
}

open (MRRANK, "sort -t\\| +0 -1n $RRFDIR/MRRANK.RRF |") || die "can't open MRRANK\n";
open (TG, ">termgroups.src") || die "can't create termgroups.src\n";

while (<MRRANK>) {
    chomp;
    ($rank,$vsab,$tty,$suppress)=split(/\|/);

#    next if ($vsab eq "SRC" || $vsab eq "MTH");
    next if ($vsab eq "SRC");
    next unless $updated{$vsab};
    $belowsrc = $oldvsab{$vsab};
    $belowtty = $tty;
    $s = $vsab;
    while (!$belowsrc) {
	$s = $lowsrc{$s};
	$belowtty = $tty{$highrank{$s}};
	$belowsrc = $s if $exists{"$s/$belowtty"};
    }
    unless ($exists{"$belowsrc/$belowtty"}) {
	$belowtg = $defaultlowtg{$belowsrc};
	($belowsrc, $belowtty) = split(m@/@, $belowtg);
    }
    print TG "$vsab/$tty|$belowsrc/$belowtty|$suppress|N|N|$tty|\n";
#    $belowsrc=$vsab;
#    $belowtty=$tty;
}
close(TG);
close(MRRANK);

open (MRREL, "$RRFDIR/MRREL.RRF") || die "can't open MRREL\n";
 
while (<MRREL>) {
    ($cui1,$aui1,$stype1,$rel,$cui2,$aui2,$stype2,$rela,$rui,$srui,$sab,$sl,$dir,$mg,$suppress,$cvf)=split(/\|/);
    if ($dir eq "Y") {
	$reldir{$sab}="Y";
    }
}

# make sources.src

open (MRSAB, "$RRFDIR/MRSAB.RRF") || die "can't open MRSAB\n";
open (SABS, ">sources.src") || die "can't create sources.src\n";

while (<MRSAB>) {
    chomp;
    ($vcui,$rcui,$vsab,$rsab,$son,$sf,$sver,$vstart,$vend,$imeta,$rmeta,$slc,$scc,$srl,$tfr,$cfr,$cxty,$ttyl,$atnl,$lat,$cenc,$curver,$sabin,$ssn,$scit)=split(/\|/);

    next if ($vsab eq "SRC" || $vsab eq "MTH");
    next if ($vsab eq "NOTE" || $vsab eq "HDA99" || $vsab eq "HPC99" || $vsab eq "OMIM97");
    next unless $updated{$vsab};
    next if $lowsrc{$vsab} eq '' && $rsab ne 'MED' && $rsab ne 'MBD';
    $belowsrc = $oldvsab{$vsab};
    if (!$belowsrc) {
	$belowsrc = $lowsrc{$vsab};
    }
    $scit=~s/^ //;
    # set correct SVER for NCI's versioned-MTH source
    if ($rsab eq 'MTH') {
	($sver = $vsab) =~ s/^MTH_//;
    }
    print SABS "$vsab|$belowsrc|$srl|$vsab|$rsab|$sver|$sf|$son|||$scc|$slc|nci-reg\@apelon.com|$cxty||$lat|$scit||$cenc|$reldir{$vsab}|\n";
}
