#!/usr/bin/perl
#
# check4britishisms.pl
# checks a file for british spellings
# outputs to STDOUT 
# written by BK 4/00

if($#ARGV != 1){die "\nusage: $0  field_to_check filename\n\n"}
$field = ($ARGV[0]);
$file =  ($ARGV[1]);

$delim =~ s/"//g;
$delim =~ s/-t//;

$britcnt = 0;
$wordcnt = 0;
$corrcnt = 0;

print "\n\tChecking field $field in $file\n";
print "\tUsing \"|\" as delimiter\n\n";
# exit;

# read in brit.amer.map
open (BRIT, "$ENV{INV_HOME_OLD}/etc/brit.amer.map") or die "Can't open Brit/Amer map file, $!";
while(<BRIT>){
	chomp;
	($brit,$am)=split(/\|/,$_);
	$britcnt++;
	$bhash{$brit}=$am;

}
close BRIT;
print "\tFound $britcnt British spellings to check against\n\n";

$field--;
 printf "%-6s %s\n", "Line #", "British|American";

open (IN, "$file") or die "Can't open $file, $!";
while(<IN>){
	chomp;
	@field = split(/\|/,$_);
	# print "$field[$field]\n";
	@word = split(/\b/,$field[$field]);
	for $word (@word){
		$wordcnt++;
		$w = lc($word);
		if($bhash{$w}){
			$corrcnt++;
			if(ord(substr($word,0,1))< 91) { 
				$corr = ucfirst($bhash{$w});
			}
			else { 
				$corr = $bhash{$w};
			}
		printf "%6d %s|%s\n", $., $word,$corr;
                #print "$.: $word|$corr\n" ;

		}
	}
}
print "\n\tChecked $wordcnt Words, Found $corrcnt corrections\n";
print "\n";	





