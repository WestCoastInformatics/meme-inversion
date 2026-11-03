#!/usr/bin/perl
#
# e.g.: updatevsabs.pl sab.vsab.map MRSAB.RRF.orig >MRSAB.RRF
#
# Update VSABs in MRSAB.RRF.orig according to map in sab.vsab.map

die "usage: $0 sab.vsab.map MRSAB.RRF.orig, stopped" if $#ARGV != 1;

$mapfile = shift;
open(MAP, $mapfile);
while (<MAP>) {
    ($RSAB, $oldVSAB, $newVSAB) = split(/[|\n]/);
    $oldVSAB{$RSAB} = $oldVSAB;
    $newVSAB{$RSAB} = $newVSAB unless $newVSAB eq 'same';
}

while (<>) {
    chomp;
    @f = split(/[|\n]/);
    # fields: VCUI,RCUI,VSAB,RSAB,SON,SF,SVER,VSTART,VEND,IMETA,RMETA,SLC,SCC,
    #         SRL,TFR,CFR,CXTY,TTYL,ATNL,LAT,CENC,CURVER,SABIN,SSN,SCIT
    $VSAB = $f[2];
    $RSAB = $f[3];
    $CURVER = $f[21];
    if ($CURVER eq 'Y') {
	if ($oldVSAB{$RSAB} ne '' && $VSAB ne $oldVSAB{$RSAB}) {
	    print STDERR "$mapfile: $RSAB VSAB is $oldVSAB{$RSAB}, not $VSAB\n";
	}
	if ($RSAB eq 'MTH') {
	    $f[6] = substr($newVSAB{$RSAB},4);
	}
	$f[2] = $newVSAB{$RSAB} if $newVSAB{$RSAB} ne '';
	print join("|", @f), "|\n";
    } else {
	print "$_\n";
    }
}
