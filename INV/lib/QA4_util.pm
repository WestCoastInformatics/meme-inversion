#!/usr/bin/perl 
# %W%      %G%

#package QA4_util;

# herein are contained the various subroutines that are called from QA4.pm
# 

#
#----------------------------------------------------------------------#
# NUMERICALLY()
#----------------------------------------------------------------------#
# used for sorting by numerical order 
sub numerically { $a <=> $b }

#
#----------------------------------------------------------------------#
# PRINT_FIELD_REPORT()
#----------------------------------------------------------------------#
# prints the field report 
# takes:
# file type (classes, merges, rels, etc.)
# hashes: lo, hi, fcnts
# returns:
# nothing
#
sub print_field_report{
my($file,$rec_cnt,$fnum,$name,%fnum2name,$lo,$hi,$x,$non_zero);
$file = shift @_;
$rec_cnt = shift @_;

open(LABELS, "$ENV{INV_HOME}/etc/$file.fields") or die "Can't open $file.fields, $!";
while(<LABELS>){
	chomp;
	($fnum,$name)=split(/\|/);
	$fnum2name{$fnum}=$name;
}
close LABELS;
$fld_cnt = scalar(keys(%fnum2name));
 
print FILE "\n";
print FILE "Fld# Field Name                  length range  # nonzero\n";
print FILE "---- --------------------------- ------------- ---------\n";
for($x=0;$x<$fld_cnt;$x++){
	$fnum = $x +1;
	$lo = $lo{$x};
	$hi = $hi{$x};
	$non_zero = $fcnts{$x}>0?$fcnts{$x}:0;
	#print "$fnum : $lo - $hi : $fcnts{$x}\n";
	$name = $fnum2name{$fnum};
	printf FILE ("%4d %-26s  %3d - %4d %12d\n", $fnum,$name,$lo,$hi,$non_zero        );
}
print FILE "---------------------------------------------- ---------\n";
printf FILE ("%44s%12d\n", "Total Records",$rec_cnt);

print FILE "\n";
 
} # end of field counts block



#
#----------------------------------------------------------------------#
# GET_TTY_INFO()
#----------------------------------------------------------------------#
# gets obsolete TTY info from MRDOC.RRF if exists
# READS: ../src/MRDOC.RRF
# CREATES: %obsolete_tty
# 
sub get_tty_info{
my(@F);
my($obs, $obs_tty_cnt);

	#look for a MRDOC.RRF file
	if(-e "../src/MRDOC.RRF"){
		open(MRDOC, "../src/MRDOC.RRF") or return("Can't open the file '../src/MRDOC.RRF'");
		# global var indicating existance of MRDOC.RRF
		$mrdoc_exists++;
		while(<MRDOC>){
			@F = split(/\|/);
			next unless($F[2] eq 'tty_class');
			if($F[3] eq 'obsolete'){
				$obsolete_tty{$F[1]}++;
			}
		}
		if($obs_tty_cnt = scalar(keys(%obsolete_tty))){
			print $main::fh_summ "\nObsolete TTYs: $obs_tty_cnt - ";
			foreach $obs (keys(%obsolete_tty)){
				print $main::fh_summ "$obs ";
			}
			print $main::fh_summ "\n";
		}
	}
	else {
		return "Can't find a local 'MRDOC.RRF'\nPlease create this file before the final QA\n";
	}
	return(0);
}	# end of get_tty_info()

#----------------------------------------------------------------------#
# CK4RAW3()
#----------------------------------------------------------------------#
sub ck4raw3{
$cxt = "$main::dir/../src";
$dir = ".";

print $main::fh_summ "\n./contexts.src\n";
print $main::fh_file "\nCONTEXTS.SRC\n";
if(-d $cxt){
   opendir(TMP, "../tmp") or die "Can't open TMP dir: \"../tmp/\"";
   while(defined($cfile = readdir(CXT))){
      #print "$cfile\n";
      if($cfile =~ /raw3$/){
         $raw3 = $cfile;
         last;
      }
   }
   opendir(DIR, "$cxt") or die "Can't open Contexts dir - \"$cxt\" ";
   while(defined($file = readdir(DIR))){
      if($file eq "contexts.src"){
         $fnd_cxt++;
         if(-z $file){
            $zero_cxt++;
         }
         last;
      }
   }

   print $main::fh_file " the 'cxt' directory exists\n";

   if($raw3){ 
		print $main::fh_file " a raw3 file exists: '$raw3'\n";
	}
   if($fnd_cxt){ 
		print $main::fh_file " 'contexts.src' exists\n";

   	if($zero_cxt){ 
			print $main::fh_file "'contexts.src' exists but has zero length\n";
	
			print $main::fh_err  "--------------- CONTEXTS.SRC --------------- \n";
			print $main::fh_err "A 'cxt' directory exists\n";
			print $main::fh_err "but the 'contexts.src file has zero length\n";
			print $main::fh_err "You should have a valid 'contexts.src' file\n\n";
	
			print $main::fh_summ "A 'cxt' directory exists\n";
			print $main::fh_summ "but the 'contexts.src file has zero length\n";
			print $main::fh_summ "You should have a 'contexts.src' file\n\n";
		}
	}
   else{ 
		print $main::fh_file " but no 'contexts.src' file was found\n";
		print $main::fh_file " this is an error and should be fixed\n";
		print $main::fh_file " create a 'contexts.src' file in this dir\n\n";

		print $main::fh_err  "--------------- CONTEXTS.SRC ---------------\n";
		print $main::fh_err " CXT directory exists but no 'contexts.src file was found\n";
		print $main::fh_err " You should have a 'contexts.src' file\n\n";
	}
}
else{ 
	print $main::fh_summ "\nNo CXT directory found\n";
	print $main::fh_file "No CXT directory found, 'contexts.src' not required\n\n";
	print $main::fh_err "No CXT directory found, 'contexts.src' not required\n\n";
}

}	# end of ck4raw3()


# creates a hash of invalid rel/relas 
#
#----------------------------------------------------------------------#
# MAKE_INVALID_RELA_HASH()
#----------------------------------------------------------------------#
sub make_invalid_rela_hash{
	%invalid_rela_hash = (
		"NT|ingredient_of" => '1',
		"BT|ingredient_of" => '1',
		"NT|has_ingredient" => '1',
		"BT|has_ingredient" => '1',
		)
}

#----------------------------------------------------------------------#
# LOAD_CHAR_ENT_HASH()
#----------------------------------------------------------------------#
# called from QA4.pl
# creates a hash of valid HTML character entities
sub load_char_ent_hash{
$char_ent = "$ENV{INV_HOME}/etc/char_entities.txt";
open(CHARS, "$char_ent") or die "Can't open $char_ent, $!";
while(<CHARS>){
        next if(/^#/);
        chomp;
        @F=split(/\|/);
        $charent{$F[1]}++;
}
}	#end of load_char_ent_hash()


#----------------------------------------------------------------------#
# GET_CLASS_SAIDS()
#----------------------------------------------------------------------#
# gets a hash of saids from classes_atoms.src
# in case one didn't already exist
sub get_class_saids{
	my($class) = "$main::dir/classes_atoms.src";
	open(CLASS, "$class") or return $!;
	my($said);
	while(<CLASS>){
		($said) = split(/\|/);
		$said{$said}++;
	}
}	# end of get_class_saids()

#----------------------------------------------------------------------#
# GET_SA_SAIDS()
#----------------------------------------------------------------------#
# creates a hash of saids from source_atoms.dat
# called by check_treepos() in QA4.pm
sub get_sa_saids{
	my($said);
	my($sa) = "$main::dir/../cxt/source_atoms.dat";
	open(SA, "$sa") or return $!;
	while(<SA>){
		($said)=split(/\|/);
		$sa{$said}++;
	}
}	# end of get_sa_saids()


#----------------------------------------------------------------------#
# GET_RELAS() 
#----------------------------------------------------------------------#

#This makes a hash of valid RELAs for error checking
sub get_relas{	
  my (@fields);
  %rela = ();
  print "Using RELA file: '$valid_relas'\n";
  open (RELAS, "$valid_relas") or die "Can't open RELA file, $!";
  while (<RELAS>){
	 next if(/^#/);
	 next if(/^\s*$/);
    chomp;
    #@fields = split(/\|/);
    #$rela{$fields[2]} =1;	#hashes valid values for 
    #$rela{$fields[9]} =1;	#later comparison
    $rela{$_}++;
   }
  return %rela;
  close(RELAS);
 }		# end of get_relas

# get the valid languages
sub get_valid_lang {
	my(@fields);
	%valid_lang = ();
	open (LANG, "$valid_langs") or die "Can't open valid_lang file, $!";
	while(<LANG>){
		next if(/^#/);
		chomp;
		($lang,$abrv)=split(/\|/);
		$valid_lang{$abrv}++;
	}
	return;
	close(LANG);
}

#----------------------------------------------------------------------#
# COUNT_SELF_MERGE()  
#----------------------------------------------------------------------#
sub count_self_merge{
	my ($filename) = @_;
	my (%seen) = ();
	my ($linecnt, $bad);
	my (%bad_line)= '';
	my $x = 0;
	$bad = 0;
	open(IN, "<$main::dir/$filename") or die "Can't open $filename, reason $!";
	while(<IN>){ #checks for duplicate merges
	$linecnt++;
	chomp;
	@fields = split /\|/;
	 $obj1 = "$fields[0]-$fields[8]-$fields[9]";
	 $obj2 = "$fields[2]-$fields[10]-$fields[11]";
	if ($obj1 gt $obj2){
		#print "$obj1|$obj2\n";
		 $merge = "$obj2|$obj1";
		#print "1>2: $merge\n";
	 }
	elsif ($obj1 lt $obj2){
		#print "$obj1|$obj2\n";
		$merge = "$obj1|$obj2";
		#print "1<2: $merge\n";
	 }
	elsif($obj1 eq $obj2){
		#print "1=2\n";
		#print "$obj1|$obj2\n";
		 $bad++;
		 unless($bad > $limit){$bad_line{$linecnt} = $_};
	}
	else{ print "you'll never see this error msg\n"}
	if ($seen{$merge}++){
		$bad++;
		unless($bad > $limit){$bad_line{$linecnt} = $_}
	}
	#print "\n";
}
print $main::fh_file "\n----- Merges between the same atoms - $filename -----\n";
print $main::fh_file "$bad\tBad Merges \n";
if($bad){
	print $main::fh_err "---- Merges between same atoms: $bad\n";
	foreach $x ((keys(%bad_line))){
		if($x){
			printf $main::fh_err "%d %s\n", $x, $bad_line{$x};
		}
	}
}
  
printf $main::fh_summ "%6d %s\n", $bad, " Merges between the same atoms";
close IN;
%bad_line = %seen=();
}		# end of count_self_merge()




#----------------------------------------------------------------------#
# TALLY() 
#----------------------------------------------------------------------#
# called from QA4.pl
#	passes 2 arg
#	1 - code for file, e.g., "class" to signify a classes_atoms type file
#	2 - name of file to check
#	
# calls tallythis() to create the tally string
# calls tallyfield() to create the tally
# calls trunc_array() to truncate overly long strings

sub tally{ # Nels wrote the orig code
  # set up string for 
  my ($x, $file)=@_;
  #my ($i, $c, $p, $pf, $v, $savep, $X);
  my ($cl,$r,$m,$a,$rt);
  my ($i, $pf, $X);
  local (%count, $tot, $tallythis);
  
  
 SWITCH: {
   if($x =~ /class/){
     # the fields to tally
     #$str = "\$3\$5\$6\$7\$8\$10"; # meme2
     $str = "\$3\$5\$6\$7\$9";	# meme3
     $cl++;
     
     # the string in $fmt is the output format for the header and
     # the display string, also used by trunc_array() to 
     # truncate display strings that are bigger than this.
     #$fmt = "%-20s %-5s %-5s %-5s %-5s %-5s %8s";
     #$fmt = "%-20s %-5s %-5s %-5s %-5s %12s";
     $fmt = "%-22s %-5s %-5s %-5s %-5s %12s";
     
     # the test to display in the column heads
     @hd = qw(Termgroup    Stat TBR Rel Sup Count);
     last SWITCH;
    }
   
   if($x =~ /rel/)	{
     # Field lengths are
     # 1|8|10|20|8|10|1|1|1|1|10
     # Lev, Rnam, RelAtt, rel_src, Gen, Stat, TBR, Rel
     # $str = "\$1\$3\$4\$6\$7\$8\$9\$10\$11"; # meme2
     
     # Lev,Rnam,RelAtt,RelSrc,RelLab,Stat,TBR,Rel,Sup
     $str = "\$2\$4\$5\$7\$8\$9\$10\$11\$12";	# meme3
     $r++;
     
     $fmt = "%-2s %-4s %-28s %-10s %-10s %-2s %-2s %-2s %-2s %7s";
     @hd = qw(L RN Rel_Attrib Rel_Src Rel_Label S T R S Count);
     last SWITCH;
    }
   
   if($x =~ /attr/){
     # old tally
     #$str = "\$2\$3\$5\$6\$7\$8\$9";
     $str = "\$3\$4\$6\$7\$8\$9\$10\$11";
     $a++;
     #$fmt = "%-3s %-18s %-14s %-3s %-4s %-4s %-5s %-13s %7s";
     $fmt = "%-2s %-22s %-14s %-2s %-3s %-3s %-4s %-13s %7s";
     @hd = qw (Lv Attr_Name SRC St TBR Rel Sup Type Count);
     last SWITCH;
    }
   
   if($x =~ /merge/){
     #$str = "\$2\$4\$6\$7\$8\$9";	# meme2
     $str = "\$2\$4\$6\$7\$8\$9\$11";	# meme3
     $m++;
     $fmt = "%-3s %-14s %-2s %-2s %-17s %-15s %-15s %8s";
     @hd = qw (MLv Src MD CS MergeSet Src1 Src2 Count);
     last SWITCH;
    }
	if($x =~ /retired/){
	 	$str ="\$2\$3\$4";
		$fmt = "%-15s %-20s %-20s %8s";
		@hd = qw (ID_type ID_qual ATN Count);
		$rt++;
		last SWITCH;
	}
  }	# end of SWITCH

  $[ = 1;      # array first element is 1 not 0
  $, = ' ';    # set output field separator
  
  # changes "$3$4$5..." into
  # $3 . "|" $4 . "|" . $5 etc.
  $tallythis = &tallythis($str); # make the string
  
  &tallyfile($file);
	if($r && (!$sab)){
		if($SAB){$sab = $SAB} 	# use user supplied val if exists
		else{
			print $main::fh_file "\n\nSAB not available, Sources & Labels are truncated\n";
			print $main::fh_file "Run full QA to see full values or use \" -s {SAB}\" \n"; 
		}

	}
  # print header
  print $main::fh_file "\n----- Tally Field Counts - $file -----\n";
  printf $main::fh_file "$fmt\n", $hd[1],$hd[2],$hd[3],$hd[4],$hd[5],$hd[6],$hd[7],$hd[8],$hd[9],$hd[10];

  foreach $X (sort keys(%count)) {
    $tot += $count{$X};
    @pf=split(/\|/,$X);
    
    if($cl){	printf $main::fh_file "$fmt\n", $pf[1],$pf[2],$pf[3],$pf[4],$pf[5], $count{$X}}
    
     if($r){	# if relat
## 		 printf $main::fh_file "Array index: $[\n";
## 		 foreach $z (@pf){
## 			printf $fh_file "%2d %s\n", ++$zzz, $z;
## 		 	print $fh_file "$zzz: $pf[$zzz]\n";
## 		 	print $fh_file "\n";
## 		 }
##		 $zzz=0;

			# truncate the Rel_Src & Rel_Label if they are bigger than 8
			# replace the sab with '{SAB}' & tail
			if(($pf[4] =~ /$main::sab/)&& length($pf[4]) >= 8){
				$pf[4] =~ /$main::sab/;
				$pf[4] = "{SAB}".$';
				$sab_flg++;
			}

			if(($pf[5] =~ /$main::sab/)&& length($pf[5]) >= 8){
				$pf[5] =~ /$main::sab/;
				$pf[5] = "{SAB}".$';
				$sab_flg++;
			}

			# this truncates any field that is longer than the spec. format
    	&trunc_array($fmt);

      printf $main::fh_file "$fmt\n", $pf[1],$pf[2],$pf[3],$pf[4],$pf[5],$pf[6],$pf[7],$pf[8],$pf[9],$count{$X};
		}
    
    if($a){	
    	&trunc_array($fmt);
			printf $main::fh_file "$fmt\n", $pf[1],$pf[2],$pf[3],$pf[4],$pf[5],$pf[6],$pf[7],$pf[8],$count{$X}}
    
    if($m){	
    	&trunc_array($fmt);
			printf $main::fh_file "$fmt\n", $pf[1],$pf[2],$pf[3],$pf[4],$pf[5],$pf[6],$pf[7],$count{$X}}

		if($rt){
			printf $main::fh_file "$fmt\n", $pf[1],$pf[2],$pf[3],$count{$X}}
		}
  print $main::fh_file "====================\n";
  print $main::fh_file 'TOTAL		' . $tot, "\n\n";
 if($sab_flg){ 
		print $main::fh_file "\n(Where '{SAB}' refers to the Source's SAB)\n"}
 }	# end of tally()

#----------------------------------------------------------------------#
# TRUNC_ARRAY()
#----------------------------------------------------------------------#
sub trunc_array{
# uses the format string to determine the proper size of each element
# of the tallyfield array and truncates each field to the proper size
# 
  # it's that non-std use of $[ that screws things up
  $[ = 0;
  my($fmt,$x,@f);
  $fmt = shift;
  $fmt =~  s/s|%|-//g;     
  (@f) = split(/ /,$fmt); 
  for ($i=0;$i<$#f;$i++){
    $y = ($f[$i])-1;
    $z = substr($pf[$i],0,$y);
    $pf[$i]=$z;
    
    # length should be 1 less than the format to allow for spacing
    #if(length($pf[$i]) > (($f[$i])+1)){
    #	$pf[$i] = substr($pf[$i],0,$i-1);
    #}
   }
  $[ = 1;	# reset array index var.
 }

#----------------------------------------------------------------------#
# TALLYTHIS() 
#----------------------------------------------------------------------#
# called by tally()
# takes a string that is the fields to send to tallyfile
# e.g., "\$2\$4\$6\$7\$8\$9\$11"
#
# returns the string to send to tallyfile
# string looks like this:
# $fields[3] . "|" . $fields[4] . "|" . $fields[6] . "|" . $fields[7] . "|" . $fields[8] . "|" . $fields[9] . "|" . $fields[10] . "|" . $fields[11]
#
sub tallythis{
  my $arg = $_[0];
  my ($c, $v, $p, $savep,$file);
  $file = shift;
  for ($i=1; $i<=length($arg); $i++) {	#
    $c = substr($arg, $i, 1);
    if ($c eq '(') {
      $p++;
     } elsif ($c eq ')') {
       $p--;
       if ($p==0) {
	 $tallythis .= ') . "|" . ';
	 next;
	}
      }
    if ($v==1) {
      if ($c lt '0' || $c gt '9') {
	$v=0;
	$tallythis .= ' . "|" . ' if $p==$savep;
       }
     }
    
    if ($c eq '$') {
$v=1;
$savep=$p;
	}
	$tallythis .= $c;
		}

		$tallythis =~ s/ \. "\|" \. $//;
		$tallythis =~ s/\$([1-9][0-9]*)/\$fields[$1]/g;
		$tallythis =~ s/\$0/\$_/g;
		$tallythis =~ s/ \. "\|" \. ([,)])/$1/g;
		$tallythis =~ s/substr\(([^,)]*),([^,)]*)\)/substr($1,$2,999999)/g;

#print "TallyThis: $tallythis\n";
return $tallythis;
}	# end of tallythis()


#----------------------------------------------------------------------#
# TALLYFILE() 
#----------------------------------------------------------------------#
# called by tally()
sub tallyfile{
  my($file) = shift;
  open(INFILE, "<$main::dir/$file") || die "Can't open $file: $!";
  $prg = '
$[ = 1;
$| = 1;
while (<INFILE>) {
		chop;
		@fields = split(/[|\n]/o);
		$count{' . $tallythis . '}++;
}
';
  eval $prg;
  
  close (INFILE);
 }	# end of tallyfile()


#----------------------------------------------------------------------#
#	CHECKFIELDS() 
#----------------------------------------------------------------------#
sub checkfields{ 
# 02/227/2001
# derived from the awk script 'checkfields' with the help
# of a2p, the awk to perl translator
# with prettifying enhancements by WAK
  my ($file) = @_;
  my (%count, $x, $tot, $i, $len, $j, %l, %u, %n, @Fld);
  my ($saved_base, $saved_OFS, $saved_ORS);

  print $main::fh_file "\n----- Checkfields - $file -----\n";
  print $main::fh_file "Fields      Lines\n";
  print $main::fh_file "------      ------\n";
  
  open(INFILE, "<$main::dir/$file") || die "can't open $main::dir/$file";
  while (<INFILE>) {
    $count{1+tr/|/|/}++; # hash key is the no. of fields, value is the count
   }
  close(INFILE);
  
  foreach $x (sort keys(%count)) {
    printf $main::fh_file "%6d %8s\n", $x, $count{$x};
    $tot += $count{$x};
   }
  print $main::fh_file "=================\n";
  printf $main::fh_file "%-6s %10s\n\n","TOTAL", $tot;
  
  print $main::fh_file "Field       Length Range        nonzero\n";
  print $main::fh_file "-----       ------------        -------\n";
  
  $[ = 1;                       # set array base to 1
  open(INFILE, "$main::dir/$file") || die "can't open $file";
  
  $saved_base = $[;
  $[ = 1;			# set array base to 1
  $saved_OFS = $,;
  $, = ' ';		# set output field separator
  $saved_ORS = $\;
  $\ = "\n";		# set output record separator
  
  while (<INFILE>) {
    chomp;	# strip record separator
    @Fld = split(/\|/, $_, 9999);
    if (($. == 1)) {
      $j = $#Fld;
     	 for ($i = 1; $i <= $j; $i++) {
			$l{$i} = $u{$i} = length($Fld[$i]); 
	 	}
     }
    if (($j < $#Fld)) { $j = $#Fld; }
    for ($i = 1; $i <= $j; $i++) {
      $len = length($Fld[$i]);
      if ($len < $l{$i}) { $l{$i} = $len; }
      if ($len > $u{$i}) { $u{$i} = $len; }
      if ($len > 0) { $n{$i}++; }
     }
    
    #print $_ if $Fld[1];
   }
  
  for ($i = 1; $i <= $j; $i++) {
    #print $i . '	' . $l{$i} . ' - ' . $u{$i} . '		' . $n{$i};
    printf $main::fh_file "%5d %s%5d %s %6d %14d\n", $i, '  ', $l{$i},' -',$u{$i}, $n{$i};
   }

  $[ = 0;		# set array base back to what it was 
  $, = $saved_OFS;		# set output field separator back to what it was 
  $\ = $saved_ORS;		# set output record separator back to what it was 
  
 }     # end of checkfields()



# Tabulates all characters in a file. 
# Usage: chars.pl input > output

#----------------------------------------------------------------------#
#	QUICK_CHAR_COUNTS() 
#----------------------------------------------------------------------#
sub quick_char_count{ # counts all non-alphanumeric characters, prints out list 
  use integer;
  my ($file) = @_;
  my (%hash);
  my $err_cnt = 0;
  print $main::fh_file "\n----- Quick Character Count - $file -----\n";
  open (INFILE, "<$main::dir/$file");
  
  while (<INFILE>) {
    @_ = split //;	#splits characters 
    for (@_) {
       s/\s/\\s/;	#skips spaces and tabs
      s/\t/\\t/;
      ++$hash{$_} unless /\w/}	#skips "word" characters
   }	# end of while(<INFILE>)
  
  for (sort keys %hash){print $main::fh_file "$_\t$hash{$_}\n" if $hash{$_} }
  
  print $main::fh_file "\n----- Character Checks - $file -----\n";
  if ($hash{"("} ne $hash{")"}){ #Alerts if mismatches
    print $main::fh_file "Mismatched parens: ( = ", $hash{"("}, "	) = ", $hash{")"}, "\n"; 
    $err = abs($hash{"("}-$hash{")"});
    printf $main::fh_summ "%6d %s\n", $err, " Mismatched Parentheses";
    print "\tMismatched Parentheses\n";
    $err_cnt = $err;
   }
  if ($hash{"["} ne $hash{"]"}){
    print $main::fh_file "Mismatched brackets: [ = ", $hash{"["}, "	] = ", $hash{"]"}, "\n";
    $err = abs($hash{"["}-$hash{"]"});
    printf $main::fh_summ "%6d %s\n", $err, " Mismatched Square Brackets";
    $err_cnt += $err;
   }
  if ($hash{"{"} ne $hash{"}"}){
    print $main::fh_file "Mismatched braces: { = ", $hash{"{"}, "	} = ", $hash{"}"}, "\n";
    $err = abs($hash{"{"}-$hash{"}"});
    #printf $main::fh_summ "%16d %-32s\n", $err, "Mismatched Curly Braces";
    printf $main::fh_summ "%6d %s\n", $err, " Mismatched Curly Braces";
    $err_cnt += $err;		
   }	
  #printf $main::fh_summ "%6d %s\n", $err_cnt, "Total Bad Character";
  
  close INFILE;
 }		# end of quick_char_count()


####sub checkspell{	#Not currently used
####  # hash is global not local fix before using
####  my ($in) = @_;							# pick up input file name
####  print $main::fh_file "Checked Spelling in $in\n";
####  open (IN, $in);
####  open (MRCON, "/lti8f/M97MR/MRCON");
####  use integer;								# more efficient
####  
####  while (<IN>) {chomp; $_ = lc $_; $hash{$_} = 1}	# create lower case hash key
####  
####  while (<MRCON>)
####   {
####    ($cui, $lang, $p, $lui, $pf, $sui, $string) = split /\|/;
####    next unless $lang eq 'ENG';							# limit check to English
####    $_ = lc $string;													# lower case
####    @array = split;															# split on white space
####    for $i (@array) {$hash{$i} = 2 if $hash{$i}}	# mark hits w/ a "2"
####   }
####  
####  for (keys %hash) {print "$_\n" if $hash{$_} == 1}	# i.e., print only those terms
####  # that did not appear at all
####  # in Meta, else thay would
####  # have a "2"
####  if($err){
####    printf $main::fh_summ "%d %s\n", $styerr, "Bad Spellings";
####    printf "%d %s\n", $styerr, "Bad Spellings";
####   }
#### }		# end of checkspell()



#----------------------------------------------------------------------#
# VALID_STYS() 
#----------------------------------------------------------------------#
sub valid_stys {
# takes a global hash of stys from the attributes file
# file name is passed as parameter
# print bad stys to error file
# returns a count of invalid stys

  my(@F,$a,$b,$c,$errnum,$linecnt,$sty,$styerr,%styerr,%styhash,$x);
  # make hash of valid stys
  # looks like:
  # Acquired Abnormality
  # Activity
  # Age Group
  open(STY, "$valid_stys") or die "Can't open STY file: \"$valid_stys\", $!";
 LINE:
  while(<STY>){
    if(/^#/){ next; }	# ignore comments
    if(/^\s*$/){ next; }	# ignore blank lines
       chomp;
		 @F=split(/\|/);
       $val_sty{$F[0]}++;		
      } 
    close (STY);
    
    foreach $sty (keys(%stys)){
      unless($val_sty{$sty})	{
	$styerr{$sty}= $stys{$sty};
	$styerr++;
	#print "$styerr: $_\n";
       }
     }		# end of foreach STY
    if($styerr){
      push(@bad_sty, sprintf "%6s %s","Count", "Semantic Type");
      push(@bad_sty, sprintf "------ -------------");

      foreach $x (sort(keys(%styerr))){
	push(@bad_sty,sprintf "%6d %-36s", ($styerr{$x}), $x);
       }
      push(@bad_sty,"\n");
      
     }		# end of if($styerr)
    return($styerr);
    
   }		# end of valid_stys()
  
#----------------------------------------------------------------------#
# CK_FIELD_LENS() 
#----------------------------------------------------------------------#
# takes a file to check
# returns a count of errors
# writes to @bad_len, declared local in QA4.pm
# updated for MEME3
sub ck_field_lens{
    my($err,$err_flg,$file,@f,$linecnt, $x, @err,%err);
    my($str,$fno);
    $file = $_[0];
    $ucfile = uc($file);
    $linecnt = 0;
    $err = 0;
    # set the field lengths here for each file
    if($file =~ /class/){
      @len = (12,20,40,30,1,1,1,1200,10);
     }
    elsif($file =~ /relat/){
      @len = (12,1,50,10,100,50,26,20,1,1,1,10,20,50,20,50);
     }
    elsif($file =~ /attr/){
		# no limit on length for field 4
		# 1:12,2:50,3:1,4:30,5:none
		# 6:20,7:1,8:1,9:1,10:1
		# 11:23,12:50,13:20,14:32
      @len = (12,50,1,30,0,20,1,1,1,1,23,50,20,32);
     }
    elsif($file =~ /merge/){
      @len = (50,5,50,20,1500,1,1,30,20,50,20,50);
     }
    elsif($file =~ /string/){
      @len = (10,1000,10,1000,10,20);
     }
    elsif($file =~ /termgroup/){	# updated 11/12/2001
      #@len = (20,20,1,1,1,20);
      @len = (40,40,1,1,1,20);
     }
	 elsif($file =~ /retired/){	# updated 02/02/2004
	 	@len = (50,20,50,50,50);
	}
    elsif($file =~ /source/){		# updated 11/12/2001
      @len = (26,20,12,20,20,20,20,1200,100,1000,1000,1000,100,100,1000,10);
     }

    else{	
      print "Sorry, I can't check field lengths for $file\n";
      return;
     }
    #print	"\tField Lengths\n";
    # print "\tChecking $file for field lens\n";
    
    open(IN, "$main::$dir/$file") or die "Can't open $file, $!";
    # print "First element: $[\n";
    ## Changing the array index is a really bad idea
    ## makes for REALLY nasty bugs
    $[ = 0; 

    push(@bad_len, "Line #  Field #  Field size  Limit  Field contents");
    push(@bad_len, "------  -------  ----------  -----  --------------");

      while(<IN>){
	$linecnt++;
	#print;
	chomp;
	@f = split(/\|/);
       FIELD:
      # go through each field of the record
      for ($i=0;$i<(scalar(@len));$i++){
	if($len[$i]==0){	# 0 means 'Unlimited' size, don't check
	  next FIELD;
	 }
	if(length($f[$i]) > $len[$i]){
	  #printf "%d-%s: %d >	%d \n", $i,$f[$i],length($f[$i]), $len[$i];
	  if($err<$main::limit){
	    $flen = length($f[$i]);
	    $fno = $i+1;
	    
	    #$str = "$fno\t$flen\t$len[$i]\n$f[$i]\n";
	    $str=sprintf("%6d %7d %11d %7d  %s",$.,$fno,$flen,$len[$i],$f[$i]);
	    push(@bad_len, $str);
	    $err++;
	   }   # end of if($err<$main::limit)

	  # stops after limit is reached
	  else{$err++;last}
	 }	  #end of if(length($f[$i])
       }		# end of for loop
     }		# end of while (<IN>)
    close IN;
    $[ = 1;	# changing back to the way the rest of the code works
    return($err);
   } # end of ck_field_len()

#----------------------------------------------------------------------#
# MAKE_SAID_HASH()
#----------------------------------------------------------------------#
# makes a hash of all SAIDs in the classes file
# Returns TRUE if sucessful, FALSE if unsucessful

sub make_said_hash{
  my $x;
  open(CLASS, "$main::dir/classes_atoms.src") or return 0;
  while(<CLASS>){
    ($x) = split(/\|/);
    $main::said_class{$x}++;
   }
  close CLASS;
  return 1;
 }


#----------------------------------------------------------------------#
# COLLECT_SABS() 
#----------------------------------------------------------------------#
# reads $termids_file
# creates hashes %nsab and %ssab, norm and stripped sabs resp.
# called by check_source() to check validity of norm and stripped sources 
# in sources.src
# a NORM source - MSH2002
# a STRIPPED source - MSH
sub collect_sabs{
	$[ = 0;
	# set in QA4.pl
	print "Using Term IDs file: '$termids_file'\n";
	open (TID, "$termids_file") or die "In 'collect_sabs(), Can't open $termids_file, $!";
	while(<TID>){
		chomp;
		next if(/^#|^\*|^x/);	# ignore commented lines
		next unless(/\w/);  # ignore blank lines
		@F=split(/\|/,$_);
		# 12/4/01 WAK
		# changed termids so that all SABs in field 4 fit the form:
		# SAB{termgroup1, termgroup2, etc.}
		#$F[3]=~/(^[A-Z0-9]*)/;
		#$F[3]=~/(\w*)\{/;
		#$str = $1;

		# 2006/08/08 - WAK
		# changed to allow records in the termid files that carry
		# multiple VSABs, e.g., ICD9CM_2007/MTHICD9CM_2007
		$ind = index($F[3],'{',0);
		$str = substr($F[3],0,$ind);
		next unless(length($str) > 2);
		@sab = split(/\//, $str);
		foreach $sab (@sab){
			if($sab =~ /[0-9]/){		# norm source, e.g. MSH2002
				#print "Norm: $str\n";
				$nsab{$sab}++;
				$sab =~ /([A-Z]*)/;	# get the stripped source
				#print "Stripped: $1\n";
				$ssab{$1}++;
			}
			else{							# already a stripped source, e.g. MTH	
				$ssab{$str}++;
				#print "Stripped: $str\n";
			}
		}
	}
}


#----------------------------------------------------------------------#
# PRINT_ERROR() 
#----------------------------------------------------------------------#
sub print_error{
	my($i,$saved_base);
	my($test,$cnt,@arr) = @_;
	$saved_base = $[;
	$[ = 0;
	print $main::fh_err "---- $test: $cnt ----\n";
	for ($i=0;$i<scalar(@arr);$i++){
	print $main::fh_err "$arr[$i]\n";
	}
	if($cnt>$limit){print $main::fh_err "---- Truncated at $limit ----\n"}
	print $main::fh_err "\n";
 }

#----------------------------------------------------------------------#
# MAKE_TID_AoA()  
#----------------------------------------------------------------------#
sub make_tid_AoA{
	my($i)=0;
	my($stat,$low,$high,$str,$src);
	my($j);
	my $prev_high = 0;
	
	# set in QA4.pl
	open (TID, "$termids_file") or die "Can't open $termids_file, $!";
	while(<TID>){
	chomp;
	if(/^#|^\*|^x/){
		next;
		}
	next unless(/\w/);
	($stat,$low,$high,$str)=split(/\|/);
	$low =~ s/^ *//;
	$high =~ s/^ *//;
	($src) = split(/-/,$str);
	# print "$low - $high | $src\n";
	$tid[$i] = [$low,$high,$src];
	if($low < $prev_high){
		print $main::fh_file "ERROR: Overlapping ranges\n";
		print $main::fh_file "\t$src: Low $low  Prev. High $prev_high\n\n";
	 }
	$prev_high = $high;
	$i++;
	}
close TID;
} # end of make_tid_AoA()


#----------------------------------------------------------------------#
# LOOKUP_SAID() 
#----------------------------------------------------------------------#
sub lookup_said{
	my (@a,$j,$src,$last);
	my ($said) = shift;
	
# each time a number is looked up it gets stuffed into a global hash
# key - src; value - said
	
# starting with the last of the arrays
# check to see if it's bigger than the low value
# stop if it is, keep going if it isn't
#
# for tid
#	0 - lo, 1 - hi, 2 - src name 
	
# if out of range
	
	if($said > $tid[$#tid][1]){ 
	push(@{$said_err{'Not Found'}}, $said); 
	return;
	}
	
	for ($j=$#tid;$j>0;$j--){
	@a = @{$tid[$j]};
	if($said < $a[0]){	  
		next;
	 }
	
	$src = $a[-1];
	push @{$said_err{$src}}, $said;  # save each SAID in the array
	return;
	}
 }
	
# saids not found go into a global hash in lookup_said()
# the hash is a hash of arrays
# uses global hash created by lookup_said()
# creates the array of errors to print, the count of the no. of errors
#--------------------------------------------------------------------#
# MAKE_SAID_ERROR_ARRAY()
#--------------------------------------------------------------------#
sub make_said_error_array{
# foreach sorted src, find the low, the high and the count
# format a string and push it onto the array.
# returns count of errors

	my($x,$y,$lo,$hi,$cnt,$src);
	$id_ntfnd = 0;	# reset for each use of said checking
	#@id_ntfnd = ();
	if(keys(%said_err)){
	$str="Source of SAID                      Range                      Count";
	push(@id_ntfnd, $str);
	$str="----------------------------------  -----------------------    -----";
	push(@id_ntfnd, $str);
	}
	foreach $x (sort(keys(%said_err))){
	my @said = sort @{$said_err{$x}};
	$cnt = @said;
	$lo = $said[0];
	$hi = $said[-1];
	$src = substr($x,0,34);
	$str = sprintf("%-35s %9d %s %9d %s %4d", $src,$lo," - ",$hi,"	",$cnt);
	push(@id_ntfnd, $str);
	$id_ntfnd += $cnt;
	}
	return $id_ntfnd;
 }

#--------------------------------------------------------------------#
# GET_TERMIDS()
#--------------------------------------------------------------------#
sub get_termids{
	my($sab,$str,$stat,$lo,$hi);

	# set in QA4.pl
	print FILE "\n";
	open (TID, "$termids_file") or return "Can't open termid file";
	while(<TID>){
		chomp;
		next if(/^#|^\*|^x/);	# ignore commented lines
		next unless(/\w/);  # ignore blank lines
		($stat,$lo,$hi,$str)=split(/\|/);
		if($str =~ /(.+?)\{/){
			$sab = $1;
			next if($sab =~ /\//);
			next if($sab =~ /\{/);
			$HoSAB{$sab}{"hi"}=$hi;
			$HoSAB{$sab}{"lo"}=$lo;
		}
	}
}

#--------------------------------------------------------------------#
# CHECK_TERMID_RANGE()
#--------------------------------------------------------------------#
# uses the hash %HoSAB created in &get_termids()
# takes an SAB, the lowest value SAID, the highest value SAID
# returns 1 if error, 0 otherwise
# writes results to the output file
#
sub check_termid_range{
	my $sab = shift;
	my $src_lo = shift;
	my $src_hi = shift;
	my $err;
	if($HoSAB{$sab}){	# if the SAB is found in the hash
		if($src_lo < $HoSAB{$sab}{lo}){
			$err++;
			print FILE "ERROR: SAIDs ($src_lo)in $sab start before valid range $low\n";
			push(@bad_range,"SAIDs in $sab start before valid range $low");
		}
		if($src_hi > $HoSAB{$sab}{hi}){
			$err++;
			print FILE "ERROR: SAIDs ($src_hi) in $sab end after valid range $high\n";
			push(@bad_range,"SAIDs in $sab end after valid range $high");
		}
	}
	else {	# SAB not found in hash
		print FILE "ERROR: The SAB '$sab' was not found in '$termids_file'\n";
		print $main::fh_err "\nThe SAB '$sab' was not found in '$termids_file'\n";
	}
	if($err){return $err}
	return;
}

# Checks the low and high values for SAIDs found in classes against
# the assigned termids for this SAB in /u/umls/termids
# called from QA4.pm:check_classes
# takes an SAB, lowest value SAID, highest value SAID
# returns 1 if error, 0 otherwise
#
#--------------------------------------------------------------------#
# CHECK_TERMIDS()
#--------------------------------------------------------------------#
sub check_termids{
	my $sab = shift;
	my $src_lo = shift;
	my $src_hi = shift;
	my $err;

	# set in QA4.pl
	print FILE "\n";
	open (TID, "$termids_file") or die "Can't open $termids_file, $!";
	while(<TID>){
		chomp;
		next if(/^#|^\*|^x/);	# ignore commented lines
		next unless(/\w/);  # ignore blank lines
		($stat,$low,$high,$str)=split(/\|/);
		next unless($str =~ $sab);
		$found++;
		if($src_lo < $low){ 
			$err++;
			print FILE "ERROR: SAIDs ($src_lo)in $sab start before valid range $low\n";
			print $main::fh_err "ERROR: SAIDs ($src_lo)in $sab start before valid range $low\n";
			push(@bad_range,"SAIDs in $sab start before valid range $low");
		}
		if($src_hi > $high){ 
			$err++;
			print FILE "ERROR: SAIDs ($src_hi) in $sab end after valid range $high\n";
			print $main::fh_err "ERROR: SAIDs ($src_lo)in $sab end before valid range $low\n";
			push(@bad_range,"SAIDs in $sab end after valid range $high");
		}
	}
	if($found&&!$err){
		print FILE "SAIDs in $sab are within the range assigned in $termids_file\n\n";
	}
	if(!$found){
		print FILE "$sab Not Found in $termids_file, No SAID Range Checking\n";
		print "\n\t$sab Not Found in $termids_file, No SAID Range Checking\n\n";	
		push(@bad_range, "$sab not found in $termids_file");
	}
	return($err);
}

# takes an "id" and and "id_type"
sub check_id {
	my($id) = shift;
	my($type) = shift;
	
	# AUI: in NCI-MEME, 'A' followed by 7 digits
	#      in NLM, 'A' followed by 7 or 8 digits, (new AUIs are now 8)
	# if the id for the type matches the pattern return 1, else 0
   SWITCH: {
      if($type eq 'AUI'){return(($id =~ /^A\d{7,8}$/)?1:0);last SWITCH;}
      if($type eq 'SRC_ATOM_ID'){return($id =~ /^\d{7,9}$/)?1:0; last SWITCH;}
      if($type eq 'ATOM_ID'){return(($id =~ /^\d{4,}$/)?1:0);last SWITCH;}
      if($type eq 'CONCEPT_ID'){return(($id =~ /^\d{4,}$/)?1:0);last SWITCH;}
      if($type eq 'CUI'){return(($id =~ /^C\d{7,}$/)?1:0);last SWITCH;}
      if($type eq 'CUI_STRIPPED_SOURCE'){return(($id =~ /^C\d{7,}$/)?1:0);last SWITCH;}
      if($type eq 'CUI_SOURCE'){return(($id =~ /^C\d{7,}$/)?1:0);last SWITCH;}
      if($type eq 'CODE_SOURCE'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'CODE_STRIPPED_SOURCE'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'CODE_TERMGROUP'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'CODE_ROOT_TERMGROUP'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'CODE_STRIPPED_TERMGROUP'){return(($id =~ /.{3,}/)?1:0);last SWITCH;}
      if($type eq 'SOURCE_AUI'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'SOURCE_CUI'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'SOURCE_DUI'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'SOURCE_RUI'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'ROOT_SOURCE_AUI'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'ROOT_SOURCE_DUI'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'ROOT_SOURCE_CUI'){return(($id =~ /.+/)?1:0);last SWITCH;}
      if($type eq 'SRC_REL_ID'){return(($id =~ /\d+/)?1:0);last SWITCH;}
   }


}	# end of check_id()




1;









