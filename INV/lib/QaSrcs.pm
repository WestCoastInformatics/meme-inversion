#!/usr/bin/perl
#!/usr/bin/perl
#

# 1  = source_name
# 2  = low_source
# 3  = restriction_level
# 4  = normalized_source
# 5  = stripped_source
# 6  = version
# 7  = source_family
# 8  = official_name
# 9  = nlm_contact
# 10 = acquisition-contact
# 11 = content-contact
# 12 = license_contact
# 13 = inverter
# 14 = context_type
# 15 = url
# 16 = language
# 17 = citation
# 18 = license_info
# 19 = character_set
# 20 = rel_directionality_flag



unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaSrcs;

use FldMon;
use LineMon;
use iutl;
{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT, $temp);
  my ($cfgrsab,$cfg2rsab);
  
  my %mons=();
  my %lmons=();

  my %Dblowsrc=();

  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();
  my %seenErrors=();

  my %tallySelection=();
  my ($VlVsab2RsabRef, $VlVsabRef, $VlLatRef, $VlRsabRef);

  my $_fldCount = 0;

  my $_IlFmForeginRsabSFMatch = 1; # 1. RSAB = SF for non-English source.
  my $_IlFmRsabNormRsabMismatch = 1; # RSAB != Norm for non MSH

  sub init {
    my ($self, $log, $cfg) = @_;
    $_theLog = $log;
    $_theCfg = $cfg;
    $_OUT = $$_theCfg->getEle('ofhReport');
    $_EOUT = $$_theCfg->getEle('errhReport');
    $cfgrsab = $$_theCfg->getEle('RSAB');
    $cfg2rsab = $$_theCfg->getEle('CFG2RSAB')
  }

  sub setValidRefs {
    my ($self, $l_valids) = @_;
    $VlVsab2RsabRef = $l_valids->{'Vsab2Rsab'};
    $VlVsabRef = $l_valids->{'Vsab'};
    $VlRsabRef = $l_valids->{'Rsab'};
    $VlLatRef = $l_valids->{'language'};
  }
  
  sub getLowVsab {
      # Get current sources (also low sources)
      my @rows = `$ENV{INV_HOME}/bin/api_metadata.sh current_sources --quiet`;
      chomp(@rows);
      my $row;
      foreach $row (@rows) {
          my ($rsab, $vsab) = split /\|/, $row;
          $Dblowsrc{$rsab} = $vsab;
      }
  }  

  sub new {
    my $class = shift;
    print "Creating a new QaSrc\n";
    my $ref = {};
    my ($i, $fnum, $tHash, $temp);

    $tHash = \%{$$_theCfg->getHashRef('FieldMon.Source')};
    foreach $i (sort keys (%{$tHash})) {
      $fnum = $$_theCfg->getEle("FieldMon.Source.$i.fieldNum", '0');
      if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Source', $i);
      } else {
		$$_theLog->logError("Encountered invalid FieldMon.Source.$i.fieldNum\n");
      }
    }
    $tHash = \%{$$_theCfg->getHashRef('LineMon.Source')};
    foreach $i (sort keys(%{$tHash})) {
      $temp = $$_theCfg->getEle("LineMon.Source.$i.fieldCt", '');
      if ($temp ne '') {
		$_fldCount = $temp;
	  } else {
		$lmons{$i} = new LineMon('Source',$i);
	  }
    }
    if ($_fldCount != 0) {
	  $_fldCount += 2;
	}


    $_IlFmForeginRsabSFMatch = $temp
      if (($temp = $$_theCfg->getEle('InLineMon.Source.1.enable', '')) ne '');

    return bless ($ref, $class);
  }


  our $recNum = 0;

  sub process {
    my @tmparray = @_;
    $recNum++;
    #print "in QaSrc: <@_>\n";
    my ($key, $ign, $tmp);
    foreach $key (keys (%mons)) {
      $mons{"$key"}->process($_[$key], $recNum);
    }
    foreach $key (keys (%lmons)) {
      $lmons{"$key"}->process(@tmparray[1..$#tmparray]);
    }

    ## remember vsab2rsab
    $$VlVsab2RsabRef{"@_[1]"} = @_[5];
    
     
    #remember vsab to language
    $$VlLatRef{"@_[1]"} = @_[16];
    
    ## get the low soource from DB
    &getLowVsab();

    ## other cross field checks go here.

    # 0. count number of fields.
    if ($_fldCount != 0 && $_fldCount != @_) {
      if ($errCount{'EFieldCount'}++ < 10) {
		my $l = @_;
		$l -= 2;
		$Errors{"EFieldCount_$_[1]"} = $l;
      }
    }

    ##check if tabs exist in file
   if ($_[1] ne ''){
    my $full_line  = "$_[1]|$_[2]|$_[3]|$_[4]|$_[5]|$_[6]|$_[7]|$_[8]|$_[9]_$[10]|$_[11]|$_[12]|$_[13]|$_[14]|$_[15]|$_[16]|$_[17]|$_[18]|$_[19]|$_[20]";
	 if ($full_line =~ /\t/){
	       if ($errCount{'tabsinfile'}++ < 10) {
                $Errors{"Vtabsinfile_$_[1]"} = "$_[5]";
		   }
		}
	}

    # 1. RSAB matches SF for non-English source.
    if ($_IlFmForeginRsabSFMatch == 1) {
      if (@_[5] eq @_[7] && @_[16] ne 'ENG') {
		if ($errCount{'EForeignRsabSFMatch'}++ < 10) {
		  $Errors{"EForeignRsabSFMatch_$_[1]"} = "@_[1]|@_[5]|@_[7]";
		}
      }
    }
    # 2. RSAB mismatch with NOrmalizedRSAB for non MSH atoms
    if ($_IlFmRsabNormRsabMismatch == 1) {
      if (@_[7] ne 'MSH' && @_[1] ne @_[4]) {
		if ($errCount{'ERsabNormRsabMismatch'}++ < 10) {
		  $Errors{"ERsabNormRsabMismatch_$_[1]"} = "@_[4]";
		}
      }
    }
    # 3. CXTY is not null, warn the invertor the value is not null.
      if (@_[14] ne ''){
             if ($errCount{'ENotNullCXTY'}++ < 10) {
               $Errors{"ENotNullCXTY_$_[1]"} = "@_[14]";
            }
       }
    #4. Check if the low Vsab exists in the DB
if (defined($Dblowsrc{"@_[5]"})){
           if (@_[2] ne $Dblowsrc{"@_[5]"}){
           if ($errCount{'ENoLowSrc'}++ < 10) {
               $Errors{"ENoLowSrc_$_[1]"} = "@_[2]|DBLowSource|$Dblowsrc{@_[5]}";
            }
         }
       }
  }

  sub reportNONEED {
    my $self = shift;
    my ($key, $ln, @vals);
    foreach $key (sort {$a <=> $b} (keys (%mons))) {
      $mons{"$key"}->report();
    }
    foreach $key (sort {$a <=> $b} (keys (%lmons))) {
      $lmons{"$key"}->report();
    }

    print $_OUT "End of Sources check\n";
    print $_OUT "=======================\n\n";
  }

  sub reportInfo {
    my $self = shift;
    my ($key, $ln, @vals);

    print $_EOUT "Sources: Information\n";

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
    print $_EOUT "Sources: Warnings\n";

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
    print $_EOUT "Sources: Errors\n";

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

    print $_OUT "Sources:\n";
    print $_EOUT "Sources:\n";
    $self->reportErrors();
    $self->reportWarnings();
    $self->reportInfo();
    print $_OUT "End of Sources check\n";
    print $_EOUT "End of Sources check\n";
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
    %Dblowsrc=();
  }

  sub getAllRef {
    my $self = shift;
    my $which = shift;
    return $mons{$which}->getAllHsh();
  }

  #sub getVsab2Rsab { return \%Vsab2Rsab;  }

  sub setOtherValids {
    # here we need to copy the valid values collected in this module to the
    # global valids.
    my ($key, $val);
    while (($key, $val) = each (%{$mons{'1'}->getAllHsh()})) {
      $$VlVsabRef{"$key"} = $val;
    }
    while (($key, $val) = each (%{$mons{'5'}->getAllHsh()})) {
      $$VlRsabRef{"$key"} = $val;
    }
    # add other valids here
    $$VlVsabRef{'SRC'}++;
    $$VlRsabRef{'SRC'}++;
    $$VlVsab2RsabRef{'SRC'} = 'SRC';

  }
}
1

