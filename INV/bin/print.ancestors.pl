#!/usr/bin/perl

# looks for cycles within a tree
# to look for cycles across trees, run this, then print the ids backwards
# & comm -12 to look for overlap

open (CYCLES, ">cycles.out");
open (ANC, ">ancestors.tmp");

while (<>)
	{
	#chomp;
	@fields=split(/\|/);
	$treepos=$fields[2];
	@path=split(/\./,$treepos);
	foreach $id (@path)
		{
		if ($hash{$id})
			{
			print CYCLES "$id\n";
			}
		$hash{$id}=1;
		print ANC "$id|$fields[0]\n";
		}
	foreach $id (@path)
		{
		$hash{$id}="";
		}
	}
