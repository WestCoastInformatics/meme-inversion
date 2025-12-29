#!/usr/bin/perl
#
# changes
# 06/28/2007 WAK (1-ELQXM) fixed bug in error reporting
#
# simple.contexts.pl
# based on simple.cxt.pl, this script shows the structure of the
# contexts tree in an indented format starting from the root.
#
# National Cancer Institute Thesaurus V-NCI (isa)
#   Abnormal Cell C12913 (isa)
#     Abnormal Connective and Soft Tissue Cell C36843 (isa)
#       Abnormal Endothelial Cell C37086 (isa)
#         Atypical Endothelial Cell C37087 (isa)
#         Neoplastic Endothelial Cell C37088 (isa)
#           Epithelioid Endothelial Cell C37093 (isa)
#             Large Round Epithelioid Endothelial Cell C37094 (isa)

# 
# last update: Mon Aug 21 15:34:40 PDT 2006
# called from cxt/

# requires: source_atoms.dat, contexts.src 
# Old style compatibility
# assumes that you are calling the script from the cxt/ directory, 
# and that 'contexts.src' is in '../etc',
# and source_atoms.dat in in cxt (local)
# 
# Old Style
# usage: simple.contexts.pl > hierarchy.SAB

# New Style
# usage: simple.contexts.pl -n > ../cxt/hierarchy.SAB

# using the contexts.src file, makes a "pretty" hierarchical file
# also see the error file 'hier.errors'

$etcdir = $cxtdir = $tmpdir = '.';	# orig location of hier.html, source_atoms.dat
$srcdir = '../src';	# orig location of contexts.src

while(@ARGV){
	$arg = shift(@ARGV);
	if($arg eq "-n"){
		$etcdir = "../etc";
		$cxtdir = "../cxt";
		$srcdir = "../src";
		$tmpdir = "../tmp";
	}
}

print STDERR "reading $cxtdir/source_atoms.dat\n";
print STDERR "reading $srcdir/contexts.src\n";
print STDERR "writing $cxtdir/hier.errors\n";
print STDERR "writing $cxtdir/hier.html\n";

open (HTML, ">$cxtdir/hier.html");
print HTML "\<HTML\>";
print HTML "\<BODY\>";
print HTML "\n";
open (ERRORS, ">$cxtdir/hier.errors")|| die "Can't open file: '$tmpdir/hier.errors', $!";
print ERRORS "Yo\n";
open(ATOMS, "<$cxtdir/source_atoms.dat") or die "Can't open $etcdir/source_atoms.dat, $!";
while (<ATOMS>) {
	chomp;
    #($id,$termgroup,$scode,$term) = split(/\|/);
    ($id,$nul,$scode,$term) = split(/\|/);
    $term{$id} = $term;
    $scode{$id}=$scode;
}

# read contexts.src

# get the root and create an entry for it
open(CONT, "$srcdir/contexts.src") or die "Can't find '$srcdir/contexts.src', $!";
while(<CONT>){
	@F = split(/\|/);
	next unless($F[1] eq "PAR");
	@tree = split(/\./,$F[7]);
	$root = $tree[0];
	$tree{$root} = $F[2];
	last;
}

# go back to beginning of the file
seek(CONT,0,0);

# read the file
while(<CONT>){
	@F=split(/\|/);
	next unless($F[1] eq "PAR");
	$tree{"$F[7].$F[0]"} = $F[2];
}
close(CONT);
foreach $key (sort(keys(%tree))){
	@codes = split(/\./, $key);
	$rela = $tree{$key};
	$show=0;
	for ($i=0; $i<=$#codes; $i++) {
		if ($cxt[$i] ne $codes[$i]) {
			$show=1;
		}
		$cxt[$i] = $codes[$i];
		if ($show) {
			print '  ' x $i, $term{$codes[$i]}, ' ', $scode{$codes[$i]}, ' (',$rela,')', "\n";
			$j=$i+1;
			print HTML "\<H$j\>";
			print HTML $term{$codes[$i]}, ' ', $scode{$codes[$i]};
			print HTML "\<\/H$j\>";
			print HTML "\n";
			print ERRORS "hierarchy error at $key\n" if $i != $#codes;
		}
	}
	$#cxt = $#codes;
}
	
print HTML "\n";
print HTML "\<\/BODY\>";
print HTML "\<\/HTML\>";
print HTML "\n";




