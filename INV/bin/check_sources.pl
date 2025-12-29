#!/usr/bin/perl
use integer;
# changes
# 06/28/2007 WAK (1-ELQTB): changes for subfields in MRSAB
# check_source.src.pl
#
# usage: check_sources.src.pl [| more]
#
# 06/25/2007 - WAK
# assumes that Content Contact, License Contact, and Citation have
# subfields delimited by ';'

# Mon Sep 29 15:15:50 PDT 2003 - WAK
# 2006/08/07 modified to read class_src from ../etc -NEO
#
# Use this script to display the fields of a MEME4 sources.src file
# in an easy to read format of one field per line.
#
# The script can also be used to create a file for editing with a 'label|value'
# format. Use the script 'make.sources.src' to convert the template format into
# the standard 'sources.src' format
#
# Also displays the Name of the field, the Number, the Size and the Size Limit
# Fields that are blank or oversized are flagged.
#
# field size limits
#         1  2  3  4  5  6  7  8    9   10   11   12   13  14  15   16 17   18   19 20
@lim = (0,20,20,12,20,20,20,20,1200,100,1000,1000,1000,100,100,4000,10,4000,4000,50,1);

# Contact Name
# Contact Title
# Contact Organization
# Contact Address 1
# Contact Address 2
# Contact City
# Contact State or Province
# Contact Country
# Contact Zip or Post Code
# Contact Telephone
# Contact Fax
# Contact Email:
# Contact URL:
#
#
# SCIT
#

# Author(s) (last name, first name, initial)
# Personal author address
# Organization author(s) (not the publisher)
# Editor(s)
# Title
# Content Designator
# Medium Designator
# Edition
# Place of Publication (may be inferred or unknown)
# Publisher
# Date of publication/date of copyright
# Date of revision
# Location
# Extent
# Series
# Availability Statement (URL)
# Language
# Notes

@SCC_label = ("Name","Title","Organization","Address 1","Address 2","City","State/Prov.","Country","Zip","Telephone","Fax","Email","URL");

@SLC_label = ("Name","Title","Organization","Address 1","Address 2","City","State/Prov.","Country","Zip","Telephone","Fax","Email","URL");

@SCIT_label = ("Author name(s)","Personal author address","Organization author(s)","Editor(s)","Title","Content Designator","Medium Designator","Edition","Place of Pub.","Publisher","Date of pub. or copyright","Date of revision","Locatio
n","Extent","Series","Avail. Statement (URL)","Language","Notes"),

# field names
@name = ("NULL", "Source Name", "Low Source", "Restriction Level",
        "Normalized Source","Stripped Source", "Version", "Source Family",
        "Official Name", "NLM contact", "Acquisition Contact", "Content Contact",
        "License Contact", "Inverter", "Context Type", "URL", "Language", "Citation",
        "License Info", "Char Set", "Rel Direction Flag");

$sources = shift(@ARGV);
unless($sources){ $sources = "./dummy_sources.src"}
$class = "../etc/class_src";

if(-e "$sources"){}
else{print "Can't find file '$source'..."}

if(-e "$class"){&print_class_src()}
else{print "Can't find file '$class'..."}

print "  ------ sources.src -------\n";
open(SOURCE, "$sources") or die "Can't open/read $sources, $!";
printf "%-25s %10s %10s %12s\n", "Field Name", "Field No.", "Length", "Size Limit";
print "-" x 60;
print "\n";
while(<SOURCE>){
        chomp;
        @F = split(/\|/);
        # if mult sources, print divider
        if($src){
                print "=" x 18;
                print " $F[0] ";
                print "=" x 30;
                print "\n";
                printf "%-25s %10s %10s %12s\n", "Field Name", "Field No.", "Length", "Size Limit";
                print "-" x 60;
                print "\n";
        }
        unshift(@F,"NULL");
        foreach $i (1 .. 20){
                $len = length($F[$i]);
                printf "%-25s %10d %10d %12d\n",$name[$i],$i,$len,$lim[$i];
                #print " Length: $len  Limit: $lim[$i]\n";
                if($len > $lim[$i]){
                        print "  **** This Field exceeds the size Limit **** \n";
                }
                if($i == 11){
                        @data = split(';',$F[$i]);
                        for $k (0 .. 12){
                                printf "  %-14s %-50s\n",$SCC_label[$k],$data[$k];
                        }
                }
                elsif($i == 12){
                        @data = split(';',$F[$i]);
                        for $k (0 .. 12){
                                printf "  %-14s %-50s\n",$SLC_label[$k],$data[$k];
                        }
                }
                elsif($i == 17){
                        @data = split(';',$F[$i]);
                        for $k (0 .. 18){
                                printf("  %-27s%-50s\n", $SCIT_label[$k],$data[$k]);
                        }
                }
                elsif($F[$i] eq ""){ print " - BLANK -\n" }
                else{ print "$F[$i]\n" }
                print "\n";
                $src++;
        }
}

# if the file 'class_src' exists
# print the 3rd (termgroup), 4th (code) and 8th (atom name) fields
sub print_class_src{
        #open(CLASS, "../etc/class_src");
        open(CLASS, "$class");
        print "  ------ SRC Atoms ------\n";
        while(<CLASS>){
                ($said,$src,$tg,$code,$stat,$tbr,$rel,$term)=split(/\|/);
                printf "%-12s %-55s\n", "Termgroup", $tg;
                printf "%-12s %-55s\n", "Code", $code;
                printf "%-12s %-55s\n", "Term", $term;
                print "-" x 60;
                print "\n";
        }
        close CLASS;
        print "-" x 60;
        print "\n";
        print "\n";
}
