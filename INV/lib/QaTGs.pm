#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaTGs;

use FldMon;
use LineMon;
use iutl;
{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT, $temp);
  my ($VlSrcRef, $VlTg2SupRef, $VlTgRef);
  my ($cfgrsab, $cfg2rsab, $VlVsab2RsabRef, $rsabtty);
    
  my %mons=();
  my %lmons=();

  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();

#  my %DblowTG=();
  my %currTG=();
  my %hthash = ();
  
  my %tallySelection=();

  my $recNum = 0;

  my $_IlFmTgTtyMismatch = 1;   # 1. TG and tty do not match.


  # tests BEGIN tests BEGIN tests BEGIN tests BEGIN tests BEGIN
  my @IL=();

  ## BAC: left unimplemented after M5 migration
  #get the TG information from the DB
#       sub getLowTG {
#        my $db = Midsvcs->get('editing-db');
#        my $oracleuser = 'meow';
#        my $oraclepassword = GeneralUtils->getOraclePassword($oracleuser,$db);
#        my $dbh = new OracleIF("db=$db&user=$oracleuser&password=$oraclepassword");
#
#        my ($val);
#
#        # first get VSAB source_rank
#             if ($cfg2rsab ne ''){
#        my @lowTG = $dbh->selectAllAsRef
#          ("SELECT c.source, a.tty, a.termgroup
#            FROM termgroup_rank a, source_version c
#            WHERE substr(a.termgroup,1,instr(a.termgroup,'/')-1) = c.current_name and c.source='$cfgrsab'
#            OR substr(a.termgroup,1,instr(a.termgroup,'/')-1) = c.current_name and c.source IN ($cfg2rsab)");
#        foreach $val(@lowTG){
#         $DblowTG{"$val->[0]/$val->[1]"} = $val->[2];
#        }
#       } else {
#    my @lowTG = $dbh->selectAllAsRef
#          ("SELECT c.source, a.tty, a.termgroup
#            FROM termgroup_rank a, source_version c
#            WHERE substr(a.termgroup,1,instr(a.termgroup,'/')-1) = c.current_name and c.source='$cfgrsab'");
#        foreach $val(@lowTG){
#         $DblowTG{"$val->[0]/$val->[1]"} = $val->[2];
#        }
#      }
#   }

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

  # LM1. tty in each line must be present in the termgroup.
  my $subref_checkTgTtyMismatch = \&nullFunc;
  sub make_checkTgTtyMismatch {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkTgTtyMismatch = sub {
	  #print "tg: $IL[1]\ttty: $IL[6]\n";
	  if (($IL[1] !~ /$IL[6]$/) && $$countHash{'VTgTtyMismatch'}++ < 10) {
		$$msgHash{"VTgTtyMismatch_$recNum"} = "$IL[1]|$IL[6]";
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
	$cfgrsab = $$_theCfg->getEle('RSAB');
	$cfg2rsab = $$_theCfg->getEle('CFG2RSAB');
  }


  sub setValidRefs {
	my ($self, $l_valids) = @_;
	$VlSrcRef = $l_valids->{'Vsab'};
	$VlTgRef = $l_valids->{'Tg'};
	$VlTg2SupRef = $l_valids->{'Tg2Sup'};
	$VlVsab2RsabRef = $l_valids->{'Vsab2Rsab'};
  }


  sub crTest {
	my ($mStr, $num, $mkFn, $str) = @_;
	my ($type);
	if ($$_theCfg->getEle("$mStr.$num.enable", 0) eq '1') {
	  $type = $$_theCfg->getEle("$mStr.1.type", 'info');
	  &$mkFn($type);
	  $$_theLog->logInfo("Enabled check $mStr.$num \n\t($str)\n");
	  #print "Enabled check $mStr.$num [$type] \n\t($str)\n";
	} else {
	  $$_theLog->logInfo("** Not checking $mStr.$num \n\t($str)\n");
	  #print "** Not checking $mStr.$num [$type]\n\t($str)\n";
	}
  }

  sub new {
	my $class = shift;

	my $ref = {};
    my ($i, $fnum, $tHash, $temp, $temp1);
    my $lmStr = "IlLineMon.Termgroup";

	## 1. create FieldMons
	$tHash = \%{$$_theCfg->getHashRef('FieldMon.Termgroup')};
	foreach $i (sort keys (%{$tHash})) {
	  $fnum = $$_theCfg->getEle("FieldMon.Termgroup.$i.fieldNum", '0');
	  if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Termgroup', $i);
	  } else {
		$$_theLog->logError("Encountered invalid ".
							"FieldMon.Termgroup.$i.fieldNum\n");
	  }
	}

	## 2. create LineMons
	$tHash = \%{$$_theCfg->getHashRef('LineMon.Termgroup')};
	foreach $i (sort keys(%{$tHash})) {
	  $lmons{$i} = new LineMon('Termgroup',$i);
	}


	## 3. read inline FieldMons and create the check functions
	# ILM_0: field count
	if (($temp = $$_theCfg->getEle("$lmStr.0.enable", 0)) == 1) {
	  $temp = $$_theCfg->getEle("$lmStr.0.fieldCt", 6);
	  if ($temp != 0) {
		$temp += 2;
		$temp1 = $$_theCfg->getEle("$lmStr.0.type", 'info');
		&make_checkFldCount($temp, $temp1);
	  }
	}

	&crTest($lmStr, 1, \&make_checkTgTtyMismatch,
			"ILM_1: tty in each line must be present in the termgroup.");


	## 4. force tally on vsab[1] and rsab[5] fields
	my $i;
	foreach $i (1, 5) {
	  $tallySelection{"$i"} = $mons{"$i"}->{'tally'};
	  $mons{"$i"}->{'tally'} = 1;
	}

	return bless ($ref, $class);
  }



  sub process {
	@IL = @_;
    my @tmparray = @_;
	$recNum++;

	my ($key, $ign, $src, $tty);
	foreach $key (keys (%mons)) {
	  $mons{"$key"}->process($_[$key], $recNum);
	}
	foreach $key (keys (%lmons)) {
	  $lmons{"$key"}->process(@tmparray[1..$#tmparray]);
	}

    # collect the current TG values in to a hash
    $currTG{"@_[1]"}++;
    
    #create a new hash for checking low termgroups
    my ($tempsab,$temptty) = split (/\//, @_[1]);
         if (defined($$VlVsab2RsabRef{"$tempsab"})){
         $rsabtty = "$$VlVsab2RsabRef{$tempsab}/@_[6]";
        }
         $hthash{"$rsabtty"} = @_[2];
     
    #Get the existing termgroups from the midp database
    #&getLowTG();
    
	## other cross field checks go here.

	# ILM_0: field count
	&$subref_checkFldCount();

	# ILM_1: tty in each line must be present in the termgroup.
	&$subref_checkTgTtyMismatch();

	## other valid checks.
	# source in tg must be a valid one specified in sources file.
	$key = $_[1];
	$$VlTgRef{"$key"}++;
	($src,$tty) = split(/\//, $key);
	if (!defined($$VlSrcRef{"$src"})) {
	  if ($errCount{'EUndefinedSrc'}++ < 10) {
		$Errors{"EUndefinedSrc_$recNum"} = $src;
	  }
	}

      ##check if tabs exist in file
	if ($_[1] ne ''){
	    my $full_line  = "$_[1]|$_[2]|$_[3]|$_[4]|$_[5]|$_[6]";
	    if ($full_line =~ /\t/){
		if ($errCount{'tabsinfile'}++ < 10) {
		    $Errors{"Vtabsinfile_$_[1]"} = "$_[2]";
		}
	    }
	}
	

	## BAC: check disabled with migration to M5
#       #Check to see if Low TG exists in DB
#       if ($DblowTG{"$rsabtty"} ne $hthash{"$rsabtty"}){
#           if (!defined($currTG{"@_[2]"})){
#               if($errCount{'ENoLowTG'}++ < 10) {
#                   $Errors{"ENoLowTG_$_[1]"} = "$hthash{$rsabtty}|DBlowTG|$DblowTG{$rsabtty}";
#               }
#           }
#       }
	# collect tg2supp info
	$$VlTg2SupRef{"$_[1]"} = $_[3];
  }

  sub reportInfo {
	my $self = shift;
	my ($key, $ln, @vals);

	print $_EOUT "Termgroups: Information\n";

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
	print $_EOUT "Termgroups: Warnings\n";

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
	print $_EOUT "Termgroups: Errors\n";

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
	my ($i, $j);
	while (($i, $j) = each(%tallySelection)) {
	  $mons{"$i"}->{'tally'} = $j;
	}

	print $_OUT "Termgroups:\n";
	print $_EOUT "Termgroups:\n";
	$self->reportErrors();
	$self->reportWarnings();
	$self->reportInfo();
	print $_OUT "End of Termgroups check\n";
	print $_EOUT "End of Termgroups check\n";
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
#	%DblowTG=();
  }

  sub setOtherValids {

	# add other valid termgroups.
	$$VlTgRef{'SRC/RPT'}++;
	$$VlTgRef{'SRC/RAB'}++;
	$$VlTgRef{'SRC/VPT'}++;
	$$VlTgRef{'SRC/VAB'}++;
	$$VlTgRef{'SRC/RHT'}++;
	$$VlTgRef{'SRC/RSY'}++;
	$$VlTgRef{'SRC/VSY'}++;
	$$VlTgRef{'SRC/SSN'}++;

	$$VlTg2SupRef{'SRC/RPT'} = 'N';
	$$VlTg2SupRef{'SRC/RAB'} = 'N';
	$$VlTg2SupRef{'SRC/VPT'} = 'N';
	$$VlTg2SupRef{'SRC/VAB'} = 'N';
	$$VlTg2SupRef{'SRC/RHT'} = 'N';
	$$VlTg2SupRef{'SRC/RSY'} = 'N';
	$$VlTg2SupRef{'SRC/VSY'} = 'N';
	$$VlTg2SupRef{'SRC/SSN'} = 'N';

  }


  sub getAllRef {
	shift;
	my $which = shift;
	return $mons{$which}->getAllHsh();
  }

}

1

