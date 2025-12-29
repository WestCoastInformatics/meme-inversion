#!/usr/bin/perl

# Scans the input for non-ASCII chars and prints the lines
# containing 8-bit chars. Output is in input encoding.

# Command line options:
# -e <input encodings>
# -c (comma separated unicode codepoints) - show only examples for these character
# -n (#) show only first n examples
# -r (raw output only)

# ARGV[1] has have the input file name.

use Getopt::Std;
getopts("e:n:c:r");

use Encode;
use charnames(":full");
use utf8;

$cp1252mapfile = "$ENV{INV_HOME_OLD}/bin/CP1252.TXT";
$inputEncoding = $opt_e || 'utf8';
foreach (split /,/, $opt_c) {
  s/^[uU]\+//;
  tr/a-z/A-Z/;
  push @chars, hex $_;
}

$inputFile = $ARGV[0];
die "Need an input file name as argument." unless $inputFile;
die "Input file does not exist." unless -e $inputFile;
die "Input file is not readable." unless -r $inputFile;

eval {
  &{"do_" . $inputEncoding};
};
die $@ if $@;
exit 0;

sub do_utf8 {
  $SIG{__WARN__} = sub { die "ERROR: Doesn't look like input is in UTF-8\n"; };
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

  foreach $c (sort keys %example) {
    if (@chars) {
      next unless grep { $_ == $c } @chars;
    }
    print "\n", "-" x 60, "\n" unless $opt_r;
    $n = scalar(@{ $example{$c} });
    $x = ($n == 1 ? "$n case" : "$n cases");
    $x .= ($opt_n ? ($opt_n < $n ? " (top $opt_n shown)" : " (all shown)") : "");
    printf("Examples for: U+%.4X (%s): $x\n\n", $c, charnames::viacode($c)) unless $opt_r;
    $i=0;
    foreach $r (@{ $example{$c} }) {
      print $r->[0];
      print " " x $r->[1], "^", "\n" if $r->[1]>0 && !$opt_r;
      $i++;
      last if $opt_n && $i >= $opt_n;
    }
  }
}

sub do_cp1252 {
  $SIG{__WARN__} = sub { die "ERROR: Doesn't look like input is in CP1252\n"; };

  $cp1252map = &load_map($cp1252mapfile);

  unless ($opt_r) {
    print "=" x 60, "\n";
    print "Input file: $inputFile\n";
    print "Encoding: CP1252", "\n";
    print "=" x 60, "\n";
  }

  open(I, $inputFile) || die;
  while (<I>) {
    $line = $_;
    @x = unpack("C*", $line);
    next unless grep { $_ > 0x7f } @x;
    $pos = -1;
    foreach $c (@x) {
      $pos++;
      next if $c <= 0x7f;
      push @{ $example{$c} }, [ $line, $pos ];
    }
  }
  close(I);

  foreach $c (sort keys %example) {
    if (@chars) {
      $u = $cp1252map->{$c}->{unicodeval};
      next unless grep { $_ == $u } @chars;
    }
    print "\n", "-" x 60, "\n" unless $opt_r;
    $n = scalar(@{ $example{$c} });
    $x = ($n == 1 ? "$n case" : "$n cases");
    $x .= ($opt_n ? ($opt_n < $n ? " (top $opt_n shown)" : " (all shown)") : "");

    $u = ($cp1252map->{$c}->{unicodeval} ? sprintf("U+%.4X", $cp1252map->{$c}->{unicodeval}) : "???");
    $n = $cp1252map->{$c}->{name} || "???";
    printf("CP1252 code: %d (maps to %s:%s): $x\n\n", $c, $u, $n) unless $opt_r;
    $i=0;
    foreach $r (@{ $example{$c} }) {
      print $r->[0];
      print " " x $r->[1], "^", "\n" if $r->[1]>0 && !$opt_r;
      $i++;
      last if $opt_n && $i >= $opt_n;
    }
  }
}

# loads a map as in http://www.unicode.org/Public/MAPPINGS/*
# into a data structure and returns a reference to it
sub load_map {
  my($file) = @_;
  my(%map);

  open(B, $file) || die "Cannot load map: $file\n";
  while (<B>) {
    next if /^\#/ || /^\s*$/;
    chomp;
    @_ = split /\t/, $_;
    if (@_ == 3) {
      my($d) = hex($_[0]);
      if ($_[1] =~ /^\s*$/) {
	$map{$d}->{unicode} = undef;
	$map{$d}->{unicodeval} = undef;
	$map{$d}->{name} = $_[2];
	$map{$d}->{name} =~ s/\#//;
      } else {
	$map{$d}->{unicode} = $_[1];
	$map{$d}->{unicodeval} = hex($_[1]);
	$map{$d}->{name} = $_[2];
	$map{$d}->{name} =~ s/\#//;
      }
    } else {
      next;
    }
  }
  close(B);
  return \%map;
}
