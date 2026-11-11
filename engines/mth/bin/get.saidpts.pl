#!/usr/bin/perl
#
# e.g. "get.saidpts.pl >said.ptsaid"

$rank{'SRC/RPT'} = ++$n;
$rank{'SRC/VPT'} = ++$n;
$rank{'SRC/RAB'} = ++$n;
$rank{'SRC/VAB'} = ++$n;
$rank{'SRC/SSN'} = ++$n;
$rank{'SRC/RSY'} = ++$n;
$rank{'SRC/VSY'} = ++$n;

open(INPUT, "Meta/MRRANK.RRF");
while (<INPUT>) {
    chomp;
    s/[^|]*\|//;
    s@\|@/@;
    s/\|.*//;
    $rank{$_} = ++$n;
}

#open(INPUT, "cxt/source_atoms.dat");
#while (<INPUT>) {
#    chomp;
#    s/\|.*//;
#    $ispt{$_} = 1;
#}

open(INPUT, "classes_atoms.src");
while (<INPUT>) {
    chomp;
    @f = split(/[|\n]/);
    $rank = $rank{$f[2]};
    die "unknown termgroup " . $f[2] . ", stopped" if $rank eq '';
    $said = $f[0];
    $code = $f[3];
#    if ($ispt{$said}) {
#	$ptrank{$code} = 0;	# the highest rank
#	$ptid{$code} = $said;
#    } else {
	$ptrank{$code} = 9999 if $ptrank{$code} eq '';
	if ($rank < $ptrank{$code}) {
	    $ptrank{$code} = $rank;
	    $ptid{$code} = $said;
	}
#    }
}

open(INPUT, "classes_atoms.src");
while (<INPUT>) {
    chomp;
    @f = split(/[|\n]/);
    $said = $f[0];
    $code = $f[3];
    print $said, '|', $ptid{$code}, "\n";
}
