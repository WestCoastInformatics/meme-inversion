#
# File: Contexts.pm
# Author: Brian Carlsen (2007)
#
# Dependencies
#   Various tools expect files in particular formats
#   1. bt_nt_rels.dat
#     src_atom_id_1|rel|rela|src_atom_id_2|srui|rg
#   2. source_atoms.dat
#     said|sabtty|code|str|hcd|id|type|qualifier|
#   3. treepos.dat
#     src_atom_id|hcd|treepos|rela|sort_field|srui|rg
#   4. code_ranges.dat
#     src_atom_id|cxt level|low range|high range
# Changes
# 02/19/2008 NEO (1-GIRJB): avoid warning on strings that evaluate as false (e.g. "0")
# 01/28/2008 BAC (1-GBOHD): fix to build children in CONTEXT attributes even when SIBs not being built.
# 11/26/2007 TK (1-FUGSH): It is accetable for a given level to be completely contained in its parent level.
# 10/24/2007 BAC (1-FLHKX): Move use open ":utf8" directive.
# 08/28/2007 BAC (1-F4AZ7): write null SIB rela values.
# 06/21/2007 BAC (1-EJPAX): Small fix needed in cycle detection during
#   relsToTreeposHelper.  When comparing $ptr to $anc\., we need to check a word
#   boundary before $anc in case values in $ptr are not fixed-length.
# 05/31/2007 BAC (1-D9NBZ): first version.
#
package Contexts;

use Digest::MD5 qw(md5_hex);
use Encode qw(encode_utf8);
use open ":utf8";

#
# Configuration parameters
#
$tmp_dir      = ".";
$dir          = ".";
$ignore_rela  = 0;
$mrdoc_dir    = "../src";
$inverse_flag = 0;
$verbose      = 0;

$root_src_atom_id = 0;
$root_termgroup   = "";
$root_code        = "";
$root_string      = "";

#
# Global hashes for tracking data
#
our %source_atoms = ();
our %nt_bt_rels   = ();
our %code_ranges  = ();
our %treepos      = ();

# %treepos_siblings should be local
our %treepos_siblings = ();

our @errors = ();

############################################################
# Configuration Procedures
############################################################

#
# Sets package configuration variables
# Returns void
#
sub configure {

  #
  # Set parameters
  #
  my ( $l_dir, $l_mrdoc_dir, $l_ignore_rela, $l_inverse_flag, $l_verbose ) = @_;
  setDir($l_dir);
  setTmpDir($l_dir);
  setIgnoreRela($l_ignore_rela);
  setMRDOCDir($l_mrdoc_dir);
  setInverseFlag($l_inverse_flag);
  setVerbose($l_verbose);
}

#
# Print configuration information
# Returns void
#
sub printConfiguration {
  print "Directory:          $dir\n";
  print "Tmp Directory:      $tmp_dir\n";
  print "MRDOC Directory:    $mrdoc_dir\n";
  print "Ignore Rela:        ", ( $ignore_rela  ? "true" : "false" ), "\n";
  print "Inverse Flag:       ", ( $inverse_flag ? "true" : "false" ), "\n";
  print "Verbose:            ", ( $verbose      ? "true" : "false" ), "\n";
}

#
# Sets "dir"
# Returns void
#
sub setDir {
  ($dir) = @_;
  if ( !( -e $dir ) ) {
    die "Non-existent dir: $dir\n";
  }
}

#
# Sets "tmp_dir"
# Returns void
#
sub setTmpDir {
  ($tmp_dir) = @_;
  if ( !( -e $tmp_dir ) ) {
    die "Non-existent tmp dir: $tmp_dir\n";
  }
}

#
# Sets "ignore_rela" flag
# Returns void
#
sub setIgnoreRela {
  ($ignore_rela) = @_;
}

#
# Sets "mrdoc_dir"
# Returns void
#
sub setMRDOCDir {
  ($mrdoc_dir) = @_;
  if ( !( -e $mrdoc_dir ) ) {
    die "Non-existent MRDOC Dir: $mrdoc_dir\n";
  }
}

#
# Sets "inverse" flag
# Returns void
#
sub setInverseFlag {
  ($inverse_flag) = @_;
}

#
# Sets "verbose" flag
# Returns void
#
sub setVerbose {
  ($verbose) = @_;
}

#
# Sets the "root atom" configuration variables
# Returns void
#
sub configureRoot {
  ( $l_root_src_atom_id, $l_root_termgroup, $l_root_code, $l_root_string ) = @_;
  print "Contexts.pm:    Configuring root (tree-top)\n" if $verbose;
  setRootSrcAtomId($l_root_src_atom_id);
  setRootTermgroup($l_root_termgroup);
  setRootCode($l_root_code);
  setRootString($l_root_string);
}

#
# Sets "src_atom_id" of context root
# Returns void
#
sub setRootSrcAtomId {
  ($root_src_atom_id) = @_;
}

#
# Sets "termgroup" of context root
# Returns void
#
sub setRootTermgroup {
  ($root_termgroup) = @_;
}

#
# Sets "code" of context root
# Returns void
#
sub setRootCode {
  ($root_code) = @_;
}

#
# Sets "string" of context root
# Returns void
#
sub setRootString {
  ($root_string) = @_;
}

#
# Returns any errors in @errors.
#
sub getErrors {
  return @errors;
}

############################################################
# Cacheing functions
############################################################

#
# Clears all global caches
# Returns void
#
sub clearCaches {
  print "Contexts.pm: Clear global caches\n" if $verbose;
  %source_atoms     = ();
  %nt_bt_rels       = ();
  %code_ranges      = ();
  %treepos          = ();
  %treepos_siblings = ();
}

#
# Loads source_atoms.dat into %source_atoms
# Returns void
#
sub cacheAtoms {
  print "Contexts.pm: cache $dir/source_atoms.dat in \%source_atoms\n"
    if $verbose;
  %source_atoms = ();
  open( F, "$dir/source_atoms.dat" )
    || die "Could not open $dir/source_atoms.dat: $? $!\n";
  while (<F>) {
    chomp;
    (
      $src_atom_id, $termgroup, $code, $string, $hcd, $sg_id, $sg_type,
      $sg_qualifier
      )
      = split /\|/;
    if ( $source_atoms{$src_atom_id} ) {
      print STDERR "source_atoms entry for $src_atom_id is duplicated.\n";
      print join "|", %{ $source_atoms{$src_atom_id} } . print "\n";
      die;
    }
    $source_atoms{$src_atom_id}             = {};
    $source_atoms{$src_atom_id}->{"sabtty"} = $termgroup;
    $source_atoms{$src_atom_id}->{"code"}   = $code;
    $source_atoms{$src_atom_id}->{"str"}    = $string;
    $source_atoms{$src_atom_id}->{"hcd"}  = $hcd          if $hcd;
    $source_atoms{$src_atom_id}->{"id"}   = $sg_id        if $sg_id ne "";
    $source_atoms{$src_atom_id}->{"type"} = $sg_type      if $sg_type;
    $source_atoms{$src_atom_id}->{"qual"} = $sg_qualifier if $sg_qualifier;
  }
  close(F);
  print "Contexts.pm:    \%source_atoms = ", scalar( keys %source_atoms ),
    " rows\n"
    if $verbose;
}

#
# Loads bt_nt_rels.dat file into %bt_nt_rels and %inv_bt_nt_rels
# Returns void
#
sub cacheRels {
  print "Contexts.pm: cache $dir/bt_nt_rels.dat in \%nt_bt_rels\n"
    if $verbose;
  %nt_bt_rels = ();
  my ($mrdoc_dir) = @_;
  if ($inverse_flag) {
    open( F, "$mrdoc_dir/MRDOC.RRF" )
      || die "Could not open $mrdoc_dir/MRDOC.RRF: $? $!\n";
    while (<F>) {
      chomp;
      ( $dockey, $value, $type, $expl ) = split /\|/;
      $inverse_rela{$value} = $expl if $type eq "rela_inverse";
      $inverse_rel{$value}  = $expl if $type eq "rel_inverse";
    }
    close(F);
  }
  open( F, "$dir/bt_nt_rels.dat" )
    || die "Could not open $dir/bt_nt_rels.dat: $? $!\n";
  my $ct = 0;
  while (<F>) {
    chomp;
    $ct++;
    ( $par_atom_id, $rel, $rela, $chd_atom_id, $srui, $rg ) = split /\|/;
    if ($inverse_flag) {
      die "Could not find inverse REL for $rel in MRDOC\n"
        unless $inverse_rel{$rel};
      die "Could not find inverse RELA for $rela in MRDOC\n"
        unless $inverse_rela{$rela};

      push @{ $nt_bt_rels{$chd_atom_id} },
        {
        "rel"  => $inverse_rel{$rel},
        "rela" => $inverse_rela{$rela},
        "par"  => $par_atom_id,
        "srui" => $srui,
        "rg"   => $rg
        };
    }
    else {
      push @{ $nt_bt_rels{$chd_atom_id} },
        {
        "rel"  => $rel,
        "rela" => $rela,
        "par"  => $par_atom_id,
        "srui" => $srui,
        "rg"   => $rg
        };
    }
  }
  close(F);
  print "Contexts.pm:    \%nt_bt_rels = ", scalar( keys %nt_bt_rels ),
    " children\n"
    if $verbose;
  print "Contexts.pm:    \%nt_bt_rels = $ct entries\n" if $verbose;
}

#
# Loads code_ranges.dat file into %code_ranges.
# Returns void
#
sub cacheRanges {
  print "Contexts.pm: cache $dir/code_ranges.dat in \%code_ranges\n"
    if $verbose;
  %code_ranges = ();
  open( F, "$dir/code_ranges.dat" )
    || die "Could not open $dir/code_ranges.dat: $? $!\n";
  while (<F>) {
    chomp;
    ( $src_atom_id, $cxl, $low_range, $high_range ) = split /\|/;
    if ( $code_ranges{$src_atom_id} ) {
      print STDERR "code_ranges entry for $src_atom_id is duplicated.\n";
      print join "|", %{ $code_ranges{$src_atom_id} } . print "|\n";
      die;
    }
    $code_ranges{$src_atom_id}           = {};
    $code_ranges{$src_atom_id}->{"cxl"}  = $cxl;
    $code_ranges{$src_atom_id}->{"low"}  = $low_range;
    $code_ranges{$src_atom_id}->{"high"} = $high_range;

  }
  close(F);
  print "Contexts.pm:    \%code_ranges = ", scalar( keys %code_ranges ),
    " rows\n"
    if $verbose;
}

sub cacheTreepos {
  print "Contexts.pm: cache $dir/treepos.dat in \%treepos\n" if $verbose;
  %treepos = ();
  open( F, "$dir/treepos.dat" )
    || die "Could not open $dir/treepos.dat: $? $!\n";
  while (<F>) {
    chomp;
    ( $src_atom_id, $hcd, $pos, $rela, $sort_field, $srui, $rg ) =
      split /\|/;

    my $treepos_key = "$pos,$rela";
    if ( $ignore_rela == 1 ) {
      $treepos_key = "$pos,";
    }

    if ( $treepos{$treepos_key} ) {
      print STDERR "treepos entry for $treepos_key is duplicated.\n";
      print join "|", %{ $treepos{$treepos_key} } . print "\n";
      die;
    }
    $treepos{$treepos_key} = {};
    $treepos{$treepos_key}->{"said"} = $src_atom_id;
    $treepos{$treepos_key}->{"hcd"}  = $hcd        if $hcd;
    $treepos{$treepos_key}->{"srui"} = $srui       if $srui;
    $treepos{$treepos_key}->{"rela"} = $rela       if $rela;
    $treepos{$treepos_key}->{"rg"}   = $rg         if $rg ne "";
    $treepos{$treepos_key}->{"sf"}   = $sort_field if $sort_field ne "";
  }
  close(F);
  print "Contexts.pm:    \%treepos = ", scalar( keys %treepos ), " rows\n"
    if $verbose;
}

########################################################
# Treepos functions
########################################################

#
# generate the contexts.src file
#
sub treeposToContextsFile {
  my ( $generate_sibs, $source ) = @_;

  print "Contexts.pm:    Convert \%treepos to $dir/contexts.src" if $verbose;

  @errors = ();

  if ( !%treepos ) {
    cacheTreepos();
  }

#
# Prepare contexts.src for output
# src_atom_id|rel|rela|par|source|source_of_label|hcd|treepos|release_mode|srui|rg|src_atom_id|sg_type_1|sg_qualifier_1|par|sg_type_2|sg_qualifier_2|
#
  open( F, ">$dir/contexts.src" )
    || die "Could not create $dir/contexts.src: $? $!\n";

  #
  # Iterate through the treepos hash
  #
  my $release_mode = "00";
  if ($generate_sibs) {
    $release_mode = "11";
  }

  %treepos_siblings = ();

  foreach $key ( keys %treepos ) {

    #
    # Get treepos parameters
    # src_atom_id|hcd|treepos|rela|sort_field|srui|rg|
    #
    my ($tree_position) = split /,/, $key;

    my $src_atom_id = $treepos{$key}->{"said"};
    my $hcd         = $treepos{$key}->{"hcd"};
    my $rela        = $treepos{$key}->{"rela"};
    my $srui        = $treepos{$key}->{"srui"};
    my $rg          = $treepos{$key}->{"rg"};

    #
    # Split tree position into components
    #
    @tree_position = split /\./, $tree_position;
    my $tree_position_size = ( scalar @tree_position );

    #
    # root node is not needed, skip it
    #
    next if $tree_position_size == 1;

    #
    # Remove self and acquire parent atom
    #
    pop @tree_position;
    my $par = $tree_position[ $tree_position_size - 2 ];
    $tree_position = join( ".", @tree_position );

    #
    # keeps track of sibs
    #
    if ($generate_sibs) {
      my $sibling_key = "$tree_position,$rela";
      if ($ignore_rela) { $sibling_key = "$tree_position,"; }
      push( @{ $treepos_siblings{$sibling_key} }, $src_atom_id );
    }

    #
    # Get source_atoms parameters
    # src_atom_id|termgroup|code|string|hcd|sg_id|sg_type|sg_qualifier|
    #
    my $sg_type_1 = $source_atoms{$src_atom_id}->{"type"};
    if ( !$sg_type_1 ) {
      $sg_type_1 = "SRC_ATOM_ID";
      $sg_id_1   = $src_atom_id;
    }
    else {
      $sg_id_1 = $source_atoms{$src_atom_id}->{"id"};
    }
    my $sg_qualifier_1 = $source_atoms{$src_atom_id}->{"qual"};
    my $sg_type_2      = $source_atoms{$par}->{"type"};
    if ( !$sg_type_2 ) {
      $sg_type_2 = "SRC_ATOM_ID";
      $sg_id_2   = $par;
    }
    else {
      $sg_id_2 = $source_atoms{$par}->{"id"};
    }
    my $sg_qualifier_2 = $source_atoms{$par}->{"qual"};

    #
    # Write to contexts.src the PAR row except for the root node
    #
    print F
"$src_atom_id|PAR|$rela|$par|$source|$source|$hcd|$tree_position|$release_mode|$srui|$rg|$sg_id_1|$sg_type_1|$sg_qualifier_1|$sg_id_2|$sg_type_2|$sg_qualifier_2|\n";
  }

  if ($generate_sibs) {
    local %sibling_pairs = ();

    # populates %sibling_pairs
    unless ( generateSiblings($generate_sibs) ) { return 0; }

    foreach $key ( keys %sibling_pairs ) {
      my ( $child, $sibling ) = split /,/, $key;
      my $rela      = $sibling_pairs{$key}->{"rela"};
    #
    # For SIBS, only UWDA should have RELA values
    #
	  if ($source !~ /UWDA/) {
	    $rela = "";
	  }
      my $sg_type_1 = $source_atoms{$child}->{"type"};
      if ( !$sg_type_1 ) {
        $sg_type_1 = "SRC_ATOM_ID";
        $sg_id_1   = $child;
      }
      else {
        $sg_id_1 = $source_atoms{$child}->{"id"};
      }
      my $sg_qualifier_1 = $source_atoms{$child}->{"qual"};
      my $sg_type_2      = $source_atoms{$sibling}->{"type"};
      if ( !$sg_type_2 ) {
        $sg_type_2 = "SRC_ATOM_ID";
        $sg_id_2   = $sibling;
      }
      else {
        $sg_id_2 = $source_atoms{$sibling}->{"id"};
      }
      my $sg_qualifier_2 = $source_atoms{$sibling}->{"qual"};

#
# Write to contexts.src the SIB row
# child|SIB|rela|sibling|source|source|||11|||sg_type_1|sg_qualifier_1|sibling|sg_type_2|sg_qualifier_2|
# Note: hcd, srui,rg are not used
#
      print F
"$child|SIB|$rela|$sibling|$source|$source|||11|||$sg_id_1|$sg_type_1|$sg_qualifier_1|$sg_id_2|$sg_type_2|$sg_qualifier_2|\n";
    }
  }
  close(F);

  return ( ( scalar(@errors) == 0 ) ? 1 : 0 );

}

#
# count the number of siblings
#
sub countSiblings {
  local %sibling_pairs = ();
  if ( !%treepos ) { cacheTreepos(); }

  @errors = ();

  foreach $key ( keys %treepos ) {

    #
    # Get treepos parameters
    # src_atom_id|hcd|treepos|rela|sort_field|srui|rg|
    #
    my ($tree_position) = split /,/, $key;
    my $rela = $treepos{$key}->{"rela"};

    @tree_position = split /\./, $tree_position;
    my $tree_position_size = ( scalar @tree_position );

    # root node is not needed
    next if $tree_position_size == 1;

    # Remove self
    my $src_atom_id = pop @tree_position;
    $tree_position = join( ".", @tree_position );

    #
    # keeps track of sibs
    #
    my $sibling_key = "$tree_position,$rela";
    if ($ignore_rela) { $sibling_key = "$tree_position,"; }
    push( @{ $treepos_siblings{$sibling_key} }, $src_atom_id );
  }

  my $sib_ct = 0;
  foreach $key ( keys %treepos_siblings ) {
    my $ct = scalar( @{ $treepos_siblings{$key} } );
    $sib_ct += ( ( ( $ct - 1 ) * $ct ) / 2 );
  }
  print "Contexts.pm:    This source has $sib_ct siblings\n";

  return 1;
}

#
# generate siblings
# Expects %sibling_pairs to be declared as local before calling this subroutine
#
sub generateSiblings {
  my ( $generate_sibs) = @_;
  @errors = ();

  if ( !%treepos_siblings ) {    # populate %treepos_siblings
    foreach $key ( keys %treepos ) {

      #
      # Get treepos parameters
      # src_atom_id|hcd|treepos|rela|sort_field|srui|rg|
      #
      my ($tree_position) = split /,/, $key;
      my $rela = $treepos{$key}->{"rela"};

      @tree_position = split /\./, $tree_position;
      my $tree_position_size = ( scalar @tree_position );

      # root node is not needed
      next if $tree_position_size == 1;

      # Remove self
      my $src_atom_id = pop @tree_position;
      $tree_position = join( ".", @tree_position );

      #
      # keeps track of sibs
      #
      my $sibling_key = "$tree_position,$rela";
      if ($ignore_rela) { $sibling_key = "$tree_position,"; }
      push( @{ $treepos_siblings{$sibling_key} }, $src_atom_id );
    }
  }

  #
  # Populate %sibling_pairs if $generate_sibs flag is set
  #
  %sibling_pairs = ();

  if ($generate_sibs) {
    foreach $key ( keys %treepos_siblings ) {
      my @siblings        = sort @{ $treepos_siblings{$key} };
      my $siblings_length = ( scalar @siblings );
      if ( $siblings_length < 2 ) { next; }

      my ($tree_position) = split /,/, $key;
      my $rela = $treepos{$key}->{"rela"};
      if ($ignore_rela) {
        my @tree_position = split /\./, $tree_position;
        push @tree_position, $siblings[0];
        $tree_position = join( ".", @tree_position );
        $rela = $treepos{"$tree_position,"}->{"rela"};
      }
    
      # cycle through the sibling list
      for ( $i = 0 ; $i < $siblings_length - 1 ; $i++ ) {
        for ( $j = $i + 1 ; $j < $siblings_length ; $j++ ) {
          my $child   = $siblings[$i];
          my $sibling = $siblings[$j];

          # ignore if child is the same as siblings
          if ( $child == $sibling ) { next; }

          # ignore duplicates
          if ( $sibling_pairs{"$child,$sibling"} ) { next; }

          $sibling_pairs{"$child,$sibling"} = { "rela" => $rela };
        }
      }
    }
  }
  return ( ( scalar(@errors) == 0 ) ? 1 : 0 );
}

#
# check the QA condition of the cached treepos data
# implements MEME_CONTEXTS:qa_treepos function
#
sub checkTreepos {
  print "Contexts.pm:    QA \%treepos\n" if $verbose;

  @errors = ();

  #
  # Ensure that all termgroups have a /
  # in them after the source name
  #
  foreach $src_atom_id ( keys %source_atoms ) {
    my $sabtty = $source_atoms{$src_atom_id}->{"sabtty"};
    my ( $sab, $tty ) = split /\//, $sabtty;
    unless ( $sab && $tty ) {
      push @errors, "Atom $src_atom_id has termgroup without '/': $sabtty\n";
    }
  }

  #
  # Ensure that first atom_id in each treenum is the root
  #
  my @root_src_atom_ids = &getTreeposRoots;
  if ( scalar(@root_src_atom_ids) > 1 ) {
    push @errors,
      (   "treepos.dat has too many roots: "
        . ( join ",", @root_src_atom_ids )
        . "\n" );
  }

  return ( ( scalar(@errors) == 0 ) ? 1 : 0 );
}

#
# generates attributes.cxt.src
#
sub treeposToAttributesFile {
  my ( $generate_sibs, $id, $source ) = @_;

  print "Contexts.pm:    Convert \%treepos to $dir/attributes.cxt.src\n"
    if $verbose;

  @errors = ();
  if ( !%treepos_siblings ) {
    unless ( generateSiblings($generate_sibs) ) { return 0; }
  }

  open( F, ">$dir/attributes.cxt.src" )
    || die "Could not create $dir/attributes.cxt.src: $? $!\n";

  #
  # Track CXN by $src_atom_id
  #
  my %context_number = ();

  #
  # Write CONTEXT attributes for each tree position
  #
  foreach $key ( keys %treepos ) {

    #
    # Increments src_attribute_id
    #
    $id++;

    my ($tree_position) = split /\,/, $key;
    my $rela = $treepos{$key}->{"rela"};

    #
    # Remove self and then figure out the parent
    #
    my @tree_position      = split /\./, $tree_position;
    my $tree_position_size = ( scalar @tree_position );
    my $src_atom_id        = pop @tree_position;
    my $parent_tree_position = join( ".", @tree_position );
    #
    # keep track of the context number in the first element of the array
    # do not display for the
    #
    $context_number{$src_atom_id}++;

    my $ANC       = replaceIDByString(@tree_position);
    my $SELF      = $source_atoms{$src_atom_id}->{"str"};
    my $CHDandSIB = "More contexts not shown\t";

    #
    # figure out SIB and CHD for the first 10 contexts
    #
    if ( $context_number{$src_atom_id} < 11 ) {

      my $SIBS = "";
      
      if ($generate_sibs) {

        #
        # recompose the key for %treepos_siblings to get siblings
        #
        my $sibling_key = "$parent_tree_position,$rela";
        if ($ignore_rela) { $sibling_key = "$parent_tree_position,"; }
        my @siblings = @{ $treepos_siblings{$sibling_key} };

        #
        # Remove self from sibling list
        #
        @siblings = grep { $_ ne $src_atom_id } @siblings;

        #
        # Acquire SIB string & sort it
        #
        $SIBS = replaceIDByString( hasChildren( "$sibling_key", @siblings ) );
        @siblings = sort( split /\~/, $SIBS );
        $SIBS = join( "~", @siblings );
      }

      #
      # get children
      #
      $sibling_key = "$parent_tree_position.$src_atom_id,$rela";
      if ($ignore_rela) { $sibling_key = "$parent_tree_position.$src_atom_id,"; }
      my @children = @{ $treepos_siblings{$sibling_key} };

      #
      # Acquire CHD string & sort it
      #
      my $CHD = replaceIDByString( hasChildren( "$sibling_key", @children ) );
      @children = sort( split /\~/, $CHD );
      $CHD = join( "~", @children );

      #
      # Compose CHD and SIB strings
      #
      $CHDandSIB = "$CHD\t$SIBS";
    }

    if ( $context_number{$src_atom_id} < 12 ) {
      my $hcd             = $treepos{$key}->{"hcd"};
      my $attribute_value =
"$context_number{$src_atom_id}\t$hcd\:\:~~~~~~\t$ANC\t$SELF\t$CHDandSIB";
      my $hash_code = md5_hex( encode_utf8($attribute_value) );
      print F
"$id|$src_atom_id|S|CONTEXT|$attribute_value|$source|R|n|N|N|SRC_ATOM_ID|||$hash_code|\n";
    }
  }
  close(F);
  return ( ( scalar(@errors) == 0 ) ? 1 : 0 );
}

#
# Take in an array of src_atom_ids and return with a string of name~name~..
#
sub replaceIDByString {
  my (@ids) = @_;
  my @array_of_strings = ();
  for ( $i = 0 ; $i < ( scalar @ids ) ; $i++ ) {
    if ( $ids[$i] eq "^" ) { next; }
    else {
      my $str = $source_atoms{ $ids[$i] }->{"str"};
      if ($str eq '') {
        push @errors, "No string for source atom $ids[$i]\n";
      }
      if ( $ids[ $i + 1 ] eq "^" ) { $str = $str . $ids[ $i + 1 ]; }
      push( @array_of_strings, $str );
    }
  }
  return join( "~", @array_of_strings );
}

#
# look up a tree_position and an array of ids, add ^ to indicate
# the id has children
#
sub hasChildren {
  my ( $sibling_key, @ids ) = @_;
  my ( $tree_position, $rela ) = split /,/, $sibling_key;
  my @temp_ids = ();

  foreach $key (@ids) {
    push( @temp_ids, $key );
    $sibling_key = $tree_position . "." . $key . "," . $rela;
    if ( $treepos_siblings{$sibling_key} ) { push( @temp_ids, "^" ); }
  }
  return @temp_ids;
}

#
# Adds RELA values for the top-level treepos positions based
# on the RELA of this things children.  Used just before
# addRootToTreepos to ensure 2 level tree positions
# have properly set RELA values.
#
sub addTopLevelTreeposRela {
  print "Contexts.pm: Add top-level RELAs to \%treepos\n" if $verbose;

  %root_relas = ();

  #
  # Lookup RELA values for things like A.B but not A.B.C*
  #  SAve RELA values
  #
  foreach $key ( keys %treepos ) {

    my ( $ptr, $rela ) = split /,/, $key;

    if ( $ptr =~ /.*\..*/ && $ptr !~ /.*\..*\..*/ ) {
      my ($top) = split /\./, $ptr;
      $rela = $treepos{$key}->{"rela"};
      $root_relas{$top} = $rela;
      print "Setting root RELA: $top: $rela\n";
    }
  }

  #
  # Set RELAs for top-level treepos entries based on %root_relas
  #
  foreach $key ( keys %treepos ) {

    my ( $ptr, $rela ) = split /,/, $key;
    if ( $root_relas{$ptr} ) {

      #
      # Overwrite RELA
      #
      $treepos{$key}->{"rela"} = $root_relas{$ptr};
    }
  }
}

#
# Adds an entry to %treepos for root, pre-pends root
# src atom id to each treepos.  Add it if %treepos is in memory
# Fails if an entry for $treepos, $rela already exists
#
sub addRootToTreepos {
  print "Contexts.pm: Add root to \%treepos\n" if $verbose;
  unless ($root_src_atom_id) {
    die "Cannot call addRootToTreepos without first calling configureRoot\n";
  }
  if ( $treepos{"$root_src_atom_id,"} ) {
    print STDERR "Treepos entry for ($root_src_atom_id,) is duplicated.\n";
    die;
  }

  # prepend the $root_src_atom_id
  foreach $key ( keys %treepos ) {

    # save the content
    my $src_atom_id = $treepos{$key}->{"said"};
    my $hcd         = $treepos{$key}->{"hcd"};

    my $sort_field = $treepos{$key}->{"sf"};
    my $srui       = $treepos{$key}->{"srui"};
    my $rela       = $treepos{$key}->{"rela"};
    my $rg         = $treepos{$key}->{"rg"};

    # delete the old
    delete $treepos{$key};
    my $prepended_key = $root_src_atom_id . "." . $key;

    # add the new with the prepended key
    $treepos{$prepended_key} = {};
    $treepos{$prepended_key}->{"said"} = $src_atom_id;
    $treepos{$prepended_key}->{"hcd"}  = $hcd        if $hcd;
    $treepos{$prepended_key}->{"sf"}   = $sort_field if $sort_field ne "";
    $treepos{$prepended_key}->{"srui"} = $srui       if $srui;
    $treepos{$prepended_key}->{"rela"} = $rela       if $rela;
    $treepos{$prepended_key}->{"rg"}   = $rg if $rg ne "";
  }

  # add the root
  $treepos{"$root_src_atom_id,"} = { "said" => "$root_src_atom_id" };
}

#
# Adds an entry to source_atoms.dat
# Returns void
# Fails if an entry already exists for this src_atom_id
#
sub appendRootToAtomsFile {
  print "Contexts.pm: Append root atom to $dir/source_atoms.dat\n"
    if $verbose;
  unless ($root_src_atom_id) {
    die "Cannot call addRootToAtomsFile without first calling configureRoot\n";
  }
  open( F, "$dir/source_atoms.dat" )
    || die "Could not open $dir/source_atoms.dat: $? $!\n";
  while (<F>) {
    chomp;
    ($file_src_atom_id) = split /\|/;
    if ( $file_src_atom_id == $root_src_atom_id ) {
      print STDERR
"Source atoms entry for $root_src_atom_id is already exists in src_atoms.dat.\n";
      print "$_\n";
      die;
    }
  }
  close(F);

  open( F, ">>$dir/source_atoms.dat" )
    || die "Could not open $dir/source_atoms.dat for append: $? $!\n";
  print F "$root_src_atom_id|$root_termgroup|$root_code|$root_string||||\n";
  close(F);
}

#
# Convert %nt_bt_rels, %source_atoms into %treepos file
# Returns true/false
#
sub relsToTreepos {
  return &relsToTreeposHelper(0);
}

#
# Convert %nt_bt_rels, %source_atoms into treepos.dat file
# Returns true/false
#
sub relsToTreeposFile {
  return &relsToTreeposHelper(1);
}

#
# Helper function for converting rels to treepos.
# Returns true/false
#
sub relsToTreeposHelper {
  my ($file_mode) = @_;
  print "Contexts.pm: Load \%treepos from \%nt_bt_rels\n" if $verbose;

  %treepos = ();
  @errors  = ();
  my %tree_tops;

  if ($file_mode) {
    open( F, ">$dir/treepos.dat" )
      || die "Could not open $dir/treepos.dat for write: $? $!\n";
  }

  #
  # For each child, follow chain to parent
  #
  my $src_atom_id;
  foreach $src_atom_id ( keys %nt_bt_rels ) {

    # TODO: this should probably be in the rels file, not in atoms file.
    my $hcd = $source_atoms{$src_atom_id}->{"hcd"};

    my @tree_positions       = ( { "ptr" => $src_atom_id } );
    my @par_tree_positions   = ();
    my @final_tree_positions = ();

    while (1) {

      #
      # Iterate through each tree position
      #
      foreach $tree_position (@tree_positions) {

        #
        # Set tree position parameters
        #
        my $rela = $tree_position->{"rela"};
        my $srui = $tree_position->{"srui"};
        my $rg   = $tree_position->{"rg"};
        my $ptr  = $tree_position->{"ptr"};

        #
        # Acquire top-level ancestor
        #
        my ($top) = split /\./, $ptr;

        #
        # Determine if rela, srui, rg needs to be set (based on first
        # par/chd relationship)
        #
        my $set_rela_srui_sg = ( $ptr eq $top );

        #
        # Find all parents for the top node of
        # tree position and add to par_tree_positions
        #
        my $ct    = 0;
        my $found = 0;
        foreach $parent ( @{ $nt_bt_rels{$top} } ) {
          $ct++;
          if ($set_rela_srui_sg) {
            $rela = $parent->{"rela"};
            $srui = $parent->{"srui"};
            $rg   = $parent->{"rg"};
          }

          #
          # Skip if we're paying attention to RELA and it doesn't match
          #
          next if ( $rela eq $parent->{"rela"} && !$ignore_rela );
          $found++;

          #
          # Get next ancestor
          #
          my $anc = $parent->{"par"};

          #
          # check for cycles
          #
          if ( $ptr =~ /\b$anc\./ ) {
            die "Cycle detected, ptr=$ptr, anc=$anc\n";
          }

          #
          # Compose ptr and new tree_position object.
          #
          my $anc_ptr = "$anc.$ptr";
          push @par_tree_positions,
            {
            "ptr"  => $anc_ptr,
            "rela" => $rela,
            "srui" => $srui,
            "rg"   => $rg
            };
        }

        #
        # If parents were found but none passed the rela condition, bail
        #
        if ( !$found && $ct && !$ignore_rela ) {
          print STDERR "Rela could not be matched to any parents.\n";
          print STDERR "  ptr = $ptr, rela = $rela\n";
          die;
        }

        #
        # If no parents were found, we're at the tree-top,
        # Add this tree position in to @final_tree_positions
        #
        if ( $ct == 0 ) {
          push @final_tree_positions, $tree_position;
          $tree_tops{$top} = 1;
        }

      }

      #
      # Finish if par_tree_positions is empty,
      # no additional ancestors are needed for
      # those entries in @tree_positions.  finish this round.
      #
      last if ( scalar(@par_tree_positions) == 0 );

      #
      # If continuing swap @tree_positions, @par_tree_positions
      #
      @tree_positions     = @par_tree_positions;
      @par_tree_positions = ();
    }

    #
    # Iterate through final tree positions and load ptr.
    #
    my $tree_position;
    foreach $tree_position (@final_tree_positions) {
      my %tp   = %{$tree_position};
      my $ptr  = $tp{"ptr"};
      my $rela = $tp{"rela"};
      my $srui = $tp{"srui"};
      my $rg   = $tp{"rg"};

      if ($file_mode) {
        print F "$src_atom_id|$hcd|$ptr|$rela||$srui|$rg|\n";
      }
      else {
        my $treepos_key = "$ptr,$rela";
        if ($ignore_rela) {
          $treepos_key = "$ptr,";
        }
        $treepos{$treepos_key} = {};
        $treepos{$treepos_key}->{"said"} = $src_atom_id;
        $treepos{$treepos_key}->{"hcd"}  = $hcd  if $hcd;
        $treepos{$treepos_key}->{"rela"} = $rela if $rela;
        $treepos{$treepos_key}->{"srui"} = $srui if $srui;
        $treepos{$treepos_key}->{"rg"}   = $rg   if $rg ne "";
      }
    }
  }

  #
  # Add treepos entry for tree-top if there is only one
  #
  if ( scalar( keys %tree_tops ) == 1 ) {
    ($src_atom_id) = %tree_tops;
    print "Contexts.pm:    Adding \%treepos entry for tree-top $src_atom_id\n";

    &configureRoot(
      $src_atom_id,
      $source_atoms{$src_atom_id}->{"sabtty"},
      $source_atoms{$src_atom_id}->{"code"},
      $source_atoms{$src_atom_id}->{"str"}
    );
  }

  foreach $src_atom_id ( sort keys %tree_tops ) {
    if ($file_mode) {
      print F "$src_atom_id||$src_atom_id|||||\n";
    }
    else {
      $treepos{"$src_atom_id,"} = {};
      $treepos{"$src_atom_id,"}->{"said"} = $src_atom_id;
    }
  }

  if ($file_mode) {
    close(F);
  }

  return ( scalar(@errors) == 0 );
}

#
# Look up tree-top src_atom_ids in %treepos
# Return an array of tree-top atoms
#
sub getTreeposRoots {
  print "Contexts.pm: Return root atom ids from \%treepos\n" if $verbose;
  my %results;
  foreach $key ( keys %treepos ) {
    my ($tree_position) = split /,/,  $key;
    my ($top)           = split /\./, $tree_position;
    $results{$top} = 1;
  }
  return sort keys %results;
}

#
# Write %treepos to $dir/treepos.dat
# Return void
#
sub writeTreeposFile {
  print "Contexts.pm: Write \%treepos to $dir/treepos.dat\n";
  open( F, ">$dir/treepos.dat" )
    || die "Could not open $dir/treepos.dat for write: $? $!\n";
  foreach $key ( keys %treepos ) {
    %fields = %{ $treepos{$key} };
    my ($tree_position) = split /,/, $key;
    print F $fields{"said"}, "|";
    print F $fields{"hcd"},  "|";
    print F $tree_position, "|";
    print F $fields{"rela"}, "|";
    print F $fields{"sf"},   "|";
    print F $fields{"srui"}, "|";
    print F $fields{"rg"},   "|\n";
  }
  close(F);
}

########################################################
# Atoms functions
########################################################

#
# Adds an entry to %source_atoms
# Returns void
# Fails if an entry for $src_atom_id already exists
#
sub addRootToAtoms {
  print "Contexts.pm: Add root atom to \%source_atoms\n" if $verbose;
  unless ($root_src_atom_id) {
    die "Cannot call addRootToAtoms without first calling configureRoot\n";
  }
  if ( $source_atoms{$root_src_atom_id} ) {
    my %hash = %{ $source_atoms{$root_src_atom_id} };
    print STDERR "Source atoms entry for $root_src_atom_id is duplicated.\n";
    print STDERR "  Entry 1: { sabtty =>", $hash{"sabtty"}, ", code => ",
      $hash{"code"}, ", string => ", $hash{"str"}, "\n";
    print STDERR
"  Entry 2: { sabtty => $root_termgroup, code => $root_code, str => $root_string }\n";
    die;
  }
  $source_atoms{$src_atom_id} = {
    "sabtty" => $root_termgroup,
    "code"   => $root_code,
    "str"    => $root_string
  };
}

########################################################
# Ranges functions
########################################################

#
# Check that the ranges correctly match
# Returns 1 if passed, 0 if errors.
# Saves errors in @errors
#
sub checkRanges {
  print "Contexts.pm:    QA \%code_ranges and \%source_atoms.dat\n"
    if $verbose;

  @errors = ();

  #
  # Cache code -> src_atom_id for prefix-sytle code lookups
  #
  my %prefix_parent_codes;
  foreach $src_atom_id ( keys %source_atoms ) {
    my $code = $source_atoms{$src_atom_id}->{"code"};
    $prefix_parent_codes{$code} = $src_atom_id;
  }

  #
  # Confirm each src_atom_id in source_atoms has a code in a range
  #
  my $src_atom_id;
  foreach $src_atom_id ( keys %source_atoms ) {
    my $code = $source_atoms{$src_atom_id}->{"code"};

    #
    # Handle case in code_ranges.dat
    #
    if ( $code_ranges{$src_atom_id} ) {

      my $low  = $code_ranges{$src_atom_id}->{"low"};
      my $high = $code_ranges{$src_atom_id}->{"high"};
      my $cxl  = $code_ranges{$src_atom_id}->{"cxl"};

      my $found = 0;
      foreach $key ( keys %code_ranges ) {

        next if $key eq $src_atom_id;
        my $comp_low  = $code_ranges{$key}->{"low"};
        my $comp_high = $code_ranges{$key}->{"high"};
        my $comp_cxl  = $code_ranges{$key}->{"cxl"};

        #
        # Use numeric comparison if codes are numbers
        #
        if ( ( $low =~ /^[0-9\.]*$/ ) && ( $high =~ /^[0-9\.]*$/ ) ) {
          if ( $comp_low <= $low
            && $comp_high >= $high
            && ( $comp_cxl + 1 == $cxl ) )
          {
            $found++;
            last;
          }
          if ( $comp_low < $low
            && $comp_high > $high
            && $comp_cxl > $cxl )
          {
            push @errors,
"Code range for $src_atom_id has narrower range than its descendent ($key)\n";
          }
        }

        #
        # Use string comparison if codes are not numbers
        #
        else {
          if ( $comp_low le $low
            && $comp_high ge $high
            && ( $comp_cxl + 1 == $cxl ) )
          {
            $found++;
            last;
          }
          if ( $comp_low lt $low
            && $comp_high gt $high
            && $comp_cxl > $cxl )
          {
            push @errors,
"Code range for $src_atom_id has narrower range than its descendent ($key)\n";
          }
        }
      }
      if ( $cxl ne "00" && !$found ) {
        push @errors,
          "Code range for $src_atom_id ($low,$high) has no container at level ",
          ( $cxl - 1 ), "\n";
      }
    }

    #
    # Handle the prefix-code case (e.g E10.91)
    #
    elsif ( $code =~ /\./ && $code !~ /\-/ ) {
      my $lookup_code = $code;
      if ( $code =~ /^.*\..$/ ) {
        $lookup_code =~ s/^(.*)..$/$1/;
      }
      else {
        $lookup_code =~ s/^(.*).$/$1/;
      }
      my $par_atom_id = $prefix_parent_codes{$lookup_code};

      # if case like 657.00 where 657.0 does not exist, look for 657
      unless ($par_atom_id) {
        if ( $lookup_code =~ /\.0$/ && $code =~ /0.$/ ) {
          $lookup_code =~ s/^(.*)..$/$1/;
          print
"Contexts.pm:      Warning: found case of .0X code without immediate parent: $code\n";
        }
        $par_atom_id = $prefix_parent_codes{$lookup_code};
      }

      if ( !par_atom_id ) {
        push @errors,
          "$src_atom_id has code ($code, $lookup_code) out of range\n";
      }
    }

    #
    # Handle case of atoms not directly in code_ranges.dat
    #
    else {

      if ( $code =~ /\-/ ) {
        push @errors,
"$src_atom_id has source_atoms.dat entry that appears like a range ($code) without having a code_ranges.dat entry\n";
      }

      #
      # If no range encloses $code, report error
      #
      $found = 0;
      foreach $key ( keys %code_ranges ) {
        my $comp_low  = $code_ranges{$key}->{"low"};
        my $comp_high = $code_ranges{$key}->{"high"};
        my $comp_cxl  = $code_ranges{$key}->{"cxl"};
        if ( ( $comp_low =~ /^[0-9\.]*$/ )
          && ( $comp_high =~ /^[0-9\.]*$/ ) )
        {
          if ( $comp_low <= $code
            && $comp_high >= $code )
          {
            $found++;
            last;
          }
        }

        else {
          if ( $comp_low le $code
            && $comp_high ge $code )
          {
            $found++;
            last;
          }
        }
      }
      if ( !$found ) {
        push @errors, "$src_atom_id has code ($code) out of range\n";
      }
    }
  }

  return ( ( scalar(@errors) == 0 ) ? 1 : 0 );
}

#
# Populate %nt_bt_rels from %code_ranges %source_atoms
# Returns 1 on succsss, 0 on failure
# Use &getErrors to see errors
#
sub rangesToRels {
  return &rangesToRelsHelper(0);
}

#
# Write bt_nt_rels.dat from %code_ranges and %source_atoms
# Returns 1 on succsss, 0 on failure
# Use &getErrors to see errors
#
sub rangesToRelsFile {
  return &rangesToRelsHelper(1);
}

#
# Helper function (do not call directly)
# Returns 1 on succsss, 0 on failure
# Use &getErrors to see errors
#
sub rangesToRelsHelper {
  my ($file_mode) = @_;

  print "Contexts.pm:    Convert \%code_ranges and \%source_atoms to rels\n"
    if $verbose;
  %nt_bt_rels = ();
  @errors     = ();

  #
  # Cache code -> src_atom_id for prefix-sytle code lookups
  #
  my %prefix_parent_codes;
  foreach $src_atom_id ( keys %source_atoms ) {
    my $code = $source_atoms{$src_atom_id}->{"code"};
    $prefix_parent_codes{$code} = $src_atom_id;
  }

  #
  # Handle write mode
  #
  if ($file_mode) {
    open( F, ">$dir/bt_nt_rels.dat" )
      || die "could not open $dir/bt_nt_rels.dat: $? $!\n";
  }

  #
  # Create rels between atoms and code ranges
  #
  my $src_atom_id;
  foreach $src_atom_id ( keys %source_atoms ) {
    my $code = $source_atoms{$src_atom_id}->{"code"};

    #
    # Handle case where src_atom_id in %code_ranges
    #
    if ( $code_ranges{$src_atom_id} ) {
      my $low  = $code_ranges{$src_atom_id}->{"low"};
      my $high = $code_ranges{$src_atom_id}->{"high"};
      my $cxl  = $code_ranges{$src_atom_id}->{"cxl"};

      #
      # Skip the root
      #
      next if $cxl eq "00";

      my $key;
      my $par_atom_id = 0;
      foreach $key ( keys %code_ranges ) {
        next if $key eq $src_atom_id;
        my $comp_low  = $code_ranges{$key}->{"low"};
        my $comp_high = $code_ranges{$key}->{"high"};
        my $comp_cxl  = $code_ranges{$key}->{"cxl"};

        #
        # Use numeric comparison if codes are numbers
        #
        if ( ( $low =~ /^[0-9\.]*$/ ) && ( $high =~ /^[0-9\.]*$/ ) ) {
          if ( $comp_low <= $low
            && $comp_high >= $high
            && ( $comp_cxl + 1 == $cxl ) )
          {
            $par_atom_id = $key;
            last;
          }
        }

        #
        # Use string comparison if codes are not numbers
        #
        else {
          if ( $comp_low le $low
            && $comp_high ge $high
            && ( $comp_cxl + 1 == $cxl ) )
          {
            $par_atom_id = $key;
            last;
          }
        }
      }

      if ($par_atom_id) {

        #
        # Either write to file
        #
        if ($file_mode) {
          print F "$par_atom_id|CHD||$src_atom_id|||\n";
        }

        #
        # Populate %nt_bt_rels
        #
        else {
          my $rel;
          if ($inverse_flag) { $rel = "CHD"; }
          else { $rel = "PAR"; }
          push @{ $nt_bt_rels{$src_atom_id} },
            {
            "rel"  => "$rel",
            "rela" => "",
            "par"  => $par_atom_id,
            "srui" => "",
            "rg"   => ""
            };
        }
      }
      else {
        push @errors, "No parent found for $src_atom_id\n";
      }
    }

    #
    # Handle the prefix-code case (e.g E10.91)
    #
    elsif ( $code =~ /\./ && $code !~ /\-/ ) {
      my $lookup_code = $code;
      if ( $code =~ /^.*\..$/ ) {
        $lookup_code =~ s/^(.*)..$/$1/;
      }
      else {
        $lookup_code =~ s/^(.*).$/$1/;
      }

      $par_atom_id = $prefix_parent_codes{$lookup_code};

      # if case like 657.00 where 657.0 does not exist, look for 657
      unless ($par_atom_id) {
        if ( $lookup_code =~ /\.0$/ && $code =~ /0.$/ ) {
          $lookup_code =~ s/^(.*)..$/$1/;
          print
"Contexts.pm:      Warning: found case of .0X code without immediate parent: $code\n";
        }
        $par_atom_id = $prefix_parent_codes{$lookup_code};
      }

      if ($par_atom_id) {

        #
        # Either write to file
        #
        if ($file_mode) {
          print F "$par_atom_id|CHD||$src_atom_id|||\n";
        }

        #
        # Populate %nt_bt_rels
        #
        else {
          my $rel;
          if ($inverse_flag) { $rel = "CHD"; }
          else { $rel = "PAR"; }
          push @{ $nt_bt_rels{$src_atom_id} },
            {
            "rel"  => "$rel",
            "rela" => "",
            "par"  => $par_atom_id,
            "srui" => "",
            "rg"   => ""
            };
        }
      }
      else {
        push @errors,
          "$src_atom_id has code ($code, $lookup_code) out of range\n";
      }
    }

    #
    # Handle case where src_atom_id not in %code_ranges
    #
    else {

      #
      # If no range encloses $code, report error
      #
      $found = 0;
      my $key;
      my $par_atom_id = 0;
      my $max_cxl     = -1;
      foreach $key ( keys %code_ranges ) {
        my $comp_low  = $code_ranges{$key}->{"low"};
        my $comp_high = $code_ranges{$key}->{"high"};
        my $comp_cxl  = $code_ranges{$key}->{"cxl"};

        if ( ( $comp_low =~ /^[0-9\.]*$/ )
          && ( $comp_high =~ /^[0-9\.]*$/ ) )
        {
          if ( $comp_low <= $code
            && $comp_high >= $code )
          {
            if ( $comp_cxl > $max_cxl ) {
              $par_atom_id = $key;
              $max_cxl     = $comp_cxl;
            }
          }
        }

        else {
          if ( $comp_low le $code
            && $comp_high ge $code )
          {
            if ( $comp_cxl > $max_cxl ) {
              $par_atom_id = $key;
              $max_cxl     = $comp_cxl;
            }
          }
        }
      }
      if ($par_atom_id) {

        #
        # Either write to file
        #
        if ($file_mode) {
          print F "$par_atom_id|CHD||$src_atom_id|||\n";
        }

        #
        # Populate %nt_bt_rels
        #
        else {
          my $rel;
          if ($inverse_flag) { $rel = "CHD"; }
          else { $rel = "PAR"; }
          push @{ $nt_bt_rels{$src_atom_id} },
            {
            "rel"  => "$rel",
            "rela" => "",
            "par"  => $par_atom_id,
            "srui" => "",
            "rg"   => ""
            };
        }
      }
      else {
        push @errors, "$src_atom_id has code ($code) out of range\n";
      }
    }
  }

  if ($file_mode) {
    close(F);
  }

  return scalar(@errors) == 0;
}

#
# Writes %nt_bt_rels to bt_nt_rels.dat
# Returns void
#
sub writeRels {
  print "Contexts.pm:    Write \%nt_bt_rels to $dir/bt_nt_rels.dat\n"
    if $verbose;
  if ($inverse_flag) {
    open( F, "$mrdoc_dir/MRDOC.RRF" )
      || die "Could not open $mrdoc_dir/MRDOC.RRF: $? $!\n";
    while (<F>) {
      chomp;
      ( $dockey, $value, $type, $expl ) = split /\|/;
      $inverse_rela{$value} = $expl if $type eq "rela_inverse";
      $inverse_rel{$value}  = $expl if $type eq "rel_inverse";
    }
    close(F);
  }

  open( F, ">$dir/bt_nt_rels.dat" )
    || die "could not open $dir/bt_nt_rels.dat: $! $?\n";

  #
  # Write out entries, convert REL, RELA back if $inverse_flag is used.
  #
  my $src_atom_id;
  foreach $src_atom_id (%nt_bt_rels) {
    foreach $parent ( @{ $nt_bt_rels{$src_atom_id} } ) {
      my $rel  = $parent->{"rel"};
      my $rela = $parent->{"rela"};
      if ($inverse_flag) {
        $rel  = $inverse_rel{$rel};
        $rela = $inverse_rela{$rela};
      }
      print F $parent->{"par"}, "|", $rel, "|", $rela, "|", "$src_atom_id|",
        $parent->{"srui"}, "|", $parent->{"rg"}, "\n";
    }
  }

  close(F);
}

return 1;
