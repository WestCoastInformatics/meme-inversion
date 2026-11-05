#!/usr/bin/perl

#5/20/09 SLQ
#remove cycles from bt_nt_rel*

$sab='RADLEX_3_14';

use integer;
use Encode qw(encode_utf8);
use lib "$ENV{INV_HOME_OLD}/lib";

BEGIN{
	unshift @INC,"$ENV{ENV_HOME}/bin";
	require "env.pl";
	use open ":utf8";
}

open(IN, "<:utf8", "../tmp/bt_nt_rels.tmp.sort") or "die can't open IN, $!\n";

while(<IN>){
	chomp;
	($id1,$rel,$rela,$id2)=split(/\|/);
	$hash{"$id1|$id2"}++;
}
close(IN);


open(BTNT, "<:utf8", "../tmp/bt_nt_rels.tmp.sort") or "die can't open BTNT, $!\n";
open(CTXT, ">:utf8", "../cxt/bt_nt_rels.dat") or die "Can't open/write CTXT, $!";
open(OUT, ">:utf8", "../tmp/cycles_in_hier.txt") or die "Can't open/write CTXT, $!";

while(<BTNT>){
	chomp;
	($id1,$rel,$rela,$id2)=split(/\|/);
	if($hash{"$id2|$id1"}){
		print OUT "ERROR: removing cycle in data : $_\n";
	}
	else{
		print CTXT "$_\n";
	}
} #end while loop
close(BTNT);
