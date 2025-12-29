#!/usr/bin/perl

# Scans the input for non-ASCII chars and prints the lines
# containing 8-bit chars. Output is in input encoding.

# Command line options:
# -e <input encodings>
# -c (comma separated unicode codepoints) - show only examples for these character
# -n (#) show only first n examples
# -r (raw output only)
# -v (give VSAB of the selected files)

# ARGV[1] has have the input file name.

use Getopt::Std;
getopts("e:n:c:r:v");

use Encode;
use charnames(":full");
use utf8;

foreach (split /,/, $opt_c) {
  s/^[uU]\+//;
  tr/a-z/A-Z/;
  push @chars, hex $_;
}
$inputEncoding = 'utf8';

$inputFile = $ARGV[0];
die "Need an input file name as argument." unless $inputFile;
die "Input file does not exist." unless -e $inputFile;
die "Input file is not readable." unless -r $inputFile;

eval {
  &{"do_" . $inputEncoding};
};
die $@ if $@;
exit 0;

sub fbc{
my(%map);
  
  open (IN, "< $ENV{INV_HOME}/etc/Forbidden_characters.txt") || die "can't open IN\n";
  
  while (<IN>){
      chomp;
          my ($unicode, $map_string, $uname) = split(/\$/);
                  $map{$uname}->{name} = $uname;
                  $map{$uname}->{replace} = $map_string;
                  $map{$uname}->{unicode} = $unicode;
        }
        close (IN);
        return \%map;
         }


sub do_utf8{
  $SIG{__WARN__} = sub { die "ERROR: Doesn't look like input is in UTF-8\n"; };
 
  $fcmap  = &fbc();

   $ENV{"LC_CTYPE"} = "UTF-8";
   binmode(STDOUT, ":utf8");
 
 
  open(I, $inputFile) || die;
  binmode(I, ":utf8");
 
  unless ($opt_r) {
    print "=" x 60, "\n";
    print "Input file: $inputFile\n";
    print "Encoding: UTF-8", "\n";
    print "=" x 60, "\n";
  }
 
  while (<I>) {
    $line = $_;
    @x = unpack("U*", $line);
    next unless grep { $_ > 0x7f } @x;
    $pos = -1;
    foreach $c (@x) {
      $pos++;
      next if $c <= 0x7f;
      push @{ $example{$c} }, [ $line, $pos ];
      }
   }

  close(I);

   foreach $c(sort keys %example) {
        $st = charnames::viacode($c);
        $u = $fcmap->{$st}->{name};
        if (@chars){
      next unless grep { $_ == $c } @chars;
    }

    $uconvst = $fcmap->{$u}->{replace};
    $hash{$st} = $c;

      if ($u){
    print "\n", "-" x 60, "\n" unless $opt_r;
    #print "$uconvst\n";
    #print "$u\n";
    #print "$ut\n";

    $n = scalar(@{ $example{$c} });
    $x = ($n == 1 ? "$n case" : "$n cases");
    $x .= ($opt_n ? ($opt_n < $n ? " (top $opt_n shown)" : " (all shown)") : "");
    printf ("Examples for: U+%.4X (%s): $x\n\n", $c, charnames::viacode($c)) unless $opt_r;
    printf ("Replacement character for U+%.4x is: %s\n\n", $c, $uconvst) unless $opt_r;
    $i=0;
    foreach $r (@{ $example{$c}}) {
      print  $r->[0];
      print  " " x $r->[1], "^", "\n" if $r->[1]>0 && !$opt_r;
      $i++;
      last if $opt_n && $i >= $opt_n;
        }
      }else{
      next;
     }
   }
}
