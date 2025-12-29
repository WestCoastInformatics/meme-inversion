#!/usr/bin/perl
#
use Getopt::Std;

my %options=();
getopts("i:f:", \%options);

our $inDir;
if (defined $options{i}) { $inDir = $options{i}; } 
else { $inDir = "../src"; }

our $outFile;
if (defined $options{f}) { $outFile = $options{f}; } 
else { $outFile = '../temp/defaults' }

print "inDir => $inDir\n";
print "outfile => $outFile\n";


our %a_defs=();
our %m_defs=();
our %at_defs=();
our %r_defs=();
our %id2tty=();

our %codeMap = ('SRC_ATOM_ID', 1,
		'ATOM_ID', 'AID',
		'SOURCE_ATOM_ID', 1,
		'CONCEPT_ID', 'CID',
		'AUI', 'AUI',
		'CUI', 'CUI',
		'RUI', 'RUI',
		'SOURCE_AUI', 'SAUI',
		'SOURCE_CUI', 'SCUI',
		'SOURCE_DUI', 'SDUI',
		'SOURCE_RUI', 'SRUI',
		'ROOT_SOURCE_AUI', 'RSAUI',
		'ROOT_SOURCE_CUI', 'RSCUI',
		'ROOT_SOURCE_DUI', 'RSDUI',
		'ROOT_SOURCE_RUI', 'RSRUI',
		'CODE_TERMGROUP', 2,
		'CODE_STRIPPED_TERMGROUP', 2,
		'CODE_SOURCE', 3,
		'CODE_STRIPPED_SOURCE', 3,
		'CUI_SOURCE', 3,
		'CUI_ROOT_SOURCE', 3,
		'CUI_STRIPPED_SOURCE', 3
	       );

sub prTime {
  my $str = shift;
  my $mdt = `date`;
  #print ERRS "$str => $mdt\n";
  print "$str =>  $mdt\n";
}

our $ii = 0;
sub getTTY {
  my $id = shift(@_);;
  my $type = shift(@_);
  my $qual = shift(@_);
  my ($ign, $val);

  if ($val = $codeMap{"$type"}) {
    if ($val == 1) {
      return $id2tty{"$id"};
    } elsif ($val == 2) {
      ($ign, $tty) = split(/\//, $qual);
      return $tty;
    } elsif ($val == 3) {
      return $qual;
    } else {
      return $val;
    }
  }
  return 'NONE';
}



sub processAtoms {
  open ATOMS, "< $inDir/classes_atoms.src" or die "no atoms file. \n";

  my ($ign, $aid, $sab, $sabtty, $tty, $status, $tbr, $rlsd, $supp);
  while (<ATOMS>) {
    chomp;
    ($aid, $ign, $sabtty, $ign, $status, $tbr, $rlsd, $ign, $supp) 
      = split(/\|/);
    # get tty
    ($sab, $tty) = split(/\//, $sabtty);
    $id2tty{"$aid"} = $tty;
    $a_defs{"$tty|$status\_$tbr\_$rlsd\_$supp"}++;
  }
  close(ATOMS);
}

sub processAttrs {
  my ($ign, $aid, $lvl, $name, $sab, $stat, $tbr, $rlsd, $supp, $idt,$idq, $tty);

  # read attrs from file
  open ATTRS, "< $inDir/attributes.src" or die "no attr file.\n";
  while (<ATTRS>) {
    chomp;
    ($ign, $aid, $lvl, $name, $ign, $sab, $stat, $tbr, $rlsd, 
     $supp, $idt, $idq) = split(/\|/, $_);

    $tty = &getTTY($aid, $idt, $idq);
    $at_defs{"$tty\_$name\_$lvl|$stat\_$tbr\_$rlsd\_$supp"}++;
  }
  close(ATTRS);
}


sub processMerges {
  my ($ign, $id1, $id2, $mlvl, $mset, $iv, $dem, $cstat, $t1, $q1, $t2, $q2);
  my ($tty1, $tty2);

  open MRGS, "< $inDir/mergefacts.src" or die "no merge file.\n";
  while (<MRGS>) {
    chomp;
    ($id1, $mlv, $id2, $ign, $iv, $dem, $cstat, $mset, $t1, $q1, $t2, $q2) 
      = split(/\|/, $_);
    $tty1 = &getTTY($id1, $t1, $q1);
    $tty2 = &getTTY($id2, $t2, $q2);
    $m_defs{"$tty1\_$tty2\_$mset\_$mlv|$iv\_$dem\_$cstat"}++;
  }
  close(MRGS);
}


sub processRels {
  my ($ign, $rlvl, $id1, $rel, $rela, $id2, $stat, $tbr, $rlsd, $supp);
  my ($t1, $q1, $t2, $q2, $tty1, $tty2);

  open RELS, "< $inDir/relationships.src" or die "no rel file.\n";
  while (<RELS>) {
    chomp;
    ($ign, $rlvl, $id1, $rel, $rela, $id2, $ign, $ign, $stat, $tbr, 
     $rlsd, $supp, $t1, $q1, $t2, $q2)  = split(/\|/, $_);
    $tty1 = &getTTY($id1, $t1, $q1);
    $tty2 = &getTTY($id2, $t2, $q2);
    $r_defs{"$tty1\_$tty2\_$rlvl\_$rel\_$rela|$stat\_$tbr\_$rlsd\_$supp"}++;
  }
  close(RELS);
}

sub dumpResults {
  my ($key, $ln, $val);
  open OUT, "> $outFile" or die "no defaults.src file.\n";

  print OUT "Atom | tty | status-tbr-rlsd-supp | count\n";
  $ln = 1;
  foreach $key (sort keys (%a_defs)) {
    $val = $a_defs{"$key"};
    print OUT "$ln|$key|$val\n";
    $ln++;
  }
  print OUT "\n\n";
  $ln = 1;
  print OUT "Attr | tty-name-lvl | stat-tbr-rlsd-supp\n";
  foreach $key (sort keys (%at_defs)) {
    $val = $at_defs{"$key"};
    print OUT "$ln|$key|$val\n";
    $ln++;
  }
  print OUT "\n\n";
  $ln = 1;
  print OUT "Mrgs | tty1-tty2-mset- lvl | iv-dem-cstat\n";
  foreach $key (sort keys (%m_defs)) {
    $val = $m_defs{"$key"};
    print OUT "$ln|$key|$val\n";
    $ln++;
  }
  print OUT "\n\n";
  $ln = 1;
  print OUT "Rels | tty1-tty2-lvl-rel-rela | stat-tbr-rlsd-supp\n";
  foreach $key (sort keys (%r_defs)) {
    $val = $r_defs{"$key"};
    print OUT "$ln|$key|$val\n";
    $ln++;
  }
  close (OUT);
}

sub runMain {
  &prTime("Begin Atoms");
  &processAtoms;
  &prTime("Begin Atts");
  &processAttrs;
  &prTime("Begin Merges");
  &processMerges;
  &prTime("Begin Rels");
  &processRels;
  &prTime("End Rels");
  &dumpResults;
  &prTime("End Dump results.");
}

&runMain;
