#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';


package Merge;

{
  my ($_theLog, $_theCfg, $_OUT);
  my %_valids = ( sgId1 => 0, lvl => 0, sgId2 => 0, vsab => 0, iv => 0,
				  demote => 0, changeStatus => 0, mergeSet => 0, sgType1 => 0,
				  sgQual1 => 0, sgType2 => 0, sgQual2 => 0 );

  sub init {
    my ($self, $log, $cfg) = @_;
    $_theLog = $log;
    $_theCfg = $cfg;
  }

  sub setFileHandler { shift; $_OUT = shift; }

  sub setDefaults {
    my ($self, $thisData) = @_;
    my ($key, $val);

    # now apply specific values
    while (($key, $val) = each %{$thisData}) { 
      if (defined ($_valids{"$key"})) {
		$self->{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Merge attribute <$key> encountered\n");
      }
    }
  }

  sub new {
    my ($class, $defTag) = @_;
    my $ref = { sgId1 => '',
				lvl => '',
				sgId2 => '',
				vsab => '',
				iv => '',
				demote => '',
				changeStatus => '',
				mergeSet => '',
				sgType1 => '',
				sgQual1 => '',
				sgType2 => '',
				sgQual2 => '',};


    # apply common defaults
    my ($key, $val, $temp );
    $temp = \%{$$_theCfg->getHashRef('Merge.Defaults')};
    while (($key, $val) = each %{$temp}) {
      if (defined ($_valids{"$key"})) {
		$$ref{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Merge attribute <$key> encountered\n");
      }
    }

    # now apply specific defaults
    if ($defTag ne '') {
      $temp = \%{$$_theCfg->getHashRef("$defTag")};
      while (($key, $val) = each %{$temp}) {
		if (defined ($_valids{"$key"})) {
		  $$ref{"$key"} = $val;
		} else {
		  $$_theLog->logError("Invalid Merge attribute <$key> encountered\n");
		}
      }
    }

    return bless($ref,$class);
  }

  sub dumpMerge {
    my ($self, $thisData) = @_;
    my ($key, $val);

    # now apply specific values
    while (($key, $val) = each %{$thisData}) { 
      if (defined ($_valids{"$key"})) {
		$self->{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Merge attribute <$key> encountered\n");
      }
    }

    print $_OUT "$self->{'sgId1'}|$self->{'lvl'}|$self->{'sgId2'}|$self->{'vsab'}|$self->{'iv'}|$self->{'demote'}|$self->{'changeStatus'}|$self->{'mergeSet'}|$self->{'sgType1'}|$self->{'sgQual1'}|$self->{'sgType2'}|$self->{'sgQual2'}|\n";

  }

}
1

