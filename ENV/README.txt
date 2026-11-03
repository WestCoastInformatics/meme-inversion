Version Information
-------------------
RELEASE=4
VERSION=1.0
DATE=20051206
AUTHORITY=BAC

This release of the common environment does not add any new environment variables.
Notable changes include:

  o Fix to env.pl script to better handle UTf-8 data in perl 5.8.  We use the
    ":utf8" open pragma for STDIN, STDOUT, and STDERR instead of the legacy
    ":encoding(utf-8)" pragma.

See INSTALL.txt for installation instructions


Old Release Information
-----------------------
RELEASE=4
VERSION=0.5
DATE=20051028
AUTHORITY=BAC

This release of the common environment does not add any new environment variables. 
However, it does extend the env.pl script to include BINMODE calls to set the 
character encoding of STDIN, STDOUT, and STDERR to UTF-8 by default.  This is needed
for Perl 5.8 (but not 5.6) installations
