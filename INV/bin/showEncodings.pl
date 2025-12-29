#!/usr/bin/perl
#


# Converts from known encodings to UTF-8

# Command line options:
# -s <encoding> (source encoding - to see a full list use -e)
# -e (show all encodings)
# -d (ensure \r\n line termination)
# -u (ensure \n line termination)

# Standard source encodings:
# CP1252 -> cp1252
# ISO-8859-1

use Encode;
use Encode::Encoder;

# All available encodings
print join("\n", Encode->encodings(":all")), "\n";

