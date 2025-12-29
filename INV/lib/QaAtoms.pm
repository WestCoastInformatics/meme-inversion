#!/usr/bin/perl
#

# Fields:
# 1  = src_atom_id
# 2  = source
# 3  = termgroup
# 4  = code
# 5  = status
# 6  = tobereleased
# 7  = released
# 8  = atom_name
# 9  = suppressible
# 10 = source_aui
# 11 = source_cui
# 12 = source_dui
# 13 = language
# 14 = order_id
# 15 = last_release_cui

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

use List::Util qw(min max);

package QaAtoms;

use FldMon;
use LineMon;
use CharCount;
{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT);

  my ($VlTtyRef, $VlVsabRef, $VlLatRef, $VlVsab2RsabRef, $VlTGRef, $VlTg2SupRef);

  my ($VlSaidRef, $VlSrcAtoms, $VlCdVsab, $VlCdRsab, $VlCdVTG, $VlCdRTG);
  my ($VlSauiVsab, $VlScuiVsab, $VlSduiVsab);
  my ($VlSauiRsab, $VlRcuiRsab, $VlSduiRsab);


  my %mons=();
  my %lmons=();

  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();

  my %currentrsab = ();
  my %atomAui = ();
  my %dupStrCI=();				# case insensitive strings.
  my %dupStrCS=();				# case sensitive strings
  my %srcTg=();					# src vab/rab records.
  my %tallySelection=();

  my $pat6 = qr{\<[\d]*\>$};
  #my $pat7 = qr{&[[:alnum:]]+;};
  my $pat7 = qr{&\#?[[:alnum:]]+;};

  # tests BEGIN tests BEGIN tests BEGIN tests BEGIN tests BEGIN
  my @IL=();

  {
      # Get TTY class
      my @rows = `$ENV{INV_HOME}/bin/api_metadata.sh current_sources --quiet`;
      chomp(@rows);
      
      my $row;
      foreach $row (@rows) {
          my ($rsab, $vsab) = split /\|/, $row;
	  $currentrsab{$rsab} = $vsab;
      }
  }


  sub setMsgCountHashes {
	# use info as the default.
	my $type = shift;
	if ($type eq 'error') {
	  return (\%errCount, \%Errors);
	} elsif ($type eq 'wrng') {
	  return (\%wrngCount, \%Warnings);
	} else {
	  return (\%infoCount, \%Information);
	}
  }

  sub nullFunc { return; }

  # ILM_0: field count check.
  my $subref_checkFldCount= \&nullFunc;
  sub make_checkFldCount {
	my ($valFldCount, $msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkFldCount = sub {
	  if ($valFldCount != @IL) {
		if ($$countHash{"VFieldCount"}++ < 10) {
		  my $l = @IL;
		  $l -= 2;
		  $$msgHash{"VFieldCount_$IL[1]"} = $l;
		}
	  }
	}
  }

  # ILM_1: count number of duplicate case-sensitive strings.
  my $subref_checkDupCSStrings = \&nullFunc;
  sub make_checkDupCSStrings {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkDupCSStrings = sub {
	  if (defined($dupStrCS{"$IL[8]"})) {
		if ($$countHash{"VDplctCSSStrings"}++ < 10) {
		  $$msgHash{"VDplctCSSStrings_$IL[1]"} = $IL[8];
		}
	  }
	    else { $dupStrCS{"$IL[8]"}++; }
	}
  }

  # ILM_2: count number of duplicate case_insesntive strings.
  # don't list case insensitive strings if the strings are equal (as covered in ILM_1).
  my $subref_checkDupCIStrings = \&nullFunc;
  sub make_checkDupCIStrings {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkDupCIStrings = sub {
	  my $tmp = uc($IL[8]);
	  if (defined($dupStrCI{"$tmp"})) {
		  if ($$countHash{'VDplctCIStrings'}++ < 10) {
			$$msgHash{"VDplctCIStrings_$IL[1]"} = $IL[8];
		}
	  }
	  else { $dupStrCI{"$tmp"}++; }
	}
  }

  # ILM_3: check tty and tg agree
  my $subref_checkTgVsabMismatch = \&nullFunc;
  sub make_checkTgVsabMismatch {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkTgVsabMismatch = sub {
	  if ($IL[3] !~ /^$IL[2]/ && $$countHash{'VTgVsabMismatch'}++ < 10) {
		$$msgHash{'VTgVsabMismatch_$IL[1]'} = "$IL[2]|$IL[3]";
	  }
	}
  }

  # ILM_4: Code not mathcing with any of the non-null saui/sdui/scui
  my $subref_checkCdACDuiMismatch = \&nullFunc;
  sub make_checkCdACDuiMismatch {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkCdACDuiMismatch = sub {
	  if ($IL[10] ne '' && $IL[11] ne '' && $IL[12] ne ''
		  && $IL[4] ne $IL[10] && $IL[4] ne $IL[11] && $IL[4] ne $IL[12]
		  && $$countHash{'VCdACDuiMismatch'}++ < 10) {
		$$msgHash{'VCdACDuiMismatch_$IL[1]'} ="$IL[4]|$IL[10]|$IL[11]|$IL[12]";
	  }
	}
  }

  # ILM_5: Angle brackets in str. $pat6 = qr(\<[\d]*\>$);
  my $subref_checkStrsWithBracketNums = \&nullFunc;
  sub make_checkStrsWithBracketNums {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkStrsWithBracketNums = sub {
	  if ($IL[8] =~ /$pat6/ && $$countHash{'VStrsWithBracketNums'}++ < 10) {
		$$msgHash{"VStrWithBracketNums_$IL[1]"} = $IL[8];
	  }
	}
  }

  # ILM_6: check for XML chars. $pat7 = &[[:alnum:]]+
  my $subref_checkStrsWithXMLChars = \&nullFunc;
  sub make_checkStrsWithXMLChars {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkStrsWithXMLChars = sub {
	  if ($IL[8] =~ /$pat7/ && $$countHash{'VStrsWithXMLChars'}++ < 10) {
		$$msgHash{"VStrWithXMLChars_$IL[1]"} = $IL[8];
	  }
	}
  }

  # ILM_7: check for foreign SRC atoms.
  my $subref_checkForeignSrcAtoms = \&nullFunc;
  sub make_checkForeignSrcAtoms {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkForeignSrcAtoms = sub {
	  if ($IL[2] eq 'SRC' && $IL[13] ne 'ENG'
		  && $$countHash{'VForeignSrc'}++ < 20) {
		$$msgHash{"VForeignSrc_$IL[1]"} = "$IL[2]|$IL[4]|$IL[13]|$IL[8]";
	  }
	}
  }

  # IFM_1: check for valid source (collected from sources.src file)
  my $subref_checkUndefinedSource = \&nullFunc;
  sub make_checkUndefinedSource {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkUndefinedSource = sub {
	  if ((!defined($$VlVsabRef{"$IL[2]"}))
		  && $$countHash{'VUndefinedSource'}++ < 10) {
		$$msgHash{"VUndefinedSource_$IL[1]"} = $IL[2];
	  }
	}
  }

  # IFM_2: check for valid termgroup (collected from termgroups.src file)
  my $subref_checkUndefinedTg = \&nullFunc;
  sub make_checkUndefinedTg {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkUndefinedTg = sub {
	  if ((!defined($$VlTGRef{"$IL[3]"}))
		  && $$countHash{'VUndefinedTG'}++ < 10) {
		$$msgHash{"VUndefinedTG_$IL[1]"} = $IL[3];
	  }
	}
  }

  # IFM_3: check if tty is valid
  my $subref_checkUndefinedTTY = \&nullFunc;
  sub make_checkUndefinedTTY {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkUndefinedTTY = sub {
	  my $key = shift;
	  if ((!defined($$VlTtyRef{"$key"}))
		  && $$countHash{'VUndefinedTTY'}++ < 10) {
		$$msgHash{"VUndefinedTTY_$IL[1]"} = $key;
	  }
	}
  }

  # IFM_4: code does not Match SRC/[VR]AB Name
  my $subref_checkInvVabRabCode = \&nullFunc;
  sub make_checkInvVabRabCode {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvVabRabCode = sub {
	  # code must be "V-@_[8]"
	  if ($IL[4] ne "V-$IL[8]" && $$countHash{'VInvVabRabCode'}++ < 10) {
		$$msgHash{"VInvVabRabCode_$IL[1]"} = $IL[4];
	  }
	}
  }

  # IFM_5: there should be only 1 of each VAB|Cd RAB|Cd records.
  my $subref_checkDupSrcVabRab = \&nullFunc;
  sub make_checkDupSrcVabRab {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkDupSrcVabRab = sub {
	  my $key = shift;
	  if (defined($srcTg{"SRC/$key|$IL[4]"})) {
		if ($$countHash{'VDupSrcVabRab'}++ < 10) {
		  $$msgHash{"VDupSrcVabRab_$IL[1]"} = "SRC/$key|$IL[4]";
		}
	  } else {
		$srcTg{"SRC/$key|$IL[4]"}++;
	  }
	}
  }

  # IFM_6: Mismatched Supress flag.
  my $subref_checkSuppMismatch = \&nullFunc;
  sub make_checkSuppMismatch {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkSuppMismatch = sub {
	  my $curSup = $IL[9];
	  my $tgSup = $$VlTg2SupRef{"$IL[3]"};
	  if ($tgSup eq 'Y' && $curSup ne 'Y' && $curSup ne 'O'
		  && $$countHash{'VSuppMismatch_Y'}++ < 10) {
		$$msgHash{"VSuppMismatch_Y_$IL[1]"} = "$IL[3]|$tgSup|$curSup";
	  } elsif ($tgSup eq 'N' && $curSup eq 'Y'
			   && $$countHash{'VSuppMismatch_N'}++ < 10) {
		$$msgHash{"VSuppMismatch_N_$IL[1]"} = "$IL[3]|$tgSup|$curSup";
	  } elsif ($tgSup eq 'O' && $curSup ne 'O'
			   && $$countHash{'VSuppMismatch_O'}++ < 10) {
		$$msgHash{"VSuppMismatch_O_$IL[1]"} = "$IL[3]|$tgSup|$curSup";
	  }
	}
  }
  
    # IFM_7: non unique AUI fields.
  my $subref_checkNonUniqueAuis = \&nullFunc;
  sub make_checkNonUniqueAuis {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNonUniqueAuis = sub {
	  my $aui = "$IL[3]|$IL[8]|$IL[4]|$IL[10]|$IL[11]|$IL[12]";
	  if (defined($atomAui{"$aui"})) {
		if ($$countHash{'ENonUniqueAuis'}++ < 20) {
		  $$msgHash{"ENonUniqueAuis_$IL[1]"} = $atomAui{"$aui"};
		}
	  } else {
		$atomAui{"$aui"} = $IL[1];
	  }
	}
  }
  
   # IFM_8: check if the LAT field is same (collected from sources.src file)
  my $subref_checkLATmismatch = \&nullFunc;
  sub make_checkLATmismatch {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkLATmismatch = sub {
	 my $curlan = $IL[13];
            my $srclan =$$VlLatRef{"$IL[2]"};
            if ($IL[2] ne "SRC"){
               if (($curlan ne $srclan)
                  && $$countHash{'VLATmismatch'}++ < 10) {
                $$msgHash{"VLATmismatch_$IL[1]"} = $IL[13];
	    }
	  }
    }
  }
  

  # tests END tests END tests END tests END tests END tests END tests END




  sub init {
	my ($self, $log, $cfg) = @_;
	$_theLog = $log;
	$_theCfg = $cfg;
	$_OUT = $$_theCfg->getEle('ofhReport');
	$_EOUT = $$_theCfg->getEle('errhReport');
  }


  sub setValidRefs {
	my ($self, $l_valids) = @_;

	$VlTtyRef = $$l_valids{'Tty'};

	$VlVsabRef = $$l_valids{'Vsab'};
	$VlLatRef = $$l_valids{'language'};
	$VlVsab2RsabRef = $$l_valids{'Vsab2Rsab'};

	$VlTGRef = $$l_valids{'Tg'};
	$VlTg2SupRef = $$l_valids{'Tg2Sup'};

	$VlSaidRef = $$l_valids{'Said'};
	$VlCdVsab = $$l_valids{'CdVsab'};
	$VlCdRsab = $$l_valids{'CdRsab'};
	$VlCdVTG = $$l_valids{'CdVTg'};
	$VlCdRTG = $$l_valids{'CdRTg'};
	$VlSauiVsab = $$l_valids{'SauiVsab'};
	$VlSauiRsab = $$l_valids{'SauiRsab'};
	$VlScuiVsab = $$l_valids{'ScuiVsab'};
	$VlRcuiRsab = $$l_valids{'ScuiRsab'};
	$VlSduiVsab = $$l_valids{'SduiVsab'};
	$VlSduiRsab = $$l_valids{'SduiRsab'};

	$VlSrcAtoms = $$l_valids{'SrcAtoms'};

  }

  sub crTest {
	my ($mStr, $num, $mkFn, $str) = @_;
	my ($type);
	if ($$_theCfg->getEle("$mStr.$num.enable", 0) eq '1') {
	  $type = $$_theCfg->getEle("$mStr.1.type", 'info');
	  &$mkFn($type);
	  $$_theLog->logInfo("Enabled check $mStr.$num \n\t($str)\n");
	} else {
	  $$_theLog->logInfo("** Not checking $mStr.$num \n\t($str)\n");
	}
  }

  sub new {
	my $class = shift;
	my $ref = {};
	my ($i, $fnum, $tHash, $temp, $temp1, $msgType);
	my $lmStr = "IlLineMon.Atom";
	my $fmStr = "IlFileMon.Atom";

	## 1. create FieldMons
	$tHash = \%{$$_theCfg->getHashRef('FieldMon.Atom')};
	foreach $i (sort keys (%{$tHash})) {
	  $fnum = $$_theCfg->getEle("FieldMon.Atom.$i.fieldNum", '0');
	  if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Atom', $i);
	  } else {
		$$_theLog->logError("Encountered invalid FieldMon.Atom.$i.fieldNum\n");
	  }
	}

	## 2. create LineMons
	$tHash = \%{$$_theCfg->getHashRef('LineMon.Atom')};
	foreach $i (sort keys(%{$tHash})) {
	  $lmons{$i} = new LineMon('Atom',$i);
	}


	## 3. read inline FieldMons and create the check functions
	# ILM_0: field count
	if (($temp = $$_theCfg->getEle("$lmStr.0.enable", 0)) == 1) {
	  $temp = $$_theCfg->getEle("$lmStr.0.fieldCt", 14);
	  if ($temp != 0) {
		$temp += 2;
		$temp1 = $$_theCfg->getEle("$lmStr.0.type", 'info');
		&make_checkFldCount($temp, $temp1);
	  }
	}

	&crTest($lmStr, 1, \&make_checkDupCSStrings,
			"ILM_1: count number of duplicate case-sensitive strings");

	&crTest($lmStr, 2, \&make_checkDupCIStrings,
			"ILM_2: count number of duplicate case_insesntive strings");

	&crTest($lmStr, 3, \&make_checkTgVsabMismatch,
			"ILM_3: check tty and tg agree");

	&crTest($lmStr, 4, \&make_checkCdACDuiMismatch,
			"ILM_4: Code not mathcing with any of the non-null".
			"saui/sdui/scui");

	&crTest($lmStr, 5, \&make_checkStrsWithBracketNums,
			"ILM_5: Angle brackets in str. $pat6 = qr(\<[\d]*\>$)");

	&crTest($lmStr, 6, \&make_checkStrsWithXMLChars,
			"ILM_6: check for XML chars. $pat7 = &[[:alnum:]]");

	&crTest($lmStr, 7, \&make_checkForeignSrcAtoms,
			"ILM_7: check for foreign SRC atoms");


	## 4. read inline FileMons and create the check functions
	&crTest($fmStr, 1, \&make_checkUndefinedSource,
			" IFM_1: check for valid source (collected from sources.src file");

	&crTest($fmStr, 2, \&make_checkUndefinedTg,
			" IFM_2: check for valid termgroup (collected from ".
			"termgroups.src file");

	&crTest($fmStr, 3, \&make_checkUndefinedTTY,
			" IFM_3: check if tty is vali");

	&crTest($fmStr, 4, \&make_checkInvVabRabCode,
			" IFM_4: code does not Match SRC/[VR]AB Nam");

	&crTest($fmStr, 5, \&make_checkDupSrcVabRab,
			" IFM_5: there should be only 1 of each VAB|Cd RAB|Cd records");

	&crTest($fmStr, 6, \&make_checkSuppMismatch,
			" IFM_6: Mismatched Supress flag");
	
	&crTest($fmStr, 7, \&make_checkNonUniqueAuis,
			"IFM_7: non unique AUI fields");
	
    &crTest($fmStr, 8, \&make_checkLATmismatch,
			"IFM_8: Language field mismatch ");

	# 5. remember the following tally fields: srcAtomId[1], code[4], saui[10],
	#    scui[11], sdui[12]
	# irrespective of what the user wants, set the tally fields
	my $i;
	foreach $i (1) {
	  $tallySelection{"$i"} = $mons{"$i"}->{'tally'};
	  $mons{"$i"}->{'tally'} = 1;
	}
	# at report time set the tally fields back to users selection.

	return bless ($ref, $class);
  }


  sub process {
	my $self = $_[0];
	@IL = @_;
	my @tmparray = @_;
	my ($key, $tmp, $ign, $vsb, $rsb, $tty);

	# do FieldMon Checks.
	foreach $key (keys (%mons)) {
	  $mons{"$key"}->process($_[$key], $_[1]);
	}

	# do LineMon Checks.
	foreach $key (keys (%lmons)) {
	  $lmons{"$key"}->process(@tmparray[1..$#tmparray]);
	}

	## other checks go here.
	# ILM_0: field count
	&$subref_checkFldCount();

	# ILM_1: count number of duplicate case-sensitive strings.
	&$subref_checkDupCSStrings();

	# ILM_2: count number of duplicate case_insesntive strings.
	&$subref_checkDupCIStrings();

	# ILM_3: check tty and tg agree
	&$subref_checkTgVsabMismatch();

	# ILM_4: Code not mathcing with any of the non-null saui/sdui/scui
	&$subref_checkCdACDuiMismatch();

    # ILM_5: Angle brackets in str. $pat6 = qr(\<[\d]*\>$);
	&$subref_checkStrsWithBracketNums();

	# ILM_6: check for XML chars. $pat7 = &[[:alnum:]]+
	&$subref_checkStrsWithXMLChars();

	# ILM_7: check for foreign SRC atoms.
	&$subref_checkForeignSrcAtoms();

	# IFM_1: check for valid source (collected from sources.src file)
	&$subref_checkUndefinedSource();

	# IFM_2: check for valid termgroup (collected from termgroups.src file)
	&$subref_checkUndefinedTg();

	($ign, $key) = split(/\//, $_[3]);
	if ($_[2] ne 'SRC') {
	  # IFM_3: check if tty is valid
	  &$subref_checkUndefinedTTY($key);
	} else {
	  if ($key eq 'RAB' || $key eq 'VAB') {
		# IFM_4: code does not Match SRC/[VR]AB Name
		&$subref_checkInvVabRabCode();

		# IFM_5: there should be only 1 of each VAB|Cd RAB|Cd records.
		&$subref_checkDupSrcVabRab($key);
	  }
	}

	# IFM_6: Mismatched Supress flag.
	&$subref_checkSuppMismatch();
    
    # IFM_7: non unique AUI fields.
	&$subref_checkNonUniqueAuis();

    #IFM_8: Language field mis match
    &$subref_checkLATmismatch();
    
	## now remember various cd/saui/scui/sdui data
	($vsb, $tty) = split(/\//, $_[3]);
	$rsb = defined($$VlVsab2RsabRef{"$_[2]"}) ? 
	  $$VlVsab2RsabRef{"$_[2]"} : '';
	$rsb = 'SRC' if ($rsb eq '' && $vsb eq 'SRC');

	if ($_[4] ne '') {
	  $$VlCdVsab{"$_[4]|$_[2]"}++;
	  $$VlCdVTG{"$_[4]|$_[3]"}++;
	  if ($rsb ne '') {
		$$VlCdRsab{"$_[4]|$rsb"}++;
		$$VlCdRTG{"$_[4]|$rsb/$tty"}++;
	  }
	}
	if ($_[10] ne '') {
	  $$VlSauiVsab{"$_[10]|$_[2]"}++;
	  $$VlSauiRsab{"$_[10]|$rsb"}++ if ($rsb ne '');
	}
	if ($_[11] ne '') {
	  $$VlScuiVsab{"$_[11]|$_[2]"}++;
	  $$VlRcuiRsab{"$_[11]|$rsb"}++ if ($rsb ne '');
	}
	if ($_[12] ne '') {
	  $$VlSduiVsab{"$_[12]|$_[2]"}++;
	  $$VlSduiRsab{"$_[12]|$rsb"}++ if ($rsb ne '');
	}
        
       # check for tabs in the file
       if ($_[1] ne ''){
      my $full_line  = "$_[1]|$_[2]|$_[3]|$_[4]|$_[5]|$_[6]|$_[7]|$_[8]|$_[9]_$[10]|$_[11]|$_[12]|$_[13]|$_[14]|$_[15]";
	 if ($full_line =~ /\t/){
	       if ($errCount{'tabsinfile'}++ < 10) {
                $Errors{"Vtabsinfile_$_[1]"} = "$_[8]";
		   }
		}
	}


       #check if the root atoms should be present
      
       if ($_[3] eq 'SRC/RPT' || $_[3] eq 'SRC/RHT' || $_[3] eq 'SRC/RAB' || $_[3] eq 'SRC/SSN'){
       my ($v,$rsab) = split(/\-/, $_[4]);	
       if (defined($currentrsab{$rsab})){
             if ($errCount{'root_atoms_exist_in_db'}++ < 10) {
                $Errors{"Vroot_atoms_exist_in_db_$_[1]"} = "$_[4]|$_[3]";
                    }          
            }
         }

	# remember src atoms
	if ($_[2] eq 'SRC' && $_[3] =~ /(RPT|VPT)/) {
	  $$VlSrcAtoms{"$_[3]|$_[4]"} = $_[1];
	}
         if ($_[3] eq 'SRC/VPT' || $_[3] eq 'SRC/VAB'){
               my ($v, $sab) = split(/\-/, $_[4]);
            if (!defined ($$VlVsab2RsabRef{"$sab"})){
             if ($errCount{'badcodeversion'}++ < 10) {
                $Errors{"VBadcodeversion_$_[1]"} = "$_[4]";
          }
        }
      }   

  }

  sub reportInfo {
	my $self = shift;
	my ($key, $ln, @vals);

	print $_EOUT "Atoms: Information\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportInfo();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportInfo();
	}

	# present other class specific information here
	my $ln = keys %infoCount;
	if ($ln > 0) {
	  print $_EOUT "  Info Counts: $ln\n";
	  foreach $key (sort keys(%infoCount)) {
		print $_EOUT "\t$key = $infoCount{$key}\n";
	  }
	  print $_EOUT "\n\n  Info data:\n";
	  foreach $key (sort keys(%Information)) {
		print $_EOUT "\tINFO: $key => $Information{$key}\n";
	  }
	  print $_EOUT "\n\n";
	}

	print $_OUT "\nValid sources are :\n";
	foreach $key (sort keys (%{$VlVsabRef})) {
	  print $_OUT "\t$key\n";
	}
	print $_OUT "\n";
	
	print $_OUT "\nValid Languages are :\n";
	foreach $key (sort keys (%{$VlLatRef})) {
	  print $_OUT "\t$key\n";
	}
	print $_OUT "\n";

	print $_OUT "Valid termgroups are :\n";
	foreach $key (sort keys (%{$VlTGRef})) {
	  print $_OUT "\t$key\n";
	}
	print $_OUT "\n";

	# print min max saids
	my $saidMon = $mons{1};
	@vals = sort {$a <=> $b} (keys (%{$saidMon->getAllHsh()}));
	print $_OUT "\n\tMin/Max saids: <$vals[0], $vals[$#vals]>\n";
  }

  sub reportWarnings {
	my $self = shift;
	my ($key, $ln, @vals);
	print $_EOUT "Atoms: Warnings\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportWarnings();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportWarnings();
	}

	# present other class specific warnings here
	my $ln = keys %wrngCount;
	if ($ln > 0) {
	  print $_EOUT "  Warning Counts: $ln\n";
	  foreach $key (sort keys(%wrngCount)) {
		print $_EOUT "\t$key = $wrngCount{$key}\n";
	  }
	  print $_EOUT "\n\n  Warning data:\n";
	  foreach $key (sort keys(%Warnings)) {
		print $_EOUT "\tWARN: $key => $Warnings{$key}\n";
	  }
	  print $_EOUT "\n\n";
	}
  }
  sub reportErrors {
	my $self = shift;
	my ($key, $ln, @vals);
	print $_EOUT "Atoms: Errors\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportErrors();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportErrors();
	}

	# present other class specific errors here
	my $ln = keys %errCount;
	if ($ln > 0) {
	  print $_EOUT "  Error Counts: $ln\n";
	  foreach $key (sort keys(%errCount)) {
		print $_EOUT "\t$key = $errCount{$key}\n";
	  }
	  print $_EOUT "\n\n  Error Data:\n";
	  foreach $key (sort keys(%Errors)) {
		print $_EOUT "\t****ERR: $key => $Errors{$key}\n";
	  }
	  print $_EOUT "\n\n";
	}
  }

  sub report {
	my ($self) = @_;
	# reset tally fields to what the user has given originally.
	my ($i, $j);
	while (($i, $j) = each(%tallySelection)) {
	  $mons{"$i"}->{'tally'} = $j;
	}

	print $_OUT "Atoms:\n";
	print $_EOUT "Atoms:\n";
	$self->reportErrors();
	$self->reportWarnings();
	$self->reportInfo();
	print $_OUT "End of Atoms check\n";
	print $_EOUT "End of Atoms check\n";
	print $_OUT "#=================\n\n";
	print $_EOUT "#=================\n\n";
  }

  # release memory.
  sub release {
	%mons = ();
	%lmons = ();

	%errCount = ();
	%Errors = ();
	%wrngCount=();
	%Warnings=();
	%infoCount=();
	%Information=();


	%atomAui = ();
	%dupStrCI=();				# case insensitive strings.
	%dupStrCS=();				# case sensitive strings
	%tallySelection = ();

  }
  sub getAllRef {
	my ($self, $which) = @_;
	return $mons{$which}->getAllHsh();
  }


  sub setOtherValids {
	# here we need to copy the valid values collected in this module to the
	# global valids.
	my ($key, $val);
	# also set any HC.RootNodeSaid from config file as a valid said.
	#HC.RootNodeSaid; HC.RootNodeCode.
	my $tmp = $$_theCfg->getEle('HC.RootNodeSaid', '');
	if ($tmp ne '') {
	  $$VlSaidRef{"$tmp"}++;
	}
	while (($key, $val) = each (%{$mons{'1'}->getAllHsh()})) {
	  $$VlSaidRef{"$key"} = $val;
	}
  }

  sub saveResults {
	$$_theLog->logIt("Writing results Doc/Atoms/Src/Tg Info\n");
	my ($self, $l_valids) = @_;

	my $file = $$_theCfg->getEle('TEMPDIR');
	my $file1 = "$file/QaInt_DSTA";

	my ($said, $vsb, $rsb, $key, $val, $lan);

	# save Doc, Source, Termgroup and Atom info.
	open (DSTA, ">:utf8", $file1)
	  or die "Could not open DSTA file $file1\n";
	# doc info
	foreach $key (keys (%{$$l_valids{'Atn'}})) {
	  print DSTA "DOC_ATN|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'Rel'}})) {
	  print DSTA "DOC_REL|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'Rela'}})) {
	  print DSTA "DOC_RELA|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'Tty'}})) {
	  print DSTA "DOC_TTY|$key\n";
	}

	# source info
	foreach $vsb (keys (%{$$l_valids{'Vsab'}})) {
	  print DSTA "SRC_VSAB|$vsb\n";
	}
	foreach $rsb (keys (%{$$l_valids{'Rsab'}})) {
	  print DSTA "SRC_RSAB|$rsb\n";
	}
	foreach $lan (keys (%{$$l_valids{'language'}})) {
	  print DSTA "LANGUAGE|$lan\n";
	}
	while (($vsb, $rsb) = each (%{$$l_valids{'Vsab2Rsab'}})) {
	  print DSTA "SRC_V2R|$vsb|$rsb\n";
	}

	# termgroup info
	foreach $key (keys (%{$$l_valids{'Tg'}})) {
	  print DSTA "TG|$key\n";
	}
	while (($key, $val) = each (%{$$l_valids{'Tg2Sup'}})) {
	  print DSTA "TGSP|$key|$val\n";
	}

	# atom info
	foreach $said (keys (%{$$l_valids{'Said'}})) {
	  print DSTA "SAID|$said\n";
	}
	foreach $key (keys (%{$$l_valids{'AUI'}})) {
	  print DSTA "AUI|$key\n";
	}
	# CDV|code|vsab..
	foreach $key (keys (%{$$l_valids{'CdVsab'}})) {
	  print DSTA "CDV|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'CdRsab'}})) {
	  print DSTA "CDR|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'CdVTg'}})) {
	  print DSTA "CDVTG|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'CdRTg'}})) {
	  print DSTA "CDRTG|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'SauiVsab'}})) {
	  print DSTA "SAV|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'SauiRsab'}})) {
	  print DSTA "SAR|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'ScuiVsab'}})) {
	  print DSTA "SCV|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'ScuiRsab'}})) {
	  print DSTA "SCR|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'SduiVsab'}})) {
	  print DSTA "SDV|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'SduiRsab'}})) {
	  print DSTA "SDR|$key\n";
	}
	while (($key, $val) = each (%{$$l_valids{'SrcAtoms'}})) {
	  print DSTA "SATOM|$key|$val\n";
	}

	# save any RelId, SruiVsab, SruiRsab from the user files (if any).
	foreach $key (keys (%{$$l_valids{'RelId'}})) {
	  print DSTA "RID|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'SruiVsab'}})) {
	  print DSTA "RUIV|$key\n";
	}
	foreach $key (keys (%{$$l_valids{'SruiRsab'}})) {
	  print DSTA "RUIR|$key\n";
	}
	close(DSTA);
	$$_theLog->logIt("Done writing results\n");
  }

  sub recoverResults {
	my ($self, $l_valids, $file1) = @_;
	$$_theLog->logIt("Reading previously saved Doc/Atoms/Src/Tg Info\n");

	if (!defined($file1)) {
	  my $tdir = $$_theCfg->getEle('TEMPDIR');
	  $file1 = "$tdir/QaInt_DSTA";
	}

	print "Entered atoms:recoverResults\n\tFile: $file1\n";
	my ($tag, $key, $skey, $val);

	open (DSTA, "<:utf8", $file1) or die "Could not open file $file1\n";
	my $atnRef = $$l_valids{'Atn'};
	my $relRef = $$l_valids{'Rel'};
	my $relaRef = $$l_valids{'Rela'};
	my $ttyRef = $$l_valids{'Tty'};
	my $vsabRef = $$l_valids{'Vsab'};
	my $lanRef = $$l_valids{'language'};
	my $rsabRef = $$l_valids{'Rsab'};
	my $v2rRef = $$l_valids{'Vsab2Rsab'};
	my $tgRef = $$l_valids{'Tg'};
	my $tgspRef = $$l_valids{'Tg2Sup'};
	my $saidRef = $$l_valids{'Said'};
	my $cdvRef = $$l_valids{'CdVsab'};
	my $cdrRef = $$l_valids{'CdRsab'};
	my $cdvtgRef = $$l_valids{'CdVTg'};
	my $cdrtgRef = $$l_valids{'CdRTg'};
	my $savRef = $$l_valids{'SauiVsab'};
	my $sarRef = $$l_valids{'SauiRsab'};
	my $scvRef = $$l_valids{'ScuiVsab'};
	my $scrRef = $$l_valids{'ScuiRsab'};
	my $sdvRef = $$l_valids{'SduiVsab'};
	my $sdrRef = $$l_valids{'SduiRsab'};
	my $satomRef = $$l_valids{'SrcAtoms'};
	my $auiRef = $$l_valids{'AUI'};

	my $relidRef = $$l_valids{'RelId'};
	my $sruivRef = $$l_valids{'SruiVsab'};
	my $sruirRef = $$l_valids{'SruiRsab'};

	while (<DSTA>) {
	  chomp;
	  next if /^\#/ || /^\s*$/;
	  ($tag,$key) = split(/\|/, $_, 2);
	  if ($tag eq 'DOC_ATN') {
		$$atnRef{"$key"}++;
	  } elsif ($tag eq 'DOC_REL') {
		$$relRef{"$key"}++;
	  } elsif ($tag eq 'DOC_RELA') {
		$$relaRef{"$key"}++;
	  } elsif ($tag eq 'DOC_TTY') {
		$$ttyRef{"$key"}++;
	  } elsif ($tag eq 'SRC_VSAB') {
		$$vsabRef{"$key"}++;
	  } elsif ($tag eq 'SRC_LANGUAGE') {
		$$lanRef{"$key"}++;
	  } elsif ($tag eq 'SRC_RSAB') {
		$$rsabRef{"$key"}++;
	  } elsif ($tag eq 'SRC_V2R') {
		($key, $val) = split(/\|/, $key, 2);
		$$v2rRef{"$key"} = $val;
	  } elsif ($tag eq 'TG') {
		$$tgRef{"$key"}++;
	  } elsif ($tag eq 'TGSP') {
		($key, $val) = split(/\|/, $key, 2);
		$$tgspRef{"$key"} = $val;
	  } elsif ($tag eq 'SAID') {
		$$saidRef{"$key"}++;
	  } elsif ($tag eq 'AUI') {
		$$auiRef{"$key"}++;
	  } elsif ($tag eq 'CDV') {
		$$cdvRef{"$key"}++;
	  } elsif ($tag eq 'CDR') {
		$$cdrRef{"$key"}++;
	  } elsif ($tag eq 'CDVTG') {
		$$cdvtgRef{"$key"}++;
	  } elsif ($tag eq 'CDRTG') {
		$$cdrtgRef{"$key"}++;
	  } elsif ($tag eq 'SAV') {
		$$savRef{"$key"}++;
	  } elsif ($tag eq 'SAR') {
		$$sarRef{"$key"}++;
	  } elsif ($tag eq 'SCV') {
		$$scvRef{"$key"}++;
	  } elsif ($tag eq 'SCR') {
		$$scrRef{"$key"}++;
	  } elsif ($tag eq 'SDV') {
		$$sdvRef{"$key"}++;
	  } elsif ($tag eq 'SDR') {
		$$sdrRef{"$key"}++;
	  } elsif ($tag eq 'SATOM') {
		($key, $val) = split(/\|/, $key, 2);
		$$satomRef{"$key"} = $val;
	  } elsif ($tag eq 'RID') {
		$$relidRef{"$key"}++;
	  } elsif ($tag eq 'RUIV') {
		$$sruivRef{"$key"}++;
	  } elsif ($tag eq 'RUIR') {
		$$sruirRef{"$key"}++;
	  }
	}
	close(SAIDS);

	$$_theLog->logIt("Done Reading Atoms/Src/Tg Info\n");
  }

}
1

