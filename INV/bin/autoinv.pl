#!/usr/bin/perl
# CHANGES
#  11/10/2006 BAC (1-CDMK9): use Digest::MD5 instead of MD5.
#  03/14/2007 NEO (1-DQJTT): add "NumberAfter|<filename>" specification option.
#  02/19/2008 NEO (1-GIRLM): fix to make <const:XYZ> work in where clauses
# e.g. "autoinv.pl inv.spec"

die "usage: $0 specfile ...\n" if $#ARGV < 0;

use Digest::MD5 qw(md5_hex);

$fieldSep = '|';   # default for SourceFieldSep

chomp($dir = `pwd`);
while (<>) {
    chomp;
    $specLine = $.;
    next if /^$/ || /^#/;
    if (s/^SourceDir\|//) {
        ($sourceDir, $recurse) = split(/\|/);
        $recurse = ($recurse eq 'recursive');
    } elsif (s/^SourceExt\|//) {
        $sourceExt = $_;
    } elsif (s/^SourceFieldSep\|//) {
        $fieldSep = $_;
        $fieldSep = "\t" if $fieldSep eq 'TAB';
        $fieldSep = '|' if $fieldSep eq 'BAR';
        die "bad SourceFieldSep $fieldSep at spec line $specLine, stopped" if length($fieldSep) != 1;
    } elsif (s/^Schema\|//) {
        ($file, $schema) = /^([^|]*)\|(.*)/;
        $schema{$file} = $schema;
    } elsif (s/^DefineConst\|([^|]*)\|//) {
        $constname = $1;
        $const{$constname} = $_;
    } elsif (s/^SourceSchemaDefType\|//) {
        $schemaType = $_;
    } elsif (s/^SourceAtomIdBase\|//) {
        $said = $_;
    } elsif (s/^SourceAtomIdLimit\|//) {
        $maxsaid = $_;
    } elsif (s/^Dest\|//) {
        $dest = $_;
        $line_number = 0;
        chdir $dir || die "can't change to $dir at spec line $specLine: $!\n";
        if ($dest =~ s/\|append$//) {
            open(OLD, "tail -1 $dest |") || die "can't open $dest at spec line $specLine: $!\n";
            $_ = <OLD>;
            close(OLD);
            chomp;
            s/\|.*//;
            $line_number = $_;
            open(OUT, ">>$dest") || die "can't append to $dest at spec line $specLine: $!\n";
        } else {
            open(OUT, ">$dest") || die "can't create $dest at spec line $specLine: $!\n";
        }
        select(OUT);
        $| = 1;
        select(STDOUT);
    } elsif (s/^NumberAfter\|//) {
        $fname = $_;
        chdir $dir || die "can't change to $dir at spec line $specLine: $!\n";
        open(OLD, "tail -1 $fname |") || die "can't open $fname at spec line $specLine: $!\n";
        $_ = <OLD>;
        close(OLD);
        chomp;
        s/\|.*//;
        $line_number = $_;
    } elsif (s/^Copy\|//) {
        $copyFile = $_;
        chdir $dir || die "can't change to $dir at spec line $specLine: $!\n";
        open(INPUT, $copyFile) || die "can't find Copy file $copyFile at spec line $specLine, stopped";
        while (<INPUT>) {
            print OUT $_;
            chomp;
            s/\|.*//;
            $line_number = $_;
        }
    } elsif (s/^Scan\|//) {
        $qual = '';
        $fileSpec = $_;
        if ($fileSpec =~ /\|/) {
            ($fileSpec, $qual) = ($fileSpec =~ /^([^|]*)\|(.*)/);
        }
        @specs = ();
        $allspecs = '';
        while (<>) {
            $specLine = $.;
            last if /^$/;
            next if /^#/;
            chomp;
            s/^\t//;
            push(@specs, $_);
            $allspecs .= $_;
        }
        $eof = ($_ eq '');
        die "no output spec lines for Scan|$fileSpec at spec line $specLine, stopped" if $#specs == -1;
        unless ($qual eq '' || $qual =~ s/^where //) {
            die "qualifier syntax error in Scan|$fileSpec|$qual at spec line $specLine, stopped";
        }
        $matchQual = '';
        if ($qual =~ /(\S+)\s+matches\s+(.+)/) {
            $matchQual = 1;
            $joinExpr = $1;
            $matchDest = $2;
            if (substr($matchDest,0,1) eq '"') {
                if ($qual =~ s/(\S+)\s+matches\s+"([^"]+)"/(\$thisMatches)/) {
                    $matchDest = $2;
                } else {
                    die "bad format in \"matches\" clause at spec line $specLine, stopped";
                }
            } else {
                if ($qual =~ s/(\S+)\s+matches\s+(\S+)/(\$thisMatches)/) {
                    $matchDest = $2;
                } else {
                    die "bad format in \"matches\" clause at spec line $specLine, stopped";
                }
            }
            if ($matchDest =~ /^([^.]*)\.([^.]*)$/) {
                $matchFileSpec = $1;
                $matchDestFieldName = $2;
            } else {
                $matchFileSpec = $matchDest;
                $matchDestFieldName = '';
            }
            @saveColumns = ();
            $matchFile = &findFile($matchFileSpec);
            open(MATCH, $matchFile) || die "can't open $matchFile at spec line $specLine: $!\n";
            if ($matchDestFieldName ne '') {
                if ($schemaType eq 'FirstLine') {
                    $matchSchema = <MATCH>;
                    chomp($matchSchema);
                    $matchSchema =~ s/\r$//;
                    $matchSchema =~ s/^\xEF\xBB\xBF//;
                } elsif ($schemaType eq 'InThisSpec') {
                    $matchSchema = $schema{$matchFileSpec};
                    $matchSchema = $schema{$matchFile} if $matchSchema eq '';
                    die "Schema not specified for $matchFileSpec at spec line $specLine, stopped" if $matchSchema eq '';
                } else {
                    die "unknown SourceSchemaDefType at spec line $specLine, stopped";
                }
                @matchSchema = split(/\Q$fieldSep\E/, $matchSchema);
                %matchFieldNum = ();
                for ($i=0; $i<=$#matchSchema; $i++) {
                    $matchFieldName = $matchSchema[$i];
                    $matchFieldNum{$matchFieldName} = $i;
                    push(@saveColumns, $matchFieldName) if $allspecs =~ /\Q$matchFileSpec\E\.($matchFieldName|<([^>]*:)?$matchFieldName>)/;
                }
                $matchDestFieldNum = $matchFieldNum{$matchDestFieldName};
                die "field $matchDestFieldName not found in $matchFileSpec at spec line $specLine, stopped" if $matchDestFieldNum eq '';
            }
            $joinUsed = 0;
            %match = ();
            while (<MATCH>) {
                chomp;
                s/\r$//;
                if ($matchDestFieldName ne '') {
                    @matchFields = split(/\Q$fieldSep\E/);
                    $matchDestFieldValue = $matchFields[$matchDestFieldNum];
                    $match{$matchDestFieldValue} = 1;
                    for ($i=0; $i<=$#saveColumns; $i++) {
                        $saveFieldName = $saveColumns[$i];
                        $saveFieldNum = $matchFieldNum{$saveFieldName};
                        die "non-unique join values for $matchDestFieldValue.$saveFieldName at spec line $specLine, stopped" if $match{"$matchDestFieldValue|$saveFieldName"} ne '' && $match{"$matchDestFieldValue|$saveFieldName"} ne $matchFields[$saveFieldNum];
                        $match{"$matchDestFieldValue|$saveFieldName"} = $matchFields[$saveFieldNum];
                        $joinUsed = 1;
                    }
                } else {
                    $match{$_} = 1;
                }
            }
        }
        # allow a second "matches" qualification
        $match2Qual = '';
        if ($qual =~ /(\S+)\s+matches\s+(.+)/) {
            $match2Qual = 1;
            $join2Expr = $1;
            $matchDest = $2;
            if (substr($matchDest,0,1) eq '"') {
                if ($qual =~ s/(\S+)\s+matches\s+"([^"]+)"/(\$thisMatches2)/) {
                    $matchDest = $2;
                } else {
                    die "bad format in \"matches\" clause at spec line $specLine, stopped";
                }
            } else {
                if ($qual =~ s/(\S+)\s+matches\s+(\S+)/(\$thisMatches2)/) {
                    $matchDest = $2;
                } else {
                    die "bad format in \"matches\" clause at spec line $specLine, stopped";
                }
            }
            if ($matchDest =~ /^([^.]*)\.([^.]*)$/) {
                $matchFileSpec2 = $1;
                $matchDestFieldName = $2;
            } else {
                $matchFileSpec2 = $matchDest;
                $matchDestFieldName = '';
            }
            @saveColumns = ();
            $matchFile = &findFile($matchFileSpec2);
            open(MATCH, $matchFile) || die "can't open $matchFile at spec line $specLine: $!\n";
            if ($matchDestFieldName ne '') {
                if ($schemaType eq 'FirstLine') {
                    $matchSchema = <MATCH>;
                    chomp($matchSchema);
                    $matchSchema =~ s/\r$//;
                    $matchSchema =~ s/^\xEF\xBB\xBF//;
                } elsif ($schemaType eq 'InThisSpec') {
                    $matchSchema = $schema{$matchFileSpec2};
                    $matchSchema = $schema{$matchFile} if $matchSchema eq '';
                    die "Schema not specified for $matchFileSpec2 at spec line $specLine, stopped" if $matchSchema eq '';
                } else {
                    die "unknown SourceSchemaDefType at spec line $specLine, stopped";
                }
                @matchSchema = split(/\Q$fieldSep\E/, $matchSchema);
                %matchFieldNum = ();
                for ($i=0; $i<=$#matchSchema; $i++) {
                    $matchFieldName = $matchSchema[$i];
                    $matchFieldNum{$matchFieldName} = $i;
                    push(@saveColumns, $matchFieldName) if $allspecs =~ /\Q$matchFileSpec2\E\.($matchFieldName|<([^>]*:)?$matchFieldName>)/;
                }
                $matchDestFieldNum = $matchFieldNum{$matchDestFieldName};
                die "field $matchDestFieldName not found in $matchFileSpec2 at spec line $specLine, stopped" if $matchDestFieldNum eq '';
            }
            $join2Used = 0;
            %match2 = ();
            while (<MATCH>) {
                chomp;
                s/\r$//;
                if ($matchDestFieldName ne '') {
                    @matchFields = split(/\Q$fieldSep\E/);
                    $matchDestFieldValue = $matchFields[$matchDestFieldNum];
                    $match2{$matchDestFieldValue} = 1;
                    for ($i=0; $i<=$#saveColumns; $i++) {
                        $saveFieldName = $saveColumns[$i];
                        $saveFieldNum = $matchFieldNum{$saveFieldName};
                        die "non-unique join values for $matchDestFieldValue.$saveFieldName at spec line $specLine, stopped" if $match2{"$matchDestFieldValue|$saveFieldName"} ne '' && $match2{"$matchDestFieldValue|$saveFieldName"} ne $matchFields[$saveFieldNum];
                        $match2{"$matchDestFieldValue|$saveFieldName"} = $matchFields[$saveFieldNum];
                        $join2Used = 1;
                    }
                } else {
                    $match2{$_} = 1;
                }
            }
        }
        # don't currently allow a third "matches" qualification
        if ($qual =~ /\S+\s+matches\s+\S+/) {
            die "Sorry, three or more \"matches\" clauses in one qualification are not\ncurrently supported (at spec line $specLine), stopped";
        }
        $fileName = &findFile($fileSpec);
        open(INPUT, $fileName) || die "can't open $fileName at spec line $specLine: $!\n";
        if ($schemaType eq 'FirstLine') {
            $schema = <INPUT>;
            chomp($schema);
            $schema =~ s/\r$//;
            $schema =~ s/^\xEF\xBB\xBF//;
        } elsif ($schemaType eq 'InThisSpec') {
            $schema = $schema{$fileSpec};
            $schema = $schema{$fileName} if $schema eq '';
            die "Schema not specified for $fileSpec at spec line $specLine, stopped" if $schema eq '';
        } else {
            die "unknown SourceSchemaDefType at spec line $specLine, stopped";
        }
        @schema = split(/\Q$fieldSep\E/, $schema);
        for ($i=0; $i<=$#schema; $i++) {
            $fieldNum{$schema[$i]} = $i;
        }
        while (<INPUT>) {
            chomp;
            s/\r$//;
            $inputLine = $_;
            @fields = split(/\Q$fieldSep\E/);
            if ($matchQual) {
                $joinValue = &fillFields($joinExpr, 0);
                $thisMatches = $match{$joinValue};
            }
            if ($match2Qual) {
                $join2Value = &fillFields($join2Expr, 0);
                $thisMatches2 = $match2{$join2Value};
            }
            if ($qual eq '' || &evalQual($qual)) {
                foreach $spec (@specs) {
                    $output = $spec;
                    if ($joinUsed) {
                        while ($output =~ /\Q$matchFileSpec\E\.(<replace:[^:]*:[^:]*:[\w:]+>|[\w<>:]+)/) {
                            $fieldName = $1;
                            $encode = $squeeze = $toReplace = $replaceWith = '';
                            if ($fieldName =~ /^<(.*)>$/) {
                                $fieldName = $1;
                                $encode = ($fieldName =~ s/^XMLcodeOf://);
                                $squeeze = ($fieldName =~ s/^squeeze://);
                                if ($fieldName =~ s/^replace:([^:]*):([^:]*)://) {
                                    $toReplace = $1;
                                    $replaceWith = $2;
                                }
                            }
                            $val = $match{"$joinValue|$fieldName"};
                            $val =~ s/\Q$toReplace\E/$replaceWith/g if $toReplace ne '';
                            $val = sprintf("&#x%02X;", ord($val)) if $encode;
                            $val =~ tr/|/ /;  # remove any "|" chars from data 
                            if ($squeeze) {
                                $val =~ s/  +/ /g;
                                $val =~ s/^ //;
                                $val =~ s/ $//;
                            }
                            $output =~ s/\Q$matchFileSpec\E\.(<replace:[^:]*:[^:]*:[\w:]+>|[\w<>:]+)/$val/;
                        }
                    }
                    if ($join2Used) {
                        while ($output =~ /\Q$matchFileSpec2\E\.(<replace:[^:]*:[^:]*:[\w:]+>|[\w<>:]+)/) {
                            $fieldName = $1;
                            $encode = $squeeze = $toReplace = $replaceWith = '';
                            if ($fieldName =~ /^<(.*)>$/) {
                                $fieldName = $1;
                                $encode = ($fieldName =~ s/^XMLcodeOf://);
                                $squeeze = ($fieldName =~ s/^squeeze://);
                                if ($fieldName =~ s/^replace:([^:]*):([^:]*)://) {
                                    $toReplace = $1;
                                    $replaceWith = $2;
                                }
                            }
                            $val = $match2{"$join2Value|$fieldName"};
                            $val =~ s/\Q$toReplace\E/$replaceWith/g if $toReplace ne '';
                            $val = sprintf("&#x%02X;", ord($val)) if $encode;
                            $val =~ tr/|/ /;  # remove any "|" chars from data 
                            if ($squeeze) {
                                $val =~ s/  +/ /g;
                                $val =~ s/^ //;
                                $val =~ s/ $//;
                            }
                            $output =~ s/\Q$matchFileSpec2\E\.(<replace:[^:]*:[^:]*:[\w:]+>|[\w<>:]+)/$val/;
                        }
                    }
                    if ($output =~ /^\bsrc_atom_id\b/) {
                        die "SourceAtomIdBase not specified at spec line $specLine, stopped" if $said eq '';
                        ++$said;
                        die "SourceAtomIdLimit $maxsaid exceeded at spec line $specLine, stopped" if $maxsaid ne '' && $said > $maxsaid;
                        $output =~ s/\bsrc_atom_id\b/$said/g;
                    }
                    $output = &fillFields($output, 0);
                    if ($output =~ /\|md5hash\|$/) {
                        @outFields = split(/\|/, $output);
                        $attrVal = $outFields[4];
                        $md5hash = md5_hex($attrVal);
                        $output =~ s/\|md5hash\|$/|$md5hash|/;
                    }
                    #{ to balance next line
                    if ($output =~ /^(.*)\{split:(.):([^}]*)\}(.*)$/) {
                        $left = $1;
                        $splitChar = $2;
                        $values = $3;
                        $right = $4;
                        @values = split(/\Q$splitChar\E/, $values);
                        foreach $value (@values) {
                            if ($left =~ /\bline_number\b/ || $right =~ /\bline_number\b/) {
                                ++$line_number;
                                ($leftout = $left) =~ s/\bline_number\b/$line_number/g;
                                ($rightout = $right) =~ s/\bline_number\b/$line_number/g;
                            }
                            print OUT "$leftout$value$rightout\n";
                        }
                    } else {
                        if ($output =~ /\bline_number\b/) {
                            ++$line_number;
                            $output =~ s/\bline_number\b/$line_number/g;
                        }
                        print OUT "$output\n";
                    }
                }
            }
        }
    }
    last if $eof;
}

close(OUT);

sub evalQual {
    local($qual) = @_;
    local($substitutedQual, $val, $cmd);
    $substitutedQual = &fillFields($qual, 1);
    $cmd = "\$val = ($substitutedQual)";
    eval $cmd;
    return $val;
}

# fillFields($str, $asExpr): substitutes fields marked as "<FIELDNAME>"
# in $str with the contents of field FIELDNAME from the %fields array.
# If FIELDNAME is given as "const:CONSTNAME", then instead of replacing it
# with the contents of a field from the input file, it will be replaced
# with the value of the specified constant set with the DefineConst directive.
# If FIELDNAME is given as "XMLcodeOf:FIELDNAME", then it will substitute
# the XML character entity for the first char of the field contents, e.g.,
# "|" will become: "&#x7C;"
# If FIELDNAME is given as "replace:x:y:FIELDNAME", then all instances of
# x in the contents of FIELDNAME will be replaced with y.
# If the contents of FIELDNAME, after processing any "replace" specification,
# includes any "|" characters, they will be converted to spaces (but this
# conversion is not done if FIELDNAME is "WholeLine").
# If FIELDNAME is given as "squeeze:FIELDNAME", then multiple consecutive
# spaces in the contents of FIELDNAME will be replaced with a single space,
# and leading/trailing spaces will be deleted.
# The combination "squeeze:replace:x:y:FIELDNAME" also works, but other
# combinations may not.
# The special FIELDNAME "WholeLine" refers to a copy of the entire input line.
# If $asExpr is true, then each instance of a <FIELDNAME> will be
# replaced with a perl expression that will eval to the fieldValue
# instead of being replaced with the fieldValue itself

sub fillFields {
    local($str, $asExpr) = @_;
    local($pos, $fieldSpec, $fieldName, $val, $encode, $squeeze, $fieldNum);
    local($right, $const, $toReplace, $replaceWith);
    $pos=0;
    while (($pos = index($str, '<', $pos)) >= 0) {
        if (substr($str, $pos) =~ /^<([^>]+)>/) {
            $fieldSpec = $1;
            $fieldName = $fieldSpec;
            $encode = ($fieldName =~ s/^XMLcodeOf://);
            $squeeze = ($fieldName =~ s/^squeeze://);
            $const = ($fieldName =~ s/^const://);
            $toReplace = $replaceWith = '';
            if ($fieldName =~ s/^replace:([^:]*):([^:]*)://) {
                $toReplace = $1;
                $replaceWith = $2;
            }
            if ($const) {
                if (defined $const{$fieldName}) {
                    $val = $const{$fieldName};
                    $fieldNum = $fieldName;  # used for $val... varname if $asExpr
                } else {
                    die "constant $fieldName hasn't been defined at spec line $specLine, stopped";
                }
            } else {
                if ($fieldName eq 'WholeLine') {
                    $val = $inputLine;
                } else {
                    $fieldNum = $fieldNum{$fieldName};
                    die "field $fieldName not found at spec line $specLine, stopped" if $fieldNum eq '';
                    $val = $fields[$fieldNum];
                }
            }
            $val =~ s/\Q$toReplace\E/$replaceWith/g if $toReplace ne '';
            $val = sprintf("&#x%02X;", ord($val)) if $encode;
            # remove any "|" chars from data 
            $val =~ tr/|/ / if $fieldName ne 'WholeLine';
            if ($squeeze) {
                $val =~ s/  +/ /g;
                $val =~ s/^ //;
                $val =~ s/ $//;
            }
            if ($asExpr) {
                eval "\$val$fieldNum = \$val";
                $right = substr($str,$pos+length($fieldSpec)+2);
                $str = substr($str,0,$pos) . "\${val$fieldNum}";
                $pos = length($str)-1;
                $str .= $right;
            } else {
                $right = substr($str,$pos+length($fieldSpec)+2);
                $str = substr($str,0,$pos) . $val;
                $pos = length($str)-1;
                $str .= $right;
            }
        }
        ++$pos;
    }
#    ###### old: ######
#    while ($str =~ /\G.*<([^|>]+)>/) {
#       $fieldSpec = $1;
#       $fieldName = $fieldSpec;
#       $encode = ($fieldName =~ s/^XMLcodeOf://);
#       $fieldNum = $fieldNum{$fieldName};
#       die "field $fieldName not found at spec line $specLine, stopped" if $fieldNum eq '';
#       $val = $fields[$fieldNum];
#       $val = ord($val) if $encode;
#       if ($asExpr) {
#           eval "\$val$fieldNum = \$val";
#           $str =~ s/<\Q$fieldSpec\E>/\$val$fieldNum/;
#       } else {
#           $str =~ s/<\Q$fieldSpec\E>/$val/;
#       }
#    }
    return $str;
}

# findFile($fileSpec): find file matching fileSpec; if fileSpec has '*'
# wildcards, looks for file ending with $sourceExt; otherwise, looks for
# file with the exact name "$fileSpec"; searches directories below
# $sourceDir if $recurse is true, otherwise just in $sourceDir; returns
# the resulting filename relative to $sourceDir (and leaves $sourceDir
# as the current directory); gives error if multiple matches are found.
#
# However, if $fileSpec starts with "/", it is returned as an absolute
# pathname, and no matching or searching is done.

sub findFile {
    local($fileSpec) = @_;
    local($files, @files, $searchStr);
    $searchStr = ($fileSpec =~ /\*/) ? "$fileSpec$sourceExt" : $fileSpec;
    return $searchStr if $searchStr =~ m@^/@;
    if ($sourceDir ne '') {
        chdir $sourceDir || die "can't change to $sourceDir at spec line $specLine: $!\n";
    }
    if ($recurse) {
        $files = `find . -name "$searchStr" -print`;
    } else {
        $files = `find . \! -name '.' -type d -prune -o -name "$searchStr" -print`;
    }
    @files = split(/\n/, $files);
    die "multiple files found matching $searchStr at spec line $specLine, stopped" if $#files > 0;
    die "no file found matching $searchStr at spec line $specLine, stopped" if $#files == -1;
    return $files[0];
}
