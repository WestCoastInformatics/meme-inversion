#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package SrcStats;

{
  my ($_inDir, $_ofile, $_pbar_cb);
  my $logwin = '';
  my $_pbar_present = 0;

  # other modes: 1 - extensive.
  my $_mode = 0;
  my %atoms = ();
  my %codeMap = ('SRC_ATOM_ID', '1',
				 'ATOM_ID', 'AID',
				 'SOURCE_ATOM_ID', '1',
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
				 'CODE_TERMGROUP', 'CT',
				 'CODE_STRIPPED_TERMGROUP', 'CST',
				 'CODE_SOURCE', 'CS',
				 'CODE_STRIPPED_SOURCE', 'CSS',
				 'CUI_SOURCE', 'CUIS',
				 'CUI_ROOT_SOURCE', 'CUIRS',
				 'CUI_STRIPPED_SOURCE', 'CRUISS'
				);

  sub getTTY {
    my $id = shift(@_);;
    my $type = shift(@_);
    my $qual = shift(@_);
    my ($ign, $val, $tty);

    if ($val = $codeMap{"$type"}) {
      if ($val eq '1') {
		return $atoms{"$id"};
      } else {
		return "$val<$qual>";
      }
    }
    return 'NONE';
  }



  sub new {
    my $class = shift;
    $_inDir = "../src";
    $_ofile = "../tmp/stats";
    my $ref = {};
    return bless ($ref, $class);
  }

  sub setLogwin {
    my $class = shift;
    if (@_ > 0) {
      $logwin = shift;
    }
  }

  sub setPbar {
    my $class = shift;
    $_pbar_cb = shift;
    $_pbar_present = 1;
  }

  sub setMode {
    my $class = shift;
    if (@_ > 0) { 
      my $temp = shift;
      if ($temp >= 0 && $temp < 2) {
		$_mode = $temp;
      } else {
		$_mode = 0;
      }
    }
    &msg("Current mode is $_mode\n");
  }

  sub process {
    my $class = shift;
    $_inDir = shift;
    $_ofile = shift;

    &msg ("Input Directory: $_inDir\n");
    &msg("Output File: $_ofile\n");

    open (OUT, ">:utf8", $_ofile) or die "could not open $_ofile file.\n";
    &readAtoms ;
    &$_pbar_cb(25) if ($_pbar_present == 1);
    &readAttrs ;
    &$_pbar_cb(50) if ($_pbar_present == 1);
    &readMerges ;
    &$_pbar_cb(75) if ($_pbar_present == 1);
    &readRels ;
    &$_pbar_cb(100) if ($_pbar_present == 1);
    close(OUT);
    &msg("Finished collecting stats.\n");
  }

  sub msg {
    my $msg = shift;
    #if ($logwin eq '') { print "$msg"; }
    #else { $logwin->insert('end', $msg); }
    print "$msg";
    if ($logwin ne '') {
      $logwin->insert('end', $msg);
    }
  }




  sub readAtoms {
    &msg("Reading atoms.\n");
    open ATOMS, "< $_inDir/classes_atoms.src" or die "no atoms file. \n";
    my $many = 0;
    my (@F, $tty, $id, $key, $msg);
    my %ttycount = ();
    while (<ATOMS>) {
      chomp;
      @F = split(/\|/, $_);
      $tty = (split("/", $F[2]))[1];
      $id = $F[0];
      $atoms{$id} = $tty;
      if ($_mode == 1) {
		#$ttycount{"$tty<$F[4]$F[5]$F[6]$F[8]>"}++;
		$ttycount{"$F[2]<$F[4]$F[5]$F[6]$F[8]>"}++;
      } else {
		#$ttycount{$tty}++;
		$ttycount{"$F[2]"}++;
      }
    }
    foreach $key (sort keys (%ttycount)) {
      $msg = "A|$key|$ttycount{$key}\n";
      print OUT "$msg";
      &msg("$msg");
    }
    close (ATOMS);
    &msg("Done reading atoms.\n");
  }

  sub readAttrs {
    my $kk = 0;
    &msg("Reading Attributes.\n");
    open ATTRS, "< $_inDir/attributes.src" or die "no attr file. \n";
    my ($nam, $tty, @F, $key, $msg);
    my %attrcount = ();
    while (<ATTRS>) {
      $kk++;
      chomp;
      @F = split(/\|/, $_);
      if (($kk % 2000) == 0) {
		&msg(">");
      }
      if (($kk % 100000) == 0) {
		&msg("\n$kk: $F[1], $F[10], $F[11]\n");
      }
      $tty = &getTTY($F[1], $F[10], $F[11]);
      if ($_mode == 1) {
		$attrcount{"${tty}_${F[2]}_${F[3]}<${F[6]}${F[7]}${F[8]}${F[9]}>"}++;
      } else {
		$attrcount{"${tty}_${F[2]}_${F[3]}"}++;
      }
    }
    foreach $key (sort keys (%attrcount)) {
      $msg = "AT|$key|$attrcount{$key}\n";
      print OUT "$msg";
      &msg("$msg");
    }
    close (ATTRS);
    &msg("Done Reading Attributes.\n");
  }




  sub readMerges {
    &msg("Reading Merges.\n");
    open MERGES, "< $_inDir/mergefacts.src" or die "no merges file.\n";
    my ($tty1, $tty2, $jnk, $key, @F, $msg);
    my %mrcount = ();
    while (<MERGES>) {
      chomp;
      @F = split(/\|/, $_);
      # f0/2 -> aid1/2; f8/10 -> type1/2; f9/11 -> qual1/2; f7 -> mset

      $tty1 = &getTTY($F[0], $F[8], $F[9]);
      $tty2 = &getTTY($F[2], $F[10], $F[11]);

      if ($_mode == 1) {
		$mrcount{"${F[7]}_${tty1}_${tty2}<$F[5]$F[6]>"}++;
      } else {
		$mrcount{"${F[7]}_${tty1}_${tty2}"}++;
      }
    }
    foreach $key (sort keys (%mrcount)) {
      $msg = "M|$key|$mrcount{$key}\n";
      print OUT "$msg";
      &msg("$msg");
    }
    close (MERGES);
    &msg("Done Reading Merges.\n");
  }

  sub readRels {
    &msg("Reading Rels.\n");
    open RELS, "< $_inDir/relationships.src" or die "no rels file.\n";
    my ($tty1, $tty2, $jnk, $key, @F, $msg);
    my %relcount = ();
    while (<RELS>) {
      chomp;
      @F = split(/\|/, $_);
      # f0/2 -> aid1/2; f12/14 -> type1/2, f13/15 -> qual1/2; f3/4 -> rel/a;

      $tty1 = &getTTY($F[2], $F[12], $F[13]);
      $tty2 = &getTTY($F[5], $F[14], $F[15]);
      if ($_mode == 1) { 
		$relcount{"${F[3]}_${tty1}_${tty2}_$F[4]<$F[8]$F[9]$F[10]$F[11]>"}++;
      } else {
		$relcount{"${F[3]}_${tty1}_${tty2}_$F[4]"}++;
      }
    }
    foreach $key (sort keys (%relcount)) {
      $msg = "R|$key|$relcount{$key}\n";
      print OUT "$msg";
      &msg("$msg");
    }
    close (RELS);
    &msg("Done Reading Rels.\n");
  }
}
1
