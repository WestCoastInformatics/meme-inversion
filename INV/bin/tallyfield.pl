#!/usr/bin/perl -X

# Uses perl to tally tokens in 'awkfield(s)' in file(s) or stdin
# 'awkfield(s)' requires AWK syntax for compatibility with previous AWK version
# 
# tallyfield '$2' junk -- tallies tokens in 2nd "|"-delimited field of junk file
# tallyfield 'substr($2,1,5)' junk -- tallies tokens consisting of 1st 5-chars
#        in 2nd "|"-delimited field of junk file

$[ = 1;			# array first element number
$, = ' ';		# set output field separator
$\ = "\n";		# set output record separator

if($#ARGV < 1) {
	print "Usage: tallyfield 'awkfield(s)' filename(s)";
	exit 1;
}

$arg=shift;
for ($i=1; $i<=length($arg); $i++) {
    $c = substr($arg, $i, 1);
    if ($c eq '(') {
	$p++;
    } elsif ($c eq ')') {
	$p--;
	if ($p==0) {
	    $tallythis .= ') . "|" . ';
	    next;
	}
    }
    if ($v==1) {
	if ($c lt '0' || $c gt '9') {
	    $v=0;
	    $tallythis .= ' . "|" . ' if $p==$savep;
	}
    }
    if ($c eq '$') {
	$v=1;
	$savep=$p;
    }
    $tallythis .= $c;
}
$tallythis =~ s/ \. "\|" \. $//;
$tallythis =~ s/\$([1-9][0-9]*)/\$fields[$1]/g;
$tallythis =~ s/\$0/\$_/g;
$tallythis =~ s/ \. "\|" \. ([,)])/$1/g;
$tallythis =~ s/substr\(([^,)]*),([^,)]*)\)/substr($1,$2,999999)/g;
$prg = '
$[ = 1;
while (<>) {
    #chop;
    @fields = split(/[|\n]/);
    $count{' . $tallythis . '}++;
}
';

eval $prg;

foreach $X (sort keys(count)) { print $X . ' ' . $count{$X}; $tot +=
$count{$X}; } print '===================='; print 'TOTAL ' . $tot;
