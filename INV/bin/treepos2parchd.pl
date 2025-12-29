#!/usr/bin/perl

# creates a file of parent said|chd said, e.g. for read.stys.pl

# usage:  treepos2parchd.pl treepos.dat

open (PAR, ">par_chd_rels");

while (<>)

	{
	@fields=split(/\|/);
	$treepos=$fields[2];
	@path=split(/\./,$treepos);
	print PAR "$path[$#path-1]|$fields[0]\n" unless $path[$#path-1] ==$fields[0];
	}
