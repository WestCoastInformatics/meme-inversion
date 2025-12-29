#!/usr/bin/perl
#!/usr/bin/perl
#

# fields
# 1  = source_atom_id_1
# 2  = relationship_name
# 3  = relationship_attribute
# 4  = source_atom_id_2
# 5  = source
# 6  = source_of_label
# 7  = hcd
# 8  = parent_treenum
# 9  = release_mode
# 10 = source_rui
# 11 = relationship_group
# 12 = sg_id_1
# 13 = sg_type_1
# 14 = sg_qualifier_1
# 15 = sg_id_2
# 16 = sg_type_2
# 17 = sg_qualifier_2


unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaCxts;

use FldMon;
use iutl;

{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT);
  my ($VlSaidRef);
  my ($VlRelaRef, $VlVsab2RsabRef, $VlSruiVsabRef);
  my ($VlSruiRsabRef, $temp);

  my %mons=();
  my %lmons=();
  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();

  my %cxtUis=();
  my %parsgids1 =();  
  my %parsgids2 =();
  my %parsgids3 =();

  my $pat3 = qr{^(SRC_ATOM_ID|SRC_REL_ID|CUI|AUI|RUI)$};


  my $recId = '';

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
		  $$msgHash{"VFieldCount_$recId"} = $l;
		}
	  }
	}
  }

  # ILM_1: PAR with null PTR
  my $subref_checkParWNullPtr = \&nullFunc;
  sub make_checkParWNullPtr {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkParWNullPtr = sub {
	  if ($IL[2] eq 'PAR' && $IL[8] eq ''
		  && $$countHash{'VParWNullPtr'}++ < 10) {
		$Errors{"EParWNullPtr_$recId"}++;
	  }
	}
  }

  # ILM_2: non unique RUI fields
  my $subref_checkNonUniqueRui = \&nullFunc;
  sub make_checkNonUniqueRui {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNonUniqueRui = sub {
	  my $tmp;
	  $tmp = "$IL[5]|$IL[2]|$IL[3]|$IL[12]|$IL[13]|$IL[14]|$IL[15]|$IL[16]|$IL[17]|$IL[8]";
	  if (defined($cxtUis{"$tmp"})) {
		if ($$countHash{'VNonUniqueRui'}++ < 10) {
		  my $tmp1 = $cxtUis{"$tmp"};
		  $$msgHash{"VNonUniqueRui_$recId"} = "$tmp1";
		}
	  } else {
		$cxtUis{"$tmp"} = $recId;
	  }
	}
  }

  # ILM_3: SIB rel with non-null RELA (sab UWDA is an exception).
  my $subref_checkSibWRela = \&nullFunc;
  sub make_checkSibWRela {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkSibWRela = sub {
	  if ($IL[2] eq 'SIB' && $IL[5] ne 'UWDA' && $IL[3] ne ''
		  && $$countHash{'VSibWRela'}++ < 10) {
		$$msgHash{"VSibWRela_$recId"} = "@_[1]|@_[4]|@_[3]";
	  }
	}
  }

  # ILM_4: VSAB ne source of label
  my $subref_checkVsabNeSL = \&nullFunc;
  sub make_checkVsabNeSL {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkVsabNeSL = sub {
	  if ($IL[5] ne $IL[6] && $$countHash{'VVsabNeSL'}++ < 10) {
		$$msgHash{"EVsabNeSL_$recId"} = "$IL[1]|$IL[4]|$IL[5]|$IL[6]";
	  }
	}
  }

  # ILM_5: parent mismatch
  my $subref_checkParentMismatch = \&nullFunc;
  sub make_checkParentMismatch {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkParentMismatch = sub {
	  # do this only when rel is 'PAR'
	  if ($IL[2] eq 'PAR' && $IL[8] !~ /$IL[4]$/) {
		if ($$countHash{'VParentMismatch'}++ < 10) {
		  $$msgHash{"VParentMismatch_$recId"} = "$IL[8]";
		}
	  }

	  # also check for cycles in ptr in all the cases
	  if ($IL[8] ne '') {
		my ($temp, $ln1, $ln2);
		my %seenPos = ();
		foreach $temp (split(/\./, $IL[8])) {
		  $ln1++;
		  $seenPos{"$temp"}++;
		  # may want to check if each pos is valid or not here.
		  if (!defined($$VlSaidRef{"$temp"})) {
			if ($errCount{'invTreePosInPtr'}++ < 10) {
			  $Errors{"VInvTreePosInPtr_$recId"} = $temp;
			}
		  }
		}
		$ln2 = keys %seenPos;
		if (($ln1 > $ln2) && $$countHash{'VCyclesInPtr'}++ < 10) {
		  $$msgHash{"VCyclesInPtr_$recId"} = $IL[8];
		}
	  }
	}
  }

 #ILM_6: SRC_ATOM_ID_1 not equal to SGID_1

   my $subref_checkSaid1toSgid1 = \&nullFunc;
  sub make_checkSaid1toSgid1 {
        my ($msgType) = @_;
        my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

        $subref_checkSaid1toSgid1 = sub {
                 if ($IL[13] eq 'SRC_ATOM_ID'){
          if ($IL[1] ne $IL[12] && $$countHash{'Said1neSgid1'}++ < 10) {
                $$msgHash{"ESaid1neSgid1_$recId"} = "$IL[1]|$IL[12]|$IL[13]";
            }
                  }
        }
  }


  #ILM_7: SRC_ATOM_ID_2 not equal to SGID_2

    my $subref_checkSaid2toSgid2 = \&nullFunc;
  sub make_checkSaid2toSgid2 {
        my ($msgType) = @_;
        my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

        $subref_checkSaid2toSgid2 = sub {
                 if ($IL[16] eq 'SRC_ATOM_ID'){
          if ($IL[4] ne $IL[15] && $$countHash{'Said2neSgid2'}++ < 10) {
                $$msgHash{"ESaid2neSgid2_$recId"} = "$IL[4]|$IL[15]|$IL[16]";
            }
                  }
        }
  }

 #ILM_8: cases where SIB is also a parent

     my $subref_checkdupliatePARSIB = \&nullFunc;
  sub make_checkdupliatePARSIB {
        my ($msgType) = @_;
        my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

       $subref_checkdupliatePARSIB = sub {
          my($tmp1, $tmp2, $tmp3, $tmp4, $tmp5, $tmp6, $tmp0, $tmp7, $tmp8, $tmp9);
            $tmp0= "$IL[12]|$IL[15]|PAR";
            $tmp1= "$IL[12]|$IL[15]|SIB";
            $tmp2= "$IL[12]|$IL[15]|CHD";
            $tmp3= "$IL[15]|$IL[12]|PAR";
            $tmp4= "$IL[15]|$IL[12]|SIB";
            $tmp5= "$IL[15]|$IL[12]|CHD";
            $tmp6 = "$IL[12]|$IL[15]|$IL[2]";


                  if (defined($parsgids1{"$tmp6"}) || defined($parsgids2{"$tmp6"}) || defined($parsgids3{"$tmp6"})){
                      #if ($$countHash{'duplicateParSib'}++ < 10){
                         if ($wrngCount{'duplicateParSib'}++ < 10){
                  #$$msgHash{"EduplicateParSib_$recId"} = "$IL[12]|duplicate|$IL[15]";
                         $Warnings{"EduplicateParSib_$recId"} = "$IL[12]|duplicate|$IL[15]";
                                      }
                                   } else {
                                         if ($IL[2] eq 'CHD'){
                                              #print "loop1|$IL[12]|$IL[15]|$IL[2]\n";
                                             $parsgids1{"$tmp0"} = $recId;
                                             $parsgids1{"$tmp1"} = $recId;
                                             #$parsgids1{"$tmp2"} = $recId;
                                             $parsgids1{"$tmp4"} = $recId;
                                             $parsgids1{"$tmp5"} = $recId;

                                            } elsif($IL[2] eq 'PAR') {
                                             #$parsgids2{"$tmp0"} = $recId;
                                             $parsgids2{"$tmp1"} = $recId;
                                             $parsgids2{"$tmp2"} = $recId;
                                             $parsgids2{"$tmp3"} = $recId;
                                             $parsgids2{"$tmp4"} = $recId;
                                                       
                                            } else {
                                             $parsgids3{"$tmp0"} = $recId;
                                             $parsgids3{"$tmp1"} = $recId;
                                             $parsgids3{"$tmp2"} = $recId;
                                             $parsgids3{"$tmp3"} = $recId;
                                             $parsgids3{"$tmp4"} = $recId;
                                             $parsgids3{"$tmp5"} = $recId;
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
	  if (my $temp = SrcQa->InvalidSg($IL[12], $IL[13], $IL[14])) {
		if ($$countHash{"${temp}1"}++ < 10) {
		  $$msgHash{"${temp}1_$recId"} = "$IL[12]|$IL[13]|$IL[14]";
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
	  if (my $temp = SrcQa->InvalidSg($IL[15], $IL[16], $IL[17])) {
		if ($$countHash{"${temp}2"}++ < 10) {
		  $$msgHash{"${temp}2_$recId"} = "$IL[15]|$IL[16]|$IL[17]";
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
	  if ($IL[3] ne '' && $IL[3] ne 'isa' && (!defined($$VlRelaRef{"$IL[3]"}))
		  && $$countHash{"VInvRela"}++ < 10) {
		$$msgHash{"VInvRela_$recId"} = "$IL[3]";
	  }
	}
  }

  # IFM_4: Invalid RELA Value
  my $subref_checkInvRela2 = \&nullFunc;
  sub make_checkInvRela2 {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvRela2 = sub {
	  # not yet implemented.
	}
  }

  # IFM_5: VSAB not in Sources
  my $subref_checkInvVSab = \&nullFunc;
  sub make_checkInvVSab {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvVSab = sub {
	  if ((!defined($$VlVsab2RsabRef{"$IL[5]"}))
		  && $$countHash{'VInvVSab'}++ < 10) {
		$$msgHash{"VInvVSab_$recId"} = "$IL[5]";
	  }
	}
  }

  # IFM_6: Dupicate Relationships
  my $subref_checkDupRel = \&nullFunc;
  sub make_checkDupRel {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkDupRel = sub {
	  # not yet implemented.
	}
  }

  # IFM_7: Verify Parent Matches SrcAtomId2
  my $subref_checkNotDone7 = \&nullFunc;
  sub make_checkNotDone7 {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNotDone7 = sub {
	}
  }

  # IFM_8: HCD Matches Atom CODE
  my $subref_checkNotDone8 = \&nullFunc;
  sub make_checkNotDone8 {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNotDone8 = sub {
	}
  }

  # IFM_9: Mixed Null and non-NULL HCD
  my $subref_checkNotDone9 = \&nullFunc;
  sub make_checkNotDone9 {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNotDone9 = sub {
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
	$VlVsab2RsabRef = $$l_valids{'Vsab2Rsab'};
	$VlSruiVsabRef = $$l_valids{'SruiVsab'};
	$VlSruiRsabRef = $$l_valids{'SruiRsab'};

	$VlSaidRef = $$l_valids{'Said'};
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

	my $lmStr = "IlLineMon.Context";
	my $fmStr = "IlFileMon.Context";


	## 1. Create FieldMons
	$tHash = \%{$$_theCfg->getHashRef('FieldMon.Context')};
	foreach $i (sort keys (%{$tHash})) {
	  $fnum = $$_theCfg->getEle("FieldMon.Context.$i.fieldNum", '0');
	  if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Context', $i);
	  } else {
		$$_theLog->logError("Encountered invalid ".
							"FieldMon.Context.$i.fieldNum\n");
	  }
	}

	## 2. Create LineMons
	$tHash = \%{$$_theCfg->getHashRef('LineMon.Context')};
	foreach $i (sort keys(%{$tHash})) {
	  $lmons{$i} = new LineMon('Context',$i);
	}


	## 3. read inline LineMons and create the functions.
	# ILM_0: field count
	if (($temp = $$_theCfg->getEle("$lmStr.0.enable", 0)) == 1) {
	  $temp = $$_theCfg->getEle("$lmStr.0.fieldCt", 17);
	  if ($temp != 0) {
		$temp += 2;
		$temp1 = $$_theCfg->getEle("lmStr.0.type", 'info');
		&make_checkFldCount($temp, $temp1);
	  }
	}

	&crTest($lmStr, 1, \&make_checkParWNullPtr,
			"ILM_1: PAR with null PTR");

	&crTest($lmStr, 2, \&make_checkNonUniqueRui,
			"ILM_2: non unique RUI fields");

	&crTest($lmStr, 3, \&make_checkSibWRela,
			"ILM_3: SIB rel with non-null RELA");

	&crTest($lmStr, 4, \&make_checkVsabNeSL,
			"ILM_4: VSAB ne source of label");

	&crTest($lmStr, 5, \&make_checkParentMismatch,
			"ILM_5: parent mismatch");

        &crTest($lmStr, 6, \&make_checkSaid1toSgid1,
                        "ILM_6: SAID1 not equal to SGID_1");

        &crTest($lmStr, 7, \&make_checkSaid2toSgid2,
                        "ILM_7: SAID_2 not equal to SGID_2");

        &crTest($lmStr, 8, \&make_checkdupliatePARSIB,
                        "ILM_8: Sgid's have both PAR/CHD and SIB relationship");


	## 4. read inline FileMons and create the check functions
	&crTest($fmStr, 1, \&make_checkInvSgId1,
			"IFM_1: sgId1 not in classes");

	&crTest($fmStr, 2, \&make_checkInvSgId2,
			"IFM_2: sgId2 not in classes");

	&crTest($fmStr, 3, \&make_checkInvRela,
			"IFM_3: RELA not in MRDOC");

	#&crTest($fmStr, 4, \&make_checkInvRela2,
	#        "IFM_4: Invalid RELA Value");

	&crTest($fmStr, 5, \&make_checkInvVSab,
			"IFM_5: VSAB not in Sources");

	#&crTest($fmStr, 6, \&make_checkDupRel,
	#        "IFM_6: Dupicate Relationships");

	#&crTest($fmStr, 7, \&make_checkNotDone7,
	#        "IFM_7: Verify Parent Matches SrcAtomId2");

	#&crTest($fmStr, 8, \&make_checkNotDone8,
	#        "IFM_8: HCD Matches Atom CODE");

	#&crTest($fmStr, 9, \&make_checkNotDone9,
	#        "IFM_9: Mixed Null and non-NULL HCD");


	return bless ($ref, $class);
  }



  sub process {
	@IL = @_;
	$recId = "$_[1]_$_[2]_$_[3]_$_[4]";
	my @tmparray = @_;

	my ($key);

	## 1. Check FieldMons
	foreach $key (keys (%mons)) {
	  $mons{"$key"}->process($_[$key], $recId);
	}

	## 2. Check LineMons
	foreach $key (keys (%lmons)) {
	  $lmons{"$key"}->process(@tmparray[1..$#tmparray]);
	}

	## Check Inline LineMons
	# ILM_0: field count check.
	&$subref_checkFldCount();

	# ILM_1: PAR with null PTR
	&$subref_checkParWNullPtr();

	# ILM_2: non unique RUI fields
	&$subref_checkNonUniqueRui();

	# ILM_3: SIB rel with non-null RELA
	&$subref_checkSibWRela();

	# ILM_4: VSAB ne source of label
	&$subref_checkVsabNeSL();

	# ILM_5: parent mismatch
	&$subref_checkParentMismatch();

        # ILM_6: SAID_1 not equal to SGID_1
        &$subref_checkSaid1toSgid1();

        # ILM_7: SAID_2 not equal to SGID_2
        &$subref_checkSaid2toSgid2();	

        # ILM_8: Sgids have both PAR and SIB relationsships
        &$subref_checkdupliatePARSIB();


	## Check Inline FileMons
	# IFM_1: sgId1 not in classes
	&$subref_checkInvSgId1();

	# IFM_2: sgId2 not in classes
	&$subref_checkInvSgId2();

	# IFM_3: RELA not in MRDOC
	&$subref_checkInvRela();

	# IFM_4: Invalid RELA Value
	&$subref_checkInvRela2();

	# IFM_5: VSAB not in Sources
	&$subref_checkInvVSab();

	# IFM_6: Dupicate Relationships
	#&$subref_checkDupRel();

	# IFM_7: Verify Parent Matches SrcAtomId2
	#&$subref_checkNotDone7();

	# IFM_8: HCD Matches Atom CODE
	#&$subref_checkNotDone8();

	# IFM_9: Mixed Null and non-NULL HCD
	#&$subref_checkNotDone9();


	## remember sruiVsab and sruiRsab here
	if ($_[10] ne '') {
	  $$VlSruiVsabRef{"$_[10]|$_[5]"}++;
	  if (defined($$VlVsab2RsabRef{"$_[5]"})) {
		$$VlSruiRsabRef{"$_[10]|$$VlVsab2RsabRef{$_[5]}"}++;
	  }
	}
       
       ##check for tabs 
        if ($_[1] ne ''){
    my $full_line  = "$_[1]|$_[2]|$_[3]|$_[4]|$_[5]|$_[6]|$_[7]|$_[8]|$_[9]_$[10]|$_[11]|$_[12]|$_[13]|$_[14]|$_[15]|$_[16]|$_[17]";
	 if ($full_line =~ /\t/){
	       if ($errCount{'tabsinfile'}++ < 10) {
                $Errors{"Vtabsinfile_$_[1]"} = "$_[3]";
		   }
		}
	}
         
	##############
	## check other
	# id1 must be a valid said.
	if (!defined($$VlSaidRef{"$_[1]"})) {
	  if ($errCount{'badSaid1'}++ < 10) {
		$Errors{"VBadSaid1_$recId"} = '';
	  }
	}
	# id2 must be a valid said.
	if (!defined($$VlSaidRef{"$_[4]"})) {
	  if ($errCount{'badSaid2'}++ < 10) {
		$Errors{"VBadSaid2_$recId"} = '';
	  }
	}
	# every id in the ptr tree must be a valid said.
	my $lastKey;
	# don't check fist node, the root node. Its definition is usually missing.
	my $first = 1;
	foreach $key (split(/\./, $_[8])) {
	  $lastKey = $key;
	  if ($first == 1) {
		$first = 0; next;
	  }
	  if (!defined($$VlSaidRef{"$key"})) {
		if ($errCount{'badTreePos'}++ < 10) {
		  $Errors{"VBadTreePos_${recId}_$key"} = '';
		}
	  }
	}
  }

  sub reportInfo {
	my $self = shift;
	my ($key, $ln, @vals);

	print $_EOUT "Contexts: Information\n";

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
	print $_EOUT "Contexts: Warnings\n";

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
	print $_EOUT "Contexts: Errors\n";

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
	print $_OUT "Contexts:\n";
	print $_EOUT "Contexts:\n";
	$self->reportErrors();
	$self->reportWarnings();
	$self->reportInfo();
	print $_OUT "End of Contexts check\n";
	print $_EOUT "End of Contexts check\n";
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
	%cxtUis=();
        %parsgids1 = ();
        %parsgids2 = ();
        %parsgids3 = ();
  }

  sub getAllRef {
	my $self = shift;
	my $which = shift;
	return $mons{$which}->getAllHsh();
  }

  sub setOtherValids {}

  sub saveResults {

	$$_theLog->logIt("Writing results Relations Info\n");
	my $file = $$_theCfg->getEle('TEMPDIR');
	my $file1 = "$file/QaInt_REL2";

	my ($said, $vsb, $rsb, $key, $val);

	# save Rel info
	open (QAREL, ">:utf8", $file1)
	  or die "Could not open Rel file $file1\n";
	# rel info
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
	my $file1 = "$file/QaInt_REL2";

	my ($tag, $key, $val);

	open (QAREL, "<:utf8", $file1) or die "Could not open file $file1\n";
	my $ruivRef = $$l_valids{'SruiVsab'};
	my $ruirRef = $$l_valids{'SruiRsab'};

	while (<QAREL>) {
	  chomp;
	  next if /^\#/ || /^\s*$/;
	  ($tag,$key) = split(/\|/, $_, 2);
	  if ($tag eq 'RUIV') {
		$$ruivRef{"$key"}++;
	  } elsif ($tag eq 'RUIR') {
		$$ruirRef{"$key"}++;
	  }
	}
	close(QAREL);
  }


}
1

