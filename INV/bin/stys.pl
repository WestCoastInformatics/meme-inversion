#!/usr/bin/perl

unshift(@INC, ".");
use lib "$ENV{INV_HOME}/bin";
use lib "$ENV{INV_HOME}/lib";

use strict 'vars';
use strict 'subs';
use Getopt::Std;

our %options = ();
getopts("c:i", \%options);

# Options:
# -c <config file>
# -i <input format for sgtypes>


use Atom;
use Attribute;
use Relation;
use Merge;
use Context;
use SrcBldr;
use NLMInv;

our ($Inv, $Log, $Cfg);
our ($styAttr);
our $cfgFile;
our $sgtype;

$cfgFile = $options{c};
$sgtype = $options{i};

if (!defined $options{c}) {
  print "Must supply a valid config file as -c option.\n";
  exit;
}

if (!defined $options{i}) {
  print "Must supply a valid sgtype as -i option.\n";
  print "valid sgtypes are '<0 for said>, <1 for code>, <2 for scui>, <3 for sdu
i>.\n";
  exit;
}



#-----------------------------------------------------------------------------
# Main
#-----------------------------------------------------------------------------
&main;
sub main {
  # create a new NLMInv obj and get common objects.
  $Inv  = new NLMInv($cfgFile);
  $Log  = $Inv->getLog;
  $Cfg  = $Inv->getCfg;

  $Inv->prTime("Begin");
  $Inv->invBegin('Append');

  $styAttr = new Attribute('Attribute.STY');
  $Inv->inheritSTYs(\$styAttr, $sgtype);   # uses File.TINS.StyTermIds

  $Inv->invEnd;
  $Inv->prTime("Done Adding STY Attributes");
}
