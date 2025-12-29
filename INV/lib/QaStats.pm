#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaStats;

{
  my ($_inDir, $_ofile, $_pbar_cb);
  my $logwin = '';
  my $_pbar_present = 0;

  my %counts2 =
    (
     ATOM1 => 'sab_lat_tty_atom_tally',
     # ATOM2 => 'sab_tty_suppress_atom_yo_tally',
     ATOM2 => 'sab_tty_suppress_atom_tally',
     ATOM3 => 'inv_sab_tty_status_tbr_suppress_atom_tally',
     ATOM4 => 'inv_saui_atom_notnull_cnt',
     ATOM5 => 'inv_scui_atom_notnull_cnt',
     ATOM6 => 'inv_sdui_atom_notnull_cnt',
     ATOM7 => 'inv_sui_atom_dup_cnt',
     ATOM8 => 'inv_isui_atom_dup_cnt',
     ATOM9 => 'inv_saui_atom_null_cnt',
     ATOM10 => 'inv_scui_atom_null_cnt',
     ATOM11 => 'inv_sdui_atom_null_cnt',

     DEF1 => 'sab_stype_def_tally',
     DEF2 => 'sab_stype_tty_def_tally',
     DEF3 => 'sab_suppress_def_yo_tally',
     DEF4 => 'inv_sab_stype_tty_def_tally',

     CXT1 => 'sab_rela_cxt_par_tally',
     CXT2 => 'sab_rela_tty_cxt_par_tally',
     CXT3 => 'inv_sab_rela_tty_cxt_par_tally',

     REL1 => 'sab_rel_rela_stype1_stype2_rel_tally',
     REL2 => 'sab_rel_rela_stype1_stype2_tty1_tty2_rel_tally',
     REL3 => 'sab_rel_rela_suppress_rel_yo_tally',
     REL4 => 'inv_sab_rel_rela_stype1_stype2_tty1_tty2_rel_tally',
     REL5 => 'inv_sab_rel_rela_stype1_stype2_squal1_squal2_rel_tally',
     REL6 => 'inv_sab_rel_rela_lvl_status_tbr_suppress_rel_tally',

     SAT1 => 'sab_atn_stype_attr_tally',
     SAT2 => 'sab_atn_stype_tty_attr_tally',
     SAT3 => 'sab_atn_stype_rel_rela_attr_tally',
     SAT4 => 'sab_atn_stype_atn_attr_tally',
     SAT5 => 'sab_atn_suppress_attr_yo_tally',
     SAT6 => 'inv_sab_atn_stype_tty_attr_tally',
     SAT7 => 'inv_sab_atn_stype_squal_attr_tally',
     SAT8 => 'inv_sab_atn_lvl_status_tbr_suppress_attr_tally',

     HIST1 => 'sab_stype_hist_tally',
     HIST2 => 'sab_stype_tty_hist_tally',

     MAP1 => 'sab_fromtype_xmapfrom_tally',
     MAP2 => 'sab_rel_rela_xmap_tally',
     MAP3 => 'sab_totype_xmapto_tally',

     SAB1 => 'sab_cnt',

     TTY1 => 'sabtty_cnt',
     TTY2 => 'sab_sabtty_tally',

     DOC1 => 'dockey_type_doc_tally',

     MSET1 => 'inv_mset_stype1_stype2_squal1_squal2_merge_tally'
    );

  my %counts = ();


  # other modes: 1 - extensive.
  my %atoms = ();
  my %relid2relrela=();
  my %srui2relrela=();

  sub new {
    my $class = shift;
    $_inDir = "../src";
    $_ofile = "../tmp/qaStats";
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

  sub process {
    my $class = shift;
    $_inDir = shift;
    $_ofile = "$_inDir/qaStats.src";

    &msg ("Input Directory: $_inDir\n");
    &msg("Output File: $_ofile\n");

    &readAtoms ;
    &$_pbar_cb(20) if ($_pbar_present == 1);
    &readRels ;
    &$_pbar_cb(40) if ($_pbar_present == 1);
    &readCxts ;
    &$_pbar_cb(60) if ($_pbar_present == 1);
    &readAttrs ;
    &$_pbar_cb(80) if ($_pbar_present == 1);
    &readMerges ;
    &$_pbar_cb(100) if ($_pbar_present == 1);
    &readSources ;
    &$_pbar_cb(120) if ($_pbar_present == 1);
    &readTermgroups ;
    &$_pbar_cb(140) if ($_pbar_present == 1);
    &readMRDOC ;
    &$_pbar_cb(160) if ($_pbar_present == 1);

    &dumpResults($_ofile);
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

  sub dumpResults {
    my $ofile = shift;
    open (OUT, ">:utf8", $_ofile) or die "could not open $_ofile file.\n";
    my ($k1, $k2, $k3, $val);
    foreach $k1 (sort keys %counts) {
      $k2 = $counts2{"$k1"};
      foreach $k3 (sort keys %{$counts{"$k1"}}) {
		print OUT "$k1|$k2|$k3|$counts{$k1}->{$k3}|\n";
      }
    }
    close(OUT);
  }



  sub readAtoms {
    &msg("Reading atoms.\n");
    open ATOMS, "< $_inDir/classes_atoms.src" or die "no atoms file. \n";

    my ($said, $vsab, $tg, $tty, $cd, $stat, $tbr, $rlsd, $str, $sup,
		$saui, $scui, $sdui, $lan, $ign, $istr);

    my %suiDup=();
    my %isuiDup=();

    while (<ATOMS>) {
      chomp;
      ($said, $vsab, $tg, $cd, $stat, $tbr, $rlsd, $str, $sup,
       $saui, $scui, $sdui, $lan) = split(/\|/, $_, 14);
      $tty = (split("/", $tg))[1];

      $atoms{$said} = $tty;

      #Atom1 sab_lat_tty_atom_tally
      $counts{'ATOM1'}{"$vsab,$lan,$tty"}++;

      #Atom2 sab_tty_suppress_atom_tally 
      $counts{'ATOM2'}{"$vsab,$tty,$sup"}++;

      #Atom3 inv_sab_tty_status_tbr_supress_atom_tally
      $counts{'ATOM3'} {"$vsab,$tty,$stat,$tbr,$sup"}++;

      #Atom4 inv_saui_atom_notnull_cnt
      $counts{'ATOM4'}{"saui"}++ if ($saui ne '');

      #Atom5 inv_scui_atom_notnull_cnt
      $counts{'ATOM5'}{"scui"}++ if ($scui ne '');

      #Atom6 inv_sdui_atom_notnull_cnt
      $counts{'ATOM6'}{"sdui"}++ if ($sdui ne '');

      $suiDup{"$str"}++;
      $istr = uc($str);
      $isuiDup{"$istr"}++;

      #Atom9 inv_saui_atom_null_cnt
      $counts{'ATOM9'}{"saui"}++ if ($saui eq '');

      #Atom10 inv_scui_atom_null_cnt
      $counts{'ATOM10'}{"scui"}++ if ($scui eq '');

      #Atom11 inv_sdui_atom_null_cnt
      $counts{'ATOM11'}{"sdui"}++ if ($sdui eq '');


    }
    my ($key, $val);
    foreach (($key, $val) = each %suiDup) {
      #Atom7 inv_sui_atom_dup_cnt
      $counts{'ATOM7'}{"Count"}++ if ($val > 1);
    }

    foreach (($key, $val) = each %suiDup) {
      #Atom8 inv_isui_atom_dup_cnt
      $counts{'ATOM8'}{"Count"}++ if ($val > 1);
    }

    close (ATOMS);
    &msg("Done reading atoms.\n");
  }

  sub readRels {
    &msg("Reading Rels.\n");
    open RELS, "< $_inDir/relationships.src" or die "no rels file.\n";
    my ($tty1, $tty2, $jnk, $key, @F, $msg);
    my ($rid, $lvl, $id1, $rel, $rela, $id2, $vsab, $sol, $stat, $tbr, $rlsd);
    my ($sup, $idt1, $idq1, $idt2, $idq2, $srui, $rlgp);
    my ($ign, $tty1, $tty2);

    while (<RELS>) {
      chomp;
      ($rid, $lvl, $id1, $rel, $rela, $id2, $vsab, $sol, $stat, $tbr, $rlsd,
       $sup, $idt1, $idq1, $idt2, $idq2, $srui, $rlgp) = split(/\|/, $_, 18);

      # remember relid2relrela and srui2relrela;
      $relid2relrela{"$rid"} = "$rel,$rela";
      $srui2relrela{"$srui"} = "$rel,$rela" if ($srui ne '');

      #Rel1a rel - sab_rel_rela_stype1_stype2_rel_tally
      # [must provide in both directions?????]
      $counts{'REL1'}{"$vsab,$rel,$rela,$idt1,$idt2"}++;

      #Rel2a rel - sab_rel_rela_stype1_stype2_tty1_tty2_rel_tally
      # [do this for type1/2 = SRC_ATOM_ID]
      if ($idt1 eq 'SRC_ATOM_ID' && $idt2 eq 'SRC_ATOM_ID') {
		$tty1 = $atoms{"$id1"};
		$tty2 = $atoms{"$id2"};
		$counts{'REL2'}{"$vsab,$rel,$rela,$idt1,$idt2,$tty1,$tty2"}++;
      }

      #Rel3a rel - sab_rel_rela_suppress_rel_yo_tally[supp in Y|O]
      $counts{'REL3'}{"$vsab,$rel,$rela"}++ if ($sup =~ /Y|O/);

      #Rel4 inv_sab_rela_rela_stype1_stype2_tty1_tty2_rel_tally
      #    for CODE_TERMGROUP and CODE_ROOT_TERMGROUP
      if (($idt1 eq 'CODE_TERMGROUP' || $idt1 eq 'CODE_ROOT_TERMGROUP')
		  && ($idt2 eq 'CODE_TERMGROUP' || $idt2 eq 'CODE_ROOT_TERMGROUP')) {
		($ign, $tty1) = split(/\//, $idq1);
		($ign, $tty2) = split(/\//, $idq2);
		$counts{'REL4'}{"$vsab,$rel,$idt1,$idt2,$tty1,$tty2"}++;
	  }

      #Rel5 inv_sab_rela_rela_stype1_stype2_squal1_squal3_rel_tally
      $counts{'REL5'}{"$vsab,$rel,$idt1,$idt2,$idq1,$idq2"}++;

      #Rel6 inv_sab_rela_rela_lvl_status_tbr_supress_rel_tally
      $counts{'REL6'}{"$vsab,$rel,$rela,$lvl,$stat,$tbr,$sup"}++;


    }
    close (RELS);
    &msg("Done Reading Rels.\n");
  }

  sub readCxts {
    &msg("Reading Rels.\n");
    open CXTS, "< $_inDir/contexts.src" or die "no cxts file.\n";

    my ($said1, $rel, $rela, $said2, $vsab, $ign);
    my ($id1, $type1, $qual1, $id2, $type2, $qual2);
    my ($ign, $tty1, $tty2);


    while (<CXTS>) {
      chomp;
      ($said1, $rel, $rela, $said2, $vsab, $ign, $ign, $ign, $ign, $ign, $ign,
       $id1, $type1, $qual1, $id2, $type2, $qual2) = split(/\|/, $_, 17);

      #Cxt1 sab_rela_cxt_par_tally [rel = PAR]
      $counts{'CXT1'}{"$vsab,$rela"}++ if ($rel eq 'PAR');

      #Cxt2 sab_rela_tty_cxt_par_tally [rel = PAR && sgtype1/2 in[AUI/SAUI]
      #$counts{'CXT2'}{""}++ if ($rel eq 'PAR');

      #Cxt3 inv_sab_rela_tty_cxt_par_tally [rel = PAR && sgtype1/2 in[AUI/SAUI]
      #$counts{'CXT3'}{""}++ if ($rel eq 'PAR');

      #Rel1b cxt - sab_rel_rela_stype1_stype2_rel_tally
      # [must provide in both directions?????]
      $counts{'REL1'}{"$vsab,$rel,$rela,$type1,$type2"}++;

      #Rel2b cxt - sab_rel_rela_stype1_stype2_tty1+tty2_rel_tally
      # [do this for type1/2 = SRC_ATOM_ID]
      $tty1 = $atoms{"$said1"};
      $tty2 = $atoms{"$said2"};
      $counts{'REL2'}{"$vsab,$rel,$rela,$type1,$type2,$tty1,$tty2"}++;

      #Rel3b cxt - sab_rel_rela_suppress_rel_yo_tally[supp in Y|O]
      # there is no suppress flag in cxt file. so ignore.
      #$counts{'REL3'}{"$vsab,$rel,$rela"}++ if ($sup =~ /Y|O/);



	
    }
    close (CXTS);
    &msg("Done Reading Rels.\n");
  }


  sub readAttrs {
    my $kk = 0;
    &msg("Reading Attributes.\n");
    open ATTRS, "< $_inDir/attributes.src" or die "no attr file. \n";
    my ($nam, $tty, $tty2, @F, $key, $msg, $vsab, $stype);

    my ($tty, $atid, $sgid, $lvl, $atn, $atv, $vsab, $stat, $tbr, $rlsd,
		$sup, $sgtype, $sgqual, $satui, $ign);

    while (<ATTRS>) {
      $kk++;
      chomp;
      ($atid, $sgid, $lvl, $atn, $atv, $vsab, $stat, $tbr, $rlsd,
       $sup, $sgtype, $sgqual, $satui) = split(/\|/, $_, 15);

      if (($kk % 2000) == 0) {
		&msg(">");
	  }
      if (($kk % 100000) == 0) {
		&msg("\n$kk: $sgid, $sgtype, $sgqual\n");
	  }

      $tty = $sgtype eq 'SRC_ATOM_ID' ? $atoms{"$sgid"} : '';

      if ($atn eq 'DEFINITION') {
		#Def1 sab_stype_def_tally [ATN=DEFINITION]
		$counts{'DEF1'}{"$vsab,$sgtype"}++;

		#Def2 sab_stype_tty_def_tally [ATN = DEFINITION & 
		#          stype = SRC_ATOM_ID]
		$counts{'DEF2'}{"$vsab,$sgtype,$tty"}++ if ($tty ne '');

		#Def3 sab_supress_def_yo_tally [ATN=DEFINITION && sup = Y|O]
		$counts{'DEF3'}{"$vsab"}++ if ($sup =~ /Y|O/);

      }	

      #Sat1 sab_atn_stype_attr_tally
      $counts{'SAT1'}{"$vsab,$atn,$sgtype"}++;

      #Sat2 sab_atn_stype_tty_attr_tally [stype in SRC_ATOM_ID]
      $counts{'SAT2'}{"$vsab,$atn,$sgtype,$tty"}++ if ($tty ne '');


      #Sat3 sab_atn_stype_rel_rela_attr_tally [stype = RUI/SRUI]
      if ($sgtype eq 'SRC_REL_ID') {
		$counts{'SAT3'}{"$vsab,$atn,$sgtype,$relid2relrela{$sgid}"}++;
      } elsif ($sgtype eq 'SOURCE_RUI' || $sgtype eq 'ROOT_SOURCE_RUI') {
		$counts{'SAT3'}{"$vsab,$atn,$sgtype,$srui2relrela{$sgid}"}++;
      }

      #Sat4??? sab_atn_stype_atn_attr_tally [stype in SRC_ATOM_ID]
      # ignore this. This is attrs to attrs (for future).
      #$counts{'SAT4'}{"??"}++;

      #Sat5 sab_atn_suppress_attr_yo_tally [supp in Y|O]
      $counts{'SAT5'}{"$vsab,$atn"}++ if ($sup =~ /Y|O/);

      if ($atn eq 'COMPONENTHISTORY') {
		#Hist1 sab_stype_hist_tally [atn = COMPONENTHISTORY]
		$counts{'HIST1'}{"$vsab,$sgtype"}++;

		#Hist2 sab_stype_tty_hist_tally [atn=COMPONENTHISTORY &&
		#             stype = SRC_ATOM_ID]
		$counts{'HIST2'}{"$vsab,$sgtype,$tty"}++ if ($tty ne '');
      }

      if ($atn eq 'XMAPFROM') {
		#Map1 sab_fromtype_xmapfrom_tally
		@F = split(/\~/, $atv);
		$counts{'MAP1'}{"$vsab,$F[3]"}++;
      } elsif ($atn eq 'XMAP') {
		#Map2 sab_rel_rela_xmap_tally
		@F = split(/\~/, $atv);
		$counts{'MAP2'}{"$vsab,$F[3],$F[4]"}++;
      } elsif ($atn eq 'XMAPTO') {
		#Map3 sab_totype_xmapto_tally
		@F = split(/\~/, $atv);
		$counts{'MAP3'}{"$vsab,$F[3]"}++;
      }

      #Ddef4 inv_sab_stype_tty_def_tally [ATN=DEFINITION &&
      #       sgtype = CODE_TERMGROUP|CODE_ROOT_TERMGROUP]
      if ($sgtype eq 'CODE_TERMGROUP' || $sgtype eq 'CODE_ROOT_TERMGROUP') {
		($ign, $tty2) = split(/\//, $sgqual);
		$counts{'DEF4'}{"$vsab,$sgtype,$tty2"}++
      }

    }
    close (ATTRS);
    &msg("Done Reading Attributes.\n");
  }




  sub readMerges {
    &msg("Reading Merges.\n");
    open MERGES, "< $_inDir/mergefacts.src" or die "no merges file.\n";
    my ($tty1, $tty2, $jnk, $key, @F, $msg);
    my ($mset, $idt1, $idq1, $idt2, $idq2, $ign);

    while (<MERGES>) {
      chomp;
      @F = split(/\|/, $_);
      $mset = $F[1];
      $idt1 = $F[8];
      $idq1 = $F[9];
      $idt2 = $F[10];
      $idq2 = $F[11];

      # f0/2 -> aid1/2; f8/10 -> type1/2; f9/11 -> qual1/2; f7 -> mset

      #Mset1 inv_mset_stype1_stype2_squal1_squal2
      $counts{'MSET1'}{"$mset,$idt1,$idt2,$idq1,$idq2"}++;
    }
    close (MERGES);
    &msg("Done Reading Merges.\n");
  }

  sub readSources {
    &msg("Reading Sources.\n");
    open SOURCES, "< $_inDir/sources.src" or die "no sources file.\n";
    my ($vsab, @F);
    
    while (<SOURCES>) {
      chomp;
      @F = split(/\|/, $_);
      $vsab = $F[0];
      
      #SAB1 sab_cnt
      $counts{'SAB1'}{""}++;
      
    }
    close (SOURCES);
    &msg("Done Reading Sources.\n");
  }
  
  sub readTermgroups {
    &msg("Reading Termgroups.\n");
    open TERMGROUPS, "< $_inDir/termgroups.src" or die "no termgroups file.\n";
    my ($tgn,$tg,$ign,$tty, @F);
    
    while (<TERMGROUPS>) {
      chomp;
      @F = split(/\|/, $_);
      $tgn = $F[0];
      ($tg,$ign)   = split(/\//,$tgn);
      $tty = $F[5];
      
      #TTY1 sabtty_cnt
      $counts{'TTY1'}{""}++;
      
      #TTY2 sab_sabtty_cnt
      $counts{'TTY2'}{"$tg"}++;
      
    }
    close (TERMGROUPS);
    &msg("Done Reading Termgroups.\n");
  }

  sub readMRDOC {
    &msg("Reading MRDOC.\n");
    open MRDOC, "< $_inDir/MRDOC.RRF" or die "no MRDOC file.\n";
    my ($dockey, $type, @F);

    while (<MRDOC>) {
      chomp;
      @F = split(/\|/, $_);
      $dockey = $F[0];
      $type = $F[2];

      #DOC1 dockey_type_doc_tally
      $counts{'DOC1'}{"$dockey,$type"}++;

    }
    close (MRDOC);
    &msg("Done Reading MRDOC.\n");
  }
  
  # to be handled
  # DCO1 dockey_type_doc_tally;


}
1

