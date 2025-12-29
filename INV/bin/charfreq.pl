#!/usr/bin/perl

# Interprets the input as characters in a given encoding (default is UTF-8)
# and outputs the character frequencies.  For some encodings, character names
# are also printed.

# Command line options:
# -e <input encoding>
# -8 (non-ascii characters only)
# -r (reverse sort by frequency)

# Output:
# Character name|UCS-2 code|UTF-8 code|Block name|frequency

use Getopt::Std;
getopts("e:r8");

use Encode;
use charnames(":full");
use utf8;

$blocksfile = "$ENV{INV_HOME_OLD}/etc/Blocks-4.0.0.txt";
$cp1252mapfile = "$ENV{INV_HOME_OLD}/etc/CP1252.TXT";
$inputEncoding = $opt_e || "utf8";

&load_blocks;

eval {
  &{"do_" . $inputEncoding};
};
die $@ if $@;

exit 0;

sub do_utf8 {
  $SIG{__WARN__} = sub { die "ERROR: Doesn't look like input is in UTF-8\n"; };
  $ENV{"LC_CTYPE"} = "UTF-8";

  binmode(STDIN, ":utf8");
  use open ":utf8";

  while (<>) {
    @x = unpack("U*", $_);
    foreach $c (@x) {
      next if $opt_8 && $c < 0x7f;
      $freq{$c}++;
    }
  };

  if ($opt_r) {
    @k = sort {$freq{$b} <=> $freq{$a} } keys %freq;
  } else {
    @k = sort { $a <=> $b } keys %freq;
  }
  foreach $k (@k) {
    if ( &code2block($k) =~ /CJK/) {
      print "";
    }
    $name =  charnames::viacode($k) || "???";
    printf("0x%x|U+%.4X|%s|%s|%d\n", $k, $k, $name, &code2block($k), $freq{$k});
  }
}

sub do_cp1252 {
  $SIG{__WARN__} = sub { die "ERROR: Doesn't look like input is in CP1252\n"; };

  $cp1252map = &load_map($cp1252mapfile);

  while (<>) {
    @x = unpack("C*", $_);
    foreach $c (@x) {
      next if $opt_8 && $c < 0x7f;
      $freq{$c}++;
    }
  };

  my(@k) = ($opt_r ? sort {$freq{$b} <=> $freq{$a} } keys %freq : sort { $a <=> $b } keys %freq);
  foreach $k (@k) {
    $u = ($cp1252map->{$k}->{unicodeval} ? sprintf("U+%.4X", $cp1252map->{$k}->{unicodeval}) : "???");
    $n = $cp1252map->{$k}->{name} || charnames::viacode($cp1252map->{$k}->{unicodeval}) || "???";
    printf("0x%x|%s|%s|%s|%d\n", $k, $u, $n, &code2block($cp1252map->{$k}->{unicodeval}), $freq{$k});
  }
}

# loads unicode code point to block name table
sub load_blocks {
  open(B, $blocksfile) || return;
  while (<B>) {
    next if /^\#/ || /^\s*$/;
    chomp;
    next unless /^(.+)\.\.(.+);\s+(.*)$/;
    $b = hex($1);
    $e = hex($2);
    $n = $3;
    push @blocks, [ $b, $e, $n ];
  }
  close(B);
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

# Given a Unicode codepoint, returns the block name
sub code2block {
  my($code) = @_;
  my($r);

  return "" unless defined($code);
  foreach $r (@blocks) {
    return $r->[2] if ($code > $r->[0] && $code < $r->[1]);
  }
  return "???";
}
