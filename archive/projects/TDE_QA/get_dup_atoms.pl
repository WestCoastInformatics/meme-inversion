#!/usr/bin/perl 
use integer;

# get_dup_atoms.pl
# Mon Oct 6 14:46:22 PDT 2003 - WAK 
#
# usage: $0 <properties_file> 
#
# looks for duplicate atoms in different concepts
# same name, code, term type in diff concepts

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
		$key = $pval."@".$tty."@".$src_code;
		$key = $pval."@".$tty."@".$src."@".$src_code;
		# is this atom used for another concept?

		#print "$key\n";

		if($seen{$key} && $seen{$key} ne $cname){
			$err++;
			#print "$seen{$key}|$key\n$cname|$key\n";
			push(@errors, "$cname|$key\n");
			push(@errors,"$seen{$key}|$key\n");
		}
		$seen{$key} = $cname;

#		$str = "$cname|$pname|$pval|Syn_Term_Type\\$tty\\Syn_Source\\$src";
#		if($src_code){
#			$str .= "\\Syn_Source_Code\\$src_code";
#		}
#		print "$str\n";
		
	}
	else{next}
}	# end of while(<PROP>)
print "\n$err duplicate atoms between different concepts\n\n";
foreach $x (@errors) { print $x}	
print "\n";
