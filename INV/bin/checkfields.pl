#!/usr/bin/perl -X
#
# checkfields.pl filename
#
# Tabulates the lines in filename by the number of '|'-delimited fields therein.
# Also min & max number of chars. in each field, and number of nonzero flds.

die "Usage: $0 filename\n" unless $#ARGV == 0;
$file = shift;

print "#flds	#lines\n";
print "-----	------\n";
# awk -F\| '{print NF}' $1 | tallyfield.pl '$0'
open(FILE, "$file") || die "can't open $file";
while (<FILE>) {
    $count{1+tr/|/|/}++;
}
close(FILE);
foreach $x (sort keys%count) {
#foreach $x (sort keys(count)) {
    print $x . '        ' . $count{$x}, "\n";
    $tot += $count{$x};
}
print "================\n";
print 'TOTAL    ' . $tot, "\n\n";

print "fld#	length range	#nonzero\n";
print "----	------------	--------\n";

open(FILE, "$file") || die "can't open $file";
while (<FILE>) {
    chop;	# strip record separator
    @Fld = split(/\|/, $_, -1);
    if (($. == 1)) {
	$j = $#Fld;
	for ($i = 0; $i <= $j; $i++) {
	    $l{$i} = $u{$i} = length($Fld[$i]);
	}
    }
    $j = $#Fld if $j < $#Fld;
    for ($i = 0; $i <= $j; $i++) {
	$len = length($Fld[$i]);
	$l{$i} = $len if $len < $l{$i};
	$u{$i} = $len if $len > $u{$i};
	++$n{$i} if $len > 0;
    }
}
for ($i = 0; $i <= $j; $i++) {
    printf "%4d\t%-12s\t%d\n", $i, $l{$i} . ' - ' . $u{$i}, $n{$i};
}
