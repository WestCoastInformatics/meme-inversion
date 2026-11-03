#!/usr/bin/perl

#using the RUI assign the rolegroup from MRSAT.TREF

open (MRSAT, "<../orig/MRSAT.TREF") || die "can't open MRSAT\n";
open (OUT, ">../tmp/nci_roles2.tmp") || die "can't open OUT\n";

while (<MRSAT>){
	chomp;
	@fields=split(/\|/);
	if ($fields[3] eq "RELATIONSHIPGROUP"){
		$hash{$fields[1]}=$fields[4];
	}
}
close (MRSAT);

open (OWL, "<../tmp/nci_roles.tmp") || die "can't open OWL\n";

while (<OWL>){
	chomp;
	($code1,$blank,$role,$code2,$rui)=split(/\|/);
	if ($hash{$rui}){
		print OUT "$code1|$blank|$role|$code2|$hash{$rui}|\n";

	}
	else{
		print OUT "$code1|$blank|$role|$code2||\n"; 
	}
}
close(OWL);
