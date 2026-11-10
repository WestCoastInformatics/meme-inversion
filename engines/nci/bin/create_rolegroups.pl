#!/usr/bin/perl

#create file of individual rolegroups that contain more than one relationship
# Input filename is supplied by the resolved common release plan.

@ARGV == 1 or die "Usage: create_rolegroups.pl relations_file\n";
my ($relations_file) = @ARGV;
-f $relations_file && !-l $relations_file or die "Missing regular relations input\n";
open (REL, "<", $relations_file) || die "can't open REL\n";
open (OUT1, ">../tmp/rolegroups.tmp") || die "can't open OUT1\n";


while (<REL>){
	chomp;
	($cui1,$group,$rel,$cui2)=split(/\|/);
	if($group ne ''){
		print OUT1 "$cui1|$group\n";
	}
}
close(REL);

#open (RELGRP, "<../tmp/rolegroups.tmp") || die "can't open RELGRP\n";
#open (OUT2, ">../tmp/rolegroups.tmp1") || die "can't open OUT2\n";

#while(<RELGRP>){
#	chomp;
#	if($hash{$_}){
#		print OUT2 "$_\n";
#	}
#	else{
#		$hash{$_}++;
#	}
#}

#close(RELGRP);

