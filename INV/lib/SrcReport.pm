#
# File: SrcReport.pm
# Author: Brian Carlsen
# Summary: Concept reporter Library
#
# CHANGES
# 02/29/2008 BAC (1-DG8I1): first version
#
#################################################################

package SrcReport;

#---------------------
# Configure libraries 
#---------------------
use strict 'vars';
use strict 'subs';
use Carp;
use Text::Wrap;

#---------------------
# Declare Global Variables
#---------------------
our $index_dir = "$ENV{PWD}/../tmp/indexes";
our $dir = ".";
our %doc_map = ();
our %sources_map = ();
our %termgroups_map = ();
our ($ATOMSFP, $ATTRIBUTESFP, $CONTEXTSFP, $RELATIONSFP, $MERGESFP);

our $verbose = 1;
our $type = "SAID";
our $script = "";
our $vsab = "";
our $id = "";

our %type_map = (
				 "SRC_ATOM_ID" => "SAID",
				 "SOURCE_CUI" => "SCUI",
				 "SOURCE_AUI" => "SAUI",
				 "SOURCE_DUI" => "SDUI",
				 "SOURCE_RUI" => "SRUI",
				 "CODE_TERMGROUP" => "CODE",
				 "CODE_SOURCE" => "CODE",
				 "SRC_REL_ID" => "SRID",
				 "ROOT_SOURCE_CUI" => "SCUI",
				 "ROOT_SOURCE_AUI" => "SAUI",
				 "ROOT_SOURCE_DUI" => "SDUI",
				 "ROOT_SOURCE_RUI" => "SRUI",
				 "CODE_ROOT_TERMGROUP" => "CODE",
				 "CODE_ROOT_SOURCE" => "CODE",
				);

#---------------------
# Set methods
#---------------------
sub setScript {
  my ($lscript) = @_;
  $script = $lscript;
}

sub setVsab {
  my ($lvsab) = @_;
  $vsab = $lvsab;
}

sub setVerbose {
  my ($lverbose) = @_;
  $verbose = $lverbose;
}

sub setType {
  my ($ltype) = @_;
  $type = $ltype;
}

sub setId {
  my ($lid) = @_;
  $id = $lid;
}

sub setDir {
  my ($ldir) = @_;
  $dir = $ldir;
  $index_dir = "$ldir/../tmp/indexes";
}

#---------------------
# Build caches 
#---------------------
sub cacheData {

  #
  # Cache sources.src
  # sab,low_sab,srl,normalized_sab,rsab,sver,sf,son,nlm_contact,
  # acquisition_contact,content_contact,license_contact,inverter,
  # cxty,url,lat,scit,license_info,char_set,reldir
  my $INH;
  open ($INH, "<:utf8", "$dir/sources.src") ||
	die "Could not open $dir/sources.src\n";
  while (<$INH>) {
	chop;
	my ($sab,$low_sab,$srl,$normalized_sab,$rsab,$sver,$sf,$son,$nlm_contact,
		$acquisition_contact,$content_contact,$license_contact,$inverter,
		$cxty,$url,$lat,$scit,$license_info,$char_set,$reldir) = split /\|/;

	$sources_map{$sab} = $_;
  }
  close ($INH);

  #
  # Cache termgroups.src
  # termgroup,low_termgroup,suppress,exclude,norm_exclude,tty
  my $INH;
  open ($INH, "<:utf8", "$dir/termgroups.src") ||
	die "Could not open $dir/termgroups.src\n";
  while (<$INH>) {
	chop;
	my ($termgroup,$low_termgroup,$suppress,$exclude,$norm_exclude,$tty) = split /\|/;

	$termgroups_map{$termgroup} = $_;
  }
  close ($INH);

  #
  # Cache doc
  # dockey,value,type,expl
  my $INH;
  open ($INH, "<:utf8", "$dir/MRDOC.RRF") ||
	die "Could not open $dir/MRDOC.RRF\n";
  while (<$INH>) {
	chop;
	my ($dockey,$value,$type,$expl) = split /\|/;
	if ($type eq "tty_class") {
	  unshift @{$doc_map{"$dockey|$value|$type"}}, $expl;
	} else {
	  $doc_map{"$dockey|$value|$type"} = $expl;
	}
  }
  close ($INH);

}

#---------------------
# Index Data
#---------------------
sub indexData {

  mkdir $index_dir;

  #
  # Index classes_atoms.src : CODE, SAUI, SCUI, SDUI, lowercase STR
  # said,source,termgroup,code,status,tbr,released,str,suppress,saui,scui,sdui,lat,order_id,lrc
  #
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $d,$mtime,$d,$d,$d) = stat("classes_atoms.src");
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $d,$mtime2,$d,$d,$d) = stat("$index_dir/classes_atoms.CODE.x");
  if (!(-e "$index_dir/classes_atoms.CODE.x") || $mtime2 < $mtime) {
	print "Indexing classes_atoms.src, please wait\n";
	my ($INH, $CODEX, $SAUIX, $SCUIX, $SDUIX, $STRX);
	open ($INH, "<:utf8", "$dir/classes_atoms.src") ||
	  die "Could not open $dir/classes_atoms.src\n";
	open ($CODEX, ">:utf8", "$index_dir/classes_atoms.CODE.x") ||
	  die "Could not open $index_dir/classes_atoms.CODE.x: $! $?\n";
	open ($SAUIX, ">:utf8", "$index_dir/classes_atoms.SAUI.x") ||
	  die "Could not open $index_dir/classes_atoms.SAUI.x: $! $?\n";
	open ($SCUIX, ">:utf8", "$index_dir/classes_atoms.SCUI.x") ||
	  die "Could not open $index_dir/classes_atoms.SCUI.x: $! $?\n";
	open ($SDUIX, ">:utf8", "$index_dir/classes_atoms.SDUI.x") ||
	  die "Could not open $index_dir/classes_atoms.SDUI.x: $! $?\n";
	open ($STRX, ">:utf8", "$index_dir/classes_atoms.STR.x") ||
	  die "Could not open $index_dir/classes_atoms.STR.x: $! $?\n";
	my $fp = 0;
	while (<$INH>) {
	  chop;
	  my ($said, $sab, $sabtty, $code, $status, $tbr, $released, $str, $suppress,
		  $saui, $scui, $sdui, $lat, $order_id, $lrc) = split /\|/;
	    
	  print $CODEX "$code|$fp\n" if $code;
	  print $SAUIX "$saui|$fp\n" if $saui;
	  print $SCUIX "$scui|$fp\n" if $scui;
	  print $SDUIX "$sdui|$fp\n" if $sdui;
	  print $STRX lc($str)."|$fp\n" if $str;
	  $fp = tell($INH);
	}
	close ($INH);
	close ($CODEX);
	close ($SAUIX);
	close ($SCUIX);
	close ($SDUIX);
	close ($STRX);
	system "/bin/sort -T . -u -o $index_dir/classes_atoms.CODE.x $index_dir/classes_atoms.CODE.x";
	if ($?) {
	  die "Error sorting classes_atoms.CODE.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/classes_atoms.SAUI.x $index_dir/classes_atoms.SAUI.x";
	if ($?) {
	  die "Error sorting classes_atoms.SAUI.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/classes_atoms.SCUI.x $index_dir/classes_atoms.SCUI.x";
	if ($?) {
	  die "Error sorting classes_atoms.SCUI.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/classes_atoms.SDUI.x $index_dir/classes_atoms.SDUI.x";
	if ($?) {
	  die "Error sorting classes_atoms.SDUI.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/classes_atoms.STR.x $index_dir/classes_atoms.STR.x";
	if ($?) {
	  die "Error sorting classes_atoms.STR.x: $! $?\n";
	}
	print "    - atoms indexed\n";
  }
    
  #
  # Cache attributes.src
  # src_att_id,sg_id,level,atn,atv,sab,status,tbr,released,
  #  suppress,sg_type,sg_qualifier,satui,hashcode
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $d,$mtime,$d,$d,$d) = stat("attributes.src");
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $d,$mtime2,$d,$d,$d) = stat("$index_dir/attributes.IDTYPE.x");
  if (!(-e "$index_dir/attributes.IDTYPE.x") || $mtime2 < $mtime) {
	print "Indexing attributes.src, please wait\n";
	my ($INH, $DEFX, $STYX, $ATTRX);
	open ($INH, "<:utf8", "$dir/attributes.src") ||
	  die "Could not open $dir/attributes.src\n";
	open ($DEFX, ">:utf8", "$index_dir/definitions.IDTYPE.x") ||
	  die "Could not open $index_dir/definitions.IDTYPE.x: $! $?\n";
	open ($STYX, ">:utf8", "$index_dir/stys.IDTYPE.x") ||
	  die "Could not open $index_dir/stys.IDTYPE.x: $! $?\n";
	open ($ATTRX, ">:utf8", "$index_dir/attributes.IDTYPE.x") ||
	  die "Could not open $index_dir/attributes.IDTYPE.x: $! $?\n";
	my $fp = 0;
	while (<$INH>) {
	  chop;
	  my ($satid,$sg_id,$level,$atn,$atv,$sab,$status,$tbr,$released,
		  $suppress,$sg_type,$sg_qual,$satui,$hashcode) = split /\|/;
	  next if $atn eq "CONTEXT";
	  $sg_type = mapSgType($sg_type);
	  if ($atn eq "SEMANTIC_TYPE") {
		print $STYX "$sg_id$sg_type|$fp\n";
	  } elsif ($atn eq "DEFINITION") {
		print $DEFX "$sg_id$sg_type|$fp\n";
	  } else {
		print $ATTRX "$sg_id$sg_type|$fp\n";
	  }
	  $fp = tell($INH);
	}
	close ($INH);
	close ($DEFX);
	close ($STYX);
	close ($ATTRX);
	system "/bin/sort -T . -u -o $index_dir/definitions.IDTYPE.x $index_dir/definitions.IDTYPE.x";
	if ($?) {
	  die "Error sorting $index_dir/definitions.IDTYPE.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/stys.IDTYPE.x $index_dir/stys.IDTYPE.x";
	if ($?) {
	  die "Error sorting $index_dir/stys.IDTYPE.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/attributes.IDTYPE.x $index_dir/attributes.IDTYPE.x";
	if ($?) {
	  die "Error sorting $index_dir/attributes.IDTYPE.x: $! $?\n";
	}
	print "    - attributes indexed\n";
  }


  #
  # Cache contexts.src
  # said1,rel,rela,said2,sab,sl,hcd,ptr,release_mode,
  #  srui,rg,sg_id_1,sg_type_1,sg_qual_1,sg_id_2,sg_type_2,sg_qual_2
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $atime,$mtime,$ctime,$d,$d) = stat("contexts.src");
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $d,$mtime2,$d,$d,$d) = stat("$index_dir/contexts.SAID.x");
  my %root_saids = ();
  if (!(-e "$index_dir/contexts.SAID.x") || $mtime2 < $mtime) {
	print "Indexing contexts.src, please wait\n";
	my ($INH, $SAIDX, $PTRX, $ROOTX);
	open ($INH, "<:utf8", "$dir/contexts.src") ||
	  die "Could not open $dir/contexts.src\n";
	open ($SAIDX, ">:utf8", "$index_dir/contexts.SAID.x") ||
	  die "Could not open $index_dir/contexts.SAID.x: $! $?\n";
	open ($PTRX, ">:utf8", "$index_dir/contexts.PTRSAID1RELA.x") ||
	  die "Could not open $index_dir/contexts.PTRSAID1RELA.x: $! $?\n";
	open ($ROOTX, ">:utf8", "$index_dir/root_saids.txt") ||
	  die "Could not open $index_dir/root_saids.txt: $! $?\n";
	my $fp = 0;
	while (<$INH>) {
	  chop;
	  my ($said1,$rel,$rela,$said2,$sab,$sl,$hcd,$ptr,$release_mode,
		  $srui,$rg,$sg_id_1,$sg_type_1,$sg_qual_1,$sg_id_2,$sg_type_2,$sg_qual_2) = split /\|/;
	  if ($rel eq "PAR") {
		print $SAIDX "$said1|$fp\n";
		print $PTRX "$ptr|$said1|$rela|$fp\n";
		my ($root_said) = split /\./, $ptr;
		$root_saids{$root_said} = 1;
	  }
	  $fp = tell($INH);
	}
	close ($INH);
	close ($SAIDX);
	close ($PTRX);
	my $root_said;
	foreach $root_said ( keys %root_saids) {
	  print $ROOTX "$root_said\n";
	}
	close($ROOTX);
	system "/bin/sort -T . -u -o $index_dir/contexts.SAID.x $index_dir/contexts.SAID.x";
	if ($?) {
	  die "Error sorting $index_dir/contexts.SAID.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/contexts.PTRSAID1RELA.x $index_dir/contexts.PTRSAID1RELA.x";
	if ($?) {
	  die "Error sorting $index_dir/contexts.PTRSAID1RELA.x: $! $?\n";
	}
	print "    - contexts indexed\n";
  }

  #
  # Cache relationships.src
  # srid,level,sg_id_1,rel,rela,sg_id_2,sat,sl,status,tbr,released,suppress,
  # sg_type_1,sg_qual_2,sg_type_2,sg_qual_2,srui,rg
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $atime,$mtime,$ctime,$d,$d) = stat("relationships.src");
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $d,$mtime2,$d,$d,$d) = stat("$index_dir/relations.IDTYPE1.x");
  if (!(-e "$index_dir/relations.IDTYPE1.x") || $mtime2 < $mtime) {
	print "Indexing relationships.src, please wait\n";
	my ($INH, $IDTYPE1X, $IDTYPE2X);
	open ($INH, "<:utf8", "$dir/relationships.src") ||
	  die "Could not open $dir/relationships.src\n";
	open ($IDTYPE1X, ">:utf8", "$index_dir/relations.IDTYPE1.x") ||
	  die "Could not open $index_dir/relations.IDTYPE1.x: $! $?\n";
	open ($IDTYPE2X, ">:utf8", "$index_dir/relations.IDTYPE2.x") ||
	  die "Could not open $index_dir/relations.IDTYPE2.x: $! $?\n";
	my $fp = 0;
	while (<$INH>) {
	  chop;
	  my ($srid,$level,$sg_id_1,$rel,$rela,$sg_id_2,$sab,$sl,$status,$tbr,$released,$suppress,
		  $sg_type_1,$sg_qual_2,$sg_type_2,$sg_qual_2,$srui,$rg) = split /\|/;
	  $sg_type_1 = mapSgType($sg_type_1);
	  $sg_type_2 = mapSgType($sg_type_2);
	  print $IDTYPE1X "$sg_id_1$sg_type_1|$fp\n";
	  print $IDTYPE2X "$sg_id_2$sg_type_2|$fp\n";
	  $fp = tell($INH);
	}
	close ($INH);
	close ($IDTYPE1X);
	close ($IDTYPE2X);
	system "/bin/sort -T . -u -o $index_dir/relations.IDTYPE1.x $index_dir/relations.IDTYPE1.x";
	if ($?) {
	  die "Error sorting $index_dir/relations.IDTYPE1.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/relations.IDTYPE2.x $index_dir/relations.IDTYPE2.x";
	if ($?) {
	  die "Error sorting $index_dir/relations.IDTYPE2.x: $! $?\n";
	}
	print "    - relationships indexed\n";
  }

  #
  # Cache mergefacts.src
  # sg_id_1,level,sg_id_2,sab,vector,make_demotion,change_status,merge_set,
  # sg_type_1, sg_qual_1, sg_type_2, sg_qual_2
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $atime,$mtime,$ctime,$d,$d) = stat("mergefacts.src");
  my ($d,$d,$d,$d,$d,$d,$d,$d,
	  $d,$mtime2,$d,$d,$d) = stat("$index_dir/merges.IDTYPE1.x");
  if (!(-e "$index_dir/merges.IDTYPE1.x") || $mtime2 < $mtime) {
	print "Indexing mergefacts.src, please wait\n";
	my ($INH, $IDTYPE1X, $IDTYPE2X);
	open ($INH, "<:utf8", "$dir/mergefacts.src") ||
	  die "Could not open $dir/mergefacts.src\n";
	open ($IDTYPE1X, ">:utf8", "$index_dir/merges.IDTYPE1.x") ||
	  die "Could not open $index_dir/merges.IDTYPE1.x: $! $?\n";
	open ($IDTYPE2X, ">:utf8", "$index_dir/merges.IDTYPE2.x") ||
	  die "Could not open $index_dir/merges.IDTYPE2.x: $! $?\n";
	my $fp = 0;
	while (<$INH>) {
	  chop;
	  my ($sg_id_1,$level,$sg_id_2,$sab,$vector,$make_demotion,$change_status,$merge_set,
		  $sg_type_1, $sg_qual_1, $sg_type_2, $sg_qual_2) = split /\|/;
	  $sg_type_1 = mapSgType($sg_type_1);
	  $sg_type_2 = mapSgType($sg_type_2);
	  print $IDTYPE1X "$sg_id_1$sg_type_1|$fp\n";
	  print $IDTYPE2X "$sg_id_2$sg_type_2|$fp\n";
	  $fp = tell($INH);
	}
	close ($INH);
	close ($IDTYPE1X);
	close ($IDTYPE2X);
	system "/bin/sort -T . -u -o $index_dir/merges.IDTYPE1.x $index_dir/merges.IDTYPE1.x";
	if ($?) {
	  die "Error sorting $index_dir/merges.IDTYPE1.x: $! $?\n";
	}
	system "/bin/sort -T . -u -o $index_dir/merges.IDTYPE2.x $index_dir/merges.IDTYPE2.x";
	if ($?) {
	  die "Error sorting $index_dir/merges.IDTYPE2.x: $! $?\n";
	}
	print "    - mergefacts indexed\n";
  }
}

#---------------------
# Map src file sg type to corresponding field
#---------------------
sub mapSgType {
  my($sg_type) = @_;
  my $map_type = $type_map{$sg_type};
  return (!$map_type) ? $sg_type : $map_type;
}

#---------------------
# Open files
#---------------------
sub openFiles {
  open ($ATOMSFP, "<:utf8", "$dir/classes_atoms.src") || die "could not open $dir/classes_atoms.src: $? $!\n";
  open ($ATTRIBUTESFP, "<:utf8", "$dir/attributes.src") || die "could not open $dir/attributes.src: $? $!\n";
  open ($CONTEXTSFP, "<:utf8", "$dir/contexts.src") || die "could not open $dir/contexts.src: $? $!\n";
  open ($RELATIONSFP, "<:utf8", "$dir/relationships.src") || die "could not open $dir/relationships.src: $? $!\n";
  open ($MERGESFP, "<:utf8", "$dir/mergefacts.src") || die "could not open $dir/mergefacts.src: $? $!\n";
}


#---------------------
# Prints report
#---------------------
sub printReport {
  my ($id) = @_;
  print "REPORT $type: $id\n\n";

  binmode(STDOUT,":utf8");
	
  #
  # Get data
  #
  if ($type eq "STR") {
	$id = lc($id);
  }
  my	@atoms = getAtoms($id, $type);
  if ($type eq "STR") {
	# for connected data, use only first atom.
	my ($atom) = @atoms;
	my ($SAID) = split /\|/, $atom;
	$id = $SAID;
	$type = "SAID";
  }
  my @stys = getSemanticTypes($id, $type);
  my @defs = getDefinitions($id, $type);
  my @cxts = getContexts($id, $type);
  my @atts = getAttributes($id,$type);
  my @rels = getRelations($id,$type);
  my @inv_rels = getInverseRelations($id,$type);
  my @merges = getMerges($id,$type);

  # Print STYs
  my $sty;
  my $prev_sty;
  foreach $sty (sort @stys) {
	my ($satid,$sg_id,$level,$atn,$atv,$sab,$status,$tbr,$released,
	    $suppress,$sg_type,$sg_qual,$satui,$hashcode) = split /\|/, $sty;
	print "STY $atv\n" unless $atv eq $prev_sty;
	$prev_sty = $atv;
  }
  if (scalar(@stys)>0) {
	print "\n";
  }

  # Print DEFs
  my $def;
  foreach $def (@defs) {
	my ($satid,$sg_id,$level,$atn,$atv,$sab,$status,$tbr,$released,
	    $suppress,$sg_type,$sg_qual,$satui,$hashcode) = split /\|/, $def;
	$Text::Wrap::columns = 80;
	print Text::Wrap::wrap('','    ',"DEF $atv\n");
  }
  if (scalar(@defs)>0) {
	print "\n";
  }

  #
  # ATOMS
  #
  print "ATOMS - STR [SAB/TTY,SAID,CODE,SCUI,SDUI,SAUI]\n";
  my $atom;
  foreach $atom (@atoms) {
	my ($SAID, $sab, $sabtty, $CODE, $status, $tbr, $released, $str, $suppress,
		$SAUI, $SCUI, $SDUI, $lat, $order_id, $lrc) = split /\|/, $atom;
	if (!$script) {
	  print "   [] $str [$sabtty,$SAID,$CODE,$SCUI,$SDUI,$SAUI]\n";
	} else {
	  print "   [] $str [$sabtty,";
	  print qq{<a href="$script?sab=$vsab&type=SAID&id=$SAID">$SAID</a>,};
	  print qq{<a href="$script?sab=$vsab&type=CODE&id=$CODE">$CODE</a>,};
	  if ($SCUI) { 
		print qq{<a href="$script?sab=$vsab&type=SCUI&id=$SCUI">$SCUI</a>,};
	  } else {
		print "$SCUI,";
	  }
	  if ($SDUI) { 
		print qq{<a href="$script?sab=$vsab&type=SDUI&id=$SDUI">$SDUI</a>,};
	  } else {
		print "$SDUI,";
	  }
	  if ($SAUI) { 
		print qq{<a href="$script?sab=$vsab&type=SAUI&id=$SAUI">$SAUI</a>,};
	  } else {
		print "$SAUI,";
	  }
	  print "]\n";
	}

	#
	# Show atom attributes if -vv
	#
	if ($verbose > 1) {
	  my @atom_atts = getAttributes($SAID,"SAID");
	  my $att;
	  foreach $att (@atom_atts) {
		my ($satid,$sg_id,$level,$atn,$atv,$sab,$status,$tbr,$released,
		    $suppress,$sg_type,$sg_qual,$satui,$hashcode) = split /\|/, $att;
		$Text::Wrap::columns = 80;
		print Text::Wrap::wrap('        ','            ',"$atn: $atv [$sab]\n");
	  }
	}
  }
  if (scalar(@atoms)==0) {
	print "NO Atoms found for $type=$id\n";
	return;
  } else {
	print "\n";
  }

  #
  # ATTRIBUTES
  #
  my $att;
  my $found = 0;
  foreach $att (@atts) {
	if (!$found++) {
	  print "ATTRIBUTES - ATN: ATV [SAB]\n";
	}
	my ($satid,$sg_id,$level,$atn,$atv,$sab,$status,$tbr,$released,
	    $suppress,$sg_type,$sg_qual,$satui,$hashcode) = split /\|/, $att;
	$Text::Wrap::columns = 80;
	print Text::Wrap::wrap('  ','    ',"$atn: $atv [$sab]\n");
  }
  if (scalar(@atts) > 0) {
	print "\n";
  }

  #
  # RELATIONS
  #
  my $relation;
  my $found = 0;
  foreach $relation (@rels) {
	if (!$found++) {
	  print "RELATIONS - [<== REL/REL <==] STR [SAB/TTY/SGID/STYPE/SQUAL]\n";
	}
	my ($srid,$level,$sg_id_1,$rel,$rela,$sg_id_2,$sab,$sl,$status,$tbr,$released,$suppress,
		$sg_type_1,$sg_qual_2,$sg_type_2,$sg_qual_2,$srui,$rg) = split /\|/, $relation;
	my $atom = getPrefAtom($sg_id_2, mapSgType($sg_type_2));
	my ($said, $atom_sab, $sabtty, $code, $status, $tbr, $released, $str, $suppress,
		$saui, $scui, $sdui, $lat, $order_id, $lrc) = split /\|/, $atom;
	if (!$script) {
	  print "$type: $id [<== $rel/$rela <==] $str [$sabtty/$sg_id_2/$sg_type_2/$sg_qual_2]\n";
	} else {
	  print "$type: $id [<== $rel/$rela <==] $str [$sabtty/";
	  if ($sg_id_2 && $sg_type_2) {
		print qq{<a href="$script?sab=$vsab&type=}.mapSgType($sg_type_2).qq{&id=$sg_id_2">$sg_id_2/$sg_type_2/$sg_qual_2</a>};
	  } else {
		print "$sg_id_2/$sg_type_2/$sg_qual_2";
	  }
	  print "]\n";
	}
	#
	# Show rel attributes if -vv
	#
	if ($verbose > 1) {
	  my @rel_atts = getAttributes($srid,"SRID");
	  my $att;
	  foreach $att (@rel_atts) {
		my ($satid,$sg_id,$level,$atn,$atv,$sab,$status,$tbr,$released,
		    $suppress,$sg_type,$sg_qual,$satui,$hashcode) = split /\|/, $att;
		$Text::Wrap::columns = 80;
		print Text::Wrap::wrap('        ','            ',"$atn: $atv [$sab]\n");
	  }
	}
  }
  if (scalar(@rels) > 0) {
	print "\n";
  }

  #
  # INVERSE RELATIONS
  #
  my $relation;
  my $found = 0;
  foreach $relation (@inv_rels) {
	if (!$found++) {
	  print "INVERSE RELATIONS - STR [SAB/SGID/STYPE/SQUAL] [<== REL/RELA <==]\n";
	}
	my ($srid,$level,$sg_id_1,$rel,$rela,$sg_id_2,$sab,$sl,$status,$tbr,$released,$suppress,
		$sg_type_1,$sg_qual_1,$sg_type_2,$sg_qual_2,$srui,$rg) = split /\|/, $relation;
	my $atom = getPrefAtom($sg_id_1,mapSgType($sg_type_1));
	my ($said, $atom_sab, $sabtty, $code, $status, $tbr, $released, $str, $suppress,
		$saui, $scui, $sdui, $lat, $order_id, $lrc) = split /\|/, $atom;
	if (!$script) {
	  print " $str [$sabtty/$sg_id_1/$sg_type_1/$sg_qual_1] [<== $rel/$rela <== ] $type: $id\n";
	} else {
	  print " $str [$sabtty/";
	  if ($sg_id_1 && $sg_type_1) {
		print qq{<a href="$script?sab=$vsab&type=}.mapSgType($sg_type_1).qq{&id=$sg_id_1">$sg_id_1/$sg_type_1/$sg_qual_1</a>};
	  } else {
		print "$sg_id_1/$sg_type_1/$sg_qual_1";
	  }
	  print "] [<== $rel/$rela <==] $type: $id\n";
	}

	if ($verbose > 1) {
	  my @rel_atts = getAttributes($srid,"SRID");
	  my $att;
	  foreach $att (@rel_atts) {
		my ($satid,$sg_id,$level,$atn,$atv,$sab,$status,$tbr,$released,
		    $suppress,$sg_type,$sg_qual,$satui,$hashcode) = split /\|/, $att;
		$Text::Wrap::columns = 80;
		print Text::Wrap::wrap('        ','            ',"$atn: $atv [$sab]\n");
	  }
	}
  }
  if (scalar(@inv_rels) > 0) {
	print "\n";
  }

  #
  # CONTEXTS
  #
  my $cxt;
  my $ct = 0;
  foreach $cxt (@cxts) {
	if (!$ct++) {
	  print "CONTEXTS - [SAB/TTY/SGID/SYPE/SQUAL/RELA/HCD]\n";
	}
	if ($ct > 10) {
	  print "Additional contexts not shown (".(scalar(@cxts)-10).")\n";
	  last;
	}
	my ($said1,$rel,$rela,$said2,$sab,$sl,$hcd,$ptr,$release_mode,
		$srui,$rg,$sg_id_1,$sg_type_1,$sg_qual_1,
		$sg_id_2,$sg_type_2,$sg_qual_2) = split /\|/,$cxt;
	my ($atom) = getAtoms($said1,"SAID");
	my ($said, $atom_sab, $sabtty, $code, $status, $tbr, $released, $str, $suppress,
		$saui, $scui, $sdui, $lat, $order_id, $lrc) = split /\|/, $atom;
	print "[$sabtty/$sg_id_1/$sg_type_1/$sg_qual_1";
	print "/$rela" if $rela;
	print "/$hcd" if $hcd;
	print "]\n";

	my $indent = printAncestors($sab, $ptr);

	# self & siblings
	if (!printSibs($sab,$ptr,$rela,$indent,$id)) {
	  my ($atom) = getAtoms($said1,"SAID");
	  my ($SAID, $atom_sab, $sabtty, $CODE, $status, $tbr, $released, $str, $suppress,
		  $SAUI, $SCUI, $SDUI, $lat, $order_id, $lrc) = split /\|/, $atom;
	  my $ui =  eval "\$$type";
	  print "$indent$str [$sabtty/$ui] ***\n";
	  printChildren("$ptr.$said1", $rela, "$indent  ");
	}
  }
  if (scalar(@cxts)) {
	print "\n";
  }

  #
  # MERGES
  #
  my $merge;
  my $found = 0;
  foreach $merge (@merges) {
	if (!$found++) {
	  print "MERGES - STR [SAB/SGID/STYPE/SQUAL] => MERGE SET =>  STR [SAB/SGID/STYPE/SQUAL]\n";
	}
	my ($sg_id_1,$level,$sg_id_2,$sab,$vector,$make_demotion,$change_status,$merge_set,
	    $sg_type_1,$ sg_qual_1,$ sg_type_2,$ sg_qual_2) = split /\|/, $merge;
	my $atom1 = getPrefAtom($sg_id_1,mapSgType($sg_type_1));
	my $atom2 = getPrefAtom($sg_id_2,mapSgType($sg_type_2));
	my ($d, $d, $sabtty1, $d, $d, $d, $d, $str1) = split /\|/, $atom1;
	my ($d, $d, $sabtty2, $d, $d, $d, $d, $str2) = split /\|/, $atom2;
	print "  $str1 [$sabtty1/$sg_id_1/$sg_type_1/$sg_qual_1] => $merge_set\n";
	print "    => $str2 [$sabtty2/$sg_id_2/$sg_type_2/$sg_qual_2]\n";
  }
    
}

#-----------------------
# Helper methods
#-----------------------
sub getAtoms {
  my ($id, $type) = @_;
  my @results;
  if ($type ne "SAID") {
	my $INDEXFP;
	open ($INDEXFP, "<:utf8", "$index_dir/classes_atoms.$type.x") 
	  || die "could not open $index_dir/classes_atoms.$type.x";
	my $line;
	foreach $line (getMatchingLines($INDEXFP, "$id")) {
	  my ($id,$fp) = split /\|/, $line;
	  unshift @results, getLine($ATOMSFP,$fp);
	}
	close($INDEXFP);
	return @results;
  } else {
	my @results = getMatchingLines($ATOMSFP,"$id");
	return @results;
  }
}


#-----------------------
# Get attributes connected to $id,$type
# $type has already been mapped through %type_map
#-----------------------
sub getAttributes {
  my ($id,$type) = @_;
  my @results = ();
  my $INDEXFP;
  open ($INDEXFP, "<:utf8", "$index_dir/attributes.IDTYPE.x") 
	|| die "could not open $index_dir/attributes.IDTYPE.x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$id$type")) {
	my ($idtype,$fp) = split /\|/, $line;
	unshift @results, getLine($ATTRIBUTESFP,$fp);
  }
  close($INDEXFP);
  return @results;
}

#-----------------------
# Get relations connected to $id,$type
# $type has already been mapped through %type_map
#-----------------------
sub getRelations {
  my ($id,$type) = @_;
  my @results = ();
  my $INDEXFP;
  open ($INDEXFP, "<:utf8", "$index_dir/relations.IDTYPE1.x") 
	|| die "could not open $index_dir/relations.IDTYPE1.x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$id$type")) {
	my ($idtype,$fp) = split /\|/, $line;
	unshift @results, getLine($RELATIONSFP,$fp);
  }
  close($INDEXFP);
  return @results;
}

#-----------------------
# Get inverse relations connected to $id,$type
# $type has already been mapped through %type_map
#-----------------------
sub getInverseRelations{
  my ($id,$type) = @_;
  my @results = ();
  my $INDEXFP;
  open ($INDEXFP, "<:utf8", "$index_dir/relations.IDTYPE2.x") 
	|| die "could not open $index_dir/relations.IDTYPE2..x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$id$type")) {
	my ($idtype,$fp) = split /\|/, $line;
	unshift @results, getLine($RELATIONSFP,$fp);
  }
  close($INDEXFP);
  return @results;
}

#-----------------------
# Get merges connected to $id,$type
# $type has already been mapped through %type_map
#-----------------------
sub getMerges {
  my ($id,$type) = @_;
  my @results = ();
  my $INDEXFP;
  open ($INDEXFP, "<:utf8", "$index_dir/merges.IDTYPE1.x") 
	|| die "could not open $index_dir/merges.IDTYPE1.x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$id$type")) {
	my ($idtype,$fp) = split /\|/, $line;
	unshift @results, getLine($MERGESFP,$fp);
  }
  close($INDEXFP);
  open ($INDEXFP, "<:utf8", "$index_dir/merges.IDTYPE2.x") 
	|| die "could not open $index_dir/merges.IDTYPE2.x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$id$type")) {
	my ($idtype,$fp) = split /\|/, $line;
	unshift @results, getLine($MERGESFP,$fp);
  }
  close($INDEXFP);
  return @results;
}


#-----------------------
# Get all STYs connected to $id,$type or any of its atoms
# $type has already been mapped through %type_map
#-----------------------
sub getDefinitions {
  my ($id, $type) = @_;
  my @results = ();
  my $INDEXFP;
  open ($INDEXFP, "<:utf8", "$index_dir/definitions.IDTYPE.x") 
	|| die "could not open $index_dir/definitions.IDTYPE.x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$id$type")) {
	my ($idtype,$fp) = split /\|/, $line;
	unshift @results, getLine($ATTRIBUTESFP,$fp);
  }
  close($INDEXFP);
  if ($type ne "SAID") {
	my $atom;
	foreach $atom (getAtoms($id,$type)) {
	  my ($said) = split /\|/, $atom;
	  foreach $line (getDefinitions($said,"SAID")) {
		unshift @results, $line;
	  }
	}
  }
  return @results;
}

#-----------------------
# Get all STYs connected to $id,$type or any of its atoms
# $type has already been mapped through %type_map
#-----------------------
sub getSemanticTypes{
  my ($id, $type) = @_;
  my @results = ();
  my $INDEXFP;
  open ($INDEXFP, "<:utf8", "$index_dir/stys.IDTYPE.x") 
	|| die "could not open $index_dir/stys.IDTYPE.x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$id$type")) {
	my ($idtype,$fp) = split /\|/, $line;
	unshift @results, getLine($ATTRIBUTESFP,$fp);
  }
  close($INDEXFP);
  if ($type ne "SAID") {
	my $atom;
	foreach $atom (getAtoms($id,$type)) {
	  my ($said) = split /\|/, $atom;
	  foreach $line (getSemanticTypes($said,"SAID")) {
		unshift @results, $line;
	  }
	}
  }
  return @results;
}

#-----------------------
# Get contexts connected to any atoms with $id,$type
# Keep those where $sg_type_1 is $type or SAID
# $type has already been mapped through %type_map
#-----------------------
sub getContexts {
  my ($id,$type) = @_;
  my @results = ();
  my $atom;
  foreach $atom (getAtoms($id,$type)) {
	my ($said) = split /\|/, $atom;
	my $INDEXFP;
	open ($INDEXFP, "<:utf8", "$index_dir/contexts.SAID.x") 
	  || die "could not open $index_dir/contexts.SAID.x";
	my $line;
	foreach $line (getMatchingLines($INDEXFP, "$said")) {
	  my ($said,$fp) = split /\|/, $line;
	  my $cxt = getLine($CONTEXTSFP,$fp);
	  my ($said1,$rel,$rela,$said2,$sab,$sl,$hcd,$ptr,$release_mode,
		  $srui,$rg,$sg_id_1,$sg_type_1,$sg_qual_1,
		  $sg_id_2,$sg_type_2,$sg_qual_2) = split /\|/,$cxt;
	  $sg_type_1 = mapSgType($sg_type_1);
	  if ($type eq $sg_type_1 || $sg_type_1 eq "SAID" || $type eq "SAID") {
		unshift @results, getLine($CONTEXTSFP,$fp);
	  }
	}
	close($INDEXFP);
  }
  return @results;
}

#-----------------------
# Returns all context nodes whose parents have tree number $PTR (e.g. finds children or sets of sibs)
#-----------------------
sub getContextsByPtrRela {
  my ($ptr,$rela) = @_;
  my @results = ();
  my $INDEXFP;
  open ($INDEXFP, "<:utf8", "$index_dir/contexts.PTRSAID1RELA.x") 
	|| die "could not open $index_dir/contexts.PTRSAID1RELA.x";
  my $line;
  foreach $line (getMatchingLines($INDEXFP, "$ptr")) {
	my ($lptr,$lsaid1,$lrela,$fp) = split /\|/, $line;
	if ($lptr eq $ptr && $lrela eq $rela) {
	  my $cxt = getLine($CONTEXTSFP,$fp);
	  unshift @results, getLine($CONTEXTSFP,$fp);
	}
  }
  close($INDEXFP);
  return @results;
}


#-----------------------
# Get the RSAB for a VSAB
#-----------------------
sub getRsab {
  my ($sab) = @_;
  my $line = $sources_map{$sab};
  my ($sab,$low_sab,$srl,$normalized_sab,$rsab,$sver,$sf,$son,$nlm_contact,
	  $acquisition_contact,$content_contact,$license_contact,$inverter,
	  $cxty,$url,$lat,$scit,$license_info,$char_set,$reldir) = split /\|/, $line;
  return $rsab;
}

#-----------------------
# Print ancestors
# Return indent level
#-----------------------
sub printAncestors {
  my($sab, $ptr) = @_;
  my $indent = "";
  my $said;
  foreach $said (split /\./, $ptr) {
	my ($atom) = getAtoms($said,"SAID");
	my ($SAID, $atom_sab, $sabtty, $CODE, $status, $tbr, $released, $str, $suppress,
	    $SAUI, $SCUI, $SDUI, $lat, $order_id, $lrc) = split /\|/, $atom;
	if ($sabtty) {
	  my $ui =  eval "\$$type";
	  if (!$script) {
		print "$indent$str [$sabtty/$ui]\n";
	  } else {
		print "$indent$str [$sabtty/";
		if ($ui) {
		  print qq{<a href="$script?sab=$vsab&type=$type&id=$ui">$ui</a>};
		}
		print "]\n";
	  }
	} else {
	  my $rsab = getRsab($sab);
	  print "$indent$rsab Root Node [SRC/RHT/V-$rsab]\n";
	}
	$indent .= "  ";
  }
  return $indent;
}

#-----------------------
# Print siblings, return whether or not we did this
#-----------------------
sub printSibs {
  my ($sab, $ptr, $rela, $indent, $id) = @_;
  my $line = $sources_map{$sab};
  my ($sab,$low_sab,$srl,$normalized_sab,$rsab,$sver,$sf,$son,$nlm_contact,
	  $acquisition_contact,$content_contact,$license_contact,$inverter,
	  $cxty,$url,$lat,$scit,$license_info,$char_set,$reldir) = split /\|/, $line;
  if ($cxty !~ /NOSIB/) {
	my $cxt;
	my @sibs;
	my $self_said = 0;
	foreach $cxt (getContextsByPtrRela($ptr,$rela)) {
	  my ($said1,$rel,$rela,$said2,$sab,$sl,$hcd,$ptr,$release_mode,
		  $srui,$rg,$sg_id_1,$sg_type_1,$sg_qual_1,
		  $sg_id_2,$sg_type_2,$sg_qual_2) = split /\|/, $cxt;
	  my ($atom) = getAtoms($said1,"SAID");
	  my ($SAID, $atom_sab, $sabtty, $CODE, $status, $tbr, $released, $str, $suppress,
		  $SAUI, $SCUI, $SDUI, $lat, $order_id, $lrc) = split /\|/, $atom;
	  my $ui =  eval "\$$type";
	  my $entry;
	  if (!$script) {
		$entry = "$str [$sabtty/$ui]";
	  } else {
		$entry = "$str [$sabtty/";
		if ($ui) {
		  $entry .= qq{<a href="$script?sab=$vsab&type=$type&id=$ui">$ui</a>};
		}
		$entry .= "]";
	  }
	  if ($ui eq $id) {
		$entry = "$entry ***"; $self_said = $SAID;
	  }
	  ;
	  unshift @sibs, "$entry";
	}
	my $sib;
	my $prev_sib;
	foreach $sib (sort @sibs) {
	  print "$indent$sib\n" unless $sib eq $prev_sib;
	  if ($sib =~ /.* \*\*\*/) {
		printChildren("$ptr.$self_said", $rela, "$indent  ");
	  }
	  $prev_sib = $sib;
	}
	# return whether there were siblings or not.
	return scalar(@sibs)>0 ? 1 : 0;
  } else {
	return 0;
  }
    
}

#-----------------------
# Print children for $ptr$rela parent, use $indent
#-----------------------
sub printChildren {
  my ($ptr, $rela, $indent) = @_;
  my @chds = ();
  my $cxt;
  foreach $cxt (getContextsByPtrRela($ptr,$rela)) {
	my ($chd_said1,$d,$chd_rela,$d,$d,$d,$d,$chd_ptr) = split /\|/, $cxt;
	my ($chd) = getAtoms($chd_said1,"SAID");
	my ($SAID, $atom_sab, $sabtty, $CODE, $status, $tbr, $released, $str, $suppress,
	    $SAUI, $SCUI, $SDUI, $lat, $order_id, $lrc) = split /\|/, $chd;
	my $ui =  eval "\$$type";
	my $entry;
	if (!$script) {
	  $entry = "$str [$sabtty/$ui]";
	} else {
	  $entry = "$str [$sabtty/";
	  if ($ui) {
		$entry .= qq{<a href="$script?sab=$vsab&type=$type&id=$ui">$ui</a>};
	  }
	  $entry .= "]";
	}
	unshift @chds, $entry;
  }
  my $chd;
  foreach $chd (sort @chds) {
	print "$indent$chd\n";
  }
  return 1;    
}

#-----------------------
# Get preferred str for an $id, $type
# Find the first preferred TTY of the group and return its string.
#-----------------------
sub getPrefAtom {
  my ($id,$type) = @_;
  my $atom;
  my $anyatom;
  foreach $atom (getAtoms($id,$type)) {
	my ($SAID, $atom_sab, $sabtty, $CODE, $status, $tbr, $released, $str, $suppress,
	    $SAUI, $SCUI, $SDUI, $lat, $order_id, $lrc) = split /\|/, $atom;
	$anyatom = $atom;
	my ($d,$tty) = split /\//, $sabtty;
	if (isPrefTty($tty)) {
	  return $atom;
	}
  }
  return $anyatom;
}

#-----------------------
# Returns 1 if TTY is "preferred", 0 otherwise
#-----------------------
sub isPrefTty {
  my ($tty) = @_;
  my $class;
  foreach $class (@{$doc_map{"TTY|$tty|tty_class"}}) {
	if ($class eq "preferred") {
	  return 1;
	}
  }
  return 0;
}


#-----------------------
# Return line for specified $FP and $pos
#-----------------------
sub getLine {
  my ($FP, $pos) = @_;
  seek($FP, $pos, 0);
  my $result = <$FP>;
  chop($result);
  return $result;
}

#-----------------------
# Perform binary search in $FP for $str and return matching lines
# Find lines matching entire key, up to | separator
#-----------------------
sub getMatchingLines {
  my ($FP, $str) = @_;
  my @results = ();
  my $seekstr = $str;
  my $flag = 0;
  if ($str =~ /\*$/) {
	$seekstr =~ s/\*$//;
	$flag = 1;
  }
  my $fp = seekstr($FP, "$seekstr");
  while (<$FP>) {
	chop;
	if ($flag) {
	  last unless $_ =~ /^$seekstr[^|]*\|/;
	  push @results, $_;
	} else {
	  last if substr($_,0,length($str)+1) gt "$str|";
	  push @results, $_ if substr($_,0,length($str)+1) eq "$str|";
	}
  }
  return @results;
}


#-----------------------
# Seek a given filehandle to the first line starting with a given string.
# The corresponding file must be sorted on the first |-separated field.
# find first line matching entire $value, up to | separator
#-----------------------
sub seekstr {
  my($FILE, $value) = @_;
  my($SIZE, $l, $h, $pos);
  my $inval;
  $SIZE = (stat($FILE))[7];
  $l = 0;   $h=$SIZE-1;
  while ($l < $h-16) {
	$pos = int(($l + $h) / 2);
	seek($FILE, $pos, 0)  ||  die "can't seek to $pos\n";
	$_ = <$FILE>  if $pos != 0;
	$_ = <$FILE>;
	if ($_ eq '') {
	  $h = $pos - 1;
	  next;
	}
	$inval = $_;
	if (substr($inval,0,length($value)) ge $value) {
	  $h = $pos - 1;
	} else {
	  $l = $pos + 1;
	}
  }
  seek($FILE, $l, 0);
  $_ = <$FILE> if $l != 0;
  $pos=tell($FILE);
  while (1) {
	$_ = <$FILE>;
	return -1 if $_ eq '';
	$inval = $_;
	if (substr($inval,0,length($value)) eq $value) {
	  seek($FILE, $pos, 0);
	  return $pos;
	} elsif ($inval gt $value) {
	  return -1;
	}
	$pos=tell($FILE);
  }
}

return 1;
