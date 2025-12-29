# QA4.pm
# --	%W%	%G%

#package QA3;
## formerly QA1_scan.pm
# this perl module contains the basic sub routines for checking
# specific .src files
# called from QA3.pl
# calls various utility subroutines in QA3_util.pm
# called from QA3.pl
#use QA3_util;

# to check MD5 hashes
use Digest::MD5 qw(md5_hex);
use Encode qw(encode_utf8);
 
use integer;
#use strict 'vars';
# imports from QA3.pl:
#local $limit = $main::limit;
# my $file = $main::file;
#local *fh_file = $main::FILE;
#local *fh_summ = *main::SUMM;
#local *fh_err = *main::ERROR;

#use subs qw(&ck_field_lens);

##########################################################################
# CHECK_CLASS()
# classes_atoms.src specific tests
##########################################################################

sub check_class{
 my($file)=@_;
 my ($err,@cf,$term,%term,%lcterm);
 my($bad_len,$bad_code,$non_ascii,$bad_space,$bad_said,$bad_value);
 my($bad_fcnt,$odd_term,$bad_term,$bad_lcterm,$bad_bracketnum);
 my($pot_charent, $valid_charent, $y, $z);
 my(@bad_code,@non_ascii,@bad_space,@bad_said,@bad_value);
 my(@bad_Ucode,$bad_Ucode);
 my(@bad_fcnt,@odd_term,@bad_term,@bad_lcterm,@bad_bracketnum);
 my($err_str,$no_term,@no_term);
 my($term_size, %term_size);
 my(@pot_charent, @valid_charent);
 my(@SRC,@bad_src,$bad_src);
 my(%HoSRC_SAB, $SAID_HI, $SAID_LO,$said);
 my($src_vpt) = 0; my($src_vab) = 0;
 my(%lang, $lang, @bad_lang, $bad_lang);
 my(%ord_id,@bad_ord_id,$bad_ord_id);
 my(%dup_ord_id,@dup_ord_id,$dup_ord_id, $ord_id_key);
 @bad_range=();
 my($bad_F1,@bad_F1);
 my($bad_F2,@bad_F2);
 my($bad_F3,@bad_F3);
 my($bad_F4,@bad_F4);
 my($bad_F5,@bad_F5);
 my($bad_F6,@bad_F6);
 my($bad_F7,@bad_F7);
 my($bad_F8,@bad_F8);
 my($bad_F9,@bad_F9);
 my($bad_F13,@bad_F13);
 my($tty, $bad_tty_sup, @bad_tty_sup, $tty_err_result, $tty_err_result_str);
 my(%dup_aui,@dup_aui,$dup_aui);
 my($auifld, @ibad_auifld_dup,$bad_auifld_dup);

 # used for field reports:
 my($i,$len);
 local(%fcnts,%lo,%hi,$rec);
  
	# if checking of treepos.dat AND source_atoms.dat are both
	# supressed, we don't need to save the SAID hash
	if($main::option{t}){ 
		my(%said);
	}
	else{ %said = ();		# %said needs to be global
	}
		
  @bad_len=();
  %said_err = ();
  my($ucfile)= uc($file);
	# 12 9s exceeds some internal limit, 9 should be within the 4 byte limit
	$SAID_low = 999999999;
	$SAID_high = 0;

  # preload error hashes with descriptions
  push(@pot_charent, "These may be broken Character Entities -- WARNING");
  push(@valid_charent, "Valid HTML/XML Character Entities -- ERROR");
  # load character_entities file into hash '%charent'
  # a hash of valid HTML character entities
  &load_char_ent_hash();

  $bad_len = &ck_field_lens($file);

  open (INFILE, "$main::dir/$file") or die "Can't open $file, $!";
  binmode(INFILE, ":utf8");
  print $main::fh_file "";
  
  # if exists, reads MRDOC.RRF and populates %obsolete_tty
  # key = obsolete tty - value = 1
  # returns error message if file not found

  $tty_err_result_str = &get_tty_info();
  if($tty_err_result_str){$tty_err_result++}

  # print "Checking $file\n";
  print "\tField Lengths\n";
  print "\tASCII chars out of range\n";
  print "\tExtra Spaces in Term\n";
  print "\tUnique SAIDs\n";
  print "\tBasic Field values\n";
  print "\tCorrect number of Fields\n";
  print "\tUnexpected chars in terms\n";
  print "\tDuplicate Terms\n";
  print "\tCase Insensitive Duplicate Terms\n";
  print "\tOccurrences of <number> in terms\n";
  
  while(<INFILE>){
	chomp;
	@cf = split(/\|/);
	$cf[2]=~ /(\w{3,})\/(\w{2,})/;
	$tty = $2;
	
	# check for SRC atoms
	# should be:
	# 1 ea. SRC|SRC/VPT|V-SAB, SRC|SRC/VAB|V-SAB
	# SRC|SRC/VSY is optional, nothing else permitted

	# save termgroups for later use checking in termgroups.src
	unless($cf[2] =~ /SRC/){
		$class_termgrp{$cf[2]}++;
		$class_src{$cf[1]}++;
	}

	# this collects info on the length of the field and 
	# whether the field has a value
	# (does much the same as 'checkfields'
	for($i=0;$i<15;$i++){
		$len = length($cf[$i]);
		unless($rec){$lo{$i} = $len;$hi{$i}=$len }
		
		if($len == 0){} 
	
		$lo{$i} = $len unless($len > $lo{$i});
		$hi{$i} = $len unless($hi{$i} > $len);

		$fcnts{$i}++ if(length($cf[$i]));
	}
	$rec++; 

	# check for 'U' codes which should probably be 'MTHU' codes
	#
	if($cf[3] =~ /^U/){
		unless($bad_Ucode > $limit){push(@bad_Ucode, $_)}
		$bad_Ucode++;
	}

	# check that a code exists
	if($cf[3] =~ /^\s*$/){
		unless($bad_code > $limit){push(@bad_code, $_)}
		$bad_code++;
	}

	# OK
	# check for ASCII chars out of range
	if ($cf[7]=~/[^\040-\176\n\t]/o){	# valid chars (compile once)
		unless($non_ascii > $limit){ push(@non_ascii, $_) }
		++$non_ascii;
	 }
		
	# check for Zero-length terms
	if(length($cf[7])==0){
		unless($no_term> $limit){push(@no_term, $_)}
		++$no_term;
	}


	# create a hash of short terms
	if(length($cf[7])<3){
		$term_size{(length($cf[7]))}++;
	}


	# OK
	# check for Excess White Space
	if(($cf[7]=~/\s{2,}/o)||($cf[7]=~/^\s/o)||($cf[7]=~/\s$/o)){
		unless($bad_space > $limit){ 
	push(@bad_space, $_); 
		}
		++$bad_space;
	 }
	
 	# get SAID range	
	#	if($cf[0] < $SAID_low){$SAID_low = $cf[0]}
	#	if($cf[0] > $SAID_high){$SAID_high = $cf[0]}
		
	# get the SAIDs for later checking
	unless($cf[1] eq "SRC"){
		$HoSRC_SAB{$cf[1]}{$cf[0]}++;
	}
	# OK
	# check for Unique SAIDs
	# hash '%said_class' is already loaded with all of the
	# SAIDs, sub routing 'make_said_hash' is run from within
	# QA3.pl
	# saved to global hash for later checking of other files
	if($said{$cf[0]}){
		unless($bad_said > $limit){ push(@bad_said,$_)}
		$bad_said++;
	 }
	else{ $said{$cf[0]}++}
	
	# OK
	# check for Basic field values
	# F | Constraints
	# 1	min. 8 digits
	# 2	> 1 word char
	# 3	> 1 word char '/' > 1 word char
	# 4	> 1 char
	# 5	RUN
	# 6	YNn
	# 7	AUN
	# 9	NY
	
	#unless (/^\d{8,}\|[A-Z_0-9\-]{3,20}\||[A-Z_0-9\-]{3,20}\/\w+?\|.+?\|[RUN]\|[YNn]\|[AUN]\|.*\|[NY]\|$/o) {
## 		unless($bad_value > $limit){ push(@bad_value,$_); }
## 		++$bad_value;
## 	 }

	# Test for Field 1 - src_atom_id
 	unless($cf[0] =~ /^\d{8,}/o){
 		unless($bad_F1 > $limit){ push(@bad_F1,$_)}
 		++$bad_F1;
	}

# no good way to test source names
	# Test for Field 2 - source
#	unless($cf[1]=~ /[A-Z_0-9\-]/){
	unless($cf[1]=~ /^\D{3,}/){
		unless($bad_F2 > $limit){ push(@bad_F2,$_)}
		++$bad_F2;
	}
	
	# Test for Field 3 - termgroup
	unless($cf[2]=~ /\w{3,}\/\w{2,}/){
		unless($bad_F3 > $limit){ push(@bad_F3,$_)}
		++$bad_F3;
	}

	# Test for Field 4 - code
	unless($cf[3]=~ /\w{1,}/){
		unless($bad_F4 > $limit){ push(@bad_F4,$_)}
		++$bad_F4;
	}

	# Test for Field 5 - status
	unless($cf[4]=~ /[RUN]/){
		unless($bad_F5 > $limit){ push(@bad_F5,$_)}
		++$bad_F5;
	}

	# Test for Field 6 - to_be_released
	unless($cf[5]=~ /[YNn]/){
		unless($bad_F6 > $limit){ push(@bad_F6,$_)}
		++$bad_F6;
	}
	
	# Test for Field 7 - released
	unless($cf[6]=~ /[NAU]/){
		unless($bad_F7 > $limit){ push(@bad_F7,$_)}
		++$bad_F7;
	}

	# Test for Field 8 - atom_name
	unless($cf[7]=~ /\w{1,}/){
		unless($bad_F8 > $limit){ push(@bad_F8,$_)}
		++$bad_F8;
	}

	# Test for Field 9 - suppressible
	unless($cf[8]=~ /[OYEMN]/){
		unless($bad_F9 > $limit){ push(@bad_F9,$_)}
		++$bad_F9;
	}

	# Test Field 9 - Obsolete TTYs must be code 'O'
	if(($obsolete_tty{$tty}) && ($cf[8] ne 'O')){
		unless($bad_tty_sup > $limit){ push(@bad_tty_sup,$_)}
		++$bad_tty_sup;
	}

	# Field 10 - SAUIs should be unique
	if($cf[9] && $dup_aui{$cf[9]}){
		unless($dup_aui > $limit){push(@dup_aui,"$cf[9]:$_"); $dup_aui++}
	}
	else{if($cf[9]){$dup_aui{$cf[9]}++}}


	# Test for Field 13 - language
	unless($cf[12]=~ /[A-Z]{3}/){
		unless($bad_F13 > $limit){ push(@bad_F13,$_)}
		++$bad_F13;
	}

	# it's required that every non-SRC atom have an order_id
	# test for unique order ID. Every non-SRC atom should have
	# a unique order_ID/code combination.
	# i.e., warn if order id is duplicated across codes
	unless($cf[1] eq "SRC"){
		if(length($cf[13]) == 0){
			unless($bad_ord_id > $limit){ push(@bad_ord_id, $_)}
			$bad_ord_id++;
		}
		# if this order_id was found in a different code it's
		# a warning, not nec. an error
		# if the hash has a the code as key, the order_id should
		# be the same
		else{
			if($dup_ord_id{$cf[13]} && $dup_ord_id{$cf[13]} ne $cf[3]){
				unless($dup_ord_id > $limit){ push(@dup_ord_id, $_)}
				$dup_ord_id++;
			}
			$dup_ord_id{$cf[13]}=$cf[3];
		}
	}


	# OK
	# Field count should be 9 (or 14) w/ extra pipe at end
	unless(((tr/\|/\|/) == 9)||((tr/\|/\|/) == 14)){
		unless($bad_fcnt > $limit){ push(@bad_fcnt, $_)}
		++$bad_fcnt;
	 }
	
	# OK
	# Unexpected Characters in Terms
	#these chars not expected in terms:
	if($cf[7]=~/[\*\$\@\?\!\^]/o){
		unless($odd_term > $limit){ push(@odd_term,$_)}
		$odd_term++;
	 }
	
	# check for HTML/XML character entities in Terms
	# valid character entities are NOT wanted and considered errors
	# strings that look like character entities, possible char ents
	# are not necessarily errors
	while($cf[7]=~/(&\w{2,6};)/g){
		if($charent{$1}){
			$err_str = $..": ".$1;
			unless($valid_charent >$limit){ 
				push(@valid_charent,$err_str);
			}
			$valid_charent++;
		}
		else{
			$err_str = $..": ".$1;
			unless($pot_charent > $limit){ push(@pot_charent, $err_str)}
			$pot_charent++;
		}
	}


	# OK
	# Duplicate Terms
	if($term{$cf[7]}){
		$bad_term++;
		unless($bad_term > $limit){ 
			push(@bad_term,$_);
		}
	 }
	else{ $term{$cf[7]}++}
	
	
	# OK
	# check Case Insensitive Duplicate terms w/ spaces rem.
	$term = lc($cf[7]);
	$term =~ s/^ | $//g;
	$term =~ s/\s+/ /;
	if($lcterm{$term}){
		$bad_lcterm++;
		unless($bad_lcterm > $limit){ push(@bad_lcterm,$_)}
	 }
	else{ $lcterm{$term}++}
	
	# Check for duplicates amoung the AUI fields:
	# termgroup (3), string (8), code (4), source_aui (10), source_dui (12)
	# $bad_auifld_dup
	$auifld = join("@",$cf[4],$cf[9],$cf[5],$cf[11],$cf[13]);
	if($auifld_dup{$auifld}){
		unless($bad_auifld_dup > $limit){ push(@bad_auifld_dup, $_)}
		$bad_auifld_dup++;
	}
	
	if($cf[1] !~ /SRC/){$sab = $cf[1]};

	# Check for <{number}> at the end of a line
	if($cf[7] =~ /<\d{1,}>\s*$/){
		unless($bad_bracketnum > $limit){ push(@bad_bracketnum,$_)}
		$bad_bracketnum++;
	 }
	# Get all the Language values
	$lang{$cf[12]}++;

	}	# end of while()

  close INFILE;

# 	# this section displays counts of the fields
# 	{
# 	my($fnum,$name,%fnum2name,$lo,$hi,$x,$non_zero);
# 	open(CLASS, "$ENV{INV_HOME}/etc/class.fields") or die "$!";	
# 	while(<CLASS>){
# 		chomp;
# 		($fnum,$name)=split(/\|/);
# 		$fnum2name{$fnum}=$name;
# 	}
# 	close CLASS;
# 
# 	print FILE "\n"; 
# 	print FILE "Fld# Field Name                  length range # nonzero\n";
# 	print FILE "---- --------------------------- ------------ ---------\n";
# 	for($x=0;$x<15;$x++){
# 		$fnum = $x +1;
# 		$lo = $lo{$x};
# 		$hi = $hi{$x};
# 		$non_zero = $fcnts{$x}>0?$fcnts{$x}:0; 
# 		#print "$fnum : $lo - $hi : $fcnts{$x}\n";
# 		$name = $fnum2name{$fnum}; 
# 		printf FILE ("%4d %-26s  %3d - %3d %12d\n", $fnum,$name,$lo,$hi,$non_zero);
# 	}
# 	print FILE "\n";
# 
# 	} # end of field counts block
	&print_field_report("class",$rec);
	
	# check the languages in %lang
	print FILE "\nLanguage    Count\n";
	print FILE "-----------------\n";

	foreach $lang (keys(%lang)){
		printf FILE "%8s %8d\n", $lang,$lang{$lang};
		push(@bad_lang, "$lang - $lang{$lang}");
	}
	if(scalar(%lang)>1){ 
		$bad_lang++;
	}

	# in QA3_util.pm
	if($retval = &get_termids()){
		die "$retval in call to get_termids()\n";
	}

	# $said_range_err = &check_termids($sab,$SAID_low,$SAID_high);
	foreach $SAB (keys(%HoSRC_SAB)){
		for $said (keys %{$HoSRC_SAB{$SAB}}){
			push(@A,$said);
		}
		@Asort = sort{$a<=>$b} @A;
		$SAID_LO = $Asort[0];
		$SAID_HI = $Asort[$#Asort];
		
		$said_range_err = &check_termid_range($SAB, $SAID_LO, $SAID_HI);
		print "\n$SAB:\n";
		print "    Lowest SAID:  $SAID_LO\n";
		print "   Highest SAID:  $SAID_HI\n";
	  
		print FILE "\n$SAB:\n";
		print FILE "    Lowest SAID:  $SAID_LO\n";
		print FILE "   Highest SAID:  $SAID_HI\n";
		@A = ();
	}
  
	# print out the count of the small terms
	print FILE "\n";
	if(($term_size{0}+$term_size{1}+$term_size{2})==0){
		print FILE "\nThere are no Terms less than 3 characters in Length.\n";
	}
	else {
		print FILE "Count of Terms less than 3 characters\n";
		print FILE "Length   Count\n";
		print FILE "------   ----\n";
		foreach $x (sort(keys(%term_size))){
			printf FILE "%5d %5d\n", $x, $term_size{$x};
		}
	}
	print FILE "\n";


  # print results
	printf $main::fh_summ "%6d %s\n", $said_range_err, " SAID range errors";  
	printf $main::fh_summ "%6d %s\n", $bad_len, " Bad Field Lengths";  
	printf $main::fh_summ "%6d %s\n", $non_ascii, " Non-ASCII characters in Term Field";
	printf $main::fh_summ "%6d %s\n", $bad_Ucode, " Codes beginning with 'U'";
	printf $main::fh_summ "%6d %s\n", $bad_code, " Codes missing";
	printf $main::fh_summ "%6d %s\n", $bad_space, " Extra spaces in Term Field";
	printf $main::fh_summ "%6d %s\n", $bad_value, " Bad values in fields";
	printf $main::fh_summ "%6d %s\n", $bad_fcnt, " Incorrect no. of fields";	
	printf $main::fh_summ "%6d %s\n", $odd_term, " Odd punctuation characters in Term Field";	
	printf $main::fh_summ "%6d %s\n", $bad_said, " Duplicate SAIDs";	
	printf $main::fh_summ "%6d %s\n", $bad_term, " Duplicate Terms";	
	printf $main::fh_summ "%6d %s\n", $bad_lcterm, " Duplicate Terms (Case Insensitive)";	
	printf $main::fh_summ "%6d %s\n", $dup_aui, " Duplicate SAUIs";	
	printf $main::fh_summ "%6d %s\n", $bad_bracketnum, " Numbers in Angle Brackets";	
	printf $main::fh_summ "%6d %s\n", $valid_charent, " HTML/XML character entities";	
	printf $main::fh_summ "%6d %s\n", $pot_charent, " Potential HTML/XML character entities";	
	printf $main::fh_summ "%6d %s\n", $no_term, " Zero-length Terms";	
	printf $main::fh_summ "%6d %s\n", $bad_lang, " Multiple Languages";	
	printf $main::fh_summ "%6d %s\n", $bad_tty_sup, " Bad Supp for Obsolete Term";	
	printf $main::fh_summ "%6d %s\n", $bad_auifld_dup, " Duplicate Termgroup/Term/SAUI/SCUI/SDUI";	
	printf $main::fh_summ "%6d %s\n", $bad_ord_id, " Missing Order_ID, Field 14";	
	printf $main::fh_summ "%6d %s\n", $dup_ord_id, " Duplicate Order_ID, Field 14";	
	#printf $main::fh_summ "%6d %s\n", $bad_src, " SRC Atom errors";	

  
  $err=$bad_len+$bad_code+$non_ascii+$bad_space+$bad_value+$bad_fcnt+$odd_term+$bad_said+$bad_term+$bad_lcterm+$said_range_err+$bad_bracketnum+$valid_charent+$no_term+$bad_src+$bad_lang+bad_F2+$bad_F2+$bad_F3+$bad_F4+$bad_F5+$bad_F6+$bad_F7+$bad_F8+$bad_F9+$bad_F13+$bad_Ucode+$bad_tty_sup+$tty_err_result+$dup_aui+$bad_auifld+$bad_ord_id+$dup_ord_id;
  if($err) { 
	print "\nErrors found, see $main::ERR for details\n";
	print $main::fh_err "\n--------------- $ucfile ---------------\n";

	&print_error("Assigned Range for SAIDs Exceeded",$said_range_err,@bad_range)if($said_range_err);
	&print_error($tty_err_result_str,$tty_err_result)if($tty_err_result);
	&print_error("Bad Field Lengths",$bad_len,@bad_len)if($bad_len);
	&print_error("'U' Codes",$bad_Ucode,@bad_Ucode)if($bad_Ucode);
	&print_error("Code Field is blank",$bad_code,@bad_code)if($bad_code);
	&print_error("NON-ASCII",$non_ascii,@non_ascii)if($non_ascii);
	&print_error("Bad Spacing",$bad_space,@bad_space)if($bad_space);
	&print_error("Bad Values",$bad_value,@bad_value)if($bad_value);
	&print_error("Incorrect Field Count",$bad_fcnt,@bad_fcnt)if($bad_fcnt);
	&print_error("Unexpected Characters",$odd_term,@odd_term)if($odd_term);
	&print_error("Duplicate SAID",$bad_said,@bad_said)if($bad_said);
	&print_error("Duplicate Term",$bad_term,@bad_term)if($bad_term);
	&print_error("Duplicate Case-insensitive Term",$bad_lcterm,@bad_lcterm)if($bad_lcterm);
	&print_error("Numbers in Brackets",$bad_bracketnum,@bad_bracketnum)if($bad_bracketnum);
	&print_error("HTML/XML Char. Entities",$valid_charent,@valid_charent)if($valid_charent);
	&print_error("Potential HTML/XML Char. Entities",$pot_charent,@pot_charent)if($pot_charent);
	&print_error("Zero-Length Term",$no_term,@no_term)if($no_term);
	&print_error("Multiple Languages",$bad_lang,@bad_lang)if($bad_lang);
	&print_error("Duplicate SAUIs",$dup_aui,@dup_aui)if($dup_aui);
	#&print_error("SRC Atom Errors",$bad_src,@bad_src)if($bad_src);

	&print_error("Bad Format in Field 1",$bad_F1,@bad_F1)if($bad_F1);
	&print_error("Bad Format in Field 2",$bad_F2,@bad_F2)if($bad_F2);
	&print_error("Bad Format in Field 3",$bad_F3,@bad_F3)if($bad_F3);
	&print_error("Bad Format in Field 4",$bad_F4,@bad_F4)if($bad_F4);
	&print_error("Bad Format in Field 5",$bad_F5,@bad_F5)if($bad_F5);
	&print_error("Bad Format in Field 6",$bad_F6,@bad_F6)if($bad_F6);
	&print_error("Bad Format in Field 7",$bad_F7,@bad_F7)if($bad_F7);
	&print_error("Bad Format in Field 8",$bad_F8,@bad_F8)if($bad_F8);
	&print_error("Bad Format in Field 9",$bad_F9,@bad_F9)if($bad_F9);
	&print_error("Bad Format in Field 13",$bad_F13,@bad_F13)if($bad_F13);
	&print_error("Bad Suppr Value for Obsolete TTY",$bad_tty_sup,@bad_tty_sup)if($bad_tty_sup);
	&print_error(" Duplicate Termgroup/Term/SAUI/SCUI/SDUI",$bad_auifld_dup,@bad_auifld_dup)if($bad_auifld_dup);
	&print_error(" Missing Order_ID, Field 14",$bad_ord_id,@bad_ord_id)if($bad_ord_id);
	&print_error(" Duplicate Order_ID (Warning), Field 14",$dup_ord_id,@dup_ord_id)if($dup_ord_id);
	}
 }	# end of check_class()



##########################################################################
# CHECK_ATTRIBUTES()
# attributes.src specific tests
##########################################################################

sub check_attr{
  
  my($file)=@_;
  my($err);
  @bad_sty=();
  my %att_said=();

  %said_err = ();
  my(%id,@att_f,$qual,%id_qual12);
  my($bad_stat_lev, @bad_stat_lev);
  my($bad_len,$bad_id,$bad_value,$bad_fcnt,$bad_tbr);
  my($bad_STstat,$bad_STlev,$bad_sty,$bad_type,$bad_qual);
  my($id_ntfnd,$bad_STY_SRC);
  my($bad_idform,@bad_idform);
  my(@bad_id,@bad_value,@bad_fcnt,@bad_tbr);
  my(@bad_STstat,@bad_STlev,@bad_type,@bad_qual);
  my(@bad_STY_SRC);
  my(%md52atnv,%atnv2md5);
  my($atnv,$md5,$bad_md5,@bad_md5);
  my($bad_atnlen,@bad_atnlen);
  my($bad_space,@bad_space);
  my($bad_atv,@bad_atv,$tmp_atv);
  my($bad_md5val,@bad_md5val);
  my($attr_dup,@attr_dup,%attr_dup);
  my($attr_dup2,@attr_dup2,%attr_dup2);
  my($bad_SOS,@bad_SOS,%bad_SOS);
  my($bad_LXT,@bad_LXT,%bad_LXT);
  %stys=();
  @id_ntfnd=();
  $id_ntfnd=0;
	my($sos_vpt) = 0;
	my($sty_ip) = 0;
	my(@bad_src,$bad_src);

 # used for field reports:
 my($len);
 local(%fcnts,%lo,%hi,$rec);
  

  my($ucfile);
  $ucfile = uc($file);
  @bad_len=();
  
  print "\tField Lengths\n";  
  $bad_len = &ck_field_lens($file);

  open (INFILE, "$main::dir/$file") or die "Can't open $file, $!";
  binmode(INFILE, ":utf8");

  print $main::fh_file "";

  print "\tDuplicate Record IDs\n";
  print "\tBasic Field Values\n";
  print "\tCorrect number of Fields\n";
  print "\tCodes and Qualifiers\n";
  print "\tTBR for Contexts and Lexical Tags\n";
  print "\tSemantic Types are Status N\n";
  print "\tSemantic Types are C level\n";
  print "\tSemantic Types have SRC of 'E-<SAB>'\n";
  print "\tID Types\n";
  print "\tIDs and Qualifiers\n";
  print "\tAttribute Duplicates\n";
  print "\tATN/ATV and MD5\n";
  print "\tSOS Attributes\n";
  print "\tLXT Attributes\n";
  
  while(<INFILE>){
	chomp;
	@att_f = split (/\|/);
	
 # this collects info on the length of the field and 
 # whether the field has a value
 # (does much the same as 'checkfields'
	for($i=0;$i<14;$i++){
		$len = length($att_f[$i]);
		unless($rec){$lo{$i} = $len;$hi{$i}=$len }
			
		if($len == 0){} 

		$lo{$i} = $len unless($len > $lo{$i});
		$hi{$i} = $len unless($hi{$i} > $len);

		$fcnts{$i}++ if(length($att_f[$i]));
	}
	 $rec++; 

	# save SAIDs for later checking
	if($att_f[10] eq "SOURCE_ATOM_ID"){ $att_said{$att_f[1]}++}
	
	# OK
	# check for unique record IDs
	if($id{$att_f[0]}){
		unless($bad_id > $limit){ push(@bad_id,$_);$bad_id++;}
	 }
	else{ $id{$att_f[0]}++}
	
	# Is the Attribute Name greater than 20 chars?
	if(length($att_f[3])>50){
		unless($bad_atnlen > $limit){push(@bad_atnlen,$_)}
		$bad_atnlen++;
	}

	# is there a SOS attribute:
	if(($att_f[3] eq 'SOS')&&($att_f[5] eq "SRC")){
		unless($bad_SOS > $limit){push(@bad_SOS, $_)}
		$bad_SOS++;
	}

	# Does the Attribute Value have spaces?
	if($att_f[3] ne "CONTEXT"){	# ignore CONTEXTs
		if(($att_f[4]=~/^\s/)||($att_f[4]=~/\s{2,}/) || ($att_f[4]=~/\s$/)){
			unless($bad_space > $limit){push(@bad_space,$_)}
			$bad_space++;
		}
	}

	# Does the Attribute Value have content?
	$tmp_atv = $att_f[4];
	$tmp_atv =~ s/ {2,}/ /;
	$tmp_atv =~ s/^ //;
	$tmp_atv =~ s/ $//;
	if($tmp_atv eq ""){
		unless($bad_atv > $limit){push(@bad_atv,$_)}
		$bad_atv++;
	}

	
	# OK 
	# save all the semantic_types for later testing
	if($att_f[3] eq "SEMANTIC_TYPE"){ $stys{$att_f[4]}++} 
	
	# OK
	# all fields should match basic constraints
	# 1	1 or more digits
	# 2	7 or more digits
	# 3 	C or S
	# 4	anything
	# 5	anything
	# 6	E-<SAB> or SAB
	if($att_f[10] eq "SOURCE_ATOM_ID"){
		unless(/^\d{1,}\|\w{7,}\|[CS]\|.+?\|.*?\|\w+?\|[YNn]\|N\|[YN]\|/){
			unless($bad_value > $limit){ push(@bad_value, $_)} 
			++$bad_value; 
		}
	 }
	
	# OK
	#should be 12 (or 14) fields with extra '|' at the end
	if($att_f[10] eq "SOURCE_ATOM_ID"){
		unless(((tr/\|/\|/) == 12) || ((tr/\|/\|/) == 14)){ 
			unless($bad_fcnt > $limit){push(@bad_fcnt, $_)}
			++$bad_fcnt;  
	 	}
	 }
	
	# OK
	# if CONTEXT, tbr is 'n'
	if($att_f[3] eq "CONTEXT"){
		unless ($att_f[7] eq 'n'){
			unless($bad_tbr > $limit){push(@bad_tbr,$_)}
			$bad_tbr++;
	
		}
	}
	
	# OK
	# if LEXICAL_TAG 
	# Lexical Tags are 'n' unless they are 'TRD', then they're 'Y'
	if($att_f[3] eq "LEXICAL_TAG"){
		if(($att_f[7] ne 'n') && ($att_f[4] ne 'TRD')){
			unless($bad_LXT > $limit){push(@bad_LXT,$_)}
			$bad_LXT++;
		}
		elsif(($att_f[7] eq 'n')&&($att_f[4] eq 'TRD')){
			unless($bad_LXT > $limit){push(@bad_LXT,$_)}
			$bad_LXT++;
	
		}
	}
	
	# OK
	if(($att_f[3] eq "SEMANTIC_TYPE") && ($att_f[5] ne "SRC")){
		unless($att_f[6] eq 'N'){
	unless($bad_STstat > $limit){
	 push(@bad_STstat,$_);
	}
	$bad_STstat++;
		}
	 }

	# check that the source value is 'E-<SAB>' for SEMANTIC_TYPE attribs
	# where we have provided default STYs
	# only sources like MeSH and UWDA provide their own STYs
	if(($att_f[3] eq "SEMANTIC_TYPE")&&($att_f[5] ne "SRC")){
		unless($att_f[5] =~ /^E\-/){
			unless($bad_STY_SRC > $limit){
	 		push(@bad_STY_SRC,$_);
			}
		$bad_STY_SRC++;
		}
	}

	
	# OK
	# STYs get a 'C' level
	if($att_f[3] eq "SEMANTIC_TYPE"){
		unless($att_f[2] eq 'C'){
			unless($bad_STlev > $limit){
	 		push(@bad_STlev,"$.: $_");
			}
		$bad_STlev++;
		}
	}
	# check that unique ATN/ATV counts match unique MD5 counts
	# the count of unique ATN/ATV pairs should match the count
	# of ATN/MD5 pairs.
	$atnv = $att_f[3].$att_f[4];
	$md5 = $att_f[3].$att_f[13];
	# if the same hash was used for a different key, that's a problem
	# if this md5 hash value was seen already, but the ATN/ATV value
	# doesn't match the current ATN/ATV
	
	if(($md52atnv{$md5}) && ($md52atnv{$md5} ne $atnv)){
		unless($bad_md5 > $limit){push(@bad_md5,"$md5:$atnv\n")}
		$bad_md5++;
	}
	$atnv2md5{$atnv}= $md5;
	$md52atnv{$md5}= $atnv;

	# 'S' level attributes should be status 'R'
	if(($att_f[2] eq 'S')&&($att_f[6] ne 'R')){
		$bad_stat_lev++;
		unless($bad_stat_lev > $limit){
			push(@bad_stat_lev, $_);
		}
	}
	
	
	# OK
	# id_type
	unless( $att_f[10] eq "SOURCE_ATOM_ID"||
			$att_f[10] eq "SRC_ATOM_ID" ||
			$att_f[10] eq "AUI" ||
			$att_f[10] eq "CUI" ||
			$att_f[10] eq "CUI_SOURCE" ||
			$att_f[10] eq "CUI_ROOT_SOURCE" ||
			$att_f[10] eq "CUI_STRIPPED_SOURCE" ||
			$att_f[10] eq "CODE_SOURCE" ||
			$att_f[10] eq "CODE_TERMGROUP" ||
			$att_f[10] eq "CODE_STRIPPED_TERMGROUP" ||
			$att_f[10] eq "ATOM_ID" || 
			$att_f[10] eq "CONCEPT_ID" ||
			$att_f[10] eq "ROOT_SOURCE_AUI" ||
			$att_f[10] eq "ROOT_SOURCE_DUI" ||
			$att_f[10] eq "ROOT_SOURCE_CUI" ||
			$att_f[10] eq "SOURCE_AUI" ||
			$att_f[10] eq "SOURCE_CUI" ||
			$att_f[10] eq "SOURCE_DUI" ||
			$att_f[10] eq "SOURCE_RUI" ||
			$att_f[10] eq "SRC_REL_ID") 
			{
	  		if($bad_type < $limit){push(@bad_type,$_)}
	  		$bad_type++;
	}	


	# F2: ID  F11: ID_TYPE
	unless(&check_id($att_f[1],$att_f[10])){
		unless($bad_idform > $limit){
			push(@bad_idform, $_);
		}
		$bad_idform++;
	}


# OK
# Qualifier req. in f12 if f11 eq CODE_SOURCE or CODE_TERMGROUP
	if(
		($att_f[10] eq "CODE_SOURCE") || 
		($att_f[10] eq "SOURCE_AUI") || 
		($att_f[10] eq "SOURCE_CUI") || 
		($att_f[10] eq "SOURCE_DUI") || 
		($att_f[10] eq "SOURCE_RUI") || 
		($att_f[10] eq "SRC_REL_ID") || 
		($att_f[10] eq "CODE_TERMGROUP") ||
		($att_f[10] eq "CODE_STRIPPED_TERMGROUP")||
		($att_f[10] eq "CODE_STRIPPED_SOURCE")||
		($att_f[10] eq "CUI_STRIPPED_SOURCE")
		){
		if($att_f[11] eq ''){
			if($bad_qual < $limit){push(@bad_qual,$_)}
		 	$bad_qual++;
		}	    
		else{   	  # save the id_qualifier for report
			$id_qual12{$att_f[11]}++;
		}
	}

	# check field 14, MD5 hash
	$md5 = md5_hex(encode_utf8($att_f[4]));
	if($md5 ne $att_f[13]){
		if($bad_md5val < $limit){push(@bad_md5val,$_) }
		$bad_md5val++;
	}
		
	# check for duplicate attributes
	# 2:id, 3:level, 4:attr_name, 5:attr_val, 6:source, 7:status, 8:TBR, 9:release, 10:suppressible, 11:id_type, 12:id_qual
	$key = join(':',$att_f[1],$att_f[2],$att_f[3],$att_f[4],$att_f[5],$att_f[6],$att_f[7],$att_f[8],$att_f[9],$att_f[10]),$att_f[11];
	if($attr_dup{$key}){
		#if($attr_dup < $limit){push(@attr_dup,$_)}
		if($attr_dup < $limit){push(@attr_dup,$key)}
		$attr_dup++;
	}
	else{ $attr_dup{$key}++}

	# check for duplicate attribute part II, ATUIs
	# 2:id,  4:attr_name, 5:attr_val, 6:source, 11:id_type, 12:id_qual, 13:source_atui 
	$key = join(':',$att_f[1],$att_f[3],$att_f[4],$att_f[5],$att_f[6],$att_f[10],$att_f[11],$att_f[12]);
	if($attr_dup2{$key}){
		#if($attr_dup2 < $limit){push(@attr_dup2,$_)}
		if($attr_dup2 < $limit){push(@attr_dup2,$key)}
		$attr_dup2++;
	}
	else{ $attr_dup2{$key}++}

 }		# end of while(<ATTRIBS>)	


 close INFILE; 

	&print_field_report("attrib",$rec);

## unless($sos_vpt == 1){
## 	push(@bad_src, "$sos_vpt valid SOS attribs for the SRC/VPT, 1 allowed");
## 	$bad_src++;
## }

## unless($sty_ip == 1){
## 	push(@bad_src, "$sty_ip valid \"STY|Intellectual Product\" attribs for the SRC/VPT, 1 allowed");
## 
## 	$bad_src++;
## }

##  unless($sab && $said_vpt){
## 		@bad_src = ();	# flush prev error messages
## 		push(@bad_src, "No SAB and/or SAID for the VPT, SRC attribute checking disabled");
## 		$bad_src = 1;
## 		$sos_vpt = $sty_ip = 1;	# disable errors for SOS & STY
## 	}

# take all the saids found above and check them against SAIDs in classes
# foreign sources are saved in the lookup_said function
# lookup_said is in QA3_util.pm
# 
	if($said_flg){
		my ($x);
		foreach $x (sort(keys(%att_said))){
			unless($said_class{$x}){
				# saves errors to %said_err
				&lookup_said($x);
			}
	 	}
	}

# prints out the counts of the ATN/ATVs vs. the MD5s
# counts should be the same
$atnv_cnt = scalar(keys(%atnv2md5));
$md5_cnt = scalar(keys(%md52atnv));
if($atnv_cnt != $md5_cnt){
	print "ATN/ATV count DOES NOT MATCH MD5 count\n";
	print $main::fh_summ "ATN/ATV count DOES NOT MATCH MD5 count\n";
	print $main::fh_summ "Unique ATN/ATV: $atnv_cnt\n";
	print $main::fh_summ "    Unique MD5: $md5_cnt\n";
	print $main::fh_summ "\n";
}

# takes all the foreign SAIDs found above and creates an array suitable
# for printing with the print_error() rountine below
# found in QA3_util.pm

  $id_ntfnd = &make_said_error_array();
  
  # check for valid stys, print to FILE & ERROR the results
  # returns # of errors found
  # sub routine in QA3_util.pm
  $bad_sty = &valid_stys();
  if($bad_sty){
	printf $main::fh_file "\n%d Bad Semantic Type%s.\n", $bad_sty, ($bad_sty == 1) ? "" : "s";
	print $main::fh_file "See ERROR_LOG for details\n";
	}
  # print out the ID qualifiers if any

	if(keys(%id_qual12)){
	  print $main::fh_file "----- ID QUALIFIERS -----\n";
	  print $main::fh_file "Qualifiers Found in Field 12\n";
	  foreach $qual (sort(keys(%id_qual12))){
	    printf $main::fh_file "%8s %8d\n", $qual,$id_qual12{$qual};
	   }
	 }
  # print results to SUMMARY
  printf $main::fh_summ "%6d %s\n", $bad_len, " Bad Field Lengths";  
  printf $main::fh_summ "%6d %s\n", $bad_id, " Duplicate Record IDs";
  printf $main::fh_summ "%6d %s\n", $bad_idform, " Bad format for IDs - F 2/11";
  printf $main::fh_summ "%6d %s\n", $bad_value, " Bad values in fields";
  printf $main::fh_summ "%6d %s\n", $bad_fcnt, " Incorrect no. of fields";	
  printf $main::fh_summ "%6d %s\n", $bad_tbr, " TBR for CONTEXT or LEXICAL TAG not 'n'"; 
  printf $main::fh_summ "%6d %s\n", $bad_STstat, " Semantic Type not Status 'N'";	
  printf $main::fh_summ "%6d %s\n", $bad_STlev, " Semantic Type w/ level not 'C'";
  printf $main::fh_summ "%6d %s\n", $bad_STY_SRC, " Source not E-<SAB> for Semantic Type (warning)";
  printf $main::fh_summ "%6d %s\n", $bad_type, " Invalid ID Type (Field 11)";
  printf $main::fh_summ "%6d %s\n", $bad_sty, " Unknown Values in Semantic Types";
  printf $main::fh_summ "%6d %s\n", $bad_stat_lev, " Source Level not Status 'R'";
  printf $main::fh_summ "%6d %s\n", $bad_md5, " MD5 ATN/ATV pair count errors";
  printf $main::fh_summ "%6d %s\n", $bad_md5val, " MD5 value errors";
  printf $main::fh_summ "%6d %s\n", $bad_atnlen, " ATN too long";
  printf $main::fh_summ "%6d %s\n", $bad_space, " Spacing errors in ATV";
  printf $main::fh_summ "%6d %s\n", $bad_atv, " No ATV";
  printf $main::fh_summ "%6d %s\n", $attr_dup, " Duplicate Attributes";
  printf $main::fh_summ "%6d %s\n", $attr_dup2, " Duplicate ATUIs";
  printf $main::fh_summ "%6d %s\n", $bad_SOS, " SOS Attributes Found";
  printf $main::fh_summ "%6d %s\n", $bad_LXT, " Bad LXT TBR settings Found";
	
  if($said_flg){
	printf $main::fh_summ "%6d %s\n", $id_ntfnd, " SAIDs NOT found in classes";
	}
  else{
	printf $main::fh_summ "%s\n", "No CLASSES FILE, SAIDs NOT Checked";
	}

  $err = $bad_len+$bad_id+$bad_idform+$bad_value+$bad_fcnt+$bad_tbr+$bad_STstat+$bad_STlev+$bad_type+$bad_qual+$id_ntfnd+$bad_sty+$bad_stat_lev+$bad_src+$bad_STY_SRC+$bad_md5val+$bad_md5+$bad_atnlen+$bad_space+$bad_atv+$attr_dup+$attr_dup2+$bad_SOS + $bad_LXT;

  if($err){ 
	print "\nErrors found, see $main::$ERR for details\n";
	print $main::fh_err "\n--------------- $ucfile ---------------\n";
	&print_error("Bad Field Lengths",$bad_len,@bad_len)if($bad_len);
	&print_error("Duplicate IDs",$bad_id,@bad_id)if($bad_id);
	&print_error("Bad Format for IDs F 2/11",$bad_idform,@bad_idform)if($bad_idform);
	&print_error("Bad Values in Fields",$bad_value,@bad_value)if($bad_value);
	&print_error("Incorrect No. of Fields",$bad_fcnt,@bad_fcnt)if($bad_fcnt);
	&print_error("TBR not 'n' for CONTEXT or LEXICAL TAG",$bad_tbr,@bad_tbr)if($bad_tbr);
	&print_error("Level not 'C' for SEMANTIC_TYPE",$bad_STlev,@bad_STlev)if($bad_STlev);
	&print_error("Status not 'N' for SEMANTIC_TYPE ",$bad_STstat,@bad_STstat)if($bad_STstat);
	&print_error("Source not 'E-<SAB>' for SEMANTIC_TYPE",$bad_STY_SRC,@bad_STY_SRC)if($bad_STY_SRC);
	&print_error("Bad ID TYPE ",$bad_type,@bad_type)if($bad_type);
	&print_error("Missing Qualifier for ID TYPE ",$bad_qual,@bad_qual)if($bad_qual);
	&print_error("SAIDs not in Classes",$id_ntfnd,@id_ntfnd)if($id_ntfnd);
	&print_error("Invalid STYs",$bad_sty,@bad_sty)if($bad_sty);
	&print_error("'S' level not status 'R'",$bad_stat_lev,@bad_stat_lev)if($bad_stat_lev);
	&print_error("MD5 ATN/ATV Pair Count Errors",$bad_md5,@bad_md5)if($bad_md5);
	&print_error("MD5 Value Errors",$bad_md5val,@bad_md5val)if($bad_md5val);
	&print_error("ATN Too Long",$bad_atnlen,@bad_atnlen)if($bad_atnlen);
	&print_error("ATV Space Errors",$bad_space,@bad_space)if($bad_space);
	&print_error("No ATV",$bad_atv,@bad_atv)if($bad_atv);
	&print_error("Attribute Duplicates",$attr_dup,@attr_dup)if($attr_dup);
	&print_error("ATUI Duplicates",$attr_dup2,@attr_dup2)if($attr_dup2);
	&print_error("SOS Attribute Found",$bad_SOS,@bad_SOS)if($bad_SOS);
	&print_error("Lexical Tags with bad TBR",$bad_LXT,@bad_LXT)if($bad_LXT);
	}  
 } # end of check_attributes


##########################################################################
# CHECK_RELS()
# Relationships.src specific tests
##########################################################################
# takes a file name to check
sub check_rels {
	
	my($file)=@_;
	my($err,$str);
	my(%id,@rf,%bad_rela,$said_err);
	my %said = ();
	%said_err = ();
	@id_ntfnd=();
	my($id_ntfnd);
	@bad_len=();
	my($bad_said, $bad_idform);
	my($bad_len,$bad_id,$bad_fcnt,$bad_value,$bad_type,$bad_rela,$bad_stat);
	my($bad_sfo,$bad_sfo_rela,$bad_nt,$bad_qual,$bad_rel_rela);
	my($rev_str,$con_rel,$dupnt,$dupbt,$con_bt,$con_nt,$dupntbt,$rfcnt);
	my(@bad_said, @bad_idform);
	my(@bad_id,@bad_fcnt,@bad_value,@bad_type,@bad_rela,@bad_stat);
	my(@bad_sfo,@bad_sfo_rela,@bad_nt);
	my(@dupnt,@dupbt,@con_rel,@dupntbt,@bad_qual,@bad_rel_rela);
	my(%bthash,%nthash);
	my(%rels,%id_qual15,%id_qual16, %bad_relrela);
	my($ucfile,$relrela, $bad_relrela);
	my($bad_relsrc,@bad_relsrc);
	my($bad_rellab,@bad_rellab);
	my($dupcode,@dupcode,%dupcode);
	my($rui_str, %rui_str, $bad_rui_dup, @bad_rui_dup);

  $bad_rela=0;
  
 # used for field reports:
 my($len);
 local(%fcnts,%lo,%hi,$rec);
  
  %rels = &get_relas();
  $ucfile = uc($file); 

  # create the hash '%invalid_rela_hash'
  # hash is '%invalid_rela_hash'
  # key = rel|rela
  # value = '1'
  #local(%invalid_rela_hash);
  &make_invalid_rela_hash();

  @bad_len=(); 
  $bad_len = &ck_field_lens($file);
  
  open (INFILE, "$main::dir/$file") or die "Can't open $file, $!";
  print FILE "";
#print "Checking $file\n";
  print "\tField Lengths\n";
  print "\tUnique File ID\n";
  print "\tCorrect No. of Fields\n";
  print "\tBasic values in Fields\n";
  print "\tCorrect Types in ID_types\n";
  print "\tSource level not status='N'\n";
  print "\tDuplicates and Conflicts in Rels\n";
  print "\tConflicting REL/RELA check\n";
  print "\tIDs and Qualifiers\n";
  print "\tValid RELAs\n";
  if($said_flg){print "\tSAIDs Verified\n"}
  else{print "\tSAIDs NOT Verified\n"}
  
while(<INFILE>){
	chomp;
	@rf = split(/\|/);
	

 # this collects info on the length of the field and 
 # whether the field has a value
 # (does much the same as 'checkfields'
	for($i=0;$i<18;$i++){
		$len = length($rf[$i]);
		unless($rec){$lo{$i} = $len;$hi{$i}=$len }
			
		if($len == 0){} 

		$lo{$i} = $len unless($len > $lo{$i});
		$hi{$i} = $len unless($hi{$i} > $len);

		$fcnts{$i}++ if(length($rf[$i]));
	}
	 $rec++; 

	# OK
	# check for duplicate ids
	if($id{$rf[0]}){
		unless($bad_id > $limit){ 
			push(@bad_id,$_);
		}
		$bad_id++;
	 }
	else{ $id{$rf[0]}++}





	# save all the SAIDs for later checking against SAIDs in classes
	# but only if field 13 is "SOURCE_ATOM_ID"
	if($rf[12] eq "SOURCE_ATOM_ID"){
		$all_saids{$rf[2]}++;
	}

	# but only if field 15 is "SOURCE_ATOM_ID"
	if($rf[14] eq "SOURCE_ATOM_ID"){
		$all_saids{$rf[5]}++;
	}

	# F3: ID  F13: ID_TYPE
	unless(&check_id($rf[2],$rf[12])){
		unless($bad_idform > $limit){
			push(@bad_idform, $_);
		}
		$bad_idform++;
	}
	# F6: ID  F15: ID_TYPE
	unless(&check_id($rf[5],$rf[14])){
		unless($bad_idform > $limit){
			push(@bad_idform, $_);
		}
		$bad_idform++;
	}
	
	
	# Fields 13/15
	# check that if CODE is used in field 13 or 15 (id_type1/2),
	# that the "id_1|id_2|id_qualifier1|id_qualifier2" string
	# is not duplicated
	if(($rf[12] =~ /CODE/)||($rf[14] =~ /CODE/)){
		$key = "$rf[2]|$rf[5]|$rf[13]|$rf[15]";
		if($dupcode{$key}){
			unless($dupcode > $limit){ push(@dupcode,$_)}
			$dupcode++;
		}
		else{$dupcode{$key}++}
	}


	# Fields 15/17
	# should be 16 (or 18) fields with extra pipe at the end
	$rfcnt = (tr/\|/\|/);
	unless(($rfcnt == 16) || ($rfcnt == 18 ))  {
		if ($bad_fcnt < $limit){push(@bad_fcnt, $_)}
		++$bad_fcnt; 
	 } 
	
	# check for correct values in other fields
	# 1 - more than one digit
	# 2 - P, C, or S
	# 3 - 
	unless($rf[12]){
		unless(/^\d{1,}\|[PCS]\|[a-zA-Z0-9\-]{5,50}\|RT|RT\?|NT|SY|BT|BRT|LK|XR|AQ|SFO\/LFO\|.*\|\w+?\|[A-Z_0-9\-]{4,20}\|[A-Z_0-9\-]{4,20}\|[DRUNS]\|[YNn]\|[YN]\|[YN]\|/o){
			unless($bad_value> $limit){ push(@bad_value, $_)} 
		++$bad_value; 
		}
	}

	# OK
	# check for valid TYPE field
	unless($rf[12] eq "ATOM_ID" || 
		$rf[12] eq "SOURCE_ATOM_ID"||
		$rf[12] eq "SRC_ATOM_ID"||
		$rf[12] eq "CONCEPT_ID" ||
		$rf[12] eq "AUI" ||
		$rf[12] eq "CUI" ||
		$rf[12] eq "CUI_SOURCE" ||
		$rf[12] eq "CUI_ROOT_SOURCE" ||
		$rf[12] eq "CUI_STRIPPED_SOURCE" ||
		$rf[12] eq "CODE_SOURCE" ||
		$rf[12] eq "CODE_STRIPPED_SOURCE" ||
		$rf[12] eq "CODE_TERMGROUP" ||
		$rf[12] eq "CODE_STRIPPED_TERMGROUP" ||
		$rf[12] eq "SOURCE_AUI"||
		$rf[12] eq "SOURCE_CUI"||
		$rf[12] eq "SOURCE_DUI"||
		$rf[12] eq "SOURCE_RUI"||
		$rf[12] eq "SRC_REL_ID"||
		$rf[12] eq "ROOT_SOURCE_CUI"||
		$rf[12] eq "ROOT_SOURCE_DUI"||
		$rf[12] eq "ROOT_SOURCE_RUI"||
		$rf[12] eq "ROOT_SOURCE_AUI"
		){
		if($bad_type < $limit){push(@bad_type,$_)}
		$bad_type++;
	 }	
	unless($rf[14] eq "ATOM_ID" || 
		$rf[14] eq "SOURCE_ATOM_ID"||
		$rf[14] eq "SRC_ATOM_ID"||
		$rf[14] eq "CONCEPT_ID" ||
		$rf[14] eq "AUI" ||
		$rf[14] eq "CUI" ||
		$rf[14] eq "CUI_STRIPPED_SOURCE" ||
		$rf[14] eq "CODE_SOURCE" ||
		$rf[14] eq "CODE_STRIPPED_SOURCE" ||
		$rf[14] eq "CODE_TERMGROUP" ||
		$rf[14] eq "CODE_STRIPPED_TERMGROUP" ||
		$rf[14] eq "SOURCE_AUI"||
		$rf[14] eq "SOURCE_CUI"||
		$rf[14] eq "SOURCE_DUI"||
		$rf[14] eq "SOURCE_RUI"||
		$rf[14] eq "SRC_REL_ID"||
		$rf[14] eq "ROOT_SOURCE_CUI"||
		$rf[14] eq "ROOT_SOURCE_DUI"||
		$rf[14] eq "ROOT_SOURCE_RUI"||
		$rf[14] eq "ROOT_SOURCE_AUI"
		){
		if($bad_type < $limit){push(@bad_type,$_)}
		$bad_type++;
	 }	
	
	# OK
	# check for valid relas
	#if line has rela, check against valid list
	if($rf[4]){
		unless ($rels{$rf[4]}){
			$bad_rela{$rf[4]}++;
			$bad_rela++;
		}
	}

	# check for REL/RELA combos that will lead to conflicts
	# these RELAs should be matched with these RELs
	# associated_with: RT
	# conceptual_part_of: NT
	# consists_of: RT
	# contains: RT
	# form_of: NT
	# ingredient_of: RT
	# isa: NT
	# part_of: NT
	# tradename_of: NT
	if(
	($rf[4] eq "associated_with"     && $rf[3] ne "RT") ||
	($rf[4] eq "conceptual_part_of"  && $rf[3] ne "NT") ||
	($rf[4] eq "has_conceptual_part" && $rf[3] ne "BT") ||
	($rf[4] eq "consists_of"         && $rf[3] ne "RT") ||
	($rf[4] eq "constitutes"         && $rf[3] ne "RT") ||
	($rf[4] eq "contains"            && $rf[3] ne "RT") ||
	($rf[4] eq "contained_in"        && $rf[3] ne "RT") ||
	($rf[4] eq "form_of"             && $rf[3] ne "NT") ||
	($rf[4] eq "has_form"            && $rf[3] ne "BT") ||
	($rf[4] eq "ingredient_of"       && $rf[3] ne "RT") ||
	($rf[4] eq "has_ingredient"      && $rf[3] ne "RT") ||
	($rf[4] eq "isa"                 && $rf[3] ne "NT") ||
	($rf[4] eq "inverse_isa"         && $rf[3] ne "BT") ||
	($rf[4] eq "part_of"             && $rf[3] ne "NT") ||
	($rf[4] eq "has_part"            && $rf[3] ne "BT") ||
	($rf[4] eq "tradename_of"        && $rf[3] ne "NT") ||
	($rf[4] eq "has_tradename"       && $rf[3] ne "BT") 
	){
		unless($bad_rel_rela > $limit){push(@bad_rel_rela, $_)}
		$bad_rel_rela++;
	}
	
	# OK
	# if S level, status can not be 'N'
	if($rf[8] eq "N"){
		if($rf[1] eq 'S'){
	$bad_stat++;
	if($bad_stat < $limit){push(@bad_stat,$_)}
		}
	 }
	
	# Check for Duplicates and Conflicts in relationships
	# if it's NT 
	#		compare against NT hash (dup err. if match)
	#		compare against BT hash (err. if match)
	#		flip it and compare against BT hash (warn if match)
	#			  write it to the NT hash
	# if it's BT 
	#		compare against NT hash
	#		compare against BT hash
	#		flip it and compare against NT hash 
	#			  write it to the BT hash
	
	if($rf[3] eq "NT"){
		$str = $rf[1]."|".$rf[2]."|".$rf[5];
		$rev_str = $rf[1]."|".$rf[5]."|".$rf[2];
		# this is a duplicate of existing NT
		if($nthash{$str}){	# dup NT err
	unless($dupnt > $limit){
	 push(@dupnt,$str);
	}
	$dupnt++;
		}
		# this is an error, NT & BT for same IDs
		if($bthash{$str}){	# conflict error
	unless($con_rel > $limit){
	 push(@con_rel,$str);
	}
	$con_rel++;
		}
		# same rel expressed as NT & BT, just a warning
		if($bthash{$rev_str}){	# NT/BT dup warn
	unless($dupntbt > $limit){
	 push(@dupntbt,$str);
	}
	$dupntbt++;
		}
		$nthash{$str}++;
	 }
	if($rf[3] eq "BT"){
		$str = $rf[1]."|".$rf[2]."|".$rf[5];
		$rev_str = $rf[1]."|".$rf[5]."|".$rf[2];
		# dup BT err
		if($bthash{$str}){
	unless($dupbt > $limit){
	 push(@dupbt,$str);
	}
	$dupbt++;
		}
		if($nthash{$str}){	# conflict error
	unless($con_rel > $limit){
	 push(@con_rel,$str);
	}
	$con_rel++;
		}
		if($nthash{$rev_str}){	# NT/BT dup warn
	unless($dupntbt > $limit){
	 push(@dupntbt,$str);
	}
	$dupntbt++;
		}
		$bthash{$str}++;
	 }
	
	# OK
	# SFO/LFO rels should be TBR='Y'
	if($rf[3] =~ /SFO/){
		if($rf[9] ne 'Y'){
			if($bad_sfo < $limit){push(@bad_sfo,$_)}
			$bad_sfo++;
		}
		if($rf[4] eq ""){
			if($bad_sfo_rela < $limit){push(@bad_sfo_rela,$_)}
			$bad_sfo_rela++;
		}
	}
	# NT rels should never be 'mapped_from'
	if($rf[3] =~ /NT/){
		if($rf[4] =~ /mapped_from/){
	if($bad_nt < $limit){push(@bad_nt,$_)}
	$bad_nt++;
		}
	 }
	# Qualifier req. in F 14 for these types in F 13
	# Qualifiers in f 14 & 16 if CODE_SOURCE or CODE_TERMGROUP
	if(($rf[12] eq "CODE_SOURCE")||($rf[12] eq "CODE_TERMGROUP")||($rf[12] eq "CUI_STRIP_SOURCE")||($rf[12] eq "CODE_STRIPPED_SOURCE")){
		if($rf[13] eq ''){
			if($bad_qual < $limit){push(@bad_qual,$_)}
			$bad_qual++;
		}
		else{		# save the id_qualifier for report
			$id_qual14{$rf[13]}++;
		}
	 }
	
	# Qualifier req. in F 16 for these types in F 15
	if(($rf[14] eq "CODE_SOURCE") || ($rf[14] eq "CODE_TERMGROUP")||($rf[14] eq "CUI_STRIPPED_SOURCE")||($rf[14] eq "CODE_STRIPPED_SOURCE")){
		if($rf[15] eq ''){
			if($bad_qual < $limit){push(@bad_qual,$_)}
			$bad_qual++;
		}
		else{		# save the id_qualifier for report
			$id_qual16{$rf[15]}++;
		}
	 }
	# check that rela of 'ingredient_of' has a 'RT' rel
	# look at hash 'invalid_rela_hash' to determine if we have an invalid 
	# rel|rela combo. hash contains 'rel|rela'
	$relrela = "$rf[3]|$rf[4]";
	if($invalid_rela_hash{$relrela}){
		$bad_relrela++;
		unless($bad_relrela > $limit){
			push(@bad_relrela, "$.: $relrela");
		}
	}

	# duplicates amoung RUI fields:
	# 3:id_1, 4:rel_name, 5:rel_attr, 6:id_2, 7:source, 13:id_type1, 14:id_qual1, 15:id_type2, 16:id_qual2, 17:source_rui
	$rui_str = join('@',$rf[2],$rf[3],$rf[4],$rf[5],$rf[6],$rf[7],$rf[12],$rf[13],$rf[14],$rf[15],$rf[16]);

	if($rui_str{$rui_str}){
		unless($bad_rui_dup > $limit){
			push(@bad_rui_dup, "$.:$_");
		}
		$bad_rui_dup++;
	}
	$rui_str{$rui_str}++;

	} # end of while(<RELS_FILE>)

	&print_field_report("rels",$rec);
  
if(keys(%id_qual14)||keys(%id_qual16)){
	print $main::fh_file "----- ID QUALIFIERS -----\n";
	if(keys(%id_qual14)){
		print $main::fh_file "Qualifiers Found in Field 14\n";}
	foreach $qual (sort(keys(%id_qual14))){
		printf $main::fh_file "%8s %8d\n", $qual,$id_qual14{$qual};
	 }
	if(keys(%id_qual16)){
		print $main::fh_file "Qualifiers Found in Field 16\n";}
	foreach $qual (sort(keys(%id_qual16))){
		printf $main::fh_file "%8s %8d\n", $qual,$id_qual16{$qual};
	 }
}
# takes the hash of bad_relas and stuffs 'em into a hash for printing
#  &make_rela_error_array();
 if($bad_rela){
		my ($x,$rela);
		print $main::fh_file "----- Unknown RELAs -----\n";
		print $main::fh_file " Count RELA\n";
		print $main::fh_file "------ --------\n";
		$str = sprintf("%6s %s","Count","Unknown RELA");
		push(@bad_rela,$str);
		$str = "------ ------------";
		push(@bad_rela,$str);
		foreach $rela (sort(keys(%bad_rela))){
			$str = sprintf("%6d %-60s", $bad_rela{$rela}, $rela);
			push(@bad_rela,$str);
			print $main::fh_file "$str\n";
	 	}
	}


# take all the saids found above and check them against SAIDs in classes
# foreign sources are saved in the lookup_said function
# lookup_said is in QA3_util.pm
	if($said_flg){
		my ($x);
		foreach $x (sort(keys(%all_saids))){
			unless($said_class{$x}){
				# saves errors to %said_err
				&lookup_said($x);
			}
		}
	}
  
# This is CHECK_RELS()
  
# takes all the foreign SAIDs found above and creates an array suitable
# for printing with the print_error() rountine below
# found in QA3_util.pm
  
  $id_ntfnd = &make_said_error_array();
  
	#printf $main::fh_summ "Error Counts\n";
 printf $main::fh_summ "%6d %s\n", $bad_len, " Bad Field Lengths";  
 #printf $main::fh_summ "%6d %s\n", $bad_said, " Bad SAID values in Field 3 or 6";
 printf $main::fh_summ "%6d %s\n", $bad_id, " Duplicates in ID field";
 printf $main::fh_summ "%6d %s\n", $bad_fcnt, " Bad field count";
 printf $main::fh_summ "%6d %s\n", $bad_value, " Bad values in fields";
 printf $main::fh_summ "%6d %s\n", $bad_type, " Bad types in ID_TYPE";
 printf $main::fh_summ "%6d %s\n", $bad_idform, " Bad ID values in Field 3 or 6";
 printf $main::fh_summ "%6d %s\n", $bad_stat, " Source level Rels w/ Stat='N' (Fields 2 & 9)";
 printf $main::fh_summ "%6d %s\n", $dupnt, " Duplicate NTs for same IDs Found (warning)";
 printf $main::fh_summ "%6d %s\n", $dupbt, " Duplicate BTs for same IDs Found (warning)" ;
 printf $main::fh_summ "%6d %s\n", $con_rel, " Conflicting BT & NT for same IDs";
 printf $main::fh_summ "%6d %s\n", $dupntbt, " Same Rel expressed as both NT and BT (warning)";
 printf $main::fh_summ "%6d %s\n", $bad_qual, " IDs Missing Qualifiers";
 printf $main::fh_summ "%6d %s\n", $bad_rela, " Bad RELAs Found";
 printf $main::fh_summ "%6d %s\n", $bad_rel_rela, " REL/RELA Conflicts";
 printf $main::fh_summ "%6d %s\n", $bad_sfo, " SFO/LFO Rel where TBR != 'Y'";
 printf $main::fh_summ "%6d %s\n", $bad_sfo_rela, " SFO/LFO Rel w/o a RELA";
 printf $main::fh_summ "%6d %s\n", $bad_nt, " NT Rel w/ ATV eq 'mapped_from'";
 printf $main::fh_summ "%6d %s\n", $bad_relrela, " Invalid REL/RELA combos";
 printf $main::fh_summ "%6d %s\n", $dupcode	, " Duplicate Code1/Code2 - id_qualifier1 - id_qualifier2 Combos";
 printf $main::fh_summ "%6d %s\n", $bad_rui_dup, " RUI duplicates";

  if($said_flg){
	printf $main::fh_summ "%6d %s\n", $id_ntfnd, " SAIDs NOT found in classes";
	}
  else{
	printf $main::fh_summ "%s\n", "No CLASSES file, SAIDs NOT Checked";
	}
  
#printf $main::fh_summ "%6d %s\n", $, " Found";
  
  $err=$bad_len+$bad_said+$bad_id+$bad_idform+$bad_value+$bad_type+$bad_fcnt+$bad_sfo+$bad_sfo_rela+$bad_nt+$bad_rela+$bad_stat+$bad_qual+$dupnt+$dupbt+$con_rel+$dupntbt+$id_ntfnd+$bad_relrela+$bad_rel_rela+$dupcode+$bad_rui_dup;
  
  if($err){
	print "\nErrors found, see $main::ERR for details\n";
	print $main::fh_err "\n--------------- $ucfile ---------------\n";
	&print_error("Bad Field Lengths",$bad_len,@bad_len)if($bad_len);
	&print_error("Bad SAID values",$bad_said,@bad_said)if($bad_said);
	&print_error("Duplicate IDs",$bad_id,@bad_id)if($bad_id);
	&print_error("Incorrect Field Count",$bad_fcnt,@bad_fcnt)if($bad_fcnt);
	&print_error("Bad Field Values",$bad_value,@bad_value)if($bad_value);
	&print_error("Bad ID Types Field 13/15",$bad_type,@bad_type)if($bad_type);
	&print_error("Bad ID Format Field 3 or 6",$bad_idform,@bad_idform)if($bad_idform);
	&print_error("Bad Status (N) for Source Level 'S'",$bad_stat,@bad_stat)if($bad_stat);
	&print_error("Duplicate NT Relationships (Warning)",$dupnt,@dupnt)if($dupnt);
	&print_error("Duplicate BT Relationships (Warning)",$dupbt,@dupbt)if($dupbt);
	&print_error("Conflicting BT & NT for same IDs",$con_rel,@con_rel)if($con_rel);
	&print_error("Same Relationship expressed as both NT & BT (Warning)",$dupntbt,@dupntbt)if($dupntbt);
	&print_error("IDs Missing Qualifiers",$bad_qual,@bad_qual)if($bad_qual);
	&print_error("Unknown RELA",$bad_rela,@bad_rela)if($bad_rela);
	&print_error("REL/RELA Conflicts",$bad_rel_rela,@bad_rel_rela)if($bad_rel_rela);
	&print_error("SFO/LFO where TBR != 'Y'",$bad_sfo,@bad_sfo)if($bad_sfo);
	&print_error("SFO/LFO w/o a RELA",$bad_sfo_rela,@bad_sfo_rela)if($bad_sfo_rela);
	&print_error("NT w/ ATV eq 'mapped_from'",$bad_nt,@bad_nt)if($bad_nt);
	&print_error("SAIDs not in Classes",$id_ntfnd,@id_ntfnd)if($id_ntfnd);
	&print_error("Invalid REL/RELA combos",$bad_relrela,@bad_relrela)if($bad_relrela);
	&print_error("Duplicated code combos",$dupcode,@dupcode)if($dupcode);
	&print_error("Duplicate RUI values",$bad_rui_dup,@bad_rui_dup)if($bad_rui_dup);

	}
 } # end of check_rels()



##########################################################################
# CHECK_MERGE()
# mergefacts.src specific tests
##########################################################################
sub check_merge{
	
	my($file)=@_;
	my($bad_idform1,@bad_idform1);
	my($bad_idform3,@bad_idform3);
	my($id_ntfnd,$bad_len,$bad_value,$bad_qual,$bad_fcnt,$bad_type);
	my(@bad_fcnt,@bad_value,@bad_type,@bad_qual);
	my($bad_mergeset,@bad_mergeset);
	my %said_err = ();
	@id_ntfnd=();
	$id_ntfnd=0;
	@bad_len=();;
	my(@mf,%said);
	my($ucfile) = uc($file);
	%said_err = ();
	@bad_len=(); 
	$bad_len = &ck_field_lens($file); 
	my(%id_qual10,%id_qual12); 

	

	# used for field reports:
	my($len);
	local(%fcnts,%lo,%hi,$rec);
  
	open (INFILE, "$main::dir/$file") or die "Can't open $file, $!";

	print FILE "";
	# print "Checking $file\n";
	print "\tField Values\n";
	print "\tField Count\n";
	print "\tID Types\n";
	print "\tIDs and Qualifiers\n";
	if($said_flg){
	print "\tSAIDs Verified\n"}
	else{print "\tSAIDs NOT Verified\n"}
	
	while(<INFILE>){ 
	chomp;
	@mf = split(/\|/);
	
	
 # this collects info on the length of the field and 
 # whether the field has a value
 # (does much the same as 'checkfields'
	for($i=0;$i<12;$i++){
		$len = length($mf[$i]);
		unless($rec){$lo{$i} = $len;$hi{$i}=$len }
			
		if($len == 0){} 

		$lo{$i} = $len unless($len > $lo{$i});
		$hi{$i} = $len unless($hi{$i} > $len);

		$fcnts{$i}++ if(length($mf[$i]));
	}
	 $rec++; 

	# save SAIDs for later checking
	if($mf[8] eq "SOURCE_ATOM_ID"){ $said_merge{$mf[0]}++}
	if($mf[10] eq "SOURCE_ATOM_ID"){ $said_merge{$mf[2]}++}
	
	# OK
	# should have 12 fields plus extra pipe at the end
	unless((tr/\|/\|/) == 12){
		unless($bad_fcnt > $limit){push(@bad_fcnt, $_)}
		++$bad_fcnt
		}
	
	# OK
	# check for correct values in other fields
	if($mf[8] eq "SOURCE_ATOM_ID"){
		unless(/^\w{8,}\|SY|MAT|NRM\|\w{8,}\|\w{5,}\|\|[YN]\|[YN]\|\w{5,}\|/o){
			unless($bad_value> $limit){ push(@bad_value, $_)} 
			++$bad_value; 
		}
	}
	# 
	# check merge_set values
	unless($mf[7] =~ /SRC/ ||
		$mf[7] =~ /-SY$/ ||
		$mf[7] =~ /-SCUI$/ ||
		$mf[7] =~ /-AB$/ ||
		$mf[7] =~ /-AE$/ ||
		$mf[7] =~ /-EX$/ ||
		$mf[7] =~ /-XREF$/ ||
		$mf[7] =~ /-LAT$/ ||
		$mf[7] =~ /-CODE$/ ||
		$mf[7] =~ /-CUI$/
		){
		if($bad_mergeset < $limit){push(@bad_mergeset,$_)}
		$bad_mergeset++;
		}
		
	# OK
	# AUI, SRC_ATOM_ID, CUI, CUI_ROOT_SOURCE, CODE_SOURCE, CODE_TERMGROUP, CODE_ROOT_TERMGROUP, ATOM_ID, CONCEPT_ID, SOURCE_AUI, ROOT_SOURCE_AUI, SOURCE_CUI, ROOT_SOURCE_CUI, SOURCE_DUI, ROOT_SOURCE_DUI, SOURCE_RUI, SRC_REL_ID, ROOT_SOURCE_RUI

	# check for valid TYPE field
	unless(
		$mf[8] eq "SRC_ATOM_ID"||
		$mf[8] eq "AUI" ||
		$mf[8] eq "CUI" ||
		$mf[8] eq "CUI_SOURCE" ||
		$mf[8] eq "CUI_ROOT_SOURCE" ||
		$mf[8] eq "CODE_SOURCE" ||
		$mf[8] eq "CODE_TERMGROUP" || 
		$mf[8] eq "CODE_ROOT_TERMGROUP" ||
		$mf[8] eq "ATOM_ID" ||
		$mf[8] eq "CONCEPT_ID" ||
		$mf[8] eq "SOURCE_AUI" ||
		$mf[8] eq "ROOT_SOURCE_AUI" ||
		$mf[8] eq "SOURCE_CUI" ||
		$mf[8] eq "ROOT_SOURCE_CUI" ||
		$mf[8] eq "SOURCE_DUI" ||
		$mf[8] eq "ROOT_SOURCE_DUI" ||
		$mf[8] eq "SOURCE_RUI" ||
		$mf[8] eq "SRC_REL_ID" ||
		$mf[8] eq "ROOT_SOURCE_RUI" 
		){

		if($bad_type < $limit){push(@bad_type,$_)}
		$bad_type++;
	 }	
	unless(
		$mf[10] eq "SRC_ATOM_ID"||
		$mf[10] eq "AUI" ||
		$mf[10] eq "CUI" ||
		$mf[10] eq "CUI_ROOT_SOURCE" ||
		$mf[10] eq "CODE_SOURCE" ||
		$mf[10] eq "CODE_TERMGROUP" || 
		$mf[10] eq "CODE_ROOT_TERMGROUP" ||
		$mf[10] eq "ATOM_ID" ||
		$mf[10] eq "CONCEPT_ID" ||
		$mf[10] eq "SOURCE_AUI" ||
		$mf[10] eq "ROOT_SOURCE_AUI" ||
		$mf[10] eq "SOURCE_CUI" ||
		$mf[10] eq "ROOT_SOURCE_CUI" ||
		$mf[10] eq "SOURCE_DUI" ||
		$mf[10] eq "ROOT_SOURCE_DUI" ||
		$mf[10] eq "SOURCE_RUI" ||
		$mf[10] eq "SRC_REL_ID" ||
		$mf[10] eq "ROOT_SOURCE_RUI" 
		){
		if($bad_type < $limit){push(@bad_type,$_)}
		$bad_type++;
	 }	
	

	# F1: ID  F9: ID_TYPE
	unless(&check_id($mf[0],$mf[8])){
		unless($bad_idform1 > $limit){
			push(@bad_idform1, $_);
		}
		$bad_idform1++;
	}
	# F3: ID  F10: ID_TYPE
	unless(&check_id($mf[2],$mf[10])){
		unless($bad_idform3 > $limit){
			push(@bad_idform3, $_);
		}
		$bad_idform3++;
	}

	# OK
	# Must have Qualifiers in f 10/12 for certain Codes 
	if(($mf[8] eq "CODE_SOURCE")||($mf[8] eq "CODE_TERMGROUP")||($mf[8] eq "CODE_STRIPPED_SOURCE")||($mf[8] eq "CUI_STRIPPED_SOURCE")){ 
		if($mf[9] eq ''){
			if($bad_qual < $limit){push(@bad_qual,$_)}
			$bad_qual++;
		}
		else{	 # save the id_qualifier for report
			$id_qual10{$mf[9]}++;
		}
	}

	# Must have Qualifiers in f 10/12 for certain Codes 
	if(($mf[10] eq "CODE_SOURCE")||($mf[10] eq "CODE_TERMGROUP")||($mf[10] eq "CODE_STRIPPED_SOURCE")||($mf[10] eq "CUI_STRIPPED_SOURCE")){ 
		if($mf[11] eq ''){
			if($bad_qual < $limit){push(@bad_qual,$_)}
			$bad_qual++;
		}
		else{	 # save the id_qualifier for report
			$id_qual12{$mf[11]}++;
		}
	}
	
	}	# end of while(<INFILE>)
  
  
	&print_field_report("merge",$rec);

# take all the saids found above and check them against SAIDs in classes
  if($said_flg){
	my ($x,$z,$src,$str);
	foreach $x (sort(keys(%said_merge))){
		unless($said_class{$x}){
		&lookup_said($x);
		#$id_ntfnd{$src}++;
	 }
	}
 }
# print to FILE the counts of ID_QUALIFIER 1 & 2 if they exist
if(keys(%id_qual10)||keys(%id_qual12)){
	print $main::fh_file "\n----- ID QUALIFIERS -----\n";
	if(keys(%id_qual10)){ print $main::fh_file "Qualifiers found in Field 10\n";}
	foreach $qual (sort(keys(%id_qual10))){
		 printf $main::fh_file "%8s %8d\n", $qual,$id_qual10{$qual};
	 }
	if(keys(%id_qual12)){ print $main::fh_file "Qualifiers found in Field 12\n";}
	foreach $qual (sort(keys(%id_qual12))){
		printf $main::fh_file "%8s %8d\n", $qual,$id_qual12{$qual};
	}
}
# takes all the foreign SAIDs found above and creates an array suitable
# for printing with the print_error() rountine below
# found in QA3_util.pm
  
 $id_ntfnd =  &make_said_error_array();
  
	#printf $main::fh_summ "Error Counts\n";
 printf $main::fh_summ "%6d %s\n", $bad_fcnt, " Bad field count";
 printf $main::fh_summ "%6d %s\n", $bad_value, " Bad values in fields";
 printf $main::fh_summ "%6d %s\n", $bad_type, " Invalid type (Field 9)";
 printf $main::fh_summ "%6d %s\n", $bad_idform1, " Invalid ID (Field 9)";
 printf $main::fh_summ "%6d %s\n", $bad_idform3, " Invalid ID (Field 11)";
 printf $main::fh_summ "%6d %s\n", $bad_qual, " Missing Qualifier (Field 10/12)";
 printf $main::fh_summ "%6d %s\n", $bad_len, " Bad Field Lengths";  
 printf $main::fh_summ "%6d %s\n", $bad_mergeset, " Bad Merge Set Values";  
#printf $main::fh_summ "%6d %s\n", $id_ntfnd, " SAIDs not in classes";  
  
  if($said_flg){
	printf $main::fh_summ "%6d %s\n", $id_ntfnd, " SAIDs NOT found in classes";
	}
  else{
	printf $main::fh_summ "%s\n", "No CLASSES file, SAIDs NOT Checked";
	}  
  
  if($bad_len||$bad_value || $bad_fcnt || $bad_type || $bad_qual || $id_ntfnd || $bad_idform1 || $bad_idform3 || $bad_mergeset)
	{ 
	print "\nErrors found, see $main::ERR for details\n";
	print $main::fh_err "\n--------------- $ucfile ---------------\n";
	&print_error("Bad Field Lengths",$bad_len,@bad_len)if($bad_len);
	&print_error("Incorrect Field Count",$bad_fcnt,@bad_fcnt)if($bad_fcnt);
	&print_error("Bad Field Values",$bad_value,@bad_value)if($bad_value);
	&print_error("Missing Qualifiers",$bad_qual,@bad_qual)if($bad_qual);
	&print_error("Incorrect ID Type in Field 9 or 11",$bad_type,@bad_type)if($bad_type);
	&print_error("SAIDs not in Classes",$id_ntfnd,@id_ntfnd)if($id_ntfnd);
	&print_error("Invalid ID Form in F 9",$bad_idform1,@bad_idform1)if($bad_idform1);
	&print_error("Invalid ID Form in F 11",$bad_idform3,@bad_idform3)if($bad_idform3);
	&print_error("Bad or Missing Mergeset values (Fld. 8)",$bad_mergeset,@bad_mergeset)if($bad_mergeset);


	print $main::fh_err "\n";
	#print $main::fh_summ "\n";
	
	}
  
 }	# end of check_merge()

##########################################################################
# CHECK_TERMGROUP()
# termgroups.src specific tests
##########################################################################
# %class_termgrp has all of the termgroups found in classes
sub check_termgroup{
	my $file = shift;
	my(@tf);
	my ($err);
	my($bad_fcnt, $bad_val, $bad_termgrp);
	my(@bad_fcnt, @bad_val, @bad_termgrp);
	my(@bad_tty, $bad_tty);
	my($ucfile) = uc($file);
	#my(%tg);
	my($bad_supp,@bad_supp);
	@bad_len=(); 
	$bad_len = &ck_field_lens($file); 
	


	# used for field reports:
	my($len);
	local(%fcnts,%lo,%hi,$rec);
  
	$hashexists = keys(%class_termgrp);		# %class_termgrp created in check_classes()
	unless($hashexists){
		print <<"EOW";
	Termgroups NOT checked for valid values, see message in QA_FILE
EOW
		print $main::fh_summ <<"EOM";
  Termgroups are NOT being checked because there is no hash of the termgroups
  that exist in Classes. Likely this is because you are running QA on only
  the termgroups file. 'QA3.pl -f termgroups.src' 

  You need to run QA on the Classes file at the same time to collect 
  termgroups in order to do this check. 'QA3.pl'

  If you get this error message while running the full set of 
  QA tests, then you can consider this a true error.
	
EOM
	}
	
	if($mrdoc_exists){

	}
	else{
		$no_mrdoc++; 
	}
	

	# print tests to screen
	#print "\tField Lengths\n";	# printed in ck_field_lens()
	print "\tField Count\n";
	print "\tField Values\n";
	print "\tValid termgroups\n";
	print "\tMissing termgroups\n";
	print "\ttermgroup vs TTY\n";

	open(TERM, "$main::dir/$file") or die "Can't open $file, $!";
	while(<TERM>){
		chomp;
		@tf = split(/\|/);
	
	
	# this collects info on the length of the field and 
	# whether the field has a value
	# (does much the same as 'checkfields'
	for($i=0;$i<6;$i++){
		$len = length($tf[$i]);
		unless($rec){$lo{$i} = $len;$hi{$i}=$len }
			
		if($len == 0){} 

		$lo{$i} = $len unless($len > $lo{$i});
		$hi{$i} = $len unless($hi{$i} > $len);

		$fcnts{$i}++ if(length($tf[$i]));
	}
	 $rec++; 

	# count fields
	# should have 6 fields plus extra pipe at the end
		unless((tr/\|/\|/) == 6){
			push(@bad_fcnt, $_);
			++$bad_fcnt
		}
	# check for correct values in other fields
		unless(/^[A-Z_0-9\-]{4,20}\/\w{2,}\|[A-Z_0-9\-]{4,20}\/\w{2,}\|[YN]\|[YN]\|[YN]\|/o){
			push(@bad_val, $_); 
			++$bad_val; 
		 }

	# save all the termgroups
		$term_termgrp{$tf[0]}++;

		if($hashexists){
			unless($class_termgrp{$tf[0]}){
				push(@bad_termgrp, $_);
				$bad_termgrp++;
		 	}
		 }
	# check that termgroup matches TTY
		$tf[0] =~ /.*?\/(.*)$/;
		$tty = $1;
		unless($tty eq $tf[5]){
			push(@bad_tty, $_);
			$bad_tty++;
		}
	# field 3, suppressible, should be 'Y' for any TTY that is obsolete
	# the hash obsolete_tty is created by get_tty_info() in QA3_util.pm,
	# called from check_class()
		if($obsolete_tty{$tty} && $tf[2] ne 'Y'){
			push(@bad_supp, $_);
			$bad_supp++;
		}

	}	# end of while(<TERM>)


	&print_field_report("termgroups",$rec);
	
	# check termgroups in termgroups.src against what's in classes
	# each termgroup in classes should have a match in the termgroups hash
	# %class_termgrp is populated in check_class()
	foreach $term_termgrp(keys(%class_termgrp)){
		unless($term_termgrp{$term_termgrp}){
			push(@miss_termgrp, $term_termgrp);
			$miss_termgrp++;
		}
	}

 #printf $main::fh_summ "Error Counts\n";
	printf $main::fh_summ "%6d %s\n", $bad_len, " Bad Field Lengths";  
	printf $main::fh_summ "%6d %s\n", $bad_fcnt, " Bad Field Count";  
	printf $main::fh_summ "%6d %s\n", $bad_val, " Bad Field Values";  
	printf $main::fh_summ "%6d %s\n", $bad_termgrp, " Bad Termgroups";  
	printf $main::fh_summ "%6d %s\n", $miss_termgrp, " Missing Termgroups";  
	printf $main::fh_summ "%6d %s\n", $bad_tty, " Bad Termtype";  
	
	$err = ($bad_len+$bad_val+$bad_fcnt+$bad_termgrp+$miss_termgrp+$bad_tty+$no_mrdoc+$bad_supp);
	
	if($err){
	print "\nErrors found, see $main::ERR for details\n";
	print $main::fh_err "\n--------------- $ucfile ---------------\n";
	&print_error("Bad Field Lengths",$bad_len,@bad_len)if($bad_len);
	&print_error("Bad Field Count",$bad_fcnt,@bad_fcnt)if($bad_fcnt);
	&print_error("Bad Values",$bad_val,@bad_val)if($bad_val);
	&print_error("TTYs don't match Fields 1/6",$bad_tty,@bad_tty)if($bad_tty);
	&print_error("Warn: Termgroup not in classes",$bad_termgrp,@bad_termgrp)if($bad_termgrp);
	&print_error("Err: Termgroup in classes not in termgroups.src",$miss_termgrp,@miss_termgrp)if($miss_termgrp);
	&print_error("Err: Obsolete TTY not suppressible in field 3",$bad_supp,@bad_supp)if($bad_supp);
	&print_error("Err: No MRDOC.RRF, incomplete QA","","")if($no_mrdoc);

	#&print_error("Bad ",$bad_,@bad_)if($bad_);

	}	# end of if($err)
}	# end of check_termgroups


##########################################################################
# CHECK_SOURCE()
# sources.src specific tests
##########################################################################
# see file specs: meow.nlm.nih.gov/MEME3/Data/src_format.html
# %class_termgrp has all of the termgroups found in classes
sub check_source{
#print "start of call\n";
	my $file = shift;
	my(@sf);
	my ($err);
	my($bad_fcnt,$bad_src,$bad_lsrc,$bad_res,$bad_nsab,$bad_ssab,$bad_ver);
	my($bad_sfam,$bad_srcname,$bad_nlm_con,$bad_acq_con,$bad_con_con);
	my($bad_lic_con,$bad_inv,$bad_CT,$bad_lang,$bad_cite);

	my(@bad_fcnt,@bad_src,@bad_lsrc,@bad_res,@bad_nsab,@bad_ssab,@bad_ver);
	my(@bad_sfam,@bad_srcname,@bad_nlm_con,@bad_acq_con,@bad_con_con);
	my(@bad_lic_con,@bad_inv,@bad_CT,@bad_lang,@bad_cite);
	my($class_src,$bad_class_src,@bad_class_src);

	#my(%valid_lang);
	%valid_lang = ();

	# used for field reports:
	my($len);
	local(%fcnts,%lo,%hi,$rec);
	
	my($bad_src_match, @bad_src_match);

	my($ucfile) = uc($file);
	@bad_len=(); 
	$bad_len = &ck_field_lens($file); 
	#print "Term IDs file : $termids_file\n";
	&collect_sabs();	# make hash of valid SABs
	#%valid_lang = &get_valid_lang();
	&get_valid_lang;
	# print tests to screen
	#print "\tField Lengths\n"; # printed in ck_field_lens()
	print <<"EOT";
	Doing Tests:
	------------
	Field Count
	Field Values
	Source Name > 5 chars
	Low Source > 5 chars
	Restriction Level 0-3
	Normalized Source exists in termids
	Stripped Source exists in termids
	Version exists
	Source Family exists in termids
	Official Name exists in termids
	NLM Contact  supplied
	Acquistion Contact  supplied
	Content Contact  supplied
	License Contact supplied
	Inverter supplied
	Content Type
	Language
	Citation

EOT

open(INFILE, "$main::dir/$file") or die "Can't open $file, $!";
while(<INFILE>){
	chomp;
	@sf = split(/\|/);
	
	# this collects info on the length of the field and 
	# whether the field has a value
	# (does much the same as 'checkfields'
	for($i=0;$i<20;$i++){
		$len = length($sf[$i]);
		unless($rec){$lo{$i} = $len;$hi{$i}=$len }
			
		if($len == 0){} 

		$lo{$i} = $len unless($len > $lo{$i});
		$hi{$i} = $len unless($hi{$i} > $len);

		$fcnts{$i}++ if(length($sf[$i]));
	}
	$rec++; 

	# count fields
	# should have 21 fields, 20 data fields and an ending '|' 
	unless((tr/\|/\|/) ==  20) {
		unless($bad_fcnt > $limit){push(@bad_fcnt, $_)}
		++$bad_fcnt
		}
	
	# check field 1 for source name
	# source name could be something like MSH2002HMCE
	# which is not found in /u/umls/termids
	# so we check to see that there are at least 5 chars
	unless($sf[0] =~ /.{4,}/){
		push(@bad_src,"$.: $sf[0]");
		$bad_src++;
	}

	# save the source value to later check against classes
	$source_src{$sf[0]}++;

	# check to see if the source is in classes
	unless($class_src{$sf[0]}){
		push(@bad_src_match, "$.:$sf[0]");
		$bad_src_match++;
	}

	# check field 2 for low source name
	# low source name could be something like MSH2001HMCE
	# which is not found in /u/umls/termids
	# so we check to see that there are at least 3 chars
	unless($sf[1] =~ /.{3,}/){
		push(@bad_lsrc,"$.: $sf[1]");
		$bad_lsrc++;
	}

	# check field 3 for restriction level
	unless($sf[2] =~ /[0-4]/){
		push(@bad_res,"$.: $sf[2]");
		$bad_res++;
	}

	# source name is usually a norm source, e.g., MSH2002
	# but it also could be a stripped source, e.g., MTHMSTFRE
	# check field 4 for source name (norm. source)
	unless(($nsab{$sf[3]})||($ssab{$sf[3]})){
		push(@bad_nsab,"$.: $sf[3]");
		$bad_nsab++;
	}

	# check field 5 for source name (stripped source)
	unless($ssab{$sf[4]}){
		push(@bad_ssab,"$.: $sf[4]");
		$bad_ssab++;
	}

	# check field 6 for version 
	# can't be blank, has to be at least one char
	unless($sf[5] =~ /.{1,}/){
		push(@bad_ver,"$.: $sf[5]");
		$bad_ver++;
	}

	# check field 7 for source family
	unless(($ssab{$sf[6]})||$nsab{$sf[6]}){
		push(@bad_sfam,"$.: $sf[6]");
		$bad_sfam++;
	}

	# check field 8 for official name
	unless($sf[7] =~ /.{6,}/){
		push(@bad_srcname,"$.: $sf[7]");
		$bad_srcname++;
	}

	# check field 9 for nlm_contact
	unless($sf[8] =~ /.{2,}@.{2,}\..*?/){
		push(@bad_nlm_con,"$.: $sf[8]");
		$bad_nlm_con++;
	}

	# check field 10 for acquisition_contact
	unless($sf[9] =~ /.{2,}@.{2,}\..*?/){
		push(@bad_acq_con,"$.: $sf[9]");
		$bad_acq_con++;
	}

	# check field 11 for content_contact
	unless($sf[10] =~ /.{2,}@.{2,}\..*?/){
		push(@bad_con_con,"$.: $sf[10]");
		$bad_con_con++;
	}

	# check field 12 for license_contact
	unless($sf[11] =~ /.{2,}@.{2,}\..*?/){
		push(@bad_lic_con,"$.: $sf[11]");
		$bad_lic_con++;
	}

	# check field 13 for inverter 
	unless($sf[12] =~ /.{2,}@.{2,}\..*?/){
		push(@bad_inv,"$.: $sf[12]");
		$bad_inv++;
	}

	# Check field 14 for Context Type
	unless($sf[13] eq ""){
		unless(($sf[13]eq"FULL")||
			($sf[13] eq "TITLE")||
			($sf[13] eq "MINI")||
			($sf[13] eq "FULL-MULTIPLE")||
			($sf[13] eq "FULL-NOSIB")||
			($sf[13] eq "FULL-MULTIPLE-NOSIB")||
			($sf[13] eq "TITLE-MULTIPLE")||
			($sf[13] eq "MINI-MULTIPLE")){
			push(@bad_CT,"$.: $sf[13]");
			$bad_CT++;
		}
	}

	# Check field 16 for Valid Language
	# contents of Language field must be found in list
	# of valid languages
	unless($valid_lang{$sf[15]}){
		push(@bad_lang,"$.: $sf[15]");
		$bad_lang++;
	}

	# Check field 17 for Citation info
	$cite_len = length($sf[16]);
	if($cite_len < 6){
		push(@bad_cite, "$. : $_\n");
		$bad_cite++;
	}	
}	# end of while(<sources.src>)
	
# check Class source against Sources termgroups
foreach $class_src (keys(%class_src)){
	unless($source_src{$class_src}){
		push(@bad_class_src, "$.:$class_src");
		$bad_class_src++;
	}
}
&print_field_report("sources",$rec);

#printf $main::fh_summ "Error Counts\n";
printf $main::fh_summ "%6d %s\n", $bad_len, " Field Length";  
printf $main::fh_summ "%6d %s\n", $bad_fcnt, " Field Count";  
printf $main::fh_summ "%6d %s\n", $bad_src, " Field  1: Source Name Value";  
printf $main::fh_summ "%6d %s\n", $bad_src_match, " Field  1: Source Name not Classes";  
printf $main::fh_summ "%6d %s\n", $bad_lsrc, " Field  2: Low Source Value";  
printf $main::fh_summ "%6d %s\n", $bad_res, " Field  3: Restriction Level Value";  
printf $main::fh_summ "%6d %s\n", $bad_nsab, " Field  4: Norm Source Value";  
printf $main::fh_summ "%6d %s\n", $bad_ssab, " Field  5: Stripped Source Value";  
printf $main::fh_summ "%6d %s\n", $bad_ver, " Field  6: Version Value";  
printf $main::fh_summ "%6d %s\n", $bad_sfam, " Field  7: Source Family Value";  
printf $main::fh_summ "%6d %s\n", $bad_srcname, " Field  8: Official Name Value";  
printf $main::fh_summ "%6d %s\n", $bad_nlm_con, " Field  9: NLM Contact Value";  
printf $main::fh_summ "%6d %s\n", $bad_acq_con, " Field 10: Acquistion Contact Value";  
printf $main::fh_summ "%6d %s\n", $bad_con_con, " Field 11: Content Contact Value";  
printf $main::fh_summ "%6d %s\n", $bad_lic_con, " Field 12: License Contact Value";  
printf $main::fh_summ "%6d %s\n", $bad_inv, " Field 13: Inverter value";  
printf $main::fh_summ "%6d %s\n", $bad_CT, " Field 14: Context Type";  
printf $main::fh_summ "%6d %s\n", $bad_lang, " Field 16: Language";  
printf $main::fh_summ "%6d %s\n", $bad_cite, " Field 17: Citation String";  

$err=$bad_fcnt+$bad_src+$bad_lsrc+$bad_res+$bad_nsab+$bad_ssab+$bad_ver+$bad_sfam+$bad_srcname+$bad_nlm_con+$bad_acq_con+$bad_con_con+$bad_lic_con+$bad_inv+$bad_CT+$bad_lang+$bad_cite+$bad_src_match+$bad_class_src;

if($err){
	print "\nErrors found, see $main::ERR for details\n";
	print $main::fh_err "\n--------------- $ucfile ---------------\n";
	&print_error("Bad Field Lengths",$bad_len,@bad_len)if($bad_len);
	&print_error("Bad Field Count, should be 20)",$bad_fcnt,@bad_fcnt)if($bad_fcnt);
	&print_error("Incorrect or Missing Source Name in Field 1 ",$bad_src,@bad_src)if($bad_src);
	&print_error("Source Name not in Classes",$bad_src_match,@bad_src_match)if($bad_src_match);
	&print_error("Incorrect or Missing Low Source Name in Field 2 ",$bad_lsrc,@bad_lsrc)if($bad_lsrc);
	&print_error("Incorrect or Missing Restriction Level in Field 3 ",$bad_res,@bad_res)if($bad_res);
	&print_error("Source Name not found in termids file, Field 4",$bad_nsab,@bad_nsab)if($bad_nsab);
	&print_error("Source Name not found in termids file, Field 5",$bad_ssab,@bad_ssab)if($bad_ssab);
	&print_error("Incorrect or Missing Version in Field 6 ",$bad_ver,@bad_ver)if($bad_ver);
	&print_error("Incorrect or Missing Source Family in Field 7 ",$bad_sfam,@bad_sfam)if($bad_sfam);
	&print_error("Incorrect or Missing Official Name in Field 8 ",$bad_srcname,@bad_srcname)if($bad_srcname);
	&print_error("Incorrect or Missing NLM contact in Field 9 ",$bad_nlm_con,@bad_nlm_con)if($bad_nlm_con);
	&print_error("Incorrect or Missing Acquisition Contact in Field 10 ",$bad_acq_con,@bad_acq_con)if($bad_acq_con);
	&print_error("Incorrect or Missing Content Contact in Field 11 ",$bad_con_con,@bad_con_con)if($bad_con_con);
	&print_error("Incorrect or Missing License Contact in Field 12 ",$bad_lic_con,@bad_lic_con)if($bad_lic_con);
	&print_error("Incorrect or Missing Inverter Contact in Field 13 ",$bad_inv,@bad_inv)if($bad_inv);
	&print_error("Incorrect or Missing Context Type in Field 14 ",$bad_CT,@bad_CT)if($bad_CT);
	&print_error("Invalid or Missing Language in Field 16 ",$bad_lang,@bad_lang)if($bad_lang);
	&print_error("Check for Missing Citation in Field 17 ",$bad_cite,@bad_cite)if($bad_cite);
	&print_error("Source in Classes not found in Sources ",$bad_class_src,@bad_class_src)if($bad_class_src);

	}	# end of if($err)
 }	# end of check_source() (sources.src)

#-----------------------------------------------------------------#
# CHECK_TREEPOS()
#-----------------------------------------------------------------#
# we assume that if treepos is being checked that there is a
# source_atoms.dat file AND that it has already been checked
# it is an error if that file doesn't exist and therefore treepos.dat
# is NOT checked
#
# if a cxt/ exists, there should be source_atoms.dat, treepos.dat
# check for the hash of saids from source_atoms.dat 
# create if it doesn't exist
# create hash of saids in classes if doesn't exist
#
# checks to perform:
# one row exists that is the root (probably the first row, but not nec.)
# the first said in field 3 is the root said
# the last said in field 3 is the same as the said in field 
# all saids in treepos.dat are in source_atoms.dat, classes_atoms.src
#  
# 
# additional?
# all saids in exclude_list.dat are in source_atoms.dat, classes_atoms.src

# treepos.dat:
# 68041003||68041003||
# 68041007||68041003.68041007||
# 68041009||68041003.68041007.68041009||
# 68041011||68041003.68041007.68041011||
# 68041013||68041003.68041007.68041013||

sub check_treepos{
	my($treepos)=shift;
	my($root,$a,$b,$c,$no_sa_flg);
	my($err_str, $err, $treenum);
	my($bad_node,$bad_root_field);
	my(@bad_node,@bad_root_field);
	my($bad_tp_root,$bad_tp_said,$bad_sa_said,$bad_cl_said);
	my(@bad_tp_root,@bad_tp_said,@bad_sa_said,@bad_cl_said);

	print "Treepos: $treepos\n";
	$treepos = $treepos;
	printf $main::fh_summ "\n";
	printf $main::fh_summ "$treepos\n";
	print FILE "\n$treepos\n";
	#printf $main::fh_summ "Error Counts\n";

	# if %said (SAIDs from classes_atoms.src) doesn't exist, create it
	unless(defined(%said)){
		if($err_str=&get_class_saids()){
			print "$err_str\n";
			print "Failed running checks on treepos.dat\n";
			print SUMM "treepos.dat was not checked, test failed\n";
			return;
		}
	}
	if(-e "$main::dir/../cxt/source_atoms.dat"){
		unless(defined(%sa)){
			if($err_str=&get_sa_saids()){
				print "$err_str\n";
				print "Can't find file 'source_atoms.dat', checking treepos.dat\n";
				print "against source_atoms.dat is disabled.\n";
				print $main::SUMM "Can't find file 'source_atoms.dat', checking treepos.dat\n";
				print $main::SUMM "against source_atoms.dat is disabled.\n";
				$no_sa_flg++;
			}
		}
	}
	else{
		print "Can't find file 'source_atoms.dat', checking treepos.dat\n";
		print "against source_atoms.dat is disabled.\n";
		print $main::SUMM "Can't find file 'source_atoms.dat', checking treepos.dat\n";
		print $main::SUMM "against source_atoms.dat is disabled.\n";
		$no_sa_flg++;
	}

	# check for a root record, has to be one
	open (TP, "$main::dir/../cxt/$treepos") or die "Can't open/find $treepos\n";
	while(<TP>){
		($a,$b,$c)=split(/\|/);
		if($a == $c){$root=$a;last}
	}
	unless($root){
		push(@bad_tp_root,"No Root was defined");
		$bad_tp_root++;
		printf $main::fh_summ "No Root in treepos.dat, tests not run, fix and re-run\n";
		print FILE "No Root in treepos.dat, tests not run, fix and re-run\n\n";
		print "No Root in treepos.dat, tests not run, fix and re-run\n";
		&print_error("No Root Record",$bad_tp_root,@bad_tp_root)if($bad_tp_root);
		return;
	}
	seek(TP,0,0);	# back to the beginning
	push(@bad_root_field, "Line #  Record");
	push(@bad_root_field, "------  -----------------------");

	push(@bad_node, "Line #    Field 1    Last value in Field 3");
	push(@bad_node, "--------  ---------- ---------------------");

	push(@bad_sa_said, "Line #    SAID not in source_atoms.dat");
	push(@bad_sa_said, "--------  -----------------------");
	while(<TP>){
		chomp;
		$treepos_rec_cnt++;
		@F = split(/\|/);
		@tr = split(/\./, $F[2]);
		# the first said in field 3 is the root said
		unless($tr[0] == $root){
			$bad_root_field++;
			unless($bad_root_field > $limit){
				push(@bad_root_field, (sprintf("%6d %4d", $.,$F[0])));
			}
		}
		# the last said in field 3 is the same as the said in field 1
		unless($F[0] == $tr[$#tr]){
			$bad_node++;
			unless($bad_node > $limit){
				push(@bad_node, (sprintf("%8d  %-10d %-10d", $.,$F[0],$tr[$#tr])));
			}
		}
		# all saids in treepos.dat are in source_atoms.dat
		foreach $treenum (@tr){
			unless($sa{$treenum}){
				$bad_sa_said++;
				unless($bad_sa_said > $limit){
					push(@bad_sa_said, (sprintf("%8d %-10d",$.,$treenum)));
				}
			}
		# old style files may have a root said that is not in classes
		# since this root appears in each record, it would be an
		# error for each record
		# removed for now
## 		# all saids in treepos.dat are in classes_atoms.src
## 			unless($said{$treenum}){
## 				$bad_cl_said++;
## 				unless($bad_cl_said > $limit){
## 					push(@bad_cl_said, (sprintf("%4d %s %8d", $.," ", $treenum)));
## 				}
## 			}
	}
}	# end of while(<TP>)

# print stats to the QA report file
#printf $main::fh_summ "Error Counts\n";
printf $main::fh_summ "%6d %s\n", $bad_root_field, "Root error (Field 3)";  
printf $main::fh_summ "%6d %s\n", $bad_sa_said, "SAIDs not in classes";
printf $main::fh_summ "%6d %s\n", $bad_node, "Leaf Node does not match Field 1";  


$err=($bad_root+$bad_root_field+$bad_sa_said+$bad_node);
if($err){
	print "\nErrors found, see $main::ERROR for details\n";

	print $main::fh_err "\n--------------- $dir/cxt/treepos.dat ---------------\n";
	&print_error(" Root in Hierarchy doesn't match Root Value",$bad_root,@bad_root_field)if($bad_root_field);
	&print_error("Leaf node does not match Field 1",$bad_node,@bad_node) if($bad_node);
	&print_error("SAIDs not found in source_atoms.dat",$bad_sa_said,@bad_sa_said) if($bad_sa_said);


	&print_error("Bad Field Lengths",$bad_len,@bad_len)if($bad_len);
	&print_error("Bad Field Count",$bad_fcnt,@bad_fcnt)if($bad_fcnt);
	}	# end of if($err)
}	# end of check_treepos()

#-----------------------------------------------------------------#
# CHECK_CONTEXTS()
#-----------------------------------------------------------------#
# checks to perform:
# every SAID in the PAR/tree path should be in classes_atoms.dat
# every tree top in the PAR/tree path should be the same SAID
# the count of PAR records should be equal or one less than the treepos count
# 

sub check_contexts{
# contexts.src:
# SAID_self|REL|?|
#  1	SAID_self - SAID of the record
#  2	REL - PAR/SIB
#  3 	?
#	4  ? - Parent SAID
	
my($contexts)=shift;

$contexts = "$main::dir"."/".$contexts;
print "\ncontexts.src: $contexts\n";
$pwd = `pwd`;
print "PWD: $pwd\n";
printf $main::fh_summ "\n";
printf $main::fh_summ "$contexts\n";
print FILE "\n$contexts\n";
#printf $main::fh_summ "Error Counts\n";

my($tr,@F,%cont_root,$i,$err,$tree_cont_diff);
my($treepos_rec_cnt,$contexts_rec_cnt);
my($err_str);
my(@cont_root,$cont_rpt,$bad_root_cnt,$par_cnt);
my($root_said_cnt,@cont_rpt);
my(@bad_said,$bad_said);

unless(scalar(keys(%sa))){
	#$source_atom = "$main::dir/cxt/source_atoms.dat";
	open (SA, "$main::dir/../cxt/source_atoms.dat") or die "In check_contexts(); Can't open/find $main::dir/../cxt/source_atoms.dat\n";
	while(<SA>){
		@F = split(/\|/);
		$sa{$F[0]}++;	# save the SAIDs in source_atoms.dat to chk treepos
	}
	close SA;
}
# if %said (SAIDs from classes_atoms.src) doesn't exist, create it
unless(defined(%said)){
	if($err_str=&get_class_saids()){
		print "$err_str\n";
		print "Failed running checks on contexts.dat\n";
		print SUMM "contexts.dat was not checked, test failed\n";
		return;
	}
}
	open (CONT, "$main::dir/contexts.src") or die "In check_contexts(); Can't open/find $main::dir/contexts.src\n";
	while(<CONT>){
		chomp;
		$contexts_rec_cnt++;
		@F =split(/\|/);
		# if PAR check the tree path
		if($F[1] eq "PAR"){
			@tr = split(/\./, $F[7]);
			$cont_root{$tr[0]}++;
			for($i=1;$i<=$#tr;$i++){
				unless($said{$tr[$i]}){
					unless($bad_said > $limit){
						push(@bad_said, "$.:$tr[$i]|$_");
					}
					$bad_said++;
				}
			}
			# count all the PAR records to compare against treepos counts
			$par_cnt++;
		}
}	# end of while(<CONT>)

	# the count of unique SAIDs in the "root" position should be 1
	if(($root_said_cnt = scalar(keys(%cont_root))) != 1){
		push(@cont_rpt, "ERROR: Too many root SAIDs!\n");
		push(@cont_rpt, "There are $root_said_cnt root SAIDs, there should be 1\n");
		foreach $root_key (keys(%cont_root)){
			unless($bad_root_cnt > $limit){ push(@cont_rpt, "$root_key\n")}
			$bad_root_cnt++;
		}
		push(@cont_rpt, "\n");
		
		
	}

#		$treepos_rec_cnt
#		$contexts_rec_cnt
	# treepos should be the same or greater by 1
	# than the count of PAR records in contexts
	unless(defined($treepos_rec_cnt)){
	print "$main::dir/../cxt/treepos.dat\n";
		if(-e "$main::dir/../cxt/treepos.dat"){
			$treepos_rec_cnt = ` wc -l $main::dir/../cxt/treepos.dat`;
			$tree_cont_diff = $treepos_rec_cnt - $par_cnt;
			if(($tree_cont_diff == 1) || ($tree_cont_diff == 0)){ }
			elsif(($tree_cont_diff > 1) || ($tree_cont_diff < 0)){
				$bad_count++;
				push(@bad_count, "Counts between treepos.dat and contexts.src don't match\n");
				push(@bad_count, "treepos.dat should equal or be greater by one than contexts.src\n");
				push(@bad_count, "Treepos.dat: $treepos_rec_cnt - Contexts.src: $contexts_rec_cnt\n");

	}
		}
		else{
			$bad_count++;
			push(@bad_count, "No treepos.dat found, can't do check");
		}
	}
	
# print stats to the QA report file
#printf $main::fh_summ "Error Counts\n";
printf $main::fh_summ "%6d %s\n", $bad_root_field, "Root error (Field 3)";  
printf $main::fh_summ "%6d %s\n", $bad_sa_said, "SAIDs not in classes";
printf $main::fh_summ "%6d %s\n", $bad_node, "Leaf Node does not match Field 1";  

$err=($bad_said+$bad_count+$bad_root_cnt);
if($err){
	print "\nErrors found, see $main::ERROR for details\n";

	print $main::fh_err "\n--------------- $dir/cxt/contexts.src ---------------\n";
	#&print_error(" Root in Hierarchy doesn't match Root Value",$bad_root,@bad_root_field)if($bad_root_field);
	#&print_error("Leaf node does not match Field 1",$bad_node,@bad_node)if($bad_node);
	&print_error("SAIDs not found in source_atoms.dat",$bad_said,@bad_said)if($bad_said);

	# print other error reports
	if($bad_root_cnt){
		foreach $line (@cont_rpt){print $main::fh_err $line}
	}
	if($bad_count){ foreach $line (@bad_count){ print $main::fh_err $line} }

	}	# end of if($err)
}	# end of check_contexts()



#---------------------------------------------------------------------#
# CHECK_SOURCE_ATOMS()
#---------------------------------------------------------------------#
# source_atoms.dat
# 8041000|SRC/RPT|V-MSH|Medical Subject Headings|
# 68041001|SRC/RAB|V-MSH|MSH|
# 68041002|SRC/SSN|V-MSH|MeSH|
# 68041003|SRC/RHT|V-MSH|MeSH|
# 68041004|SRC/VPT|V-MSH2003_2002_08_14|Medical Subject Headings, 2002_08_14|
# 68041005|SRC/VAB|V-MSH2003_2002_08_14|MSH2003_2002_08_14|
#
# checks to perform
# 	each SAID is in classes
# 	each termgroup is make up of the SAB, a '/', and a TTY
#

sub check_source_atoms{
	my($source_atom) = shift;
	my($err_str,$err,$tg_err);
	my(@bad_sa_said,@bad_tg);
	my($bad_sa_said,$bad_tg);

	$source_atom = "$main::dir/../cxt/source_atoms.dat";
	# termgroup = SAB/TTY
	if(defined($sab)){
		print "SAB: $sab\n";
	}
	else{
		print "NO SAB given, run with checking for classes turned on\n";
		print "or supply an SAB with '$0 -s SAB'\n";
		$no_sab++;
	}

	# if %said doesn't exist, create it
	unless(defined(%said)){
		if($err=&get_class_saids()){
			print "$err\n";
			print "Failed running checks on source_atoms.dat\n";
			print SUMM "source_atoms.dat was not checked, test failed\n";
			return;
		}
	}
	# this get pre-pended in case we need it
	push(@bad_sa_said, "Line #    SAID not in classes_atoms.src");
	push(@bad_sa_said, "--------  -----------------------");
	open (SA, "$source_atom") or die "In check_source_atoms; Can't open/find $source_atom\n";
	while(<SA>){
		@F = split(/\|/);
		$sa{$F[0]}++;	# save the SAIDs in source_atoms.dat to chk treepos

	unless($said{$F[0]}){
		$bad_sa_said++;
		unless($bad_sa_said > $limit){
			push(@bad_sa_said, (sprintf("%6d %-8d",$.,$F[0])));
		}
	}

## re-written 01/10/03 because SABs can have '-' in them
## and that messes up the match pattern

# if we don't have an SAB just do a minimal check
if($no_sab){
		unless($F[1] =~ /\w{3,25}\/\w{2,4}/){ $tg_err++}
	}
	# otherwise the SAB is either "SRC" 
	elsif($F[1] eq "SRC"){
		unless($F[1] =~ /SRC\/\w{2,4}/){ $tg_err++}
	}
	# or it's an actual SAB
	else{
		unless($F[1] =~ /$sab\/\w{2,4}/){ $tg_err++}
	}
	
## 		if($no_sab){
## 			unless($F[1] =~ /\w{3,25}\/\w{2,4}/){ $tg_err++}
## 		}
## 		else{
## 			unless($F[1] =~ /["$sab"|SRC]\/\w{2,4}/){ $tg_err++}
## 		}
## 		if($tg_err){
## 			$bad_tg++;
## 			unless($bad_tg > $limit){
## 				push(@bad_tg, "$.: $F[1]");
## 			}
## 			$tg_err = 0;
## 		}
	}

	#printf $main::fh_summ "$source_atom\n";
	#printf $main::fh_summ "Error Counts\n";

# print stats to the QA report file
#printf $main::fh_summ "Error Counts\n";
printf $main::fh_summ "%6d %s\n", $bad_sa_said, "SAID errors";  
printf $main::fh_summ "%6d %s\n", $bad_tg, "Termgroup errors";  


	$err=($bad_tg+$bad_sa_said);
	if($err){
		print "\nErrors found, see $main::ERROR for details\n";
		print $main::fh_err "\n--------------- $dir/source_atoms.dat ---------------\n";
		&print_error("Bad Termgroup",$bad_tg,@bad_tg)if($bad_tg);
		&print_error("SAID not in Classes",$bad_sa_said,@bad_sa_said)if($bad_sa_said);
	}

}	# end of check_source_atom()


1;




