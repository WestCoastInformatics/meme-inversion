#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package LVG;
{
  #our $lvgProg = '/umls_s/umls_apps/lvg/current/bin/lvg';
  my $lvgProg = "$ENV{INV_HOME}/bin/lvg";

  sub new {
    my $class = shift;
    my $ref = {};
    return bless ($ref, $class);
  }

  sub doFile {
    my $self = shift;
    my $inFile = shift;
    my $outFile = shift;
    my $if = shift;
    my @of = @_;

    my $ofs = "-F";
    foreach my $tmp (@of) {
      $ofs .= ":$tmp";
    }

    #`$lvgProg -f:q5 -t:2 -F:1:2:3 < $inFile > $tmpFile`;
    print "calling lvg with -f:q5 -t:$if $ofs < $inFile > $outFile";
    `$lvgProg -f:q5 -t:$if $ofs < $inFile > $outFile`;
    return 1;
  }


  sub doLine {
    my $self = shift;
    # to be implemented
  }
}

1

