#!/usr/bin/perl 
use integer;

# get_self-refs.pl
#
# usage: $0 <MRREL.TREF> 
#
# looks for self-referential rels 

print STDERR "$0\n";
$prop = $ARGV[0];
if($prop){
	print STDERR "Using: $prop\n";
}
else{ 
	die "\n\n\tUsage: $0 < MRREL.TREF ";
}

open(PROP, "$prop") or die "Can't open/read $prop, $!";

$err = 0;
while(<PROP>){
	$lnc++;
	s/\r//g;
	chomp;
	($rui,$ui1,$type1,$rel,$rela,$ui2,$type2)=split(/\|/);

	if($ui1 eq $ui2){	
			print "$ui1|$rela|$ui2\n";
	}
	else{next}
}# end of while(<PROP>)

