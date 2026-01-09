#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package iutl;
# takes an "id" and and "id_type"
sub checkId {
  my($self, $id, $type) = @_;
	
  # AUI: in NCI-MEME, 'A' followed by 7 digits
  #      in NLM, 'A' followed by 7 or 8 digits, (new AUIs are now 8)
  # if the id for the type matches the pattern return 1, else 0
 SWITCH: {
    if ($type eq 'AUI') {
      return(($id =~ /^A\d{7,8}$/)?1:0);last SWITCH;
    }
    if ($type eq 'SRC_ATOM_ID') {
      return($id =~ /^\d{7,9}$/)?1:0; last SWITCH;
    }
    if ($type eq 'ATOM_ID') {
      return(($id =~ /^\d{4,}$/)?1:0);last SWITCH;
    }
    if ($type eq 'CONCEPT_ID') {
      return(($id =~ /^\d{4,}$/)?1:0);last SWITCH;
    }
    if ($type eq 'CUI') {
      return(($id =~ /^C\d{7,}$/)?1:0);last SWITCH;
    }
    if ($type eq 'CUI_STRIPPED_SOURCE') {
      return(($id =~ /^C\d{7,}$/)?1:0);last SWITCH;
    }
    if ($type eq 'CUI_SOURCE') {
      return(($id =~ /^C\d{7,}$/)?1:0);last SWITCH;
    }
    if ($type eq 'CODE_STRIPPED_TERMGROUP') {
      return(($id =~ /.{3,}/)?1:0);last SWITCH;
    }
    return 1;
    # these are not needed.

    if ($type eq 'CODE_SOURCE') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'CODE_STRIPPED_SOURCE') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'CODE_TERMGROUP') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'CODE_ROOT_TERMGROUP') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'SOURCE_AUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'SOURCE_CUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'SOURCE_DUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'SOURCE_RUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'ROOT_SOURCE_AUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'ROOT_SOURCE_DUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'ROOT_SOURCE_CUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
    if ($type eq 'ROOT_SOURCE_RUI') {
      return(($id =~ /.+/)?1:0);last SWITCH;
    }
  }


}								# end of check_id()


{
  my %validStys = ();
  my $stysIN  = 0;
  sub validStyP {
    my ($self, $sty) = @_;
    if ($stysIN == 0) {
      open(STY, "<$ENV{INV_HOME}/etc/valid_stys")
		or die "Could not open valid_stys file in etc directory.\n";
      while (<STY>) {
		chomp;
		next if (/^(\s)*\#/);
		$validStys{"$_"}++;
      }
      my $temp = keys %validStys;
      close(STY);
      $stysIN = 1;
    }
    if (defined($validStys{"$sty"})) {
      return 1;
    }
    return 0;
  }
}

# strip blanks (at begin, end and more than 1 blank) in the given line.
# input - a string.
# output - string with blanks stripped.
sub stripBlanks {
  my($self, $str, $doQuotes, $doBars) = @_;

  $str =~ s/\s{2,}/ /g;			# more than 1 blanks to 1 blank
  $str =~ s/^\s//;			# strip leading blanks 
  $str =~ s/\s$//;			# strip trailing blanks

  if ($doQuotes == 1) {
    $str =~ s/^[ ]*//;			# strip leading blanks 
    $str =~ s/[ ]*$//;			# strip trailing blanks

    # remove leading and trainling double quotes only if they match
    if ($str =~ /^\"/ && $str =~ /\"$/) {
      $str =~ s/^\"//;			# strip leading double quote
      $str =~ s/\"$//;			# strip trailing double quote
    }
  }
  if ($doBars == 1) {           # remove bars if any at ends.
    $str =~ s/^\|//;
    $str =~ s/\|$//;
  }
  return $str;
}

# line, [seperator - \t]  => chop and trim individual elements and return 
# a list containing the elements.
sub catLine {
  my ($self, $str, $sep) = @_;
  if (!defined($sep)) {
	$sep = '\t';
  }
  ;

  chomp($str);
  # remove dos line endings, if any.
  $str =~ s/\r$//;
  return map {iutl->stripBlanks($_, 0, 1)} (split (/$sep/,$str));
}

# given a list of strings, checks if all of them are same or not.
sub sameStrings {
  my ($self, @strs) = @_;
  my $str = $strs[0];
  my $ele;
  foreach $ele (@strs) {
    return 0 if ($str ne $ele);
  }
  return 1;
}

{
  our %durations = ();

  sub startClock {
    my ($self, $which) = @_;
    $durations{"$which"} = time();
  }

  sub endClock {
    my ($self, $which) = @_;
    my $tm = time();
    $tm = $tm - $durations{"$which"};
    my $tms = $tm % 60;
    $tm = ($tm - $tms) / 60;
    my $tmm = $tm % 60;
    my $tmh = ($tm - $tmm) / 60;
    return "$tmh:$tmm:$tms";
  }
}

use Encode;
use Encode::Encoder;
# infile, encoding scheme, outFile
sub convertRaw2Utf {
  my ($self, $rawFile, $encScheme, $utfFile) = @_;
  print "inpFile: $rawFile\tcoding: $encScheme\toutFile: $utfFile\n";

  die "Encoding: $encScheme not found\n"
    unless grep { $_ eq $encScheme } Encode->encodings(":all");

  die "No encoder found for: $encScheme\n"
    unless find_encoding($encScheme)->perlio_ok;

  open(IN, "<:encoding($encScheme)", "$rawFile") or
    die "Could not open $rawFile\n";
  open (OUT, ">:utf8", $utfFile) or die "Could not open $utfFile\n";

  while (<IN>) {
    s/\r$//;
    print OUT;
  }
  close(IN);
  close(OUT);
}

# inputFile, reference to a hash, countWhiteSpace[0/1], encoding[utf];
sub charCount {
  my ($self, $iFile, $counts, $skipWS, $mode) = @_;

  if (defined($mode)) {
    die "Encoding: $mode not found\n"
      unless grep { $_ eq $mode } Encode->encodings(":all");

    die "No encoder found for: $mode\n"
      unless find_encoding($mode)->perlio_ok;
    open(IN, "<:encoding($mode)", $iFile) or die "Could not open $iFile\n";
  } else {
    open (IN, "<:utf8", $iFile) or die "Could not open $iFile\n";
  }

  while (<IN>) {
    @_ = split //;
    for (@_) { 
      if ($skipWS == 1) {
		$$counts{$_}++ unless /\w/;
	  } else {
		$$counts{$_}++;
	  }
	  ;
    }
  }
  close(IN);
}

sub cleanLine {
  shift;                                                # skip $self.
  $_ = shift;
  # make high order bit substitution.
  # clean all forbidden characters
  s/\x{00A0}/ /g;     #NO-BREAK SPACE
  s/\x{00AB}/\"/g;    #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
  s/\x{00AD}/\-/g;    #SOFT HYPHEN
  s/\x{00B4}/\'/g;    #ACUTE ACCENT
  s/\x{00BB}/\"/g;    #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
  s/\x{01C0}/\|/g;    #LATIN LETTER DENTAL CLICK
  s/\x{01C3}/\!/g;    #LATIN LETTER RETROFLEX CLICK
  s/\x{02B9}/\'/g;    #MODIFIER LETTER PRIME
  s/\x{02BA}/\"/g;    #MODIFIER LETTER DOUBLE PRIME
  s/\x{02BC}/\'/g;    #MODIFIER LETTER APOSTROPHE
  s/\x{00F7}/\//g;    #DIVISION SIGN
  s/\x{02C4}/\^/g;    #MODIFIER LETTER UP ARROWHEAD
  s/\x{02C6}/\^/g;    #MODIFIER LETTER CIRCUMFLEX ACCENT
  s/\x{02C8}/\'/g;    #MODIFIER LETTER VERTICAL LINE
  s/\x{02CB}/\`/g;    #MODIFIER LETTER GRAVE ACCENT
  s/\x{02CD}/\_/g;    #MODIFIER LETTER LOW MACRON
  s/\x{02DC}/\~/g;    #SMALL TILDE
  s/\x{0300}/\`/g;    #COMBINING GRAVE ACCENT
  s/\x{0301}/\'/g;    #COMBINING ACUTE ACCENT
  s/\x{0302}/\^/g;    #COMBINING CIRCUMFLEX ACCENT
  s/\x{0303}/\~/g;    #COMBINING TILDE
  s/\x{030B}/\"/g;    #COMBINING DOUBLE ACUTE ACCENT
  s/\x{030E}/\"/g;    #COMBINING DOUBLE VERTICAL LINE ABOVE
  s/\x{0331}/\_/g;    #COMBINING MACRON BELOW
  s/\x{0332}/\_/g;    #COMBINING LOW LINE
  s/\x{0338}/\//g;    #COMBINING LONG SOLIDUS OVERLAY
  s/\x{0589}/\:/g;    #ARMENIAN FULL STOP
  s/\x{05C0}/\|/g;    #HEBREW PUNCTUATION PASEQ
  s/\x{05C3}/\:/g;    #HEBREW PUNCTUATION SOF PASUQ
  s/\x{066A}/\%/g;    #ARABIC PERCENT SIGN
  s/\x{066D}/\*/g;    #ARABIC FIVE POINTED STAR
  s/\x{200B}/ /g;     #ZERO WIDTH SPACE
  s/\x{2010}/\-/g;    #HYPHEN
  s/\x{2011}/\-/g;    #NON-BREAKING HYPHEN
  s/\x{2012}/\-/g;    #FIGURE DASH
  s/\x{2013}/\-/g;    #EN DASH
  s/\x{2014}/\-/g;    #EM DASH
  s/\x{2015}/\--/g;   #HORIZONTAL BAR
  s/\x{2016}/\||/g;   #DOUBLE VERTICAL LINE
  s/\x{2017}/\_/g;    #DOUBLE LOW LINE
  s/\x{2018}/\'/g;    #LEFT SINGLE QUOTATION MARK
  s/\x{2019}/\'/g;    #LEFT SINGLE QUOTATION MARK
  s/\x{201A}/\,/g;    #SINGLE LOW-9 QUOTATION MARK
  s/\x{201B}/\'/g;    #SINGLE HIGH-REVERSED-9 QUOTATION MARK
  s/\x{201C}/\"/g;    #LEFT DOUBLE QUOTATION MARK
  s/\x{201D}/\"/g;    #RIGHT DOUBLE QUOTATION MARK
  s/\x{201E}/\"/g;    #DOUBLE LOW-9 QUOTATION MARK
  s/\x{201F}/\"/g;    #DOUBLE HIGH-REVERSED-9 QUOTATION MARK
  s/\x{2022}/\*/g;    #BULLET
#  s/\x{202F}/ /g;     #NARROW NO-BREAK SPACE
  s/\x{2032}/\'/g;    #PRIME
  s/\x{2033}/\"/g;    #DOUBLE PRIME
  s/\x{2034}/\'''/g;  #TRIPLE PRIME
  s/\x{2035}/\`/g;    #REVERSED PRIME
  s/\x{2036}/\"/g;    #REVERSED DOUBLE PRIME
  s/\x{2037}/\'''/g;  #REVERSED TRIPLE PRIME
  s/\x{2038}/\^/g;    #CARET
  s/\x{2039}/\</g;    #SINGLE LEFT-POINTING ANGLE QUOTATION MARK
  s/\x{203A}/\>/g;    #SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
  s/\x{203D}/\?/g;    #INTERROBANG
  s/\x{2044}/\//g;    #FRACTION SLASH
  s/\x{204E}/\*/g;    #LOW ASTERISK
  s/\x{2052}/\%/g;    #COMMERCIAL MINUS SIGN
  s/\x{2053}/\~/g;    #SWUNG DASH
  s/\x{2060}/ /g;     #WORD JOINER
  s/\x{20E5}/\\/g;    #COMBINING REVERSE SOLIDUS OVERLAY
  s/\x{2212}/\-/g;    #MINUS SIGN
  s/\x{2215}/\//g;    #DIVISION SLASH
  s/\x{2216}/\\/g;    #SET MINUS
  s/\x{2217}/\*/g;    #ASTERISK OPERATOR
  s/\x{2223}/\|/g;    #DIVIDES
  s/\x{2236}/\:/g;    #RATIO
  s/\x{223C}/\~/g;    #TILDE OPERATOR
  s/\x{2264}/\<=/g;   #LESS-THAN OR EQUAL TO
  s/\x{2265}/\>=/g;   #GREATER-THAN OR EQUAL TO
  s/\x{2266}/\<=/g;   #LESS-THAN OVER EQUAL TO
  s/\x{2267}/\>=/g;   #GREATER-THAN OVER EQUAL TO
  s/\x{2303}/\^/g;    #UP ARROWHEAD
  s/\x{2329}/\</g;    #LEFT-POINTING ANGLE BRACKET
  s/\x{232A}/\>/g;    #RIGHT-POINTING ANGLE BRACKET
  s/\x{266F}/\#/g;    #MUSIC SHARP SIGN
  s/\x{2731}/\*/g;    #HEAVY ASTERISK
  s/\x{2758}/\|/g;    #LIGHT VERTICAL BAR
  s/\x{2762}/\!/g;    #HEAVY EXCLAMATION MARK ORNAMENT
  s/\x{27E6}/\[/g;    #MATHEMATICAL LEFT WHITE SQUARE BRACKET
  s/\x{27E8}/\</g;    #MATHEMATICAL LEFT ANGLE BRACKET
  s/\x{27E9}/\>/g;    #MATHEMATICAL RIGHT ANGLE BRACKET
  s/\x{2983}/\{/g;    #LEFT WHITE CURLY BRACKET
  s/\x{2984}/\}/g;    #RIGHT WHITE CURLY BRACKET
  s/\x{3003}/\"/g;    #DITTO MARK
  s/\x{3008}/\</g;    #LEFT ANGLE BRACKET
  s/\x{3009}/\>/g;    #RIGHT ANGLE BRACKET
  s/\x{301B}/\]/g;    #RIGHT WHITE SQUARE BRACKET
  s/\x{301C}/\~/g;    #WAVE DASH
  s/\x{301D}/\"/g;    #REVERSED DOUBLE PRIME QUOTATION MARK
  s/\x{301E}/\"/g;    #DOUBLE PRIME QUOTATION MARK
  s/\x{FEFF}/ /g;     #ZERO WIDTH NO-BREAK SPACE
  s/\x{2009}/ /g;     #THIN SPACE



  #s/\x{2013}/-/g;    # en dash
  #s/\x{2014}/-/g;    # em dash
  #s/\x{2018}/\'/g;   # left single quote
  #s/\x{2019}/\'/g;   # right single quote
  #s/\x{201C}/\"/g;   # left double quote
  #s/\x{201D}/\"/g;   # right double quote
  #s/\342\211\245/>=/g;         # greater than or equal to

  # now remove blanks etc.
  s/\r//;
  s/(\ )+/ /g;
  s/^ //;
  s/ $//g;

  s/ \|$/\|/g;
  s/\| /\|/g;
  s/ \|/\|/g;

  return $_;
}

# 1: input file, 2: outputfile [3]: inpfile type[default is utf8]
sub prepareINPFile {
  my ($self, $inFile, $outFile, $mode) = @_;
  if (!defined($mode)) {
	$mode = "<:utf8";
  } else {
	$mode = "<:encoding($mode)";
  }

  open (IN, "$mode", $inFile) or die "Could not open $inFile file.\n";
  open (OUT, ">:utf8", $outFile) or die "could not open $outFile file.\n";

  while (<IN>) {
    chomp;
	# make high order bit substitution.
	s/\x{2013}/-/g;				# en dash
	s/\x{2014}/-/g;				# em dash
	s/\x{2018}/\'/g;   	        # left single quote
	s/\x{2019}/\'/g;   	        # right single quote
	s/\x{201C}/\"/g;			# left double quote
	s/\x{201D}/\"/g;			# right double quote
	#s/\342\211\245/>=/g;		# greater than or equal to
	s/\x{00AD}/-/g;				# soft hyphen
	s/\x{00A0}/ /g;				# no-break space

	# now remove blanks etc.
	s/\r//;
	s/\$/\|/g;
	s/ +/ /g;
	s/\| /\|/g;
	s/ \|/\|/g;
	s/^ //;

    # if the incoming file has any |s
    s/\|/&#124;/g;	   # any pipes need to converted to XML char. ent.

    print OUT "$_\n";
  }

  close(IN);
  close(OUT);
}

{
  my %invChars=();
  INIT {
    open(IN, "<:utf8", "$ENV{INV_HOME}/etc/invalidChars.txt")
      or die "Could not open invalid chars file.\n";
    while (<IN>) {
      chomp;
      $invChars{"$_"}++;
    }
    close(IN);
  }

	sub invalidChar {
	  my ($self, $ch) = @_;
	  return 1 if (defined($invChars{"$ch"}));
	  return 0;
	}
  sub invalidLine {
    my ($self, $line) = @_;
    my $ch;
    foreach $ch (split(//, $line)) {
      return 1 if (defined($invChars{"$ch"}));
    }
    return 0;
  }
  sub validateUtf8 {
    my ($self, $line) = @_;
    my $ans = 0;
    my $ch;
    for $ch (split(//,$line)) {
      return 2 if (defined($invChars{"$ch"}));
      $ans = 1 if (ord($ch) > 127);
    }
    return $ans;
  }

  sub addAttrName {
    my ($flh, $name) = @_;
    print $flh "DOC_ATN|$name\n";
  }
  sub addRel {
    my ($flh, $rel) = @_;
    print $flh "DOC_REL|$rel\n";
  }
  sub addRela {
    my ($flh, $rela) = @_;
    print $flh "DOC_RELA|$rela\n";
  }
  sub addTty {
    my ($flh, $tty) = @_;
    print $flh "DOC_TTY|$tty\n";
  }
  sub addTermgroup {
    my ($flh, $tg) = @_;
    print $flh "TG|$tg\n";
  }
  sub addTermgroup2Suppressible {
    my ($flh, $tg, $sup) = @_;
    print $flh "TGSP|$tg|$sup\n";
  }
  sub addVsab {
    my ($flh, $vsab) = @_;
    print $flh "SRC_VSAB|$vsab\n";
  }
  sub addRsab {
    my ($flh, $rsab) = @_;
    print $flh "SRC_RSAB|$rsab\n";
  }
  sub addVsabRsab {
    my ($flh, $vsab, $rsab) = @_;
    print $flh "SRC_V2R|$vsab|$rsab\n";
  }
   sub addlanguage{
     my ($flh,$lan) = @_;
    print $flh "LANGUAGE|$lan\n";
   }
  sub addSaid {
    my ($flh, $said) = @_;
    print $flh "SAID|$said\n";
  }
  sub addCodeVsab {
    my ($flh, $cd, $vsab) = @_;
    print $flh "CdVsab|$cd|$vsab\n";
  }
  sub addCodeRsab {
    my ($flh, $cd, $rsab) = @_;
    print $flh "CdRsab|$cd|$rsab\n";
  }
  sub addCodeTermgroupV {
    my ($flh, $cd, $vtg) = @_;
    print $flh "CdVTG|$cd|$vtg\n";
  }
  sub addCodeTermgroupR {
    my ($flh, $cd, $rtg) = @_;
    print $flh "CdRTG|$cd|$rtg\n";
  }
  sub addSauiVsab {
    my ($flh, $saui, $vsab) = @_;
    print $flh "SAV|$saui|$vsab\n";
  }
  sub addSauiRsab {
    my ($flh, $saui, $rsab) = @_;
    print $flh "SAR|$saui|$rsab\n";
  }
  sub addScuiVsab {
    my ($flh, $scui, $vsab) = @_;
    print $flh "SCV|$scui|$vsab\n";
  }
  sub addScuiRsab {
    my ($flh, $scui, $rsab) = @_;
    print $flh "SCR|$scui|$rsab\n";
  }
  sub addSduiVsab {
    my ($flh, $sdui, $vsab) = @_;
    print $flh "SDV|$sdui|$vsab\n";
  }
  sub addSduiRsab {
    my ($flh, $sdui, $rsab) = @_;
    print $flh "SDR|$sdui|$rsab\n";
  }
  sub addRid {
    my ($flh, $rid) = @_;
    print $flh "RID|$rid\n";
  }
  sub addRuiVsab {
    my ($flh, $srui, $vsab) = @_;
    print $flh "SUIV|$srui|$vsab\n";
  }
  sub addRuiRsab {
    my ($flh, $srui, $rsab) = @_;
    print $flh "SUIR|$srui|$rsab\n";
  }

}

1
