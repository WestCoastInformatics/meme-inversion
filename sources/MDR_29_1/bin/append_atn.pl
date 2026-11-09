#!/usr/bin/perl

#9/27/2011 SLQ
#appends ATN=PT_IN_VERSION to attributes.src
#update SAB

use File::Copy;
use integer;
use Digest::MD5 qw(md5_hex);
use Encode qw(encode_utf8);
use lib "$ENV{INV_HOME_OLD}/lib";

$sab = MDR_29_1;

$attr_line = `tail -1 ../src/attributes.src`;
if($?){ warn "system call failed"; exit 1}
$attr_line =~ /^(\d*)\|/;
$attr_id = $1;

open (CLASS, "<../src/classes_atoms.src") || die "can't open CLASS\n";
open (ATTR, ">>../src/attributes.src") || die "can't open ATTR\n";
#open (ATN, ">../tmp/atn.txt") || die "can't open ATN\n";

while (<CLASS>){
	chomp;
	@fields=split(/\|/);
	if(($fields[2]=~/$sab\/PT/) || ($fields[2]=~/$sab\/LLT/) || ($fields[2]=~/$sab\/OL/)){
		$hash{$fields[3]}++;
	}
	else{
			
	}
}
close (CLASS);

open (ATN, "<../orig/mdr_by_version.txt") || die "can't open ATN\n";

while (<ATN>){
	# Normalize record endings before constructing the value and its digest.
	s/\r?\n\z//;
	die "Unexpected carriage return in history at line $.\n" if /\r/;
	@fields=split(/\|/);
	if ($hash{$fields[0]}){
		$attr_id++;
		$att_val=$fields[1];
		$md5=md5_hex(encode_utf8($att_val));
		print ATTR "$attr_id|$fields[0]|S|PT_IN_VERSION|$fields[1]|$sab|R|Y|N|N|CODE_SOURCE|$sab||$md5|\n";
	}
	else{
		print "ERROR: $_\n";
	}
}
close(ATN);
