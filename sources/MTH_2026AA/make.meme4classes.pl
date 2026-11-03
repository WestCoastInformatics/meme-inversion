#!/usr/bin/perl

open(INPUT, "said.ptsaid");
while (<INPUT>) {
    ($said, $pt) = split(/[|\n]/);
    next if $said eq $pt;
    $saids{$pt} .= $said . '|';
}

$nextorderid=1000000;

open(INPUT, "ptsaid.order");
while (<INPUT>) {
    chomp;
    $pt = $_;
    chop($saids = $saids{$pt});
    $orderid{$pt} = ++$nextorderid;
    foreach $said (split(/\|/, $saids)) {
	$orderid{$said} = ++$nextorderid;
    }
}

open (INPUT, "classes_atoms3.src");
while (<INPUT>) {
    chomp;
    ($said = $_) =~ s/\|.*//;
    $orderid = $orderid{$said};
    $orderid = ++$nextorderid  if $orderid eq '';
    s/\|needs_order_id\|/|$orderid|/ or s/\|\|$/|$orderid|/;
    print $_, "\n";
}
