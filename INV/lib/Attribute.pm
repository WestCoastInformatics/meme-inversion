#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use iutl;
use strict 'vars';
use strict 'subs';


package Attribute;
use Digest::MD5 qw(md5_hex);
use Encode qw(encode_utf8);

{
  my ($_theLog, $_theCfg, $_theIdGen, $_OUT);
  my $_lastId = 0;
  my %_valids = (srcAttrId => 0, sgId => 0, lvl => 0, atn => 0,
				 atv => 0, vsab => 0, status => 0, tbr => 0, released => 0,
				 suppress => 0, sgType => 0, sgQual => 0, satui => 0,
				 digest=> 0);

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
		$$_theLog->logError("Invalid Attr attribute <$key> encountered\n");
      }
    }
  }


  sub new {
    my ($class, $defTag) = @_;
    my $ref = {srcAttrId => '',
			   sgId => '',
			   lvl => '',
			   atn => '',
			   atv => '',
			   vsab => '',
			   status => '',
			   tbr => '',
			   released => '',
			   suppress => '',
			   sgType => '',
			   sgQual => '',
			   satui => '',
			   digest => ''};


    # apply common defaults
    my ($key, $val, $temp);
    $temp = \%{$$_theCfg->getHashRef('Attribute.Defaults')};
    while (($key, $val) = each %{$temp}) {
      if (defined ($_valids{"$key"})) {
		$$ref{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Attr attribute <$key> encountered\n");
      }
    }
    # now apply specific defaults
    if ($defTag ne '') {
      $temp = \%{$$_theCfg->getHashRef("$defTag")};
      while (($key, $val) = each %{$temp}) {
		if (defined ($_valids{"$key"})) {
		  $$ref{"$key"} = $val;
		} else {
		  $$_theLog->logError("Invalid Attr attribute <$key> encountered\n");
		}
      }
    }

    return bless($ref,$class);
  }

  sub dumpAttr {
    my ($self, $thisData) = @_;

    my ($digest, $nam, $key, $val);
    $_lastId = $$_theIdGen->newAtid();

    # now apply specific values
    while (($key, $val) = each %{$thisData}) {
      if (defined ($_valids{"$key"})) {
		$self->{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Attr attribute <$key> encountered\n");
      }
    }
    
       #now apply cleanLine subroutine for all attribute values
    while (($key, $val) = each %{$thisData}) {
      if (defined ($_valids{"$key"})) {
              if ($key eq 'atv'){
                $self->{'atv'} = iutl->cleanLine($val);
          }
       }
   }
    
    # now find md5 digest.
    $digest = md5_hex(encode_utf8($self->{'atv'}));
    $self->{'digest'} = $digest;
    $self->{'srcAttrId'} = $_lastId;

    print $_OUT "$_lastId|$self->{'sgId'}|$self->{'lvl'}|$self->{'atn'}|$self->{'atv'}|$self->{'vsab'}|$self->{'status'}|$self->{'tbr'}|$self->{'released'}|$self->{'suppress'}|$self->{'sgType'}|$self->{'sgQual'}|$self->{'satui'}|$digest|\n";
    return $_lastId;
  }

  sub getLastId { return $_lastId; }

}
1

