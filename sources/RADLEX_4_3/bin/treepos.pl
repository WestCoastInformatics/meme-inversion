#!/usr/bin/perl -w

use lib "$ENV{INV_HOME_OLD}/lib";
use integer;

$out = "../cxt/treepos.out";

`$ENV{INV_HOME_OLD}/bin/contexts/bt_nt_to_treepos.pl -d ../cxt -addroot <<EOF>>$out
116482203

V-RADLEX
RADLEX
SRC/RHT
Y
Y
EOF`
