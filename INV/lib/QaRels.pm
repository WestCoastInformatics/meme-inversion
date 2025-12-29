#!/usr/bin/perl
#!/usr/bin/perl
#

# fields
# 1  = src_relationship_id
# 2  = level
# 3  = id_1
# 4  = relationship_name
# 5  = relationship_attribute
# 6  = id_2
# 7  = source
# 8  = source_of_label
# 9  = status
# 10 = tobereleased
# 11 = released
# 12 = suppressible
# 13 = id_type_1
# 14 = id_qualifier_1
# 15 = id_type_2
# 16 = id_qualifier_2
# 17 = source_rui
# 18 = relationship_group

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaRels;

use FldMon;
use iutl;

{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT, $temp);
  my ($VlVsabRef, $VlRelaRef, $VlVsab2RsabRef);
  my ($VlSruiVsabRef, $VlSruiRsabRef, $VlRelIdRef);

  my (%_valSrcAtomCd);  # note this is not a reference. rather a copy.


  my %mons=();
  my %lmons=();
  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();

  my %relRuis = ();
  my %unqSRuis = ();
  my %id12q12 = ();
  my %ntrels = ();
  my %tallySelection = ();


  my $pat3 = qr{^(associated_with|consists_of|constitutes|contains|contained_in|ingredient_of|has_ingredient)$};
  my $pat3b = qr{^(conceptual_part_of|form_of|isa|part_of|tradname_of)$};
  my $pat3c = qr{^(has_conceptual_part|has_form|inverse_isa|has_part|has_tradname)$};
  my $pat5 = qr{^(ROOT_SOURCE_AUI|SOURCE_AUI|SRC_ATOM_ID)$};
  my $pat6 = qr{^(SRC_ATOM_ID|SRC_REL_ID|CUI|AUI|RUI)$};
  my $pat8 = qr{^(translation_of|version_of)$};
  my $pat100 = qr{CODE};

  # Valid rela/rel combinations
  my %valid_relarel = (	'ingredient_of' => "RT",
						'has_conceptual_part' => "BT",
						'has_ingredient' => "BT",
						'has_form' => "BT",
						'inverse_isa' => "BT",
						'has_part' => "BT",
						'has_tradename' => "BT",

						'ingredient_of' => "NT",
						'has_ingredient' => "NT",
						'mapped_from' => "NT",
						'conceptual_part_of' => "NT",
						'form_of' => "NT",
						'isa' => "NT",
						'part_of' => "NT",
						'tradename_of' => "NT",

						'associated_with' => "RT",
						'consists_of' => "RT",
						'constitutes' => "RT",
						'contains' => "RT",
						'contained_in' => "RT",
						'ingredient_of' => "RT",
						'has_ingredient' => "RT"
					  );



  # tests BEGIN tests BEGIN tests BEGIN tests BEGIN tests BEGIN
  my @IL=();

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

  # ILM_1: VSAB not equal to Source of Label
  my $subref_checkVsabNeSL = \&nullFunc;
  sub make_checkVsabNeSL {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkVsabNeSL = sub {
	  if ($IL[7] ne $IL[8] && $$countHash{'VVsabNeSL'}++ < 10) {
		$$msgHash{"VVsabNeSL_$IL[1]"} = "$IL[1]|$IL[7]|$IL[8]";
	  }
	}
  }

  # ILM_2: self referential relationships
  my $subref_checkSelfRefRels = \&nullFunc;
  sub make_checkSelfRefRels {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkSelfRefRels = sub {
	  if ($IL[3] eq $IL[6] && $IL[13] eq $IL[15] && $IL[14] eq $IL[16]
		  && $$countHash{'VSelfRefRels'}++ < 10) {
		$$msgHash{"VSelfRefRels_$IL[1]"} = "$IL[1]|$IL[7]";
	  }
	}
  }

  # ILM_3: conflicting rel/rela
  my $subref_checkInvRelRela = \&nullFunc;
  sub make_checkInvRelRela {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvRelRela = sub {
	  if (($IL[4] ne 'RT' && $IL[5] =~ /$pat3/)
		  || ($IL[4] ne 'NT' && $IL[5] =~ /$pat3b/)
		  || ($IL[4] ne 'BT' && $IL[5] =~ /$pat3c/)) {
		if ($$countHash{'VInvRelRela'}++ < 10) {
		  $$msgHash{"VInvRelRela_$IL[1]"} = "$IL[1]|$IL[7]|$IL[4]|$IL[5]";
		}
	  }
	}
  }

  # ILM_4: Non Unique RUIS
  my $subref_checkNonUniqueRuis = \&nullFunc;
  sub make_checkNonUniqueRuis {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	# Check with the folks in the inversion group and change the following
	# relPk fiels: id1|$id2|sab|relLvl|rel|rela|srui|relGrp
	# = ILFields [13,14,3, 15,16,6, 7, 2, 4, 5, 17, 18]
	# == 2,3,4,5,6,7,13,14,15,16,17,18
	$subref_checkNonUniqueRuis = sub {
	  my $tmp = join('|', @IL[2..7,13..18]);
	  if (defined($relRuis{"$tmp"})) {
		if ($$countHash{'VNonUniqueRuis'}++ < 10) {
		  my $prevTmp = $relRuis{"$tmp"};
		  $$msgHash{"VNonUniqueRuis_$IL[1]"} = "<$prevTmp>: $tmp";
		}
	  } else {
		$relRuis{"$tmp"} = $IL[1];
	  }
	}
  }

  # ILM_5: SFO/LFO not connected to any atom
  my $subref_checkOrphanSFOLFO = \&nullFunc;
  sub make_checkOrphanSFOLFO {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkOrphanSFOLFO = sub {
	  if ($IL[4] eq 'SFO/LFO'
		  && ($IL[13] !~ /$pat5/ || $IL[15] !~ /$pat5/)
		  && $$countHash{'VOrphanSFOLFO'}++ < 10) {
		$$msgHash{"EOrphanSFOLFO_$IL[1]"} = "$IL[7]|$IL[13]|$IL[15]";
	  }
	}
  }

  # ILM_6: inv sgs for translation_of and version rel
  my $subref_checkInvSgsTransVer = \&nullFunc;
  sub make_checkInvSgsTransVer {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	#$subref_checkInvSgsTransVer = sub {
	#if ($IL[5] =~ /$pat8/ && $IL[7] eq 'SRC'
	#  && ($IL[13] ne 'CODE_TERMGROUP' || $IL[15] ne 'CODE_TERMGROUP' 
	#      || $IL[14] ne 'SRC/RPT' || $IL[16] ne 'SRC_RPT')
	#  && $$countHash{'VInvSgsTransVer'}++ < 10) {
	#$$msgHash{"VInvSgsTransVer_$IL[1]"} = "$IL[1]|$IL[5]";
	#}
	#}

	$subref_checkInvSgsTransVer = sub {
	  if ($IL[5] =~ /$pat8/ && $IL[7] eq 'SRC'
		  && ($IL[13] ne 'CODE_SOURCE' || $IL[15] ne 'CODE_SOURCE'
			  || $IL[14] ne 'SRC' || $IL[16] ne 'SRC')
		  && $$countHash{'VInvSgsTransVer'}++ < 10) {
		$$msgHash{"VInvSgsTransVer_$IL[1]"} = "$IL[1]|$IL[5]";
	  }
	}
  }

  # ILM_7: Non Unique SRUIS (don't check recs with SRUI starts with ~DA)
  my $subref_checkNonUniqueSRuis = \&nullFunc;
  sub make_checkNonUniqueSRuis {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	# Check with the folks in the inversion group and change the following
	$subref_checkNonUniqueSRuis = sub {
	  if ("$IL[17]" !~ /^~DA/) {
		if (defined($unqSRuis{"$IL[17]"})) {
		  if ($$countHash{'VNonUniqueSRuis'}++ < 10) {
			$$msgHash{"VNonUniqueSRuis_$IL[1]"} = "$IL[17]";
		  }
		} else {
		  $unqSRuis{"$IL[17]"} = $IL[1];
		}
	  }
	}
  }






  # IFM_1: sgId1 not in classes
  my $subref_checkInvSgId1 = \&nullFunc;
  sub make_checkInvSgId1 {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvSgId1 = sub {
	  if (my $temp = SrcQa->InvalidSg($IL[3], $IL[13], $IL[14])) {
		if ($$countHash{"${temp}1"}++ < 25) {
		  $$msgHash{"${temp}1_$IL[1]"} = "$IL[3]|$IL[13]|$IL[14]";
		}
	  }
	}
  }

  # IFM_2: sgId2 not in classes
  my $subref_checkInvSgId2 = \&nullFunc;
  sub make_checkInvSgId2 {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvSgId2 = sub {
	  if (my $temp = SrcQa->InvalidSg($IL[6], $IL[15], $IL[16])) {
		if ($$countHash{"${temp}2"}++ < 10) {
		  $$msgHash{"${temp}2_$IL[1]"} = "$IL[6]|$IL[15]|$IL[16]";
		}
	  }
	}
  }

  # IFM_3: RELA not in MRDOC
  my $subref_checkInvRela = \&nullFunc;
  sub make_checkInvRela {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvRela = sub {
	  if ($IL[5] ne '' &&  (!defined($$VlRelaRef{"$IL[5]"}))
		  && $$countHash{"VInvRela"}++ < 10) {
		$$msgHash{"VInvRela_$IL[1]"} = "$IL[5]";
	  }
	}
  }

  # IFM_4: Invalid Rela Value
  my $subref_checkInvRela2 = \&nullFunc;
  sub make_checkInvRela2 {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvRela2 = sub {
	  # nothing here. Need to implement this.
	}
  }

  # IFM_5: Vsab not in Sources.
  my $subref_checkInvVsab = \&nullFunc;
  sub make_checkInvVsab {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvVsab = sub {
	  if ((!defined($$VlVsabRef{"$IL[7]"}))
		  && $$countHash{'VInvVSab'}++ < 10) {
		$$msgHash{"VInvVSab_$IL[1]"} = "$IL[7]";
	  }
	}
  }

  # IFM_6: Duplicate Relationships
  my $subref_checkDupRel = \&nullFunc;
  sub make_checkDupRel {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkDupRel = sub {
	  # not yet implemnted.
	}
  }

  # IFM_7: Non-ENG Root SRC Atom without translation_of Relationship
  my $subref_checkMissingTransRel = \&nullFunc;
  sub make_checkMissingTransRel {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkMissingTransRel = sub {
	  my $key = shift;
	  if ($$countHash{'VMissingTransRel'}++ < 10) {
		$$msgHash{"VMissingTransRel_$key"}++;
	  }
	}
  }

  # IFM_8: Versioned SRC Atom without version_of Relationship
  my $subref_checkMissingVersionRel = \&nullFunc;
  sub make_checkMissingVersionRel {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkMissingVersionRel = sub {
	  my $key = shift;
	  if ($$countHash{'VMissingVersionRel'}++ < 10) {
		$$msgHash{"VMissingVersionRel_$key"}++;
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

	$VlRelaRef = $$l_valids{'Rela'};
	$VlVsabRef = $$l_valids{'Vsab'};
	$VlVsab2RsabRef = $$l_valids{'Vsab2Rsab'};

	$VlRelIdRef = $$l_valids{'RelId'};
	$VlSruiVsabRef = $$l_valids{'SruiVsab'};
	$VlSruiRsabRef = $$l_valids{'SruiRsab'};


	my ($key, $val);
	while (($key,$val) = each(%{$$l_valids{'SrcAtoms'}})) {
	  $_valSrcAtomCd{"$key"} = $val; # deep copy.
	}
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
	my ($i, $fnum, $tHash, $temp, $temp1);

	my $lmStr = "IlLineMon.Relation";
	my $fmStr = "IlFileMon.Relation";

	## 1. create FieldMons
	$tHash = \%{$$_theCfg->getHashRef('FieldMon.Relation')};
	foreach $i (sort keys (%{$tHash})) {
	  $fnum = $$_theCfg->getEle("FieldMon.Relation.$i.fieldNum", '0');
	  if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Relation', $i);
	  } else {
		$$_theLog->logError("Encountered invalid ".
							"FieldMon.Relation.$i.fieldNum\n");
	  }
	}

	## 2. create LineMons
	$tHash = \%{$$_theCfg->getHashRef('LineMon.Relation')};
	foreach $i (sort keys(%{$tHash})) {
	  $lmons{$i} = new LineMon('Relation',$i);
	}


	## 3. read inline LineMons and create the check functions.
	# ILM_0: field count
	if (($temp = $$_theCfg->getEle("$lmStr.0.enable", 0)) == 1) {
	  $temp = $$_theCfg->getEle("$lmStr.0.fieldCt", 18);
	  if ($temp != 0) {
		$temp += 2;
		$temp1 = $$_theCfg->getEle("lmStr.0.type", 'info');
		&make_checkFldCount($temp, $temp1);
	  }
	}

	&crTest($lmStr, 1, \&make_checkVsabNeSL,
			"ILM_1: VSAB not equal to Source of Label");

	&crTest($lmStr, 2, \&make_checkSelfRefRels,
			"ILM_2: self referential relationships");

	&crTest($lmStr, 3, \&make_checkInvRelRela,
			"ILM_3: conflicting rel/rela");

	&crTest($lmStr, 4, \&make_checkNonUniqueRuis,
			"ILM_4: Non Unique RUIS");

	&crTest($lmStr, 5, \&make_checkOrphanSFOLFO,
			"ILM_5: SFO/LFO not connected to any atom");

	&crTest($lmStr, 6, \&make_checkInvSgsTransVer,
			"ILM_6: inv sgs for translation_of and version rel");

	&crTest($lmStr, 7, \&make_checkNonUniqueSRuis,
			"ILM_7: non unique SRUIs");


	## 4. read inline FileMons and create the check functions
	&crTest($fmStr, 1, \&make_checkInvSgId1,
			"IFM_1: sgId1 not in classes");

	&crTest($fmStr, 2, \&make_checkInvSgId2,
			"IFM_2: sgId2 not in classes");

	&crTest($fmStr, 3, \&make_checkInvRela,
			"IFM_3: RELA not in MRDOC");

	&crTest($fmStr, 4, \&make_checkInvRela2,
			"IFM_4: Invalid Rela Value");

	&crTest($fmStr, 5, \&make_checkInvVsab,
			"IFM_5: Vsab not in Sources.");

	&crTest($fmStr, 6, \&make_checkDupRel,
			"IFM_6: Duplicate Relationships");

	&crTest($fmStr, 7, \&make_checkMissingTransRel,
			"IFM_7: Non-ENG Root SRC Atom without translation_of Relation");

	&crTest($fmStr, 8, \&make_checkMissingVersionRel,
			"IFM_8: Versioned SRC Atom without version_of Relation");


	# remember the following tally fields: relId[1]
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

	@IL = @_;
    my @tmparray = @_;
	my ($key);

	## do FieldMon Checks.
	foreach $key (keys (%mons)) {
	  $mons{"$key"}->process($_[$key], $_[1]);
	}

	## do LineMon Checks.
	foreach $key (keys (%lmons)) {
	  $lmons{"$key"}->process(@tmparray[1..$#tmparray]);
	}

	## Check Inline LineMons
	# ILM_0: field count check.
	&$subref_checkFldCount();

	# ILM_1: VSAB not equal to Source of Label
	&$subref_checkVsabNeSL();

	# ILM_2: self referential relationships
	&$subref_checkSelfRefRels();

	# ILM_3: conflicting rel/rela
	&$subref_checkInvRelRela();

	# ILM_4: Non Unique RUIS
	&$subref_checkNonUniqueRuis();

	# ILM_5 SFO/LFO not connected to any atom
	&$subref_checkOrphanSFOLFO();

	# ILM_6: inv sgs for translation_of and version rel
	&$subref_checkInvSgsTransVer();

	# ILM_7: Non Unique SRUIS (don't check recs with SRUI starts with ~DA)
	&$subref_checkNonUniqueSRuis();


	## Check Inline FileMons
	# IFM_1: sgId1 not in classes
	&$subref_checkInvSgId1();

	# IFM_2: sgId2 not in classes
	&$subref_checkInvSgId2();

	# IFM_3: RELA not in MRDOC
	&$subref_checkInvRela();

	# IFM_4: Invalid Rela Value - not yet implemented.
	#&$subref_checkInvRela2();

	# IFM_5: Vsab not in Sources.
	&$subref_checkInvVsab();

	# IFM_6: Duplicate Relationships - not yet impmented.
	#&$subref_checkDupRel();


	# IFM_7/8: prepare data
	# check if SRC/RPT or SRC/RPT without translation_of rels
	#    if ($_[7] eq 'SRC') {
	#      if ($_[13] eq 'CODE_TERMGROUP') {
	#	if ($_[14] eq 'SRC/RPT' && $_[5] eq 'has_translation') {
	#	  delete $_valSrcAtomCd{"SRC/RPT|@_[3]"};
	#	}
	#	elsif ($_[14] eq 'SRC/VPT' && $_[5] eq 'has_version') {
	#	  delete $_valSrcAtomCd{"SRC/VPT|@_[3]"};
	#	}
	#      }
	#      if ($_[15] eq 'CODE_TERMGROUP') {
	#	if ($_[16] eq 'SRC/RPT' && $_[5] eq 'translation_of') {
	#	  delete $_valSrcAtomCd{"SRC/RPT|@_[6]"};
	#	}
	#	elsif ($_[16] eq 'SRC/VPT' && $_[5] eq 'version_of') {
	#	  delete $_valSrcAtomCd{"SRC/VPT|@_[6]"};
	#	}
	#      }
	#    }

	# code_termgroup is deprecated
	if ($_[7] eq 'SRC') {
	  if ($_[13] eq 'CODE_SOURCE') {
		if ($_[14] eq 'SRC' && $_[5] eq 'has_translation') {
		  delete $_valSrcAtomCd{"SRC/RPT|@_[3]"};
		} elsif ($_[14] eq 'SRC' && $_[5] eq 'has_version') {
		  delete $_valSrcAtomCd{"SRC/VPT|@_[3]"};
		}
	  }
	  if ($_[15] eq 'CODE_SOURCE') {
		if ($_[16] eq 'SRC' && $_[5] eq 'translation_of') {
		  delete $_valSrcAtomCd{"SRC/RPT|@_[6]"};
		} elsif ($_[16] eq 'SRC' && $_[5] eq 'version_of') {
		  delete $_valSrcAtomCd{"SRC/VPT|@_[6]"};
		}
	  }
	}

       ## check if any tabs exist 
       if ($_[3] ne ''){
    my $full_line  = "$_[1]|$_[2]|$_[3]|$_[4]|$_[5]|$_[6]|$_[7]|$_[8]|$_[9]_$[10]|$_[11]|$_[12]|$_[13]|$_[14]|$_[15]|$_[16]|$_[17]|$_[18]";
	 if ($full_line =~ /\t/){
	       if ($errCount{'tabsinfile'}++ < 10) {
                $Errors{"Vtabsinfile_$_[3]"} = "$_[6]";
		   }
		}
	}


	# remember sruiVsab and sruiRsab here
	if ($_[17] ne '') {
	  $$VlSruiVsabRef{"$_[17]|$_[7]"}++;
	  if (defined($$VlVsab2RsabRef{"$_[7]"})) {
		$$VlSruiRsabRef{"$_[17]|$$VlVsab2RsabRef{$_[7]}"}++;
	  }
	}
  }

  sub reportInfo {
	my $self = shift;
	my ($key, $ln, @vals);

	print $_EOUT "Relations: Information\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportInfo();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportInfo();
	}


	my $ln = keys %infoCount;
	if ($ln > 0) {
	  print $_EOUT "  Info Counts: $ln\n";
	  # present other class specific ifnormation here
	  foreach $key (sort keys(%infoCount)) {
		print $_EOUT "\t$key = $infoCount{$key}\n";
	  }
	  print $_EOUT "\n\n  Info data:\n";
	  foreach $key (sort keys(%Information)) {
		print $_EOUT "\tINFO: $key => $Information{$key}\n";
	  }
	  print "\n\n";
	}
  }

  sub reportWarnings {
	my $self = shift;
	my ($key, $ln, @vals);
	print $_EOUT "Relations: Warnings\n";

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
	  print "\n\n";
	}
  }
  sub reportErrors {
	my $self = shift;
	my ($key, $ln, @vals);
	print $_EOUT "Relations: Errors\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportErrors();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportErrors();
	}

	# present other error numbers.
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
	my ($i, $j, $key);
	while (($i, $j) = each(%tallySelection)) {
	  $mons{"$i"}->{'tally'} = $j;
	}


	# record other errors here.
	foreach $key (keys(%_valSrcAtomCd)) {
	  if ($key =~ /RPT/) {
		# IFM_7: Non-ENG Root SRC Atom without translation_of Relationship
		&$subref_checkMissingTransRel();
	  } else {
		# IFM_8: Versioned SRC Atom without version_of Relationship
		&$subref_checkMissingVersionRel();
	  }
	}

	print $_OUT "Relations:\n";
	print $_EOUT "Relations:\n";
	$self->reportErrors();
	$self->reportWarnings();
	$self->reportInfo();
	print $_OUT "End of Relations check\n";
	print $_EOUT "End of Relations check\n";
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


	%relRuis = ();
	%unqSRuis = ();
	%id12q12 = ();
  }

  sub getAllRef {
	my ($self, $which) = @_;
	return $mons{$which}->getAllHsh();
  }

  sub setOtherValids {
	# here we need to copy the valid values collected in this module to the
	# global valids.
	my ($key, $val);
	while (($key, $val) = each (%{$mons{'1'}->getAllHsh()})) {
	  $$VlRelIdRef{"$key"} = $val;
	}
  }

  sub saveResults {

	$$_theLog->logIt("Writing results Relations Info\n");

	my $file = $$_theCfg->getEle('TEMPDIR');
	my $file1 = "$file/QaInt_REL";

	my ($said, $vsb, $rsb, $key, $val);

	# save Rel info
	open (QAREL, ">:utf8", $file1)
	  or die "Could not open Rel file $file1\n";
	# rel info
	foreach $key (keys (%{$mons{'1'}->getAllHsh()})) {
	  print QAREL "RID|$key\n";
	}

	foreach $key (keys (%{$VlSruiVsabRef})) {
	  print QAREL "RUIV|$key\n";
	}
	foreach $key (keys (%{$VlSruiRsabRef})) {
	  print QAREL "RUIR|$key\n";
	}
	close(QAREL);
  }

  sub recoverResults {
	my ($self, $l_valids) = @_;
	$$_theLog->logIt("Reading previously saved Relations Info\n");

	my $file = $$_theCfg->getEle('TEMPDIR');
	my $file1 = "$file/QaInt_REL";

	my ($key, $val, $tag);

	open (QAREL, "<:utf8", $file1) or die "Could not open file $file1\n";
	my $ridRef = $$l_valids{'RelId'};
	my $ruivRef = $$l_valids{'SruiVsab'};
	my $ruirRef = $$l_valids{'SruiRsab'};

	while (<QAREL>) {
	  chomp;
	  next if /^\#/ || /^\s*$/;
	  ($tag,$key) = split(/\|/, $_, 2);
	  if ($tag eq 'RID') {
		$$ridRef{"$key"}++;
	  } elsif ($tag eq 'RUIV') {
		$$ruivRef{"$key"}++;
	  } elsif ($tag eq 'RUIR') {
		$$ruirRef{"$key"}++;
	  }
	}
	close(QAREL);
  }

}

1

