#!/usr/bin/perl

# Script to guess the encoding of the contents of a file or STDIN

# Command line options:
# -e (list all known encoding names)
# -g (list of guesses to try - comma separated)

use Getopt::Std;
getopts("eg:");

use Encode::Guess;

# All available encodings
if ($opt_e) {
  print join("\n", Encode->encodings(":all")), "\n";
  exit 0;
}

if ($opt_g) {
  @guesses = split /,/, $opt_g;
} else {
  @guesses = Encode->encodings(":all");
}
$guesses = join("\n", @guesses);

if ($ARGV[0]) {
  open(F, $ARGV[0]) || die "Cannot open file: $ARGV[0]: $!";
  @_ = <F>;
  close(F);
} else {
  @_ = <STDIN>;
}
$data = join("", @_);

eval {
  $encoder = guess_encoding($data, @guesses);
};

die "Not one of these encodings:\n$guesses\n" unless (ref($encoder)) && !$@;

use Data::Dumper;

print Dumper($encoder), "\n";
exit 0;
