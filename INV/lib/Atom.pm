#!/usr/bin/perl
#!/usr/bin/perl
#
# class: Atom
# description: enables to dump an atom in the classes_atoms.src file.
#              An atom has 18 fields, the defaults for all these fields
#              can be specified outside. A default file $ENV{INV_HOME}/
#              etc/inv_defaults.cfg contains the defaults for each fo these
#              fields. In addition, the user defined cfg file can contain
#              default values which override the system provided defaults.
#              The constructor takes an optional argument which is the
#              tag used to specify the default values in the user config
#              file. Once constructed, a method "dumpAtom" can be used to
#              write the atom in the classes_atoms.src files.
#              dumpAtom method takes a hash as an optional argument, which
#              further specifies the values to override the defaults.
# Public Methods:
#    Atom(tag) - constructor. Creates a new atom and sets its values in this
#                order.
#                1) values from the sys defaults file
#                   ($INV_HOME/etc/in_defaults.cfg).
#                2) values from the application cfg file with a the given tag.
#    dumpAtom(hash) - hash contains further values to be used in dumping the
#                atom to the standard classes files. It results the newly
#                created atoms said.
#
# Valid key values of the atom - following are the valid keys along with their
# defaults from the systems defauls file.
#               Atom.Defaults.srcAtomId = 
#               Atom.Defaults.vsab = <VSAB>
#               Atom.Defaults.tty = 
#               Atom.Defaults.code = 
#               Atom.Defaults.status = N
#               Atom.Defaults.tbr = Y
#               Atom.Defaults.released = N
#               Atom.Defaults.str = 
#               Atom.Defaults.suppress = N
#               Atom.Defaults.saui = 
#               Atom.Defaults.scui = 
#               Atom.Defaults.sdui = 
#               Atom.Defaults.lat = ENG
#               Atom.Defaults.orderId = 
#               Atom.Defaults.lastReleaseCui = 
#
# Example:
#    Atom atm = new Atom('LNC_OP');
#    $said = atm->dumpAtom({str => 'atom name', suppress => 'Y'});
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use iutl;
use strict 'vars';
use strict 'subs';

package Atom;

{
  my ($_theLog, $_theCfg, $_theIdGen, $_OUT);
  my $_dumpOrd = 0;
  my $_lastId = 0;

  my %_valids = (srcAtomId => 0, vsab => 0, tty => 0, code => 0, status => 0,
				 tbr => 0, released => 0, str => 0, suppress => 0, saui => 0,
				 scui => 0, sdui => 0, lat => 0, orderId => 0,
				 lastReleaseCui => 0);

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
		$$_theLog->logError("Invalid Atom attribute <$key> encountered\n");
      }
    }
  }

  sub new {
    my ($class, $defTag) = @_;
    my $ref = {srcAtomId => 0,
			   vsab => '',
			   tty => 'NONE',
			   code => '',
			   status => '',
			   tbr => '',
			   released => '',
			   str => '',
			   suppress => '',
			   saui => '',
			   scui => '',
			   sdui => '',
			   lat => '',
			   orderId => '',
			   lastReleaseCui => ''};

    # apply common defaults
    my ($key, $val, $temp );
    $temp = \%{$$_theCfg->getHashRef('Atom.Defaults')};
    while (($key, $val) = each %{$temp}) {
      if (defined ($_valids{"$key"})) {
		$$ref{"$key"} = $val;
      } else {
		$$_theLog->logError("Invalid Atom attribute <$key> encountered\n");
      }
    }

    # now apply specific defaults
    if ($defTag ne '') {
      $temp = \%{$$_theCfg->getHashRef("$defTag")};
      while (($key, $val) = each %{$temp}) {
		if (defined ($_valids{"$key"})) {
		  $$ref{"$key"} = $val;
		} else {
		  $$_theLog->logError("Invalid Atom attribute <$key> encountered\n");
		}
      }
    }
    return bless ($ref, $class);
  }

  sub dumpAtom {
    my ($self, $thisData) = @_;
    my ($key, $val);

    # now apply specific values
    while (($key, $val) = each %{$thisData}) { 
      if (defined ($_valids{"$key"})) {
		$self->{$key} = $val;
      } else {
		$$_theLog->logError("Invalid Atom attribute <$key> encountered\n");
      }
    }
    
    #Now apply cleanLine subroutine for all strings

    while (($key, $val) = each %{$thisData}) {
      if (defined ($_valids{"$key"})) {
            if ($key eq "str"){
                $self->{'str'} = iutl->cleanLine($val);
              }
           }
       }
   

    $_lastId = $$_theIdGen->newAid();
    if ($_dumpOrd == 1) {
      $self->{'orderId'} = $_lastId;
    }
    $self->{'srcAtomId'} = $_lastId;

    print $_OUT "$_lastId|$self->{'vsab'}|$self->{'vsab'}/$self->{'tty'}|$self->{'code'}|$self->{'status'}|$self->{'tbr'}|$self->{'released'}|$self->{'str'}|$self->{'suppress'}|$self->{'saui'}|$self->{'scui'}|$self->{'sdui'}|$self->{'lat'}|$self->{'orderId'}|$self->{'lastReleaseCui'}\n";
    return $_lastId;
  }

  sub setDumpOrd { shift; $_dumpOrd = shift; }

  sub getLastId { return $_lastId; }

}
1

