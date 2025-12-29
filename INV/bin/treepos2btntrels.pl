#!/usr/bin/perl

# takes treepos.dat and creates a bt_nt_rels file
# does not currently deal with rela

open (OUT, ">bt_nt_rels.dat");

while (<>)

	{
	@fields=split(/\|/);
	$treepos=$fields[2];
	@path=split(/\./,$treepos);
	$test=$#path-2;
	#print "$treepos|$test\n";
	print OUT "$path[$#path-1]|||$fields[0]|\n" if $path[$#path-1];
	}
