#!/usr/bin/perl

while (<>) {
  @f = split(/\|/);
  if ($f[3] =~ /_10$/ && $f[5] eq 'CCS') {
    $f[5] = 'CCS_10';
  }
  print join('|', @f);
}
