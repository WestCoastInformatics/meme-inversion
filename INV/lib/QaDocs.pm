#!/usr/bin/perl
#!/usr/bin/perl
#

# fields
# 1 = doc_key
# 2 = value
# 3 = type
# 4 = explanation

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaDocs;

use FldMon;
use LineMon;
use iutl;
{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT, $temp);
  my %mons=();
  my %lmons=();
  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();
  my %seenErrors=();

  my ($VlAtnRef, $VlRelsRef, $VlRelaRef, $VlTtysRef);
  my ($VlAttatn, $VlSubatn);
  my %docUis=();

  my $pat01 = qr{^(abbreviation|attribute|entry_term|expanded|hierarchical|obsolete|other|preferred|synonym)$};

  my @IL=();
  my $recNum = 0;


  # tests BEGIN tests BEGIN tests BEGIN tests BEGIN tests BEGIN

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
		  $$msgHash{"VFieldCount_$recNum"} = $l;
		}
	  }
	}
  }

  # ILM_1: invalid null values
  my $subref_checkInvNullVals = \&nullFunc;
  sub make_checkInvNullVals {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvNullVals = sub {
	  if ($IL[2] eq '') {
		if ($IL[1] eq 'RELA') {
		  if (($IL[3] eq 'rela_inverse' && $IL[4] eq '')
			  || ($IL[3] eq 'expanded_form' 
				  && $IL[4] eq 'Empty relationship attribute')) {
			# allowed for null rela - so ignore
		  } else {
			if ($$countHash{'VInvNullVals'} < 10) {
			  $$msgHash{"VInvNullVals_$recNum"} = "$IL[1]|$IL[2]|$IL[3]|$IL[4]";
			}
		  }
		} else {
		  if ($$countHash{'VInvNullVals'} < 10) {
			$$msgHash{"VInvNullVals_$recNum"} = "$IL[1]|$IL[2]|$IL[3]|$IL[4]";
		  }
		}
	  }

	  # add a new one to check for ### in doc lines.
	}
  }

  # ILM_2: invalid tty class
  my $subref_checkInvTtyClass = \&nullFunc;
  sub make_checkInvTtyClass {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvTtyClass = sub {
	  if (@_[3] eq 'tty_class' && @_[4] !~ /$pat01/
		  && $$countHash{'VInvTtyClass'} < 10) {
		$$msgHash{"VInvTtyClass_$recNum"} = "$IL[1]|$IL[2]|$IL[3]|$IL[4]";
	  }
	}
  }

  # ILM_3: invalid type for dockey
  my $subref_checkInvKeyType = \&nullFunc;
  sub make_checkInvKeyType {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvKeyType = sub {
	  if (($IL[3] eq 'tty_class' && $IL[1] ne 'TTY')
		  || ($IL[3] eq 'rela_inverse' && $IL[1] ne 'RELA')) {
		if ($$countHash{'VInvKeyType'} < 10) {
		  $$msgHash{"VInvKeyType_$recNum"} = "$IL[1]|$IL[4]";
		}
	  }
	}
  }

  # ILM_4: duplicate dockey and expl
  my $subref_checkDupKeyExpl = \&nullFunc;
  sub make_checkDupKeyExpl {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkDupKeyExpl = sub {
	  if ($IL[1] ne 'TTY') {
		my $ign = "$IL[1]|$IL[2]|$IL[3]|$IL[4]";
		if (defined($docUis{"$ign"})) {
		  if ($$countHash{'VDupKeyExpl'} < 10) {
			$$msgHash{"VDupKeyExpl_$recNum"} = "$ign";
		  }
		} else {
		  $docUis{"$ign"}++;
		}
	  }
	}
  }
  # ILM_5: Check if there are any unused ATN's
  my $subref_checkUnusedATN = \&nullFunc;
  sub make_checkUnusedATN {
        my ($msgType) = @_;
        my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

        $subref_checkUnusedATN = sub {
          if ((!defined($$VlAttatn{$IL[2]})) || (!defined($$VlSubatn{$IL[2]}))){
                 if ($$countHash{'UnusedAtn'} < 10) {
                $$msgHash{"VUnusedAtn_$recNum"} = "$IL[2]";
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
	$VlAtnRef = $l_valids->{'Atn'};
	$VlRelsRef = $l_valids->{'Rel'};
	$VlRelaRef = $l_valids->{'Rela'};
	$VlTtysRef = $l_valids->{'Tty'};
       
        $VlAttatn = $$l_valids{'attn'};
        $VlSubatn = $$l_valids{'subatn'};
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
	my $lmStr = "IlLineMon.Doc";

	## 1. create FieldMons
	$tHash = \%{$$_theCfg->getHashRef('FieldMon.Doc')};
	foreach $i (sort keys (%{$tHash})) {
	  $fnum = $$_theCfg->getEle("FieldMon.Doc.$i.fieldNum", '0');
	  if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Doc', $i);
	  } else {
		$$_theLog->logError("Encountered invalid FieldMon.Doc.$i.fieldNum\n");
	  }
	}

	## 2. create LineMons
	$tHash = \%{$$_theCfg->getHashRef('LineMon.Doc')};
	foreach $i (sort keys(%{$tHash})) {
	  $lmons{$i} = new LineMon('Doc',$i);
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

	&crTest($lmStr, 1, \&make_checkInvNullVals,
			"ILM_1: invalid null values");

	&crTest($lmStr, 1, \&make_checkInvTtyClass,
			"ILM_2: invalid tty class");

	&crTest($lmStr, 1, \&make_checkInvKeyType,
			"ILM_3: invalid type for dockey");

	&crTest($lmStr, 1, \&make_checkDupKeyExpl,
			"ILM_4: duplicate dockey and expl");
        
        &crTest($lmStr, 1, \&make_checkUnusedATN,
                        "ILM_5: Unused ATNs");        
        
  
	## 4. force tally on the 1st field for further error checking in atoms.
	$mons{1}->setTally(1);

	return bless ($ref, $class);
  }


  sub process {
	@IL = @_;
	$recNum++;

	my ($key, $ign, $src, $tty, $recId);

	# do FieldMon Checks.
	foreach $key (keys (%mons)) {
	  $mons{"$key"}->process($_[$key], $recNum);
	}

	# do LineMon Checks
	foreach $key (keys (%lmons)) {
	  $lmons{"$key"}->process(@_[1..$#{@_}]);
	}


	# other cross field checks go here.

	# ILM_0: field count check.
	&$subref_checkFldCount();

	# ILM_1: invalid null values
	&$subref_checkInvNullVals();

	# ILM_2: invalid tty class
	&$subref_checkInvTtyClass();

	# ILM_3: invalid type for dockey
	&$subref_checkInvKeyType();

	# ILM_4: duplicate dockey and expl
	&$subref_checkDupKeyExpl();

        # ILM_5: Unused ATNS
        &$subref_checkUnusedATN();        
          
 
	# collect valids info here.
	if ($_[1] eq 'ATN') {
	  if ($_[3] eq 'expanded_form') {
		$$VlAtnRef{"$_[2]"}++;
	  }
	} elsif (@_[1] eq 'TTY') {
	  if ($_[3] eq 'tty_class') {
		$$VlTtysRef{"$_[2]"}++;
	  }
	} elsif ($_[1] eq 'REL' && $_[3] eq 'rel_inverse') {
	  $$VlRelsRef{"$_[2]"} = $_[4];
	  $$VlRelsRef{"$_[4]"} = $_[2];
	} elsif ($_[1] eq 'RELA' && $_[3] eq 'rela_inverse') {
	  $$VlRelaRef{"$_[2]"} = $_[4];
	}
  }

  sub reportInfo {
	my $self = shift;
	my ($key, $ln, @vals);

	print $_EOUT "Docs: Information\n";

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
	print $_EOUT "Docs: Warnings\n";

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
	print $_EOUT "Docs: Errors\n";

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
	print $_OUT "Docs:\n";
	print $_EOUT "Docs:\n";
	$self->reportErrors();
	$self->reportWarnings();
	$self->reportInfo();
	print $_OUT "End of Docs check\n";
	print $_EOUT "End of Docs check\n";
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

	%docUis=();
  }

  sub getAllRef {
	shift;
	my $which = shift;
	return $mons{$which}->getAllHsh();
  }

  sub setOtherValids {}

}
1

