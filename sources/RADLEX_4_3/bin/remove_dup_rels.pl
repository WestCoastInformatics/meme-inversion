#!/usr/bin/perl

#5/3/19 SLQ
#remove duplicate relationships 
#remove self_referential rels

use integer;
use Encode qw(encode_utf8);
use lib "$ENV{INV_HOME_OLD}/lib";

BEGIN{
	unshift @INC,"$ENV{ENV_HOME}/bin";
	require "env.pl";
	use open ":utf8";
}

open(REL, "<:utf8", "../src/relationships.src") or "die can't open REL, $!\n";
open(OUT, ">:utf8", "../tmp/relationships_no_dups_no_self_refs.tmp") or die "Can't open/write OUT, $!";
open(TMP, ">:utf8", "../tmp/dup_rels_removed.txt") or die "Can't open/write OUT, $!";

while(<REL>){
	chomp;
	($relid,$level,$id1,$relname,$rela,$id2,$sor,$sol,$stat,$tbr,$release,$suppr,$type1,$qual1,$type2,$qual2,$rui,$rg)=split(/\|/);
		
	if($id1 eq $id2){
		print TMP "Removing self-referential rel: $_\n";
	}

	elsif($hash{"$id1|$relname|$rela|$id2"}){
		print TMP "Removing duplicate rel: $id1|$rela|$id2\n";
		next;
	}
	elsif($sor eq 'SRC'){
		print OUT "$_\n";
		next;
	}	
	else{
		print OUT "$_\n";
		$hash{"$id1|$relname|$rela|$id2"}++;
	}
	
}#end of while loop	
