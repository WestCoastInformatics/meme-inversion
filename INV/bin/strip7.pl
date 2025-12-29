#!/usr/bin/perl

# removes 7 bit, ASCII characters (except NEWLINE) from UTF-8 input stream

use Encode;
use utf8;

binmode(STDIN, ":utf8");
binmode(STDOUT, ":utf8");

while (<>) {
  chomp;
  @x = unpack("U*", $_);
  foreach $c (@x) {
     print pack("U", $c) unless $c < 0x7f;
  }
  print "\n";
};
exit 0;
