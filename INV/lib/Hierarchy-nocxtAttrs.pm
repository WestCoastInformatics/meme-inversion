#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib (".");

use strict 'vars';
use strict 'subs';

package Hierarchy;


{
  my ($LogRef, $CfgRef, $HierRef);

  my %children=();
  my %parents=();
  my %cxts=();

  my %rngPars=();
  my %rngChlds=();
  my @rngTops=();


  my %ranges=();
  my %rngNodes=();
  my %lfNodes=();
  my $mode = 0;					# for number; use non 0 for textbased


  sub init {
    my ($self, $log, $cfg) = @_;
    $LogRef = $log;
    $CfgRef = $cfg;
    $mode = $$CfgRef->getEle('Hierarchy.Mode', '1');
  }


  sub new {
    if (defined($$HierRef)) {
      return $$HierRef;
    }

    my ($class) = @_;
    my $ref = {};
    $$HierRef = bless ($ref, $class);
    return $$HierRef;
  }

  sub setMode {
    my ($class, $temp) = @_;
    $mode = $temp if (defined($temp));
  }

  sub releaseMemory { %children = (); %parents = (); %cxts=(); }
  sub releaseRanges {
    %rngPars=();
    %rngChlds=();
    @rngTops=();


    %ranges=();
    %rngNodes=();
    %lfNodes=();
  }

  # regular-----------------------------------

  sub addParChild {
    my $self = shift;
    my $par = shift;
    my $chld = shift;

    push (@{$parents{"$chld"}}, $par) if (!grep (/$par/, @{$parents{"$chld"}}));
    push (@{$children{"$par"}}, $chld) if (!grep (/$chld/, @{$children{"$par"}}));
  }

  sub getParentsRef { return \%parents; }
  sub getChildrenRef { return \%children; }
  sub getParentPathsRef { return \%cxts; }
  sub getChildren {
    my $class = shift;
    my $nd = shift;
    return @{$children{"$nd"}};
  }
  sub getParents {
    my $class = shift;
    my $nd = shift;
    return @{$parents{"$nd"}};
  }
  # returns the result as a hash in the passed parameter.
  sub getDescendants {
    my $class = shift;
    my $nd = shift;
    my $result = shift;
    &getDescendants_int($nd, $result);
  }
  sub getDescendants_int {
    my $nd = shift;
    my $ans = shift;
    my $chld;
    return if (defined($$ans{"$nd"}));
    $$ans{"$nd"}++;
    foreach $chld(@{$children{"$nd"}}) {
      &getDescendants_int($chld, $ans);
    }
  }

  sub hasChildren {
    shift;
    my $nd = shift;
    return 1 if ($children{"$nd"} ne '');
    return 0;
  }
  sub hasParents {
    shift; 
    my $nd = shift;
    return 1 if (defined($parents{shift}));
    return 0;
  }


  sub dumpParChild {
    my $self = shift;
    my ($cd, $val);
    my $ln = keys (%parents);
    my $ln1 = keys (%children);

    # dump parents.
    my $tdir = $$CfgRef->getEle('TEMPDIR', '');
    if ($tdir eq '') {
      $tdir = "../tmp";
    }
    open (OUT, "> $tdir/ChldPar") or die "could not open parents file.\n";
    foreach $cd (sort keys (%parents)) {
      $val = join('|', @{$parents{"$cd"}});
      print OUT "$cd|$val\n";
    }
    # dump children
    close(OUT);
    # dump parents.
    open (OUT, "> $tdir/ParChld") or die "could not open chidren file.\n";
    foreach $cd (sort keys (%children)) {
      $val = join('|', @{$children{"$cd"}});
      print OUT "$cd|$val\n";
    }
    close(OUT);
  }


  sub getRoots {
    my $self = shift;
    my @hcRoots = ();
    my $cd;
    foreach $cd (keys (%children)) {
      if (!defined ($parents{"$cd"})) {
		push (@hcRoots, $cd);
      }
    }
    return @hcRoots;
  }

  sub setRoot {
    my $self = shift;
    my $rootId = shift;

    # find all top level nodes (with no parents) and add this as their parent.

    my $nd;
    foreach $nd (&getRoots) {
      push (@{$parents{"$nd"}}, $rootId);
      push (@{$children{"$rootId"}}, $nd);
    }
  }

  sub getSiblings {
    my $self = shift;
    my $thisNd = shift;
    my @sibs = ();
    my ($par, $chld, @temp);
    foreach $par (@{$parents{"$thisNd"}}) {
      foreach $chld (@{$children{"$par"}}) {
		@temp = grep (/^$chld$/, @sibs);
		push (@sibs, $chld) if (@temp == 0);
      }
    }
    # remove this node from the list.
    my @ans = grep(!/^$thisNd/, @sibs);
    return @ans;
  }

  sub getSibPairs {
    my $self = shift;
    my $thisNd = shift;
    my @sibs = ();
    my ($par, $chld, $sib, @temp);
    foreach $par (@{$parents{"$thisNd"}}) {
      foreach $chld (@{$children{"$par"}}) {
		@temp = grep(/^$chld$/, @sibs);
		push (@sibs, $chld) if (@temp == 0);
      }
    }
    my @ans=();
    while (@sibs > 1) {
      $thisNd = shift(@sibs);
      foreach $sib (@sibs) {
		push(@ans, "$thisNd|$sib");
      }
    }
    return @ans;
  }

  sub prepareCxts {
    my $self = shift;
    my $nd;
    # first set the contexts of the root children. (assuming that there
    # wont by any cycles at this layer).
    my @roots = &getRoots;
    if (@roots > 1) {
      $$LogRef->logError("This hierarchy has multiple root nodes \t<@roots>.\n"
						 ."\t Try adding a dummy root node and rerun.\n"
						 ."\t QUITTING!\n");
      return 1;
    }
    my ($root) = &getRoots;
    $$LogRef->logIt("Context Tree Root Node: $root\n");
    # set root context to null
    @{$cxts{"$root"}} = ();
    foreach $nd (@{$children{"$root"}}) {
      push(@{$cxts{"$nd"}}, $root);
    }
    # now call findCxt recursively.
    foreach $nd (keys (%parents)) {
      &findCxt($nd);
    }
    return 0;
  }

  our $cxtSeparator = "|";
  sub setCxtSeparator {
    my ($self, $sep) = @_;
    if (defined($sep)) {
	  $cxtSeparator = $sep;
	}
	;
  }


  # internal method.
  sub findCxt {
    my $nd = shift;
    # if previously done, just return.
    if (defined($cxts{"$nd"})) {
      return @{$cxts{"$nd"}};
    }

    my ($par, $cxt, @ans);
    @ans = ();
    foreach $par (@{$parents{"$nd"}}) {
      foreach $cxt (&findCxt("$par")) {
		push(@ans, "$cxt$cxtSeparator$par");
      }
    }
    @{$cxts{"$nd"}} = @ans;
    return @{$cxts{"$nd"}};
  }


  # range-------------------------------------


  # used for comparison.
  sub mle {
    my ($a, $b) = @_;
    if ($mode == 0) {
      return $b - $a;
    } else {
      # some thing here.
      my ($a1, $a2, $a3, $b1, $b2, $b3);
      $a =~ /^([a-zA-Z]*)([0-9]*)([a-zA-Z]*)$/;
      $a1 = $1;
      $a2 = $2;
      $a3 = $3;
      $b =~ /^([a-zA-Z]*)([0-9]*)([a-zA-Z]*)$/;
      $b1 = $1;
      $b2 = $2;
      $b3 = $3;
      return -1 if ($a1 ne $b1 || $a3 ne $b3);
      return $b2 - $a2;
    }
  }

  # external call. used to add a node or a range.
  sub addNode {
    my ($self, $tag, $low, $high, $dpt) = @_;
    if (defined $dpt) {
      # it is a range
      push (@{$ranges{"$dpt"}}, $tag);
      @{$rngNodes{"$tag"}} = ($low, $high, $dpt);
    } else {
      # it is a node
      $lfNodes{"$tag"} = $low;
    }
  }


  sub validateRanges {
    my ($key, $tag, $tag2, $lvl, $l, $h, $dpt, $valid, @tagsAtLvl);
    my ($l, $h, $d, $l2, $h2, $d2);
    my $errorP = 0;
    # first check lower and upper bounds.
    foreach $tag (keys %rngNodes) {
      ($l, $h, $d) = @{$rngNodes{"$tag"}};
      if (mle($l, $h) < 0) {
		$$LogRef->logError("Invalid Range: <$tag, $l, $h, $d>.\n");
		$errorP = 1;
      }
    }

    # check at each level they are non-intersecting
    foreach $lvl (sort keys %ranges) {
      @tagsAtLvl = @{$ranges{"$lvl"}};
      while (scalar(@tagsAtLvl) > 1) {
		$tag = shift(@tagsAtLvl);
		($l, $h, $d) = @{$rngNodes{"$tag"}};
		foreach $tag2 (@tagsAtLvl) {
		  ($l2, $h2, $d2) = @{$rngNodes{"$tag2"}};
		  if (rngIntersecting($l, $h, $l2, $h2) > 0) {
			$$LogRef->logError("Invalid ranges <$tag, $l, $h, $d> "
							   ."<$tag2, $l2, $h2, $d2>\n");
			$errorP = 1;
		  }
		}
      }
    }
    return $errorP;
  }

  sub addParChildRng {
    my ($self, $p, $c) = @_;
    push(@{$rngPars{"$c"}}, $p) if (!grep (/^$p$/, @{$rngPars{"$c"}}));
    push(@{$rngChlds{"$p"}}, $c) if (!grep (/^$c$/, @{$rngChlds{"$p"}}));
  }

  sub makeRanges {
    my ($self) = @_;
    my $errorP = 0;
    $$LogRef->logInfo("Validating ranges.\n");
    if (&validateRanges != 0) {
      $$LogRef->logError("Invalid Ranges. Bailing out...\n");
      $errorP = 1;
      #return $errorP;
    }
    $$LogRef->logInfo("Validating ranges - ok.\n");

    my ($lvl, $nxtLvl, @ptags, @ctags, $ptag, $ctag, $done, $valid);
    my ($l, $h, $d, $l2, $h2, $d2);

    foreach $lvl (sort keys %ranges) {
      $nxtLvl = $lvl + 1;
      @ptags = sortRanges(@{$ranges{"$lvl"}});

      if (defined ($ranges{"$nxtLvl"})) {
		@ctags = @{$ranges{"$nxtLvl"}};
		# insert each tag at the child level.
		foreach $ctag (@ctags) {
		  ($l2, $h2, $d2) = @{$rngNodes{"$ctag"}};
		  $done = 0;
		  foreach $ptag (@ptags) {
			# check if ctag goes into ptag, if so insert it.
			($l, $h, $d) = @{$rngNodes{"$ptag"}};
			if (mle($l,$l2) >= 0 && mle($h2, $h) >= 0 ) {
			  $self->addParChild($ptag, $ctag);
			  $self->addParChildRng($ptag, $ctag);
			  $done = 1;
			  last;
			}
		  }
		  if ($done == 0) {
			$$LogRef->logError("range <$ctag, $l2, $h2, $d2> can not go "
							   ."into any parent range.\n");
			$errorP = 1;
		  }
		}
      }
    }
    # remember top level ranges (as these are the startign ponits to insert
    # nodes.
    my @lvls = sort { $a <=> $b} keys (%ranges);
    $lvl = shift(@lvls);
    @rngTops = sortRanges(@{$ranges{"$lvl"}});

    $$LogRef->logIt("Range tops are:\n");
    $$LogRef->logIt("\t@rngTops\n");
    return $errorP;
  }

  sub sortRanges {
    my %sortedRanges=();
    my ($tag, $x, $x2, $y, $y2, $diff, @result);
    foreach $tag (@_) {
      ($x, $y) = @{$rngNodes{"$tag"}};
      $x =~ /^([a-zA-Z]*)([0-9]*)([a-zA-Z]*)$/;
      $x2 = $2;
      $y =~ /^([a-zA-Z]*)([0-9]*)([a-zA-Z]*)$/;
      $y2 = $2;
      $diff = $y2 - $x2;
      push(@{$sortedRanges{"$diff"}},$tag);
    }
    foreach $diff (sort {$a <=> $b} keys %sortedRanges) {
      push (@result, @{$sortedRanges{"$diff"}});
    }
    return @result;
  }

  sub fitsInRange {
    my ($rtag, $lfTag) = @_;
    my ($l, $h, $d) = @{$rngNodes{"$rtag"}};
    my $lfVal = $lfNodes{"$lfTag"};
    if (mle($l,$lfVal) >= 0 && mle($lfVal,$h) >= 0) {
      return 1;
    }
    return 0;
  }

  sub rngIntersecting {
    my ($l1, $h1, $l2, $h2) = @_;
    return 1 if ((mle($l2, $l1) >=0 && mle($l1, $h2) >= 0)
				 || (mle($l2, $h1) >=0 && mle($h1, $h2) >= 0)
				 || (mle($l1, $l2) >=0 && mle($l2, $h1) >= 0)
				 || (mle($l1, $h2) >=0 && mle($h2, $h1) >= 0));
    return 0;

  }

  sub insertNode {
    my ($self, $rtag, $lfTag) = @_;
    my $ctag;
    foreach $ctag (@{$rngChlds{"$rtag"}}) {
      if (fitsInRange($ctag, $lfTag)) {
		$self->insertNode($ctag, $lfTag);
		return;
      }
    }
    # could not go into any of its children. so add it here
    $self->addParChild($rtag, $lfTag);
  }

  sub insertLeaves {
    my ($self) = @_;
    my ($lfTag, $rngTag, $lfVal);
    foreach $lfTag (keys (%lfNodes)) {
      foreach $rngTag (@rngTops) {
		if (fitsInRange($rngTag, $lfTag)) {
		  $self->insertNode($rngTag, $lfTag);
		  last;
		}
      }
    }
  }

  sub addRangeInfo {
    my ($self, $rootId) = @_;
    my ($par, $chld);
    #return 1 if ($self->makeRanges);
    $self->makeRanges;
    $self->insertLeaves;

    # connect range top nodes to the supplied root.
    if (defined($rootId)) {
      foreach $chld (@rngTops) {
		push(@{$parents{"$chld"}}, $rootId);
		push(@{$children{"$rootId"}}, $chld);
      }
    }
    return 0;
  }

  # incase of ranges
  # 1. addNode
  # 2. addRngInfo
  # 3. releaseRanges
  #   any number of times call 1, 2, 3.
  # finally call prepareCxts,
  # followed by get all needed info and then releaseMemory.


  # basic proc to dump par/sib contexts and attributes.
  # arguments:
  #  pcCxt - context objectRef to dump par contexts. if 0 is passed, parent
  #          contexts are skipped.
  #  sibCxt - context objectRef to dump sib contexts If 0 is passed, sibling
  #           contexts are skipped.
  #  cxtAttr - attr objectRef to dump context attributes
  #  tag2Name - hashRef containing tag to name.
  #  tag2Said - hashRef containing tag to said if any. If 0 is passed, uses
  #             the tag as the said.
  #  tag2SgId - hashRef containing tag to SgId if any. if 0 is paased, uses
  #             the tag as the sgId.
  #  chld_p - 1/0 indicating whether to dump chidren in attributes.
  #  sibs_p - 1/0 indicating whether to dump siblings in attributes.

  sub dumpCxtsAttrs_old {
    my ($self, $pcCxt, $sibCxt, $cxtAttr, $tag2Name, $tag2Said, $tag2SgId,
		$chld_p, $sibs_p) = @_;
    if (!defined($tag2Said)) {
	  $tag2Said = 0;
	}
    if (!defined($tag2SgId)) {
	  $tag2SgId = 0;
	}

    if (!defined($chld_p)) {
	  $chld_p = 0;
	}
    if (!defined($sibs_p)) {
	  $sibs_p = 0;
	}

    my ($chldNames, $sibNames, $sib1Tag, $sib2Tag) = ('', '', '');
    my (@sibTags);
    my ($nd, $par, $sgidTree, $attrNum, @tempList, $myName, $treeNames);
    my ($cxt, $attrNum, $atId1, $atId2, $sgId1, $sgId2);
    my ($sgIdTree, @childSibTags, @childSibSaids, $thisId, $nextId);
    my ($sib1Said, $sib2Said);

    my $saidConv =  $tag2Said == 0 ? 0 : 1;
    my $sgidConv =  $tag2SgId == 0 ? 0 : 1;

    my $sub_hatName = sub {
      my $node = shift;
      my $name = $$tag2Name{"$node"};
      return ($self->hasChildren($node) == 1) ? "$name^" : "$name";
    };

    # prepare the contexts: create ptree paths.
    if ($self->prepareCxts()) {
      $$LogRef->logError("Error preparing contexts.\n");
      return 1;
    }
    # release memory for the ranges.
    $self->releaseRanges;

    # get info.
    my $parRef = $self->getParentsRef;
    my $chldRef = $self->getChildrenRef;
    my $pathRef = $self->getParentPathsRef;


    # first dump root context attr.
    my $rtndSaid = $$CfgRef->getReqEle('HC.RootNodeSaid');
    my $rtndName = $$CfgRef->getReqEle('HC.RootNodeName');
    my $rsab1 = $$CfgRef->getReqEle('RSAB');

    # dump root node context attribute
    #$$cxtAttr->dumpAttr ({sgId => $rtndSaid,
	#					  atv => "1\t::~~~~~~\t\t$rtndName\t\t"});


    # dump root node children as sibs; There should be one and only one root
    if ($sibCxt ne 0) {
      my ($rootTag) = $self->getRoots();
      @sibTags = @{$$chldRef{"$rootTag"}};

      while (@sibTags > 1) {
		$sib1Tag = shift(@sibTags);
		$sib1Said = $saidConv ? $$tag2Said{"$sib1Tag"} : $sib1Tag;
		$sgId1 = $sgidConv ? $$tag2SgId{"$sib1Tag"} : $sib1Tag;
		foreach $sib2Tag (@sibTags) {
		  $sib2Said = $saidConv ? $$tag2Said{"$sib2Tag"} : $sib2Tag;
		  $sgId2 = $sgidConv ? $$tag2SgId{"$sib2Tag"} : $sib2Tag;

		  $$sibCxt->dumpCxt({srcAtomId1 => $sib1Said, srcAtomId2 => $sib2Said,
							 ptr => '', sgId1 => $sgId1,
							 sgId2 => $sgId2});
		}
      }
    }


    $$LogRef->logDebug("Generating cxts.\n");

    # for each node
    foreach $nd (keys ( %{$parRef} )) {
      $attrNum = 0;
      # foreach cxt dump PAR context and its attributes
      $atId1 = $saidConv ? $$tag2Said{"$nd"} : $nd;

      # dump sibs of this nodes children
      if ($sibCxt ne 0) {
		@sibTags = @{$$chldRef{"$nd"}};
		while (@sibTags > 1) {
		  $sib1Tag = shift(@sibTags);
		  $sib1Said = $saidConv ? $$tag2Said{"$sib1Tag"} : $sib1Tag;
		  $sgId1 = $sgidConv ? $$tag2SgId{"$sib1Tag"} : $sib1Tag;
		  foreach $sib2Tag (@sibTags) {
			$sib2Said = $saidConv ? $$tag2Said{"$sib2Tag"} : $sib2Tag;
			$sgId2 = $sgidConv ? $$tag2SgId{"$sib2Tag"} : $sib2Tag;
			$$sibCxt->dumpCxt({srcAtomId1 => $sib1Said,
							   srcAtomId2 => $sib2Said,
							   ptr => '', sgId1 => $sgId1,
							   sgId2 => $sgId2});
		  }
		}
      }

      # chidlren 
      if ($chld_p) {
		$chldNames = join('~', (map {&$sub_hatName($_)}
								@{$$chldRef{"$nd"}}));
      }

      if ($sibs_p) {
		$sibNames = join('~', (map {&$sub_hatName($_)}
							   $self->getSiblings("$nd")));
      }



      # for each context (tree path) of that node
      foreach $cxt (@{$$pathRef{$nd}}) {
		# get the path
		@tempList = split(/\|/, $cxt);

		# change the delimeter from | to .
		if ($saidConv) {
		  $sgIdTree = join('.', map {$$tag2Said{"$_"};} @tempList);
		} else {
		  $sgIdTree = join('.', @tempList);
		}


		# get the parent node
		$par = @tempList[$#tempList];
		$atId2 = $saidConv ? $$tag2Said{"$par"} : $par;

		$sgId1 = $sgidConv ? $$tag2SgId{"$nd"} : $nd;
		$sgId2 = $sgidConv ? $$tag2SgId{"$par"} : $par;


		### dump context for PAR
		$$pcCxt->dumpCxt({srcAtomId1 => $atId1, srcAtomId2 => $atId2,
						  ptr => $sgIdTree, sgId1 => $sgId1, sgId2 => $sgId2});


		# now dump the attribute
		$attrNum++;
		#if ($attrNum < 11) {
		  # get my name
		 # $myName = $$tag2Name{"$nd"};

		  # ancestors
		 # $treeNames = join('~', (map {$$tag2Name{$_}} @tempList));


		  #$$cxtAttr->dumpAttr
			#({sgId => $atId1,
			  #atv => "$attrNum\t::~~~~~~\t$treeNames\t$myName\t$chldNames\t$sibNames"});

		#} elsif ($attrNum == 11) {
		  ## dump the special attribute stating that it has more
		  ## than 10 attrs here - never be the case in HCPCS.
		  #$$cxtAttr->dumpAttr
			#({sgId => $atId1,
			  #atv => "$11\t::~~~~~~\t${rsab1} Concept\tMore contexts not shown\t\t"});
		#}
      }
    }
    $$LogRef->logDebug("Done generating contexts.\n");

    # Release memory.
    $self->releaseMemory;
    return 0;
  }

  # basic proc to dump par/sib contexts and attributes.
  # arguments:
  #  rtCxt  - context objectRef to dump root contexts. if 0 is passed, normal
  #           pcCxt (2nd arg) is used to dump root contexts.
  #  pcCxt - context objectRef to dump par contexts. if 0 is passed, parent
  #          contexts are skipped.
  #  sibCxt - context objectRef to dump sib contexts If 0 is passed, sibling
  #           contexts are skipped.
  #  cxtAttr - attr objectRef to dump context attributes
  #  tag2Name - hashRef containing tag to name.
  #  tag2Said - hashRef containing tag to said if any. If 0 is passed, uses
  #             the tag as the said.
  #  tag2SgId - hashRef containing tag to SgId if any. if 0 is paased, uses
  #             the tag as the sgId.
  #  chld_p - 1/0 indicating whether to dump chidren in attributes.
  #  sibs_p - 1/0 indicating whether to dump siblings in attributes.
  sub dumpCxtsAttrs {
    my ($self, $rtCxt, $pcCxt, $sibCxt, $cxtAttr, $tag2Name, $tag2Said,
		$tag2SgId, $chld_p, $sibs_p) = @_;
    if (!defined($tag2Said)) {
	  $tag2Said = 0;
	}
    if (!defined($tag2SgId)) {
	  $tag2SgId = 0;
	}

    if (!defined($chld_p)) {
	  $chld_p = 0;
	}
    if (!defined($sibs_p)) {
	  $sibs_p = 0;
	}

    my ($chldNames, $sibNames, $sib1Tag, $sib2Tag) = ('', '', '');
    my (@sibTags);
    my ($nd, $par, $sgidTree, $attrNum, @tempList, $myName, $treeNames);
    my ($cxt, $attrNum, $atId1, $atId2, $sgId1, $sgId2);
    my ($sgIdTree, @childSibTags, @childSibSaids, $thisId, $nextId);
    my ($sib1Said, $sib2Said);

    my $saidConv =  $tag2Said == 0 ? 0 : 1;
    my $sgidConv =  $tag2SgId == 0 ? 0 : 1;

    my $sub_hatName = sub {
      my $node = shift;
      my $name = $$tag2Name{"$node"};
      return ($self->hasChildren($node) == 1) ? "$name^" : "$name";
    };

    # prepare the contexts: create ptree paths.
    if ($self->prepareCxts()) {
      $$LogRef->logError("Error preparing contexts.\n");
      return 1;
    }
    # release memory for the ranges.
    $self->releaseRanges;

    # get info.
    my $parRef = $self->getParentsRef;
    my $chldRef = $self->getChildrenRef;
    my $pathRef = $self->getParentPathsRef;


    # first dump root context attr.
    my $rtndSaid = $$CfgRef->getReqEle('HC.RootNodeSaid');
    my $rtndName = $$CfgRef->getReqEle('HC.RootNodeName');
    my $rsab1 = $$CfgRef->getReqEle('RSAB');

    # dump root node context attribute
    #if ($cxtAttr ne 0) {
	  #my $oldSgType = $$cxtAttr->{'sgType'};
	  #my $oldSgQual = $$cxtAttr->{'sgQual'};
	  #$$cxtAttr->{'sgType'} = 'SRC_ATOM_ID';
	  #$$cxtAttr->{'sgQual'} = '';
	  ##$$cxtAttr->dumpAttr ({sgId => $rtndSaid,
	##						atv => "1\t::~~~~~~\t\t$rtndName\t\t"});
	  #$$cxtAttr->{'sgType'} = $oldSgType;
	  #$$cxtAttr->{'sgQual'} = $oldSgQual;
    #}

    # dump root node children as sibs; There should be one and only one root
    # remove this code
    if (0) {  
	  if ($sibCxt ne 0) {
		my ($rootTag) = $self->getRoots();
		@sibTags = @{$$chldRef{"$rootTag"}};

		while (@sibTags > 1) {
		  $sib1Tag = shift(@sibTags);
		  $sib1Said = $saidConv ? $$tag2Said{"$sib1Tag"} : $sib1Tag;
		  $sgId1 = $sgidConv ? $$tag2SgId{"$sib1Tag"} : $sib1Tag;
		  foreach $sib2Tag (@sibTags) {
			$sib2Said = $saidConv ? $$tag2Said{"$sib2Tag"} : $sib2Tag;
			$sgId2 = $sgidConv ? $$tag2SgId{"$sib2Tag"} : $sib2Tag;

			$$sibCxt->dumpCxt({srcAtomId1 => $sib1Said, srcAtomId2 => $sib2Said,
							   ptr => '', sgId1 => $sgId1,
							   sgId2 => $sgId2});
		  }
		}
	  }
    }

    $$LogRef->logDebug("Generating cxts.\n");

    # for each node
    foreach $nd (keys ( %{$parRef} )) {
      $attrNum = 0;
      # foreach cxt dump PAR context and its attributes
      $atId1 = $saidConv ? $$tag2Said{"$nd"} : $nd;

      # dump sibs of this nodes children
      # old remove
      if (0) { 
		if ($sibCxt ne 0) {
		  @sibTags = @{$$chldRef{"$nd"}};
		  while (@sibTags > 1) {
			$sib1Tag = shift(@sibTags);
			$sib1Said = $saidConv ? $$tag2Said{"$sib1Tag"} : $sib1Tag;
			$sgId1 = $sgidConv ? $$tag2SgId{"$sib1Tag"} : $sib1Tag;
			foreach $sib2Tag (@sibTags) {
			  $sib2Said = $saidConv ? $$tag2Said{"$sib2Tag"} : $sib2Tag;
			  $sgId2 = $sgidConv ? $$tag2SgId{"$sib2Tag"} : $sib2Tag;
			  $$sibCxt->dumpCxt({srcAtomId1 => $sib1Said,
								 srcAtomId2 => $sib2Said,
								 ptr => '', sgId1 => $sgId1,
								 sgId2 => $sgId2});
			}
		  }
		}
      }

      # new code -- remove duplicate sibs
      if ($sibCxt ne 0) {
        $sib2Said = $saidConv ? $$tag2Said{"$nd"} : $nd;
        $sgId2 = $sgidConv ? $$tag2SgId{"$nd"} : $nd;

        foreach $sib1Tag ($self->getSiblings("$nd")) {
          $sib1Said = $saidConv ? $$tag2Said{"$sib1Tag"} : $sib1Tag;
          $sgId1 = $sgidConv ? $$tag2SgId{"$sib1Tag"} : $sib1Tag;
          if ($sib2Said > $sib1Said) {
            $$sibCxt->dumpCxt({srcAtomId1 => $sib1Said,
                               srcAtomId2 => $sib2Said,
                               ptr => '', sgId1 => $sgId1,
                               sgId2 => $sgId2});
          }
        }
	  }  

      # chidlren 
      if ($chld_p) {
		$chldNames = join('~', (map {&$sub_hatName($_)}
								@{$$chldRef{"$nd"}}));
      }

      if ($sibs_p) {
		$sibNames = join('~', (map {&$sub_hatName($_)}
							   $self->getSiblings("$nd")));
      }



      # for each context (tree path) of that node
      foreach $cxt (@{$$pathRef{$nd}}) {
		# get the path
		@tempList = split(/\|/, $cxt);

		# change the delimeter from | to .
		if ($saidConv) {
		  $sgIdTree = join('.', map {$$tag2Said{"$_"};} @tempList);
		} else {
		  $sgIdTree = join('.', @tempList);
		}


		# get the parent node
		$par = @tempList[$#tempList];
		$atId2 = $saidConv ? $$tag2Said{"$par"} : $par;

		$sgId1 = $sgidConv ? $$tag2SgId{"$nd"} : $nd;
		$sgId2 = $sgidConv ? $$tag2SgId{"$par"} : $par;


		### dump context for PAR
		if ($rtCxt ne '0' && $atId2 == $rtndSaid) {
		  $$rtCxt->dumpCxt({srcAtomId1 => $atId1, srcAtomId2 => $atId2,
							ptr => $sgIdTree, sgId1 => $sgId1,
							sgId2 => $atId2});
		} else {
		  $$pcCxt->dumpCxt({srcAtomId1 => $atId1, srcAtomId2 => $atId2,
							ptr => $sgIdTree, sgId1 => $sgId1,
							sgId2 => $sgId2});
		}


		# now dump the attribute
		#if ($cxtAttr ne 0 ) {
		  #$attrNum++;
		  #if ($attrNum < 11) {
			# get my name
			#$myName = $$tag2Name{"$nd"};

			# ancestors
			#$treeNames = join('~', (map {$$tag2Name{$_}} @tempList));
#

			#$$cxtAttr->dumpAttr
			  #({sgId => $atId1,
				#atv => "$attrNum\t::~~~~~~\t$treeNames\t$myName\t$chldNames\t$sibNames"});

		  #} elsif ($attrNum == 11) {
			## dump the special attribute stating that it has more
			## than 10 attrs here - never be the case in HCPCS.
			#$$cxtAttr->dumpAttr
			  #({sgId => $atId1,
				#atv => "$11\t::~~~~~~\t${rsab1} Concept\tMore contexts not shown\t\t"});
		  #}
		#}
      }
    }
    $$LogRef->logDebug("Done generating contexts.\n");

    # Release memory.
    $self->releaseMemory;
    return 0;
  }

}

1




