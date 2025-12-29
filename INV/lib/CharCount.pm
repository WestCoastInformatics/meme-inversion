#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package CharCount;

use Encode;
use Encode::Encoder;

use integer;


{
  my $_theLog = '';
  my %_invChars=();
  sub prntError {
    my ($msg) = @_;
    if ($_theLog ne '') {
      $$_theLog->logError("$msg");
    } else {
      print "$msg";
    }
  }

  INIT {
    open(IN, "<:utf8", "$ENV{INV_HOME}/etc/invalidChars.txt")
      or die "Could not open invalid chars file.\n";
    while (<IN>) {
      chomp;
      $_invChars{"$_"}++;
    }
    close(IN);
  }
	sub new {
	  my $class = shift;
	  my %ths1 = ();
	  my $ref = {hChar => \%ths1};

	  return bless ($ref, $class);
	}

  sub init {
    my ($self, $log) = @_;
    $_theLog = $log if (defined ($log));
  }

  sub doFile {
    my ($self, $iFile, $tempMode) = @_;
    my $mode = "utf8";
    if (defined($tempMode)) {
      $mode = $tempMode;
    }
    prntError("file: $iFile\n");
    prntError("mode: $mode\n");

    if (!grep { $_ eq $mode } Encode->encodings(":all")) {
      prntError("Encoding: $mode not found\n");
      return 0;
    }
    if (!find_encoding($mode)->perlio_ok) {
      prntError("No encoder found for: $mode\n");
      return 0;
    }

    if (!open(IN, "<:encoding($mode)", $iFile)) {
      prntError("Could not open $iFile\n");
      return 0;
    }
    my $ch;
    while (<IN>) {
      chomp;
      foreach $ch (split (//, $_)) {
		$self->{'hchar'}{"$ch"}++;
      }
    }
    close(IN);
    return 1;
  }


  sub doLine {
    my ($self, $line) = @_;
    my $ch;
    my $highBit = 0;
    my $invChar = 0;
    foreach $ch (split (//,$line)) {
      $self->{'hchar'}{"$ch"}++;
      $highBit = 1 if (ord($ch) > 127);
      $invChar = 1 if (defined($_invChars{"$ch"}));
    }
    return ($highBit + $invChar);
  }

  sub report {
    my $self = shift;
    my $out = shift;
    my $above = 127;
    $above = shift if (@_ > 0);

    my ($key, $val, $valOrd);
    foreach $key (sort keys %{$self->{'hchar'}}) {
      $val = $self->{'hchar'}{"$key"};
      $valOrd = ord($key);
      print $out "\t$valOrd\t$val\n" if ($valOrd > $above);
    }
  }

  sub getCharCountRef {
    my $self = shift;
    return $self->{'hchar'};
  }
}

1

