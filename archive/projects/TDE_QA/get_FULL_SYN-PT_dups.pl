#!/usr/bin/perl 
use integer;

# get_FULL_SYN-PT_dups.pl
# Mon Oct 6 14:46:22 PDT 2003 - WAK 
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

	if($pname eq "FULL_SYN"){	
		($null,$src,$null,$tty,$null,$src_code)=split(/\\/,$qual);

		if($tty eq "PT" && $src eq "NCI"){
			# is this PT value used for another concept?
			if($seen{$pval} && $seen{$pval} ne $cname){
				$err++;
				print "$cname|$pval\n$seen{$pval}|$pval\n";
				#push(@errors, "$cname|$pval\n");
				#push(@errors,"$seen{$pval}|$pval\n");
			}

			$seen{$pval} = $cname;
		}
#		$str = "$cname|$pname|$pval|Syn_Term_Type\\$tty\\Syn_Source\\$src";
#		if($src_code){
#			$str .= "\\Syn_Source_Code\\$src_code";
#		}
#		print "$str\n";
		
	}
	else{next}
}	# end of while(<PROP>)

exit $err;

#print "\n$err NCI/PT duplicates between different concepts\n\n";
#foreach $x (@errors) { print $x}	
#print "\n";
