#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib (".");
our $defInvCfg = "$ENV{INV_HOME}/etc/inv_defaults.cfg";

use strict 'vars';
use strict 'subs';

package NLMConfig;

use Config::Properties;
{
  my $_cfg;
  sub new {
    my ($class, $configFile, $useDefaults) = @_;
    $useDefaults = 1 if (!defined($useDefaults));

    if ($useDefaults == 1) {
      # defaults is not working in config file.
      # so create a temp file combining defaults and specific cfg files.
      `cat $defInvCfg $configFile > temp_con_file`;
      open (CFG, "<temp_con_file") or die "Could not open temp_con_file\n";
      $_cfg = new Config::Properties();
      $_cfg->load(*CFG);
      close(CFG);
      # remove the temp file.
      `rm temp_con_file`;
    } else {
      open (CFG, "< $configFile") or die "Could not open $configFile\n";
      $_cfg = new Config::Properties();
      $_cfg->load(*CFG);
      close(CFG);
    }

    # do substitution here.
    my ($name, $val, $oval, $nval);
    foreach $name ($_cfg->propertyNames) {
      $val = $_cfg->getProperty("$name");
      while ($val =~ /\<([^>]*)\>/) {
		$oval = $1;
		$nval = $_cfg->getProperty($oval);
		$val =~ s/\<$oval\>/$nval/g;
		$_cfg->setProperty($name, $val);
      }
    }
    my $ref = {};
    return bless($ref, $class);
  }

  sub getEle {
    shift;
    return $_cfg->getProperty(@_);
  }

  sub getReqEle {
    shift;
    return $_cfg->requireProperty(@_);
  }

  sub getList {
    my ($self, $name) = @_;
    my $tree = $_cfg->splitToTree(qr/\./, "$name");
    my @ans;
    foreach $name (sort keys (%{$tree})) {
      push(@ans, $$tree{"$name"});
    }
    return @ans;
  }

  sub getHashRef {
    my ($self, $name) = @_;
    return $_cfg->splitToTree(qr/\./, "$name");
  }

  sub getHash {
    my ($self, $name) = @_;
    return %{$_cfg->splitToTree(qr/\./, "$name")};
  }

  sub setEle {
    my ($self, $name, $val) = @_;
    $_cfg->setProperty($name, $val);
  }

  sub dumpAll {
    my ($self, $name, $val) = @_;
    foreach $name ($_cfg->propertyNames) {
      $val = $_cfg->getProperty("$name");
      print "$name => $val\n";
    }
  }
  sub Test {
    my $self = shift;
    print "Inside NLMConfig.\n";
    my $temp = $self->getEle('File.Atom');
    print "atom file1 is $temp\n";

    $temp = $_cfg->getProperty('File.Atom');
    print "atom file2 is $temp\n";
  }

}
1
