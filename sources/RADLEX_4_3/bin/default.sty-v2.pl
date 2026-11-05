#!/usr/bin/perl
#
# Script	default.sty.pl 
# Author	EMW (6/10/98)
#
# This script existed under 3 different names, all doing
# the same thing. Now, read.sty.pl and make_links.pl are
# symbolic links to this script, default.sty.pl   RH 1-30-03
#
# This script will traverse the PAR/CHD tree of atoms
# to assign STYs by inheritance for all atoms that are
# in a concept that does not have any STYs. 
#
# Inputs: no_sty_term_ids, sty_term_ids, par_chd_rels
# no_sty_term_ids: a list of Source Atom IDs for which to create STYs
# sty_term_ids: a file from which to inherit 
#	Src Atom ID|Semantic Type
# Outputs: default_sty_term_ids (STY assignment for all atoms in
#                                format: term_ids|STY format)
#
# reminder:  need to add the original file of defaults (sty_term_ids)
# back to make the .src file.
# NOTE:  "term_ids" are usually source_atom_ids, but they could
# be atom_ids if the inverter prefers.  SSL prefers source_atom_ids
# because it is easier to QA the stys by looking at the .src files

open(IN, "../etc/sty_term_ids") or die "Can't open file: $!\n";

while (<IN>) {
  chomp;
  ($sty_term_id, $sty) = split /\|/;
  $sty_set{$sty_term_id} .= "$sty\.";
}

foreach $sty_term_id (sort keys %sty_set) {
  chop $sty_set{$sty_term_id};
}

# note:  SSL changed this so as of 6/18/99 files are parent_id|child_id
# rather than visa versa which was the way it used to be.

open(IN, "../tmp/par_chd_rels") or die "Can't open file: $!\n";

while (<IN>) {
  chomp;
  ($par_term_id, $chd_term_id) = split /\|/;
  $parent_set{$chd_term_id} .= "$par_term_id\.";
}


open(IN, "../tmp/no_sty_term_ids") or die "Can't open file: $!\n";

get_next_id:
while (<IN>) {

  chomp;
  $flag = 0;
  $term_id = $_;

  $ancestor_set = $parent_set{$term_id};
  @ancestor_field = split /\./, $ancestor_set;
  if ($ancestor_field[0] ne '') {
    $flag = 1;
  } 

  print "$term_id\|STY NOT FOUND\n" if ($flag == 0);

  while ($flag == 1) {

    foreach $ancestor (@ancestor_field) {
      @temp = split /\./, $sty_set{$ancestor};
      if ($temp[0] ne '') {
        foreach $sty (@temp) {
          print "$term_id\|$sty\n";
        }
        next get_next_id;
      }
    }

    $next_ancestor_set = '';
    foreach $ancestor (@ancestor_field) {
      if ($parent_set{$ancestor} ne '') {
        $next_ancestor_set .= "$parent_set{$ancestor}\.";
      }
    }

    $ancestor_set = $next_ancestor_set;
    @ancestor_field = split /\./, $ancestor_set;
    if ($ancestor_field[0] eq '') {
      $flag = 0;       # if next_ancestor not found
    } else {
      $flag = 1;
    }

  }

} 

