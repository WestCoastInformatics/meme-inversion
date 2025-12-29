#!/usr/bin/perl

# SLQ 9/7/06 changed the output location of the files to ../tmp/
# make.par_chd_rels.pl
# WAK 1/10/00

# usage: make.par_chd_rels.pl SAB

# used to create the file "par_chd_rels" which is used by the
# script read.sty.pl

# reads the file TREEPOS and gathers the last two source atoms ids
# from each line and collects them in a file with this format:
# parent_src_atom_id|child_source_atom_id

# also writes a file of all the source atoms ids:
# "all.terms.needing.sty.tmp"
#
# use this file (via 'sort -u') to create a file of all the src
# atom ids that have stys. then remove from this list all occurances
# rom the file "sty_term_id" to create the file "no_sty_term_ids"
#
# sort -u all.terms.needing.sty.tmp > ! all.terms.needing.sty.sort.tmp
# cut -d\| -f1 sty_term_ids > sty_term_ids.said.tmp
# comm -13  sty_term_ids.said.tmp all.terms.needing.sty.sort.tmp > no_sty_term_ids
# par_chd_rels.pl AOD99 ./cxt/TREEPOS

unless($#ARGV == 1){ 
	print <<EOT;

	usage: $0 SAB TREEPOS

	e.g., $0 AOD99 ./cxt/TREEPOS

	reads TREEPOS to create the file \"par_chd_rels\"
	run this in the directory where you want to create the file
	this is typically in the main source directory

EOT
		 exit()}

$SAB = $ARGV[0];
$treepos = $ARGV[1];

print "\n\nRunning $0\n";
print "Creating 'par_chd_rels' for $SAB\n";
print "From from the file: $treepos\n\n";
print "Writing to: \"par_chd_rels\" and \"all.terms.needing.sty.tmp\n\n";

open (TREEPOS, "<$treepos") or die "Can't open $treepos: $!";

# TREEPOS looks like this:
# 46019043|1|AA2.8|46019020.46019022.46019024.46019043|
# where 
# 1 - source atom id of current atom
# 2 - context id, incr. for each occurance this atom in a hierarchy
#	(if the atom appears in two hierarchies, it would have '1' entry
#	and a '2' entry)
# 3 - hierarchy code (often same as used in classes_atoms.src)
# 4 - hierarchy path from top to bottom (ancestor to child)
#	the delimiter is '.'

open (PAR_CHD, ">../tmp/par_chd_rels") or die "Can't open \"par_chd_rels\": $!";
open (STY, ">../tmp/all.terms.needing.sty.tmp") or die "Can't open \"all.terms.needing.sty.tmp\": $!";

while(<TREEPOS>){
	($said,$cid,$hcode,$path) = split(/\|/);
	@path = split(/\./,$path);
	if($#path > 0){
		$y = $#path - 1;
		print PAR_CHD "$path[$y]|$path[$#path]\n";
		print STY "$path[$#path]\n$path[$y]\n";
	}
}




