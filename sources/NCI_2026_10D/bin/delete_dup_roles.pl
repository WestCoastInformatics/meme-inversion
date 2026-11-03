#!/usr/bin/perl

#remove duplicate roles

open (ROLES, "<../tmp/nci_roles2.tmp") || die "can't open ROLES\n";
open (OUT, ">../tmp/nci_roles3.tmp") || die "can't open OUT\n";

while (<ROLES>){
	chomp;
	($code1,$blank,$role,$code2,$rui)=split(/\|/);
	if($rui eq ''){
		if ($hash{"$code1|$role|$code2"}){
		}
		else{
			print OUT "$_\n";
			$hash{"$code1|$role|$code2"}++;
		}
	}
	elsif($rui ne ''){
		print OUT "$_\n"; 
	}
}
close(ROLES);
