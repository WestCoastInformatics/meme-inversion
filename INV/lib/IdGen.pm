#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");

package IdGen;

{
  # here we are restricting one and only one copy for the entire application.
  # any attemp to create another object returns the existing object.
  my $_theIdGen;
  my $_atomId = 0;
  my $_attrId = 0;
  my $_relId = 0;
  my $_mthId = 0;


  sub new {
    if (!defined($_theIdGen)) {
      my ($class, $atomId, $attrId, $relId) = @_;
      $_atomId = $atomId if (defined($atomId));
      $_attrId = $attrId if (defined($attrId));
      $_relId = $relId if (defined($relId));
      my $ref = {};
      $_theIdGen = bless($ref, $class);
    }
    return $_theIdGen;
  }

  sub reset {
    my ($self, $atomId, $attrId, $relId) = @_;
    $_atomId = $atomId if (defined($atomId));
    $_attrId = $attrId if (defined($attrId));
    $_relId = $relId if (defined($relId));
  }

  sub newAid {
    return $_atomId++;
  }

  sub newAtid {
    return $_attrId++;
  }
  sub newRid {
    return $_relId++;
  }

  sub newMthId {
    $_mthId++;
    return sprintf("MTHU%06d", $_mthId);
  }

  sub startMthId {
    my ($self, $mid) = @_;
    $_mthId = $mid if (defined($mid));
  }

  sub curAtomId { return $_atomId; }
  sub curAttrId { return $_attrId; }
  sub curRelId  { return $_relId; }
  sub curMthId  { return sprintf("MTHU%06d", $_mthId); }

}
1
