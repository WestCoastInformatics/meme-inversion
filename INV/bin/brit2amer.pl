#!/usr/bin/perl 
#
# Thu Dec 18 09:32:57 PST 2003 - WAK 
#
# converts Britishisms to American english 
# see help message below (in "sub print_help") for
# more details

use integer;
use Getopt::Std;
use Term::ANSIColor;
$Term::ANSIColor::EACHLINE = $/;

# default mapping file
$map = "$ENV{INV_HOME_OLD}/etc/brit.amer.map";
# 
getopts("hf:m:v", \%option);  #get options
# f - field to check
# m - use mapping file
# h - show help
# 
if($option{h}){ &print_help(); exit}
unless($fieldno = $option{f}){ 
	print colored(<<EOW, RED);

        No Field Number given
        $0 -h for help


EOW
	exit}
if($option{m}){$map = $option{m}} 
if($option{v}){$verbose++}

unless($filename = shift(@ARGV)){
	&print_help();
}
$fieldno--;		# field numbers start at 1

open(MAP, "$map") or die "Can't open $map, $!\n";
while(<MAP>){
	chomp;
	($brit,$amer)= split(/\|/);
	$map{$brit}=$amer;
}

open(IN, "$filename") or die "Can't open $filename, $!";
while(<IN>){
	chomp;
	@F = split(/\|/);
	$conv_str = $F[$fieldno];
	@W = split(" ", $F[$fieldno]);
	foreach $w (@W){ 
		#strip punctuation
		$w =~ s/[\,\\\/\(\)\{\}\;\.\!\@\#\$\%\^\&\\<\>\?]//g;
		#print "$w\n";
		$low = lc($w);
		if($map{$low}) {
			if(&is_upper($w)){
				$flag = 'U'}
			elsif(&is_lower($w)){ 
				$flag = 'L'}
			elsif(&is_cap($w)){
				$flag = 'C'}
			else{
				$flag = 'UNK';
				if($verbose){ print STDERR "$. : $w \n\n$_\n"}
			}
			$map = $map{$low};
			if($flag eq 'U'){
				$new = uc($map);
				$conv_str =~ s/$w/$new/g;
			}
			elsif($flag eq 'L'){ 
				$new = lc($map);
				$conv_str =~ s/$w/$new/g;
			}
			elsif($flag eq 'C'){;
				$new = to_cap($map);
				$conv_str =~ s/$w/$new/g;
			}
		}
	}
	$str = join('|',@F);
	print "$str|$conv_str\n";
}

sub to_cap{
	my($w) = shift;
	$first = substr($w,0,1);
	$rest = substr($w,1);
	return (uc($first).lc($rest));
}

sub is_upper{
	my($w) = shift;
	if($w eq (uc($w))){ return 1}
	else{ return 0}
}

sub is_lower{
	my($w) = shift;
	if($w eq (lc($w))){ return 1}
	else{ return 0}
}

sub is_cap{
	my $first;
	my($w) = shift;
	# get the first char
	$first = substr($w,0,1);
	$rest = substr($w,1);
	if(($first =~ /[A-Z]/) && (&is_lower($rest))){return 1}
	else{return 0};
}

sub print_help{
print STDERR <<EOT;
	
	usage: $0 -f fieldnum [-h] [-m mfile] file > outfile

	-h         prints help message (this screen)
	-f n       field number to convert
	-m mfile   use mapping file 'mfile' 
	-v         "verbose", print unmappable mixed case words
	           to STDERR (console)

	$0 assumes vertical bar delimited files ('|'). Looks 
	at the field specified and compares each word in it 
	to the mapping file (default = "brit.amer.map").

	A new field is appended to each line with the converted 
	equivalents, or the same field value if no substitutions
	are made.

	Output is written to STDOUT

	Words are converted to their case sensitive equivalents, i.e.,
	"Apnoea" = "Apnea"
	"ANALOGUES" = "ANALOGS"
	"aluminium" = "aluminum"

	Any word that is not purely lower case, upper case, or capitalized
	lower case, i.e., mixed case ("AntiThrombinaemia") will NOT BE
	CONVERTED and will generate an error to STDERR (the console) 
	if the '-v' flag is given.

	written by BK 12/18/2003 - bking\@msdinc.com


EOT
}
