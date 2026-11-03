#
# File:     env.pl
# Author:   Brian Carlsen  (2005)
#
# To use:
# unshift @INC,"$ENV{ENV_HOME}/bin";
# require "env.pl";
#
package env;

# Set default encodings for STD file handles
binmode(STDIN,":utf8");
binmode(STDOUT, ":utf8");
binmode(STDERR,":utf8");

# Including this package sets the environment based on $ENV{ENV_FILE}
#
unless ($ENV{"ENV_FILE"}) {
  die '$ENV_FILE must be set.';
}

open (F,"$ENV{ENV_FILE}") || die "Could not open $ENV{ENV_FILE}: $! $?\n";
while (<F>) {
  if (/=/ && ! /^#/) {
    chop;
    ($var,$val) = split /=/;
    # Remove leading and trailing quotes if they exist
    if ($val =~ /^".*"$/) {
      $val =~ s/^"//;
      $val =~ s/"$//;
    }
    # Handle the environment variable case (e.g. ${USER})
    if ($val =~ /\${[^}]+}/) {
      $val =~ s/\${/\$ENV{/g;
      my $x = eval($val);
      chop($x);
      $ENV{$var} = $x;
    }
    # Handle the backticks case (e.g. `date`)
    elsif ($val =~ /^`.*`$/) {
        my $x = eval($val);
        chop($x);
        $ENV{$var} = $x;
    } else {
        $ENV{$var} = $val;
    }
    #print "ENV{$var} = $ENV{$var}\n";
  }
}
close (F);
