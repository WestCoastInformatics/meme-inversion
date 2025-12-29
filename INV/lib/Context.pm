#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package Context;

{
  my ($_theLog, $_theCfg, $_OUT);
  my %_valids = ( srcAtomId1 => 0, rel => 0, rela => 0, srcAtomId2 => 0,
				  vsab => 0, sl => 0, hcd => 0, ptr => 0, releaseMode => 0,
				  srui => 0, relGroup => 0, sgId1 => 0, sgType1 => 0,
				  sgQual1 => 0, sgId2 => 0, sgType2 => 0, sgQual2 => 0);


  sub init {
    my ($self, $log, $cfg) = @_;
    $_theLog = $log;
    $_theCfg = $cfg;
  }

  sub setFileHandler { shift; $_OUT = shift; }

  sub setDefaults {
    my $self = shift;
    my $thisData = shift;
    my ($key, $val);

    # now apply specific values
    while (($key, $val) = each %{$thisData}) { 
      if (defined ($_valids{"$key"})) {
		$self->{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid CXT attribute <$key> encountered\n");
      }
    }
  }

  sub new {
    my ($class, $defTag) = @_;
    my $ref = { srcAtomId1 => '',
				rel => '',
				rela => '',
				srcAtomId2 => '',
				vsab => '',
				sl => '',
				hcd => '',
				ptr => '',
				releaseMode => '',
				srui => '',
				relGroup => '',
				sgId1 => '',
				sgType1=> '',
				sgQual1 => '',
				sgId2 => '',
				sgType2=> '',
				sgQual2 => '' };



    # apply common defaults
    my ($key, $val, $temp );
    $temp = \%{$$_theCfg->getHashRef('Context.Defaults')};
    while (($key, $val) = each %{$temp}) {
      if (defined ($_valids{"$key"})) {
		$$ref{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid CXT attribute <$key> encountered\n");
      }
    }

    # now apply specific defaults
    if ($defTag ne '') {
      $temp = \%{$$_theCfg->getHashRef("$defTag")};
      while (($key, $val) = each %{$temp}) {
		if (defined ($_valids{"$key"})) {
		  $$ref{"$key"} = $val;
		} else {
		  $$_theLog->logError("Invalid CXT attribute <$key> encountered\n");
		}
      }
    }

    return bless($ref,$class);
  }

  sub dumpCxt {
    my ($self, $thisData) = @_;
    my ($key, $val);

    # now apply specific values
    while (($key, $val) = each %{$thisData}) {
      if (defined ($_valids{"$key"})) {
		$self->{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid CXT attribute <$key> encountered\n");
      }
    }

    print $_OUT "$self->{'srcAtomId1'}|$self->{'rel'}|$self->{'rela'}|$self->{'srcAtomId2'}|$self->{'vsab'}|$self->{'sl'}|$self->{'hcd'}|$self->{'ptr'}|$self->{'releaseMode'}|$self->{'srui'}|$self->{'relGroup'}|$self->{'sgId1'}|$self->{'sgType1'}|$self->{'sgQual1'}|$self->{'sgId2'}|$self->{'sgType2'}|$self->{'sgQual2'}|\n";
  }


  # this version only takes id1 and ptnm; id2 is the last element in ptnm
  sub dumpCxt2 {
    my ($self, $thisData) = @_;
    my ($key, $val);

    # now apply specific values
    while (($key, $val) = each %{$thisData}) { 
      if (defined ($_valids{"$key"})) {
		$self->{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid CXT attribute <$key> encountered\n");
      }
    }

    # now set id2 as the last element of ptnm
    ($self->{'srcAtomId2'}) = reverse (split(/\./, $self->{'ptr'}));
    print $_OUT "$self->{'srcAtomId1'}|$self->{'rel'}|$self->{'rela'}|$self->{'srcAtomId2'}|$self->{'vsab'}|$self->{'sl'}|$self->{'hcd'}|$self->{'ptr'}|$self->{'releaseMode'}|$self->{'srui'}|$self->{'relGroup'}|$self->{'sgId1'}|$self->{'sgType1'}|$self->{'sgQual1'}|$self->{'sgId2'}|$self->{'sgType2'}|$self->{'sgQual2'}|\n";
  }

}

1

