#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';


package Relation;

{
  my ($_theLog, $_theCfg, $_theIdGen, $_OUT);
  my $_lastId = 0;
  my %_valids = (srcRelId=> 0, lvl => 0, sgId1 => 0, rel => 0, rela => 0,
				 sgId2 => 0, vsab => 0, sl => 0, status => 0, tbr => 0,
				 released => 0, suppress => 0, sgType1 => 0, sgQual1 => 0,
				 sgType2 => 0, sgQual2 => 0,  srui => 0, relGroup => 0);

  sub init {
    my ($self, $log, $cfg, $idg) = @_;
    $_theLog = $log;
    $_theCfg = $cfg;
    $_theIdGen = $idg;
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
		$$_theLog->logError("Invalid Rel attribute <$key> encountered\n");
      }
    }
  }


  sub new {
    my ($class, $defTag) = @_;
    my $ref = {srcRelId => '',
			   lvl => '',
			   sgId1 => '',
			   rel => '',
			   rela => '',
			   sgId2 => '',
			   vsab => '',
			   sl => '',
			   status => '',
			   tbr => '',
			   released => '',
			   suppress => '',
			   sgType1 => '',
			   sgQual1 => '',
			   sgType2 => '',
			   sgQual2 => '',
			   srui => '',
			   relGroup => ''};


    # apply common defaults
    my ($key, $val, $temp );
    $temp = \%{$$_theCfg->getHashRef('Relation.Defaults')};
    while (($key, $val) = each %{$temp}) {
      if (defined ($_valids{"$key"})) {
		$$ref{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Rel attribute <$key> encountered\n");
      }
    }

    # now apply specific defaults
    if ($defTag ne '') {
      $temp = \%{$$_theCfg->getHashRef("$defTag")};
      while (($key, $val) = each %{$temp}) {
		if (defined ($_valids{"$key"})) {
		  $$ref{"$key"} = $val;
		} else {
		  $$_theLog->logError("Invalid Rel attribute <$key> encountered\n");
		}
      }
    }

    return bless($ref,$class);
  }

  sub dumpRel {
    my ($self, $thisData) = @_;
    my ($key, $val);

    $_lastId = $$_theIdGen->newRid();

    # now apply specific values
    while (($key, $val) = each %{$thisData}) { 
      if (defined ($_valids{"$key"})) {
		$self->{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Rel attribute <$key> encountered\n");
      }
    }
    $self->{'srcRelId'} = $_lastId;


    print $_OUT "$_lastId|$self->{'lvl'}|$self->{'sgId1'}|$self->{'rel'}|$self->{'rela'}|$self->{'sgId2'}|$self->{'vsab'}|$self->{'sl'}|$self->{'status'}|$self->{'tbr'}|$self->{'released'}|$self->{'suppress'}|$self->{'sgType1'}|$self->{'sgQual1'}|$self->{'sgType2'}|$self->{'sgQual2'}|$self->{'srui'}|$self->{'relGroup'}|\n";
    return $_lastId;
  }

  sub getLastId { return $_lastId; }

}
1

