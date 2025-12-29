#!/usr/bin/perl
#!/usr/bin/perl
#

# 1  = id_1
# 2  = merge_level
# 3  = id_2
# 4  = source
# 5  = integrity_vector
# 6  = make_demotion
# 7  = change_status
# 8  = merge_set
# 9  = id_type_1
# 10 = id_qualifier_1
# 11 = id_type_2
# 12 = id_qualifier_2



unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaMerges;

use FldMon;
use LineMon;
use iutl;

{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT);
  my ($temp);

  my %mons=();
  my %lmons=();

  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();

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
		  $$msgHash{"VFieldCount_$IL[1]"} = $l;
		}
	  }
	}
  }

  # ILM_1: self referential mergefacts
  my $subref_checkSelfRefRels = \&nullFunc;
  sub make_checkSelfRefRels {
    my ($msgType) = @_;
    my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

    $subref_checkSelfRefRels = sub {
      if ($IL[1] eq $IL[3] && $IL[9] eq $IL[11] && $IL[10] eq $IL[12]
		  && $$countHash{'VSelfRefRels'}++ < 10) {
		$$msgHash{"ESelfRefRels_$recId"}++;
      }
    }
  }

  # IFM_1: sgId1 not in classes
  my $subref_checkInvSgId1 = \&nullFunc;
  sub make_checkInvSgId1 {
    my ($msgType) = @_;
    my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

    $subref_checkInvSgId1 = sub {
      if (my $temp = SrcQa->InvalidSg($IL[1], $IL[9], $IL[10])) {
		if ($$countHash{"${temp}1"}++ < 10) {
		  $$msgHash{"${temp}1_$recId"} = "$IL[1]|$IL[9]|$IL[10]";
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
      if (my $temp = SrcQa->InvalidSg($IL[3], $IL[11], $IL[12])) {
		if ($$countHash{"${temp}2"}++ < 10) {
		  $$msgHash{"${temp}2_$recId"} = "$IL[3]|$IL[11]|$IL[12]";
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

    my $lmStr = "IlLineMon.Merge";
    my $fmStr = "IlFileMon.Merge";

    ## 1. Create FieldMons
    $tHash = \%{$$_theCfg->getHashRef('FieldMon.Merge')};
    foreach $i (sort keys (%{$tHash})) {
      $fnum = $$_theCfg->getEle("FieldMon.Merge.$i.fieldNum", '0');
      if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Merge', $i);
      } else {
		$$_theLog->logError("Encountered invalid ".
							"FieldMon.Merge.$i.fieldNum\n");
      }
    }

    ## 2. create LineMons
    $tHash = \%{$$_theCfg->getHashRef('LineMon.Merge')};
    foreach $i (sort keys(%{$tHash})) {
      $lmons{$i} = new LineMon('Merge',$i);
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

    &crTest($lmStr, 1, \&make_checkSelfRefRels,
			"ILM_1: VSAB not equal to Source of Label");

    ## 4. read inline FileMons and create the check functions
    &crTest($fmStr, 1, \&make_checkInvSgId1,
			"IFM_1: sgId1 not in classes");

    &crTest($fmStr, 2, \&make_checkInvSgId2,
			"IFM_2: sgId2 not in classes");


    return bless ($ref, $class);
  }



  sub process {
    @IL = @_;
    $recId = "$_[1]_$_[3]_$_[8]";
    my @tmparray = @_;
    my ($key);

    ## do FieldMon Checks.
    foreach $key (keys (%mons)) {
      $mons{"$key"}->process($_[$key], $recId);
    }

    ## do LineMon Checks
    foreach $key (keys (%lmons)) {
      $lmons{"$key"}->process(@tmparray[1..$#tmparray]);
    }

    ## Check Inline LineMons
    # ILM_0: field count check.
    &$subref_checkFldCount();

    # ILM_1: self referential mergefacts
    &$subref_checkSelfRefRels();


    ## Check Inline FileMons
    # IFM_1: sgId1 not in classes
    &$subref_checkInvSgId1();

    # IFM_2: sgId2 not in classes
    &$subref_checkInvSgId2();
   
    ##check if any tabs exist
    if ($_[1] ne ''){
    my $full_line  = "$_[1]|$_[2]|$_[3]|$_[4]|$_[5]|$_[6]|$_[7]|$_[8]|$_[9]_$[10]|$_[11]|$_[12]";
	 if ($full_line =~ /\t/){
	       if ($errCount{'tabsinfile'}++ < 10) {
                $Errors{"Vtabsinfile_$_[1]"} = "$_[3]";
		   }
		}
	}

  }

  sub reportInfo {
    my $self = shift;
    my ($key, $ln, @vals);

    print $_OUT "Merges: Information\n";

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
    print $_OUT "Merges: Warnings\n";

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
    print $_OUT "Merges: Errors\n";

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
    print $_OUT "Merges:\n";
    print $_EOUT "Merges:\n";
    $self->reportErrors();
    $self->reportWarnings();
    $self->reportInfo();
    print $_OUT "End of Merges check\n";
    print $_EOUT "End of Merges check\n";
    print $_OUT "#=================\n\n";
    print $_EOUT "#=================\n\n";
  }

  # release memory.
  sub release {
    %mons = ();
    %lmons = ();
    %errCount = ();
    %wrngCount=();
    %Warnings=();
    %infoCount=();
    %Information=();

    %Errors = ();
  }

  sub getAllRef {
    shift;
    my $which = shift;
    return $mons{$which}->getAllHsh();
  }

  sub setOtherValids {}

}

1

