#!/usr/bin/perl
###Created by: MAJ 11/06/98
#Usage: txt2meow.pl filename (> file.html)

# modifications
# 9/23/99 BK
#	changed date to accomdate Y2K date 
#	added sub routine to ask user for alternate file name
#	added sub routine to ask user for optional note

# CONFIG
$u_note = '';
$mail = "reg\@msdinc.com";

use Cwd;

if ($#ARGV < 1){ print "Usage: txt2meow.pl <filename> <yourname>.\n";
	     exit()}

#print "\n\tOutput filename: $outfile\n";

$file = $ARGV[0];
$name = $ARGV[1];
($sec, $min, $hour, $day, $month, $year, $wday, $yday, $isdst) = localtime(time);

#$year += 1900;

$year = `date +%Y`;

$month += 1;
$path = cwd();
if($file =~ /\.txt$/){ 
	$outfile = $file;
	$outfile =~ s/\.txt$//;
}
$outfile = $outfile . ".html";

&ask_user;

&ask_note;

print "\$outfile: $outfile\n";
print "\$u_note: $u_note\n";

open(FILE, "$file") or die "Can't open/read \"$file\", $!";
@file_contents = <FILE>;
open(OUT, ">$outfile");
($junk, $stuff1, $stuff, $dir1, $dir) = split(/\//, $path);

#system("clear");


if ($dir1 eq "Recipes"){ $title = "Recipe of ". $dir}
else {$title = $dir1 . " Inversion Notes"}
$notes = $outfile;

print OUT <<END_of_Start;
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">
<HTML>
    <HEAD>
    <TITLE>
    $title
    </TITLE>
    <BODY>
    <PRE>
END_of_Start


seek(FILE,0,0);
while(<FILE>){ 
    s/</&#60/g;
    s/>/&#62/g;
    print OUT;
}
print OUT <<END_of_Body;

</PRE>
<HR>
<ADDRESS>Contact: <A HREF="mailto:$mail"> $name </A></ADDRESS>
<ADDRESS>Created: $month/$day/$year </ADDRESS>
<ADDRESS>Last Updated: $month/$day/$year </ADDRESS>
<ADDRESS><A HREF="http://unimed.nlm.nih.gov">Meta News Home</A></ADDRESS>

<!-- These comments are used by the What's new Generator -->
END_of_Body

printf OUT "<!-- Changed On: %4d/%02d/%02d", $year,$month,$day;

print OUT <<END_OF_HTML;
 -->
<!-- Changed by: $name -->
<!-- Change Note: $notes -->
<!-- Fresh for: 1 month -->
</BODY>
</HTML>
END_OF_HTML

close OUT;
close FILE;

sub ask_note {
	#system("clear");
	my $resp = '';
	my $acpt_flg = 0;
	while(! $acpt_flg) {
		if($u_note){
			#system("clear");
			print "\n\n\tType a new note or Hit RETURN to accept this note:\n\n";
			print "> $u_note\n";
			print "\n> ";
			}
		else {
			#system("clear");
			print "\n\n\tEnter a one line note for this file\n";
			print "\n\t(or hit RETURN to continue)\n> ";
		}
		$resp = <STDIN>;
		if($resp=~/^$/) {
			return $u_note;
		}
		$u_note = $resp;
			
	}

}

sub ask_user{
	#system("clear");
	my $resp = '';
	my $acpt_flg = 0;
	while(! $acpt_flg){
		print "\n\n\tOutput file: $outfile\n\n";
		print "\tEnter new name OR hit RETURN to accept: ";
		$resp = <STDIN>;
		if ($resp =~ /^$/) {
			return $outfile;
		}
		#system("clear");
		$outfile = $resp;
	}

}



