#!/usr/bin/perl

# Script to search for a unicode character in a UTF-8 encoded file
# suresh@nlm 7/2004

# Command line options:
# -c (or a single unicode character, e.g., U+00B1)
# -f (file to search)
# -g just show me the awk command

use Getopt::Std;
getopts("c:f:g");

use Encode;

$file = $opt_f;
die "Need a file in -f" unless $file;

$u = $opt_c;
die "Need a UTF-16 char in -c" unless $opt_c;
$u =~ s/^[uU]\+//;
$u =~ tr/A-Z/a-z/;

# for now convert to UTF-8 sequence of bytes and run thru awk
$octets = &utf8tobytes(chr(hex $u));
$cmd = "/bin/nawk '\$0~/$octets/' $file";
print $cmd, "\n" if $opt_g;
system $cmd unless $opt_g;
exit 0;


sub utf8tobytes {
  my($c) = @_;
  my($file) = "/tmp/foo.$$";

  open FH, ">:utf8", $file;
  print FH $c;
  close(FH);

  open(FH, $file);
  binmode FH;
  read(FH, $buffer, 100);
  close(FH);

  foreach (unpack("C*", $buffer)) {
    $r .= sprintf("\\%o",$_);
  }
  unlink $file;
  return $r;
}
