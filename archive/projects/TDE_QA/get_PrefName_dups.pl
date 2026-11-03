#!/usr/bin/perl 
use integer;

# get_PrefName_dups.pl
#
# usage: $0 <properties_file> 
#
# looks for duplicate FULL_SYN PT records in different concepts

print STDERR "$0\n";
$prop = $ARGV[0];
if($prop){
	print STDERR "Using: $prop\n";
}
else{ 
	die "\n\n\tUsage: $0 < properties_file ";
}

open(PROP, "$prop") or die "Can't open/read $prop, $!";

$err = 0;
while(<PROP>){
	$lnc++;
	s/\r//g;
	chomp;
	($cname,$pname,$pval,$qual)=split(/\|/);

	if($pname eq "Preferred_Name"){	
		if($seen{$pval} && $seen{$pval} ne $cname){
			$err++;
			print "$cname|$pval\n$seen{$pval}|$pval\n";
			#push(@errors, "$cname|$pval\n");
			#push(@errors,"$seen{$pval}|$pval\n");
		}

		$seen{$pval} = $cname;
	}
	else{next}
}	# end of while(<PROP>)

