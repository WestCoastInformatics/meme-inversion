#!/usr/bin/perl
#
# File:         print.raw3.to.attributes.pl
# Author:       Nels Olson/Deborah Shapiro/Bill King
#
#
# This script has the following usage:
# print.raw3.to.attributes.pl <source>.raw3
# source.raw3 must exist in calling directory
#
# Options:
#       -v[ersion]:     Print version information
#       -[-]help:       On-line help
#
# generates ".all"-style CONTEXT attributes and write them to a file
# called attributes.contexts-all.src, numbered so that they can be
# appended to the attributes.src file in the current directory.
# Attribute format is:
# "cid\thcd\tANC\tSELF\tCHD\tSIB"    where:
# ANC is:  root~anc2~...~parent
# SELF is: self
# CHD is:  chd1[^]~chd2[^]~...~chdK[^]
# SIB is:  sib1[^]~sib2[^]~...~sibJ[^]    ([^] is optional has-children flag)
#
# prints out a stat_report.log
# alerts user of concepts with more than 99 contexts
#                concepts with more than 200 siblings
# distributions are then displayed for
#                number of concepts with various ranges of sibling numbers
#                number of concepts with various ranges of contexts
#
# Version information
# 2007/03/20 NEO (1-DSDZH): Fixed format of "More contexts not shown" lines.
# 11/10/2006 BAC (1-CDMK9): Added to repos.
# 2006/05/04 3.1.4: Added 'encode_utf8' for md5s of UTF-8 chars
# 2006/04/25 3.1.3: Fixed to print error message if input isn't sorted
# 2006/01/06 3.1.2: Fixed to properly truncate the last context in the file
# 2003/05/05 3.1.1: Limits number of entries for a single source atom id
#                   to $MAX_COUNT (currently = 10).
# 2000/06/21 3.1.0: Script changed from cx.pl to work with <source>.raw3 input rather
#                               than <source>.raw2 input
$release = "3";
$version = "1.3";
$version_date = "2006/04/25";
$version_authority="NEO";

unshift @INC, "$ENV{ENV_HOME}/bin";
require "env.pl";
use open ":utf8";

$ENV{"LANG"} = "en_US.UTF-8";
$ENV{"LC_COLLATE"} = "C";

# used to make MD5 hashes
use Digest::MD5 qw(md5_hex);
use File::Copy;
use Encode qw(encode_utf8);

#
# Parse arguments
#
while(@ARGV) {
    $arg = shift(@ARGV);
    push (@ARGS, $arg) && next unless $arg =~ /^-/;

    if ($arg eq "-v") {
        $print_version="v";
    }
    elsif ($arg eq "-version") {
        $print_version="version";
    }
    elsif ($arg eq "-help" || $arg eq "--help") {
        $print_help=1;
    }
    else {
        $badargs = 1;
        $badswitch = $arg;
    }
}

#
# Print Help/Version info, exit
#
&PrintHelp && exit(0) if $print_help;
&PrintVersion($print_version) && exit(0) if $print_version;

#
# Get arguments
#
if ($badargs) {
}
elsif (scalar(@ARGS) == 1) {
    ($source) = @ARGS;
}
else {
    $badargs = 2;
    $badopt = $#ARGS+1;
}

#
# Check dependencies
#
print "$source\n";
if ( !(-e "$source")) {
   $badargs = 3;
}

#
# Print bad argument errors if any found
#
if ($badargs) {
    %errors = (1 => "Illegal switch: $badswitch",
               2 => "Bad number of arguments: $badopt",
               3 => "Cannot find $source; exiting..."
              );
    &PrintUsage;
    print "\n$errors{$badargs}\n";
    exit(0);
}

#
# Find last attribute-id from attributes.src file
#

$attrib = 'attributes.src';
if(-e $attrib){
        print "\tFound '$attrib'\n";
        # get last 'source_attribute_id' from attributes.src
        $lastline = `tail -1 attributes.src`;
        die "Attempt to read $attrib exited funny" if($?);
        ($id) = split(/\|/,$lastline);
        if($id =~ /\D/ || $id !~ /\d/){
                print "Whoops, last id number [$id] is not a valid number in attributes.src\n";
                print "Are you sure you've got a correct MEME3 file?\n\n ";
                exit;
        }
#        print "\n\n\tCopying old '$attrib' to /var/tmp\n";
#        copy("$attrib", "/var/tmp/$attrib") or die "copy failed $!";
        $id++;
} else {
        print "\tNo '$attrib' file found\n";
#        print "\tCreating a new '$attrib'\n";
#        `touch $attrib`;
#        die "Attempt to 'touch' $attrib exited funny" if($?);
        $id = 1;
}

#
# Program Logic
#

$\ = "\n";              # set output record separator
$MAX_COUNT = 10;
open(STAT_REPORT, ">stat_report.log");
open(SOURCE, $source) or die "can't open $source file, $!";
binmode(SOURCE, ":utf8");

#open(STDOUT, ">>$attrib") or die "can't append to attributes.src file";
#binmode(STDOUT, ":utf8");
open(STDOUT, ">attributes.contexts-all.src") or die "can't create attributes.contexts-all.src file";
binmode(STDOUT, ":utf8");

while (<SOURCE>) {
    die "input not sorted properly, stopped" if substr($_,0,22) lt $prevkey;
    $prevkey = substr($_,0,22);
    ($tmid,$cid,$level,$sort,$term,$code,$hcd,$rel,$xc,$sab) =
        /([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|[^|]*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|[^|]*\|([^|\n]*)/;

    #
    # Stop if $cid exceeds $MAX_COUNT
    #
    if ($cid > $MAX_COUNT) {
      if ($level eq ' 0' && $cid == ($MAX_COUNT+1)) {
          $atv = "$cid\t$hcd\t\t$term\tMore contexts not shown\t";
          $md5 = md5_hex(encode_utf8($atv));
          print "$id|$tmid|S|CONTEXT|$atv|$sab|R|n|N|N|SRC_ATOM_ID|||$md5|";
          ++$id;
      }
      next;
    }

    $cid =~ s/ +//;
    $tmid =~ s/ +//;
    $xc = ($xc eq '1') ? '^' : '';
    if ($tmid != $lasttmid  ||  $cid != $lastcid) {
        print {STAT_REPORT} $lasttmid, "  context_id: ", $lastcid, "  siblings: ", $sibling_counter if $sibling_counter > 200;
        $cids[$lastcid] += 1 if $tmid != $lasttmid;
        if ($lastcid > 99 && $tmid != $lasttmid && $cid != $lastcid) {
            print {STAT_REPORT} $lasttmid, "  contexts: ", $lastcid;
        }
        if ($chd_counter > 100) {
            $line .= '~[CHILDREN AFTER THE FIRST 100 HAVE BEEN TRUNCATED]';
        }
        $chd_counter = 0;
        if ($line ne '') {
            $line .= "\t" x (3 - $lastpart);
            $line =~ s/(\t[^\t]*)(\t[^\t]*)$/$2$1/;
            $siblings[$sibling_counter/10]+=1;
            $sibling_counter = 0;
            $md5 = md5_hex(encode_utf8($line));
            print "$id|$lasttmid|S|CONTEXT|$line|$lastsab|R|n|N|N|SRC_ATOM_ID|||$md5|";
            ++$id;
        }
        $lastpart=0;
        $first=1;
        $line = '';
        $lasttmid=$tmid; $lastcid=$cid; $lastsab=$sab;
    }
    $part = ($level < 50) ? 0 : ($level == 50) ? 1 : ($level == 60) ? 2 : 3;
    if ($part != $lastpart) {
        $line .= "\t" x ($part - $lastpart);
        $lastpart = $part;
        $first=1;
    }
    $chd_counter++ if $part == 3;
    unless ($chd_counter > 100) {
        $line .= '~' unless $first;
        $first=0;
        $xc = '' if $part<2;    # no child-flags needed on ancestors or self's
        $line .= "$term$xc";
        $sibling_counter++ if $part == 2;
        $line = "$cid\t$hcd\t$line" if $part == 1;
    }
}

print {STAT_REPORT} $lasttmid, "  context_id: ", $lastcid, "  siblings: ", $sibling_counter if $sibling_counter > 200;
$cids[$lastcid] += 1;
if ($lastcid > 99) {
    print {STAT_REPORT} $lasttmid, "  contexts: ", $lastcid;
}
if ($chd_counter > 100) {
    $line .= '~[CHILDREN AFTER THE FIRST 100 HAVE BEEN TRUNCATED]';
}
$line .= "\t" x (3 - $lastpart);
$line =~ s/(\t[^\t]*)(\t[^\t]*)$/$2$1/;
$siblings[$sibling_counter/10]+=1;
$md5 = md5_hex(encode_utf8($line));
print "$id|$lasttmid|S|CONTEXT|$line|$lastsab|R|n|N|N|SRC_ATOM_ID|||$md5|";

print {STAT_REPORT} "\n", "siblings", "\t", "num of concepts";
for($index = 0; $index<=$#siblings; $index++ ) {
    print {STAT_REPORT} ($index*10), "-", ($index*10)+9, "\t\t", $siblings[$index];
}

print {STAT_REPORT} "\n", "contexts", "\t", "num of concepts";
for($index = 1; $index<=$#cids; $index++ ) {
    print {STAT_REPORT} $index, "\t\t", $cids[$index];
}

#
# Cleanup & Exit
#
close $SOURCE;
close $STAT_REPORT;
close $STDOUT;
exit (0);

############################# local procedures ################################
sub PrintVersion {
    my($type) = @_;
    print "Release $release: version $version, ".
          "$version_date ($version_authority).\n"
          if $type eq "version";
    print "$version\n" if $type eq "v";
    return 1;
}

sub PrintUsage {
    print qq{ This script has the following usage:
  $0 <SAB>.raw3 (SAB = Source Abbrev.)
  <SAB>.raw3 must be located in the calling directory
    };
}

sub PrintHelp {
    &PrintUsage;
    print qq{
  Options:
        -v[ersion]:     Print version information.
        -[-]help:       On-line help
    };
    &PrintVersion("version");
    return 1;
}
