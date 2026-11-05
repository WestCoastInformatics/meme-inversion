#!/usr/bin/perl

#1/10/07 SLQ
#pt/sy merges should share same code, id those that do not 

use integer;
use Encode qw(encode_utf8);
use lib "$ENV{INV_HOME_OLD}/lib";

BEGIN{
	unshift @INC,"$ENV{ENV_HOME}/bin";
	require "env.pl";
	use open ":utf8";
}

open(CLASS, "<:utf8", "../src/classes_atoms.src") or "die can't open CLASS, $!\n";

while(<CLASS>){
	chomp;
	($said,$sab,$tg,$code,$status,$tbr,$rel,$atom,$supp,$aui,$cui,$dui,$lang,$oi)=split(/\|/);	
	$hash{$said}=$cui
}
close(CLASS);


open(MERGE, "<:utf8", "../src/mergefacts.src") or "die can't open MERGE, $!\n";
open(OUT, ">:utf8", "../tmp/mismatched_code_in_merges.tmp") or die "Can't open/write OUT, $!";

while(<MERGE>){
	chomp;
	($id1,$level,$id2,$sab,$iv,$md,$cs,$ms,$type1,$qual1,$type2,$qual2)=split(/\|/);
		
	print OUT "$hash{$id1}|SY|$hash{$id2}\n";
}
close(MERGE);

open(MISMATCH, "<:utf8", "../tmp/mismatched_code_in_merges.tmp") or "die can't open MISMATCH, $!\n";
open(OUT2, ">:utf8", "../tmp/mismatched_code_in_merges2.tmp") or die "Can't open/write OUT2, $!";

while(<MISMATCH>){
	chomp;
	($id1,$sy,$id2)=split(/\|/);
	if($id1 ne $id2){
		print OUT2 "$_\n";
	}
}
close(MISMATCH)
