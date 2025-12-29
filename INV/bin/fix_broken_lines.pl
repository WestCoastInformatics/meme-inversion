#!/usr/bin/perl
# you can use this to fix broken records
# set the match test to what constitutes a valid new record

# this line was used to fix broken LOINC Update records
#  if(/^(BEFORE\||CHANGED\||ADD\|)/){


while(<>){
	if(/^(BEFORE\||CHANGED\||ADD\|)/){
		if($str){
			print "$str\n";
			$str = '';
	 	}
	 }
	chomp;
	$str .= $_;
}
print "$str\n";


