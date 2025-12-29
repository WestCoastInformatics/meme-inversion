#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package Brit2Amer;

{
  my %_b2aTrans = ();
  my $_mapFile = "$ENV{INV_HOME}/etc/brit2amer.map";
  my $_theLog;

  sub init {
    my ($self, $log) = @_;
    $_theLog = $log if (defined($log));
  }

  sub new {
    my $class = shift;
    my $ERR = shift;
    my $ref = {};

    # read all brit2amer from file /umls_dev/NLM/inv/etc/brit2amer.map
    my ($brit, $amer);
    open (IN, "<:utf8", $_mapFile) or die "Could not open $_mapFile.\n";
    while (<IN>) {
      chomp;
      ($brit, $amer) = split(/\|/, $_);
      $_b2aTrans{"$brit"} = $amer;
      $_b2aTrans{"\u$brit"} = "\u$amer";
      $_b2aTrans{"\U$brit"} = "\U$amer";

    }
    close(IN);
    return bless ($ref, $class);
  }

  sub b2a {
    my $self = shift;
    my $bStr = shift;
    my ($i, $bWord, $aWord);
    my @words = split(/\b/, $bStr);
    foreach $i (0..$#words) {
      if ($aWord = $_b2aTrans{"@words[$i]"}) {
		@words[$i] = $aWord;
      } else {
		if ($_b2aTrans{"\L@words[$i]"}) {
		  $$_theLog->logError("Mixed case Britishism: @words[$i]\n");
		}
      }
    }
    return join('', @words);
  }
}
1

