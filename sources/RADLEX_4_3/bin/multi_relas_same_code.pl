#!/usr/bin/perl

#5/3/19 SLQ
#for QA
#id multiple relationships between same concept pairs

use integer;
use Encode qw(encode_utf8);
use lib "$ENV{INV_HOME_OLD}/lib";

BEGIN{
	unshift @INC,"$ENV{ENV_HOME}/bin";
	require "env.pl";
	use open ":utf8";
}

open(REL, "<:utf8", "../src/relationships.src") or "die can't open REL, $!\n";
open(TMP, ">:utf8", "../tmp/multi_rela_same_code.txt") or die "Can't open/write TMP, $!";

while(<REL>){
	chomp;
	($relid,$level,$id1,$relname,$rela,$id2,$sor,$sol,$stat,$tbr,$release,$suppr,$type1,$qual1,$type2,$qual2,$rui,$rg)=split(/\|/);
	
	if ($hash{"$id1|$id2"}){
		print TMP "$id1|$rela|$id2\n";
	}
	else{
		$hash{"$id1|$id2"}++;
	}
}
close(REL)
