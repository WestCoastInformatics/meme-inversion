#!/usr/bin/perl

open(MAP, "sab.vsab.map");
while (<MAP>) {
  next if /^ RSAB/;
  ($rsab, $oldvsab, $newvsab) = split(/[|\n]/);
  next if $newvsab eq 'same';
  $newvsab{$oldvsab} = $newvsab;
}

while (<>) {
  @f = split(/\|/);
  if ($f[11] eq 'SRC' && $f[12] =~ /^V/) {
    ($oldvsab) = ($f[13] =~ /^V-(.*)/);
    $newvsab = $newvsab{$oldvsab};
    if ($newvsab ne '') {
      $f[13] = 'V-' . $newvsab;
      $f[14] = $newvsab if $f[12] eq 'VAB';
    }
  }
  print join('|', @f);
}
