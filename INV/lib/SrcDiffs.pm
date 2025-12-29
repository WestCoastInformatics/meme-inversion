#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

use iutl;

package SrcDiffs;
no warnings;

{
  my ($_theLog, $_theCfg);
  my $_logwin = '';
  my $_pbar_cb;
  my $_pbar_present = 0;

  my $_inADir = '';
  my $_inBDir = '';
  my $_outDir = '';
  my $_idMapFile = '';
  my $_whichP = '';

  my @hierTTYs = ();
  my @inclAtoms = ();
  my @exclAtoms = ();
  my @inclAttrs = ();
  my @exclAttrs = ();

  my $key;
  my %mthTTYs = ();
  my %incAtoms=();
  my %excAtoms=();
  my %incAttrs=();
  my %excAttrs=();

  my %A2Bids =();
  my %B2Aids = ();
  my %AidInfo=();
  my %BidInfo=();
  my %A2BRids=();
  my %B2ARids=();

  my @multAttrs = ();

  my $_aln = 0;
  my $_bln = 0;

  my $initialized = 0;
  # a quick way to find atoms without saving intermediate info.
  # to do that set the following to 0
  my $_saveInt = 1;
  #

  sub init {
    my ($self, $log, $cfg) = @_;
    $_theLog = $log;
    $_theCfg = $cfg;

    # first read the config file if any; ADir, BDir, OutDir, mthTTY, IdMap
    # inclAtoms, inclAttrs, Which

    $_inADir = $$_theCfg->getEle('ADir', "../src_old");
    $_inBDir = $$_theCfg->getEle('BDir', "../src");
    $_outDir = $$_theCfg->getEle('OutDir', "../temp");
    $_whichP = $$_theCfg->getEle('Which', 31);
    $_idMapFile = $$_theCfg->getEle('IdMap', "$_outDir/idMap.out");

    @hierTTYs = $$_theCfg->getList('mthTTY');
    foreach $key (@hierTTYs) {
      $mthTTYs{"$key"}++;
    }

    @inclAtoms = $$_theCfg->getList('inclAtoms');
    foreach $key (@inclAtoms) {
      $incAtoms{"$key"}++;
    }

    @exclAtoms = $$_theCfg->getList('exclAtoms');
    foreach $key (@exclAtoms) {
      $excAtoms{"$key"}++;
    }

    @inclAttrs = $$_theCfg->getList('inclAttrs');
    foreach $key (@inclAttrs) {
      $incAttrs{"$key"}++;
    }

    @exclAttrs = $$_theCfg->getList('exclAttrs');
    foreach $key (@exclAttrs) {
      $excAttrs{"$key"}++;
    }
    $initialized = 1;

  }

  sub new {
    my $class = shift;
    #&init;
    my $ref = {};
    return bless ($ref, $class);
  }

  sub setLogwin {
    my $class = shift;
    if (@_ > 0) {
      $_logwin = shift;
    }
  }

  sub setPbar {
    my $class = shift;
    $_pbar_cb = shift;
    $_pbar_present = 1;
  }

  sub msg {
    my $msg = shift;
    print "$msg";
    if ($_logwin ne '') {
      $_logwin->insert('end', $msg);
    }
  }

  sub getADir { return $_inADir; }
  sub getBDir { return $_inBDir; }
  sub getODir { return $_outDir; }
  sub getWhich { return $_whichP; }
  sub setADir { my $class = shift; $_inADir = shift; }
  sub setBDir { my $class = shift; $_inBDir = shift; }
  sub setODir { my $class = shift; $_outDir = shift; }
  sub setWhich { my $class = shift; $_whichP = shift; }

  sub getHierTTYs { return @hierTTYs; }
  sub getInclAtoms { return @inclAtoms; }
  sub getExclAtoms { return @exclAtoms; }
  sub getInclAttrs { return @inclAttrs; }
  sub getExclAttrs { return @exclAttrs; }


  sub readAtoms {
    print "Processing atoms.\n";
    if ($_whichP & 1) {
      print "Reading Atoms files..\n";

      my ($inp, @val, $strTg, $ln, $key, $akey, $id1, $ln1, $ln2, $tty, @inp);
      my ($aStr, %B_str2id, %A_str2id, $sab);

      # collect all A atoms.
      open (A_ATOMS, "<:utf8", "$_inADir/classes_atoms.src")
		or die "no atoms1 file. \n";
      while (<A_ATOMS>) {
		chomp;
		@inp = split(/\|/);
		$aStr = $inp[7];		# get termgroup
		($sab, $tty) = split(/\//, $inp[2], 3);

		if (defined ($mthTTYs{"$tty"})) {
		  #tg, string - atomid
		  $strTg = "$inp[2]|$inp[4]|$inp[5]|$inp[6]|$inp[8]|$inp[12]|$aStr";
		} else {
		  #tg, code, saui, scui, sdui, string - atomid
		  $strTg = "$inp[2]|$inp[3]|$inp[4]|$inp[5]|$inp[6]|$inp[8]|$inp[9]|$inp[10]|$inp[11]|$inp[12]|$aStr";
		}
		push(@{$A_str2id{"$strTg"}}, $inp[0]);
		$AidInfo{"$inp[0]"} = "$tty|$inp[3]|$inp[4]|$inp[5]|$inp[6]|$inp[8]|$inp[9]|$inp[10]|$inp[11]";
		$_aln++;
      }
      close(A_ATOMS);

      # check if A has any duplicate atoms.
      my $dupa =1;
      foreach $key (keys (%A_str2id)) {
		@val = @{$A_str2id{"$key"}};
		$ln = @val;
		if ($ln > 1) {
		  &msg("DupAtom in A:  $dupa\t-> @val \<$key\>\n");
		  $dupa++;
		}
		last if ($dupa > 10);
      }


      # collect all B atoms.
      open (B_ATOMS, "<:utf8", "$_inBDir/classes_atoms.src")
		or die "no atoms2 file. \n";
      while (<B_ATOMS>) {
		chomp;
		@inp = split(/\|/);
		$aStr = $inp[7];

		# get tty - do not include codes for hierarchy atoms.
		($sab, $tty) = split(/\//, $inp[2], 3);
		if (defined ($mthTTYs{"$tty"})) {
		  #tg, string - atomid
		  #$strTg = "$inp[2]|$aStr";
		  $strTg = "$inp[2]|$inp[4]|$inp[5]|$inp[6]|$inp[8]|$inp[12]|$aStr";
		} else {
		  #tg, code, saui, scui, sdui, string - atomid
		  #$strTg = "$inp[2]|$inp[3]|$inp[9]|$inp[10]|$inp[11]|$aStr";
		  $strTg = "$inp[2]|$inp[3]|$inp[4]|$inp[5]|$inp[6]|$inp[8]|$inp[9]|$inp[10]|$inp[11]|$inp[12]|$aStr";
		}
		push(@{$B_str2id{"$strTg"}}, $inp[0]);
		#$BidInfo{"$inp[0]"} = "$tty|$inp[3]|$inp[9]|$inp[10]|$inp[11]";
		$BidInfo{"$inp[0]"} = "$tty|$inp[3]|$inp[4]|$inp[5]|$inp[6]|$inp[8]|$inp[9]|$inp[10]|$inp[11]";
		$_bln++;
      }
      close(B_ATOMS);

      # check if B has any duplicate atoms.
      my $dupb = 1;
      foreach $key (keys (%B_str2id)) {
		@val = @{$B_str2id{"$key"}};
		$ln = @val;
		if ($ln > 1) {
		  &msg("DupAtom in B: $dupb\t-> @val \<$key\>\n");
		  $dupb++;
		}
		last if ($dupb > 10);
      }

      &msg("Total Atoms in A - $_aln\n");
      &msg("Total Atoms in B - $_bln\n");

      if (($dupa > 1) or ($dupb > 1)) {
		&msg("Sources have duplicate atoms. Bailing out.\n");
		exit 1;
      } else {
		&msg("No duplicates in either source.\n");
      }

      # dump atom differenes.
      $a = 0;
      my ($temp, $ign);
      $temp = @inclAtoms;
      # print A - B atoms
      open (AmB_Atoms, ">:utf8", "$_outDir/AmB_atoms.src") 
		or die "could not open AmB_atoms file.\n";
      foreach $akey (sort keys (%A_str2id)) {
		($id1) = @{$A_str2id{"$akey"}};
		($tty) = split (/\|/, $AidInfo{"$id1"}, 2);
		if (defined(@{$B_str2id{"$akey"}})) {
		  ($A2Bids{"$id1"}) = @{$B_str2id{"$akey"}};
		} else {
		  $A2Bids{"$id1"} = 0;
		  if ((($temp == 0) or (defined ($incAtoms{"$tty"})))
			  && (!defined($excAtoms{"$tty"}))) {
			print AmB_Atoms "$a -> $id1\<$AidInfo{$id1}\> \n\t$akey\n";
			$a++;
		  }
		}
      }
      close(AmB_Atoms);

      $b = 0;
      # print B - A atoms
      open (BmA_Atoms, ">:utf8", "$_outDir/BmA_atoms.src") 
		or die "could not open BmA_atoms file.\n";
      foreach $akey (sort keys (%B_str2id)) {
		($id1) = @{$B_str2id{"$akey"}};
		($tty) = split(/\|/, $BidInfo{"$id1"}, 2);
		if (defined(@{$A_str2id{"$akey"}})) {
		  ($B2Aids{"$id1"}) = @{$A_str2id{"$akey"}};
		} else {
		  $B2Aids{"$id1"} = 0;
		  if ((($temp == 0) or (defined ($incAtoms{"$tty"})))
			  && (!defined($excAtoms{"$tty"}))) {
			print BmA_Atoms "$b -> $id1\<$BidInfo{$id1}\> \n\t$akey\n";
			$b++;
		  }
		}
      }
      close(BmA_Atoms);

      # release memory for str hashes.
      $ln1 = keys %A2Bids;
      $ln2 = keys %B2Aids;
      &msg("Aids => $ln1 \<$a\>\nBids => $ln2 \<$b\>\n");

      %A_str2id=();
      %B_str2id=();
      # now write the mappings into a file for futher use.
      # do this only if q option is not specified.
      if ($_saveInt == 1) {
		&msg("Dumping idmap info to idMap.\n");
		my ($x1, $x2, $inf1, $inf2);
		open (ABIDS, ">:utf8", $_idMapFile) or die "could not open $_idMapFile.\n";

		# first line, write mult attributes.
		@multAttrs = $$_theCfg->getList('multAttrs');
		my $maLn = @multAttrs;
		if ($maLn == 0) {
		  &findMultAttrs;
		}

		print ABIDS "@multAttrs\n";
		foreach $x1 (sort keys (%A2Bids)) {
		  $x2 = $ A2Bids{"$x1"};
		  $inf1 = $AidInfo{"$x1"};
		  print ABIDS "$x1|$x2|$inf1\n";
		}
		# if it has a previously created root node, remember it here.
		my $rtSaid = $$_theCfg->getEle('HC.RootNodeSaid', 0);
		if ($rtSaid != 0) {
		  $B2Aids{"$rtSaid"} = $rtSaid;
		  $A2Bids{"$rtSaid"} = $rtSaid;
		}
		foreach $x2 (sort keys (%B2Aids)) {
		  $x1 = $B2Aids{"$x2"};
		  $inf2 = $BidInfo{"$x2"};
		  if ($x1 == 0) {
			print ABIDS "0|$x2|$inf2\n";
		  }
		}
		close(ABIDS);
		my ($code, $saui, $scui, $sdui, $info);
		# read adjustment file if any
		if (-e "${_idMapFile}_adj") {
		  print "Reading adjustments file\n";
		  open (ABIDS, "<:utf8", "${_idMapFile}_adj")
			or die "could not open ${_idMapFile}_adj file.\n";
		  while (<ABIDS>) {
			chomp;
			($x1, $x2, $tty, $code, $saui, $scui, $sdui) = split(/\|/, $_, 8);
			$info = "$tty|$code|$saui|$scui|$sdui";
			$A2Bids{"$x1"} = $x2;
			$B2Aids{"$x2"} = $x1;
			$AidInfo{"$x1"} = $info;
			$BidInfo{"$x2"} = $info;
		  }
		  close(ABIDS);
		}
      }
    } else {
      &msg("Recovering idmap info from idMap.\n");
      # read from file.
      open (ABIDS, "<:utf8", $_idMapFile) or die "could not open $_idMapFile.\n";
      my ($id1, $id2, $tty, $code, $saui, $scui, $sdui, $info);

      # first read duplicate attribute names.
      $info = <ABIDS>;
      chomp($info);
      @multAttrs = split(/ /, $info);
      &msg("Multiple attrs => @multAttrs\n");

      # next read idmap info.
      while (<ABIDS>) {
		chomp;
		($id1, $id2, $tty, $code, $saui, $scui, $sdui) = split(/\|/, $_, 8);
		$info = "$tty|$code|$saui|$scui|$sdui";
		if ($id1 != 0) {
		  $A2Bids{"$id1"} = $id2;
		  $AidInfo{"$id1"} = $info;
		  if ($id2 != 0) {
			$B2Aids{"$id2"} = $id1;
			$BidInfo{"$id2"} = $info;
		  }
		} else {
		  $B2Aids{"$id2"} = $id1;
		  $BidInfo{"$id2"} = $info;
		}
      }
      close(ABIDS);

      # read adjustment file if any
      if (-e "${_idMapFile}_adj") {
		print "Reading adjustments file\n";
		open (ABIDS, "<:utf8", "${_idMapFile}_adj")
		  or die "could not open ${_idMapFile}_adj file.\n";
		while (<ABIDS>) {
		  chomp;
		  ($id1, $id2, $tty, $code, $saui, $scui, $sdui) = split(/\|/, $_, 8);
		  $info = "$tty|$code|$saui|$scui|$sdui";
		  $A2Bids{"$id1"} = $id2;
		  $AidInfo{"$id1"} = $info;
		  $B2Aids{"$id2"} = $id1;
		  $BidInfo{"$id2"} = $info;
		}
		close(ABIDS);
      }

      # temp code to check for errors.
      my $dontdo = 1;
      if ($dontdo != 1) {
		open (BLAH, ">:utf8", "../temp2/idMap2.out");
		my ($x1, $x2, $inf1, $inf2);
		print BLAH "@multAttrs\n";
		foreach $x1 (sort keys (%A2Bids)) {
		  $x2 = $ A2Bids{"$x1"};
		  $inf1 = $AidInfo{"$x1"};
		  print BLAH "$x1|$x2|$inf1\n";
		}

		foreach $x2 (sort keys (%B2Aids)) {
		  $x1 = $B2Aids{"$x1"};
		  $inf2 = $BidInfo{"$x2"};
		  if ($x1 == 0) {
			print BLAH "0|$x2|$inf2\n";
		  }
		}
		close(BLAH);
      }
    }

  }

  sub findMultAttrs {

    my ($atomId, $atomId2, $aNam, $aNam2, $aVal, $aVal2, $junk, $junk1, $ln);
    my ($key);
    my (%A_namVals, %B_namVals );
    %A_namVals=();
    %B_namVals=();
    my @allAttrs= ();
    # read attrs from A
    open (A_ATTRS, "<:utf8", "$_inADir/attributes.src")
      or die "no I_attr1 file.\n";
    while (<A_ATTRS>) {
      chomp;
      ($junk, $atomId, $junk1, $aNam, $aVal)  = split(/\|/, $_, 6);
      #$A_namVals{"$atomId|$aNam"}++;
      $key = "$atomId|$aNam";
      $A_namVals{"$key"}++;
    }
    close(A_ATTRS);
    $ln = keys(%A_namVals);
    &msg("Attrs in A => $ln \n");

    # read attrs from B
    open (B_ATTRS, "<:utf8", "$_inBDir/attributes.src")
      or die "no I_attr2 file.\n";
    while (<B_ATTRS>) {
      chomp;
      ($junk, $atomId, $junk1, $aNam, $aVal)  = split(/\|/, $_, 6);
      #$B_namVals{"$atomId|$aNam"}++;
      $key = "$atomId|$aNam";
      $B_namVals{"$key"}++;
    }
    close(B_ATTRS);
    $ln = keys(%B_namVals);
    &msg("Attrs in B => $ln \n");

    foreach $key (keys (%A_namVals)) {
      $junk = $A_namVals{"$key"};
      if ($A_namVals{"$key"} > 1) {
		($junk, $aNam) = split (/\|/, $key, 3);
		push (@multAttrs, $aNam) if (grep(/\Q$aNam\E/, @multAttrs) < 1);
      }
    }
    &msg("Attributes with Mult values (A) are => @multAttrs\n");
    foreach $key (keys (%B_namVals)) {
      if ($B_namVals{"$key"} > 1) {
		($junk, $aNam) = split (/\|/, $key, 3);
		push (@multAttrs, $aNam) if (grep(/\Q$aNam\E/, @multAttrs) < 1);
      }
    }
    &msg("Attributes with Mult values (A B)are => @multAttrs\n");
  }



  my %A_namValsDup = ();
  my %B_namValsDup = ();
  sub processAttrs {
    &msg("Processing attributes\n");
    # if precessrels is not called before, call it.
    &processRels unless ($_whichP & 8);

    #-----------------------------------------------------------
    # first find those attributes that can have multiple values. After running 
    # the following, these are saved in the list @multAttrs.
    #&findMultAttrs;

    my ($atomId, $atomId2, $aNam, $aNam2, $aVal, $aVal2, $junk, $junk1, $ln);
    my ($aEle, $bEle, $ty1, $temp, $count);
    my (%A_namVals, %B_namVals );

    #---------------------------------------------
    # read interested attributes from files.
    # read attrs from A
    open (A_ATTRS, "<:utf8", "$_inADir/attributes.src")
      or die "no I_attr1 file.\n";
    $temp = @inclAttrs;
    $count = 0;
    while (<A_ATTRS>) {
      chomp;
      $count++;
      if (($count % 5000) == 0) {
		&msg(">");
      }
      if (($count % 200000) == 0) {
		&msg(" - $count\n");
      }
      ($junk, $atomId, $junk1, $aNam, $aVal, $junk, $junk, $junk, 
       $junk, $junk, $ty1)  = split(/\|/, $_, 12);
      if ((($temp == 0) or (defined ($incAttrs{"$aNam"})))
		  && (!defined($excAttrs{"$aNam"}))) {
		# read only interested attrs.
		if ($ty1 eq 'SRC_ATOM_ID') {
		  $ty1 = '1';
		} elsif ($ty1 eq 'SRC_REL_ID') {
		  $ty1 = '2';
		} else {
		  $ty1 = '0';
		}

		$ln = grep(/\Q$aNam\E/, @multAttrs);
		# record them differently for multi-value attrs.
		if ($ln > 0) {
		  $A_namValsDup{"$atomId|$ty1|$aNam|$aVal"}++;
		} else {
		  $A_namVals{"$atomId|$ty1|$aNam"} = $aVal;
		}
      }
    }
    close(A_ATTRS);
    &msg(" - $count\n");
    $ln = keys %A_namVals;
    &msg("\nAttributes in A => $ln\n");
    $ln = keys %A_namValsDup;
    &msg("Dup attrs in A => $ln\n");

    # read attrs from B
    open (B_ATTRS, "<:utf8", "$_inBDir/attributes.src")
      or die "no I_attr2 file.\n";
    $count = 0;
    while (<B_ATTRS>) {
      chomp;
      $count++;
      if (($count % 5000) == 0) {
		&msg(">");
      }
      if (($count % 200000) == 0) {
		&msg(" - $count\n");
      }
      ($junk, $atomId, $junk1, $aNam, $aVal, $junk, $junk, $junk, 
       $junk, $junk, $ty1)  = split(/\|/, $_, 12);
      if ((($temp == 0) or (defined ($incAttrs{"$aNam"})))
		  && (!defined($excAttrs{"$aNam"}))) {
		# read only interested attrs.

		if ($ty1 eq 'SRC_ATOM_ID') {
		  $ty1 = '1';
		} elsif ($ty1 eq 'SRC_REL_ID') {
		  $ty1 = '2';
		} else {
		  $ty1 = '0';
		}

		$ln = grep(/\Q$aNam\E/, @multAttrs);
		# record them differently for multi-value attrs.
		if ($ln > 0) {
		  $B_namValsDup{"$atomId|$ty1|$aNam|$aVal"}++;
		} else {
		  $B_namVals{"$atomId|$ty1|$aNam"} = $aVal;
		}
      }
    }
    close(B_ATTRS);
    &msg(" - $count\n");
    $ln = keys %B_namVals;
    &msg("\nAttributes in B => $ln\n");
    $ln = keys %B_namValsDup;
    &msg("Dup attrs in B => $ln\n");


    # print info on multi-value attributes in A
    my $jj = 0;
    my $key;


    # -------------------------------------------
    # now find differences in attrs and dump them
    # find and print A minus B diffs.
    open (AmB_Attrs, ">:utf8", "$_outDir/AmB_attrs.src") 
      or die "no O_attr2 file.\n";
    foreach $aEle (keys (%A_namVals)) {
      ($atomId2, $ty1, $aNam2) = split(/\|/, $aEle, 4);
      $aVal2 = $A_namVals{"$aEle"};

      if ($ty1 eq '1') {
		$atomId = $A2Bids{"$atomId2"};
      } elsif ($ty1 eq '2') {
		$atomId = $A2BRids{"$atomId2"};
      } else {
		$atomId = $atomId2;
      }

      # for now ignore these.
      if ($atomId eq '0') {
		print AmB_Attrs "NEW - $atomId2\<$AidInfo{$atomId2}\> - \<$aNam2\> =>\n\t \<$aVal2\>\n\n";
      } else {
		$aVal = $B_namVals{"$atomId|$ty1|$aNam2"};
		if ($aVal ne $aVal2) {
		  print AmB_Attrs "DIFF - $atomId2\<$AidInfo{$atomId2}\>/$atomId\<$BidInfo{$atomId}\> - \<$aNam2\> =>\n\t \<$aVal2\>\n\t\<$aVal\>\n\n";
		}
      }
    }
    foreach $aEle (keys (%A_namValsDup)) {
      ($atomId2, $ty1, $aNam2, $aVal2) = split(/\|/, $aEle, 5);
      if ($ty1 eq '1') {
		$atomId = $A2Bids{"$atomId2"};
      } elsif ($ty1 eq '2') {
		$atomId = $A2Bids{"$atomId2"};
      } else {
		$atomId = $atomId2;
      }
      if (defined ($B_namValsDup{"$atomId|$ty1|$aNam2|$aVal2"})) {
		# exists. don't do any
      } else {
		print AmB_Attrs "DIFF - $atomId2\<$AidInfo{$atomId2}\>/$atomId\<$BidInfo{$atomId}\> - \<$aNam2\> =>\n\t \<$aVal2\>\n\n";
      }
    }
    close(AmB_Attrs);

    # find and print B minus A diffs.
    open (BmA_Attrs, ">:utf8", "$_outDir/BmA_attrs.src")
      or die "no O_attr1 file.\n";
    foreach $bEle (keys (%B_namVals)) {
      ($atomId2, $ty1,  $aNam2) = split(/\|/, $bEle, 4);
      $aVal2 = $B_namVals{"$bEle"};
      if ($ty1 eq '1') {
		$atomId = $B2Aids{"$atomId2"};
      } elsif ($ty1 eq '2') {
		$atomId = $B2ARids{"$atomId2"};
      } else {
		$atomId = $atomId2;
      }

      if ($atomId eq '0') {
		print BmA_Attrs "NEW - $atomId2\<$BidInfo{$atomId2}\> - \<$aNam2\> =>\n\t \<$aVal2\> \n\n";
      } else {
		$aVal = $A_namVals{"$atomId|$ty1|$aNam2"};
		if ($aVal ne $aVal2) {
		  print BmA_Attrs "DIFF - $atomId2\<$BidInfo{$atomId2}\>/$atomId\<$AidInfo{$atomId}\> - \<$aNam2\> =>\n\t \<$aVal2\> \n\t\<$aVal\>\n\n";
		}
      }
    }
    foreach $bEle (keys (%B_namValsDup)) {
      ($atomId2, $ty1, $aNam2, $aVal2) = split(/\|/, $bEle, 5);
      if ($ty1 eq '1') {
		$atomId = $B2Aids{"$atomId2"};
      } elsif ($ty1 eq '2') {
		$atomId = $B2Aids{"$atomId2"};
      } else {
		$atomId = $atomId2;
      }

      if (defined ($A_namValsDup{"$atomId|$ty1|$aNam2|$aVal2"})) {
		# exists. don't do any
      } else {
		print BmA_Attrs "NEW - $atomId2\<$BidInfo{$atomId2}\>/$atomId\<$AidInfo{$atomId}\> - \<$aNam2\> => \n\t\<$aVal2\>\n\n";
      }
    }
    close(BmA_Attrs);


    %A_namVals = ();
    %B_namVals = ();
  }


  sub processMerges {
    my ($lst, $id1, $id2, $mset, $t1, $q1, $t2, $q2, $ig);
    my ($nid1, $nid2, $aEle, $bEle, $ln);
    my (%A_mset, %B_mset);

    # create A_mset
    %A_mset = ();
    open (A_MRGS, "<:utf8", "$_inADir/mergefacts.src")
      or die "no I_merge1 file.\n";
    while (<A_MRGS>) {
      chomp;
      ($id1, $ig, $id2, $ig,$ig, $ig, $ig, $mset, $t1, $q1, $t2, $q2)
		= split(/\|/, $_, 13);
      if ($t1 eq 'SRC_ATOM_ID') {
		$q1 = 'SAI';
      }
      if ($t2 eq 'SRC_ATOM_ID') {
		$q2 = 'SAI';
      }
      $A_mset{"$q1|$id1|$q2|$id2|$mset"} = 1;
    }
    close(A_MRGS);
    $ln = keys %A_mset;
    &msg("Merges in A => $ln\n");



    # create B_mset
    %B_mset = ();
    open (B_MRGS, "<:utf8", "$_inBDir/mergefacts.src")
      or die "no I_merge2 file.\n";  
    while (<B_MRGS>) {
      chomp;
      ($id1, $ig, $id2, $ig,$ig, $ig, $ig, $mset, $t1, $q1, $t2, $q2)
		= split(/\|/, $_, 13);
      if ($t1 eq 'SRC_ATOM_ID') {
		$q1 = 'SAI';
      }
      if ($t2 eq 'SRC_ATOM_ID') {
		$q2 = 'SAI';
      }
      $B_mset{"$q1|$id1|$q2|$id2|$mset"} = 1;
    }
    close(B_MRGS);
    $ln = keys %B_mset;
    &msg("Merges in B => $ln\n");


    # now find A minus B
    open (AmB_Mrgs, ">:utf8", "$_outDir/AmB_mrgs.src")
      or die "no O_merge1 file.\n";
    foreach $aEle (keys (%A_mset)) {
      ($q1, $id1, $q2, $id2, $mset) = split(/\|/, $aEle, 6);
      if ($q1 eq 'SAI') { 
		if (defined ($A2Bids{"$id1"})) {
		  $nid1 = $A2Bids{"$id1"};
		} else {
		  $nid1 = '0';
		}
      } else {
		$nid1 = $id1;
      }
      if ($q2 eq 'SAI') { 
		if (defined ($A2Bids{"$id2"})) {
		  $nid2 = $A2Bids{"$id2"};
		} else {
		  $nid2 = '0';
		}
      } else {
		$nid2 = $id2;
      }

      if (($nid1 eq '0') || ($nid2 eq '0')) {
		print AmB_Mrgs "NEW => $id1\<$AidInfo{$id1}\> - $id2\<$AidInfo{$id2}\> - $mset - $q1 - $q2\n";
		print AmB_Mrgs"\t$nid1\<$BidInfo{$nid1}\> - $nid2\<$BidInfo{$nid2}\>\n\n";
      } elsif (!defined ($B_mset{"$q1|$nid1|$q2|$nid2|$mset"})) {
		if (!defined ($B_mset{"$q2|$nid2|$q1|$nid1|$mset"})) {
		  print AmB_Mrgs "DIFF $id1\<$AidInfo{$id1}\> - $id2\<$AidInfo{$id2}\> - $mset - $q1 - $q2\n";
		  print AmB_Mrgs"\t$nid1\<$BidInfo{$nid1}\> - $nid2\<$BidInfo{$nid2}\>\n\n";
		}
      }
    }
    close(AmB_Mrgs);

    # now find B minus A
    open (BmA_Mrgs, ">:utf8", "$_outDir/BmA_mrgs.src")
      or die "no O_merge2 file.\n";
    foreach $bEle (keys (%B_mset)) {
      ($q1, $id1, $q2, $id2, $mset) = split(/\|/, $bEle, 6);
      if ($q1 eq 'SAI') { 
		if (defined ($B2Aids{"$id1"})) {
		  $nid1 = $B2Aids{"$id1"};
		} else {
		  $nid1 = '0';
		}
      } else {
		$nid1 = $id1;
      }
      if ($q2 eq 'SAI') { 
		if (defined ($B2Aids{"$id2"})) {
		  $nid2 = $B2Aids{"$id2"};
		} else {
		  $nid2 = '0';
		}
      } else {
		$nid2 = $id2;
      }

      if (($nid1 eq '0') || ($nid2 eq '0')) {
		print BmA_Mrgs "NEW => $id1\<$BidInfo{$id1}\> - $id2\<$BidInfo{$id2}\> - $mset - $q1 - $q2\n";
		print BmA_Mrgs "\t$nid1\<$AidInfo{$nid1}\> - $nid2\<$AidInfo{$nid2}\>\n\n";
      } elsif (!defined ($A_mset{"$q1|$nid1|$q2|$nid2|$mset"})) {
		if (!defined ($A_mset{"$q2|$nid2|$q1|$nid1|$mset"})) {
		  print BmA_Mrgs "DIFF $id1\<$BidInfo{$id1}\> - $id2\<$BidInfo{$id2}\> - $mset - $q1 - $q2\n";
		  print BmA_Mrgs "\t$nid1\<$AidInfo{$nid1}\> - $nid2\<$AidInfo{$nid2}\>\n\n";
		}
      }
    }
    close(BmA_Mrgs);
    %A_mset=();
    %B_mset=();
  }


  sub processRels {
    my ($rlid, $lst, $id1, $id2, $rel, $rela, $t1, $q1, $t2, $q2, $ig);
    my ($nid1, $nid2, $aEle, $bEle, $ln, $rid1, $rid2);
    my (%A_rels, %B_rels);

    if ($_whichP & 8) {
      # create A_rels
      %A_rels = ();
      open (A_RELS, "<:utf8", "$_inADir/relationships.src")
		or die "no I_rel1 file.\n";
      while (<A_RELS>) {
		chomp;
		($rlid, $ig, $id1, $rel, $rela, $id2, $ig, $ig, $ig, $ig, $ig, $ig,
		 $t1, $q1, $t2, $q2) = split(/\|/, $_, 17);
		if ($t1 eq 'SRC_ATOM_ID') {
		  $q1 = 'SAI';
		}
		if ($t2 eq 'SRC_ATOM_ID') {
		  $q2 = 'SAI';
		}
		$A_rels{"$q1|$id1|$q2|$id2|$rel|$rela"} = $rlid;
      }
      close(A_RELS);
      $ln = keys %A_rels;
      &msg("Rels in A => $ln\n");



      # create B_rels
      %B_rels = ();
      open (B_RELS, "<:utf8", "$_inBDir/relationships.src")
		or die "no I_rel2 file.\n";
      while (<B_RELS>) {
		chomp;
		($rlid, $ig, $id1, $rel, $rela, $id2, $ig, $ig, $ig, $ig, $ig, $ig,
		 $t1, $q1, $t2, $q2) = split(/\|/, $_, 17);
		if ($t1 eq 'SRC_ATOM_ID') {
		  $q1 = 'SAI';
		}
		if ($t2 eq 'SRC_ATOM_ID') {
		  $q2 = 'SAI';
		}
		$B_rels{"$q1|$id1|$q2|$id2|$rel|$rela"} = $rlid;
      }
      close(B_RELS);
      $ln = keys %B_rels;
      &msg("Rels in B => $ln\n");


      # this is to write the rel id map to a file.
      open (ABIDS, ">:utf8", "${_idMapFile}_rel")
		or die "could not open ${_idMapFile}_rel.\n";

      # now find A minus B
      open (AmB_Rels, ">:utf8", "$_outDir/AmB_rels.src")
		or die "no O_rel1 file.\n";
      foreach $aEle (keys (%A_rels)) {
		$rid1 = $A_rels{"$aEle"};

		($q1, $id1, $q2, $id2, $rel, $rela) = split(/\|/, $aEle, 7);
		if ($q1 eq 'SAI') { 
		  if (defined ($A2Bids{"$id1"})) {
			$nid1 = $A2Bids{"$id1"};
		  } else {
			#$nid1 = '0';
			$nid1 = $id1;
		  }
		} else {
		  $nid1 = $id1;
		}
		if ($q2 eq 'SAI') { 
		  if (defined ($A2Bids{"$id2"})) {
			$nid2 = $A2Bids{"$id2"};
		  } else {
			#$nid2 = '0';
			$nid2 = $id2;
		  }
		} else {
		  $nid2 = $id2;
		}

		if (($nid1 eq '0') || ($nid2 eq '0')) {
		  print AmB_Rels "NEW => $id1\<$AidInfo{$id1}\> ";
		  print AmB_Rels "- $id2\<$AidInfo{$id2}\> ";
		  print AmB_Rels "- $rel - $rela - $q1 - $q2\n";
		  print AmB_Rels "\t$nid1\<$BidInfo{$nid1}\> - $nid2\<$BidInfo{$nid2}\>\n\n";
		  #$A2BRids{"$rid1"} = 0;
		  print ABIDS "$rid1|0\n";
	
		} elsif (!defined ($B_rels{"$q1|$nid1|$q2|$nid2|$rel|$rela"})) {
		  print AmB_Rels "DIFF $id1\<$AidInfo{$id1}\> ";
		  print AmB_Rels "- $id2\<$AidInfo{$id2}\> ";
		  print AmB_Rels "- $rel - $rela - $q1 - $q2\n";
		  print AmB_Rels "\t$nid1\<$BidInfo{$nid1}\> - $nid2\<$BidInfo{$nid2}\>\n\n";
		  #$A2BRids{"$rid1"} = 0;
		  print ABIDS "$rid1|0\n";
		} else {
		  if ($_saveInt == 1) {
			$rid2 = $B_rels{"$q1|$nid1|$q2|$nid2|$rel|$rela"};
			$A2BRids{"$rid1"} = $rid2;
			$B2ARids{"$rid2"} = $rid1;
			print ABIDS "$rid1|$rid2\n";
		  }
		}
      }
      close(AmB_Rels);

      # now find B minus A
      open (BmA_Rels, ">:utf8", "$_outDir/BmA_rels.src")
		or die "no O_rel2 file.\n";
      foreach $bEle (keys (%B_rels)) {
		$rid2 = $B_rels{"$bEle"};
		($q1, $id1, $q2, $id2, $rel, $rela) = split(/\|/, $bEle, 7);
		if ($q1 eq 'SAI') { 
		  if (defined ($B2Aids{"$id1"})) {
			$nid1 = $B2Aids{"$id1"};
		  } else {
			#$nid1 = '0';
			$nid1 = $id1;
		  }
		} else {
		  $nid1 = $id1;
		}
		if ($q2 eq 'SAI') {
		  if (defined ($B2Aids{"$id2"})) {
			$nid2 = $B2Aids{"$id2"};
		  } else {
			#$nid2 = '0';
			$nid2 = $id2;
		  }
		} else {
		  $nid2 = $id2;
		}

		if (($nid1 eq '0') || ($nid2 eq '0')) {
		  print BmA_Rels "NEW =>  $id1\<$BidInfo{$id1}\> ";
		  print BmA_Rels "- $id2\<$BidInfo{$id2}\> ";
		  print BmA_Rels "- $rel - $rela - $q1 - $q2\n";
		  print BmA_Rels "\t$nid1\<$AidInfo{$nid1}\> - $nid2\<$AidInfo{$nid2}\>\n\n";
		  #$B2ARids{"$rid2"} = 0;
		  print ABIDS "0|$rid2\n";
		} elsif (!defined ($A_rels{"$q1|$nid1|$q2|$nid2|$rel|$rela"})) {
		  print BmA_Rels "DIFF $id1\<$BidInfo{$id1}\> ";
		  print BmA_Rels "- $id2\<$BidInfo{$id2}\> ";
		  print BmA_Rels "- $rel - $rela - $q1 - $q2\n";
		  print BmA_Rels "\t$nid1\<$AidInfo{$nid1}\> - $nid2\<$AidInfo{$nid2}\>\n\n";
		  #$B2ARids{"$rid2"} = 0;
		  print ABIDS "0|$rid2\n";
		}
      }
      close(BmA_Rels);
      close(ABIDS);

      %A_rels=();
      %B_rels=();
    } else {
      &msg("Recovering idmapRel info from idMap_rel.\n");
      # read from file.
      open (ABIDS, "<:utf8", "${_idMapFile}_rel")
		or die "could not open ${_idMapFile}_rel.\n";
      my ($id1, $id2);

      # next read idmaprel info.
      while (<ABIDS>) {
		chomp;
		($id1, $id2) = split(/\|/, $_, 3);
		if ($id1 != 0 && $id2 != 0) {
		  $A2BRids{"$id1"} = $id2;
		  $B2ARids{"$id2"} = $id1;
		}
      }
      close(ABIDS);
    }
  }

  my $mode_fast = 1;
  sub processContexts {
    if ($mode_fast == 1) {
      &processContexts_fast;
    } else {
      &processContexts_slow;
    }
  }
  sub processContexts_fast {
    my ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui);
    my ($relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2);
    my ($lna, $lnb, $ambln, $bmaln, $key, $key1, $key2);

    my %aCxt = ();
    my %bCxt = ();
    $lna = 0;
    $lnb = 0;
    my $cxtTime;
    iutl->startClock("CXT");
    &msg("Reading A Contexts\n");
    # read A & B cxts
    open (ACXTS, "<:utf8", "$_inADir/contexts.src")
      or die "Could not open $_inADir/contexts.src file.\n";
    while (<ACXTS>) {
      chomp;
      $lna++;
      $aCxt{"$_"}++;
    }
    close(ACXTS);
    $cxtTime = iutl->endClock("CXT");
    &msg("Read A took $cxtTime\n");
    &$_pbar_cb(85) if ($_pbar_present == 1); 

    &msg("Reading B Contexts\n");
    iutl->startClock("CXT");
    open (BCXTS, "<:utf8", "$_inBDir/contexts.src")
      or die "Could not open $_inBDir/contexts.src file.\n";
    while (<BCXTS>) {
      chomp;
      $lnb++;
      $bCxt{"$_"}++;
    }
    close(BCXTS);
    $cxtTime = iutl->endClock("CXT");
    &msg("Read B took $cxtTime\n");
    &$_pbar_cb(90) if ($_pbar_present == 1);

    $ambln = 0;
    $bmaln = 0;

    # now read B contexts and dump B-A diffs
    &msg("Computing A-B contexts\n");
    iutl->startClock("CXT");
    open (AmB_Cxts, ">:utf8", "$_outDir/AmB_cxts.src")
      or die "Could not open $_outDir/AmB_cxts.src file.\n";
    open (AmB_Cxts2, ">:utf8", "$_outDir/AmB_cxts2.src")
      or die "Could not open $_outDir/AmB_cxts2.src file.\n";

    foreach $key (keys (%aCxt)) {
      ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui,
       $relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2)  = split(/\|/, $key, 18);

      # now convert ids from B to A
      $id1 = $A2Bids{"$id1"};
      $id2 = $A2Bids{"$id2"};
      if ($ptnum ne "") {
		$ptnum = join('.', map {$A2Bids{"$_"}} split(/\./, $ptnum));
      }
      if ($t1 eq 'SRC_ATOM_ID') {
		$sgid1 = $A2Bids{"$sgid1"};
      }
      if ($t2 eq 'SRC_ATOM_ID') {
		$sgid2 = $A2Bids{"$sgid2"};
      }

      $key1 = "$id1|$rel|$rela|$id2|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid1|$t1|$q1|$sgid2|$t2|$q2|";

      if (!defined($bCxt{"$key1"})) {
		if ($rel eq 'SIB') {
		  # incase of sibs check the opposite
		  $key2 = "$id2|$rel|$rela|$id1|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid2|$t2|$q2|$sgid1|$t1|$q1|";
		  if (!defined($bCxt{"$key2"})) {
			$ambln++;
			print AmB_Cxts2 "NEW A:\n";
			print AmB_Cxts2 "\tIn  A: <$key>\n";
			print AmB_Cxts2 "\tEq B1: <$key1>\n";
			print AmB_Cxts2 "\tEq B2: <$key2>\n";
		  }
		} else {
		  $ambln++;
		  print AmB_Cxts "NEW A:\n";
		  print AmB_Cxts "\tIn  A: <$key>\n";
		  print AmB_Cxts "\tEq B1: <$key1>\n";
		}
      }
    }
    close(AmB_Cxts);
    close(AmB_Cxts2);
    $cxtTime = iutl->endClock("CXT");
    &msg("Processing A-B took $cxtTime\n");
    &$_pbar_cb(95) if ($_pbar_present == 1);

    # now read B contexts and dump B-A diffs
    &msg("Computing B-A contexts\n");
    iutl->startClock("CXT");
    open (BmA_Cxts, ">:utf8", "$_outDir/BmA_cxts.src")
      or die "Could not open  $_outDir/BmA_cxts.src file.\n";
    open (BmA_Cxts2, ">:utf8", "$_outDir/BmA_cxts2.src")
      or die "Could not open  $_outDir/BmA_cxts2.src file.\n";

    foreach $key (keys (%bCxt)) {
      ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui,
       $relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2)  = split(/\|/, $key, 18);

      # now convert ids from B to A
      $id1 = $B2Aids{"$id1"};
      $id2 = $B2Aids{"$id2"};
      if ($ptnum ne "") {
		$ptnum = join('.', map {$B2Aids{"$_"}} split(/\./, $ptnum));
      }
      if ($t1 eq 'SRC_ATOM_ID') {
		$sgid1 = $B2Aids{"$sgid1"};
      }
      if ($t2 eq 'SRC_ATOM_ID') {
		$sgid2 = $B2Aids{"$sgid2"};
      }

      $key1 = "$id1|$rel|$rela|$id2|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid1|$t1|$q1|$sgid2|$t2|$q2|";

      if (!defined($aCxt{"$key1"})) {
		if ($rel eq 'SIB') {
		  # incase of sibs check the opposite
		  $key2 = "$id2|$rel|$rela|$id1|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid2|$t2|$q2|$sgid1|$t1|$q1|";
		  if (!defined($aCxt{"$key2"})) {
			$bmaln++;
			print BmA_Cxts2 "NEW B:\n";
			print BmA_Cxts2 "\tIn  B: <$key>\n";
			print BmA_Cxts2 "\tEq A1: <$key1>\n";
			print BmA_Cxts2 "\tEq A2: <$key2>\n";
		  }
		} else {
		  $bmaln++;
		  print BmA_Cxts "NEW B:\n";
		  print BmA_Cxts "\tIn  B: <$key>\n";
		  print BmA_Cxts "\tEq A1: <$key1>\n";
		}
      }
    }
    close(BmA_Cxts);
    close(BmA_Cxts2);
    $cxtTime = iutl->endClock("CXT");
    &msg("Prcessing B-A took $cxtTime\n");
    &$_pbar_cb(100) if ($_pbar_present == 1);


    &msg("Contexts in A => $lna\n");
    &msg("Contexts in B => $lnb\n");
    &msg("A minus B cxts => $ambln\n");
    &msg("B minus A cxts => $bmaln\n");
  }

  sub processContexts_slow {
    my ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui);
    my ($relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2);
    my ($lna, $lnb, $ambln, $bmaln, $key, @tmp, $tmp, $cxtTime);

    my %aCxt = ();
    my %bCxt = ();
    $lna = 0;
    &msg("Reading A Contexts\n");
    iutl->startClock("CXT");
    # read A cxts and convert them to Bsaids
    open (ACXTS, "<:utf8", "$_inADir/contexts.src")
      or die "Could not open $_inADir/contexts.src file.\n";
    while (<ACXTS>) {
      chomp;
      $lna++;
      ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui,
       $relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2)  = split(/\|/, $_, 18);
      # now convert ids from A to B
      $id1 = $A2Bids{"$id1"};
      $id2 = $A2Bids{"$id2"};
      if ($ptnum ne "") {
		@tmp = split(/\./, $ptnum);
		$ptnum = join('.', map {$A2Bids{"$_"}} @tmp);
      }
      if ($t1 eq 'SRC_ATOM_ID') {
		$sgid1 = $A2Bids{"$sgid1"};
      }
      if ($t2 eq 'SRC_ATOM_ID') {
		$sgid2 = $A2Bids{"$sgid2"};
      }

      $key = "$id1|$rel|$rela|$id2|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid1|$t1|$q1|$sgid2|$t2|$q2|";
      $aCxt{$key}++;
    }
    close(ACXTS);
    $cxtTime = iutl->endClock("CXT");
    &msg("Reading A Contexts took $cxtTime\n");
    &$_pbar_cb(85) if ($_pbar_present == 1);

    $lnb = 0;
    $bmaln = 0;
    # now read B contexts and dump B-A diffs
    iutl->startClock("CXT");
    &msg("Reading B Contexts\n");
    open (BCXTS, "<:utf8", "$_inBDir/contexts.src")
      or die "Could not open $_inBDir/contexts.src file.\n";
    open (BmA_Cxts, ">:utf8", "$_outDir/BmA_cxts.src")
      or die "no O_context2 file.\n";

    while (<BCXTS>) {
      chomp;
      $lnb++;
      if (!defined($aCxt{"$_"})) {
		if ($rel eq 'SIB') {
		  ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui,
		   $relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2)  = split(/\|/, $_, 18);
		  # incase of sibs check the opposite
		  $tmp = "$id2|$rel|$rela|$id1|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid2|$t2|$q2|$sgid1|$t1|$q1|";
		  if (!defined($aCxt{"$tmp"})) {
			$bmaln++;
			print BmA_Cxts "NEW = $_\n";
		  }
		} else {
		  $bmaln++;
		  print BmA_Cxts "NEW = $_\n";
		}
      }
    }
    close(BCXTS);
    close(BmA_Cxts);
    $cxtTime = iutl->endClock("CXT");
    &msg("Prcessing B-A took $cxtTime\n");
    &$_pbar_cb(90) if ($_pbar_present == 1);


    %aCxt = ();					# release memory
    # read B cxts and convert them to A saids
    &msg("Reading B Contexts\n");
    iutl->startClock("CXT");
    open (BCXTS, "<:utf8", "$_inBDir/contexts.src")
      or die "Could not open $_inBDir/contexts.src file.\n";
    while (<BCXTS>) {
      chomp;
      ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui,
       $relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2)  = split(/\|/, $_, 18);
      # now convert ids from A to B
      $id1 = $B2Aids{"$id1"};
      $id2 = $B2Aids{"$id2"};
      if ($ptnum ne "") {
		$ptnum = join('.', map {$B2Aids{"$_"}} split(/\./, $ptnum));
      }
      if ($t1 eq 'SRC_ATOM_ID') {
		$sgid1 = $B2Aids{"$sgid1"};
      }
      if ($t2 eq 'SRC_ATOM_ID') {
		$sgid2 = $B2Aids{"$sgid2"};
      }

      $bCxt{"$id1|$rel|$rela|$id2|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid1|$t1|$q1|$sgid2|$t2|$q2|"}++;
    }
    close(BCXTS);
    $cxtTime = iutl->endClock("CXT");
    &msg("Reading B Contexts took $cxtTime\n");
    &$_pbar_cb(95) if ($_pbar_present == 1);

    $ambln = 0;
    # now read B contexts and dump B-A diffs
    &msg("Reading A Contexts\n");
    iutl->startClock("CXT");
    open (ACXTS, "<:utf8", "$_inADir/contexts.src")
      or die "Could not open $_inADir/contexts.src file.\n";
    open (AmB_Cxts, ">:utf8", "$_outDir/AmB_cxts.src")
      or die "no O_context2 file.\n";

    while (<ACXTS>) {
      chomp;
      if (!defined($bCxt{"$_"})) {
		if ($rel eq 'SIB') {
		  ($id1, $rel, $rela, $id2, $src, $srclbl, $hcd, $ptnum, $rmode, $srui,
		   $relg, $sgid1, $t1, $q1, $sgid2, $t2, $q2)  = split(/\|/, $_, 18);
		  $tmp = "$id2|$rel|$rela|$id1|$src|$srclbl|$hcd|$ptnum|$rmode|$srui|$relg|$sgid2|$t2|$q2|$sgid1|$t1|$q1|";
		  if (!defined($bCxt{"$tmp"})) {
			$ambln++;
			print AmB_Cxts "NEW = $_\n";
		  }
		} else {
		  $ambln++;
		  print AmB_Cxts "NEW = $_\n";
		}
      }
    }
    close(ACXTS);
    close(AmB_Cxts);
    $cxtTime = iutl->endClock("CXT");
    &msg("Prcessing A-B took $cxtTime\n");

    &msg("Contexts in A => $lna\n");
    &msg("Contexts in B => $lnb\n");
    &msg("A minus B cxts => $ambln\n");
    &msg("B minus A cxts => $bmaln\n");

  }


  sub process {
    if ($initialized != 1) {
      &msg("Not yet initilized\n"); return;
    }
    my ($tmp);
    iutl->startClock("begin");
    iutl->startClock("ops");
    &readAtoms;
    $tmp = iutl->endClock("ops");
    &msg("Atom Processing took : $tmp\n");
    &$_pbar_cb(20) if ($_pbar_present == 1);


    iutl->startClock("ops");
    &processRels if ($_whichP & 8);
    $tmp = iutl->endClock("ops");
    &msg("Rel Processing took : $tmp\n");
    &$_pbar_cb(40) if ($_pbar_present == 1);

    iutl->startClock("ops");
    &processAttrs if ($_whichP & 2);
    &$_pbar_cb(60) if ($_pbar_present == 1);
    $tmp = iutl->endClock("ops");
    &msg("Attribute Processing took : $tmp\n");

    iutl->startClock("ops");
    &processMerges if ($_whichP & 4);
    &$_pbar_cb(80) if ($_pbar_present == 1);
    $tmp = iutl->endClock("ops");
    &msg("merge Processing took : $tmp\n");

    iutl->startClock("ops");
    &processContexts if ($_whichP & 16);
    &$_pbar_cb(100) if ($_pbar_present == 1);
    $tmp = iutl->endClock("ops");
    &msg("Cxt Processing took : $tmp\n");

    $tmp = iutl->endClock("begin");
    &msg("Processing all took: $tmp\n");
  }
}
1


