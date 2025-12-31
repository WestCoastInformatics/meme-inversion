#!/usr/bin/perl
# Module to read inversion_config.json and process new elements
# This should be included in invert_NCI.pl

use strict;
use warnings;
use JSON::PP;

# Load configuration from JSON file
sub loadInversionConfig {
    my $config_file = shift || "../etc/inversion_config.json";

    if (! -f $config_file) {
        print "No inversion config file found at $config_file - skipping dynamic configuration\n";
        return undef;
    }

    # Read file using built-in Perl functions
    open(my $fh, '<', $config_file) or die "Cannot open $config_file: $!";
    my $json_text = do { local $/; <$fh> };
    close($fh);

    my $json = JSON::PP->new;
    my $config = $json->decode($json_text);

    print "Loaded inversion configuration from $config_file\n";
    return $config;
}

# Process subsources from config
sub processSubsourceAtomsFromConfig {
    my ($config, $miscAtom1, $miscAtom2, $miscAtom3, $tgRel, $misc_merge, $Attribute) = @_;

    # Check if processing is enabled
    if (!$config->{options}->{process_subsources}) {
        print "Subsource processing disabled in config\n";
        return;
    }

    my $subsources = $config->{new_subsources};
    if (!$subsources || scalar(@$subsources) == 0) {
        print "No new subsources defined in config\n";
        return;
    }

    print "Processing " . scalar(@$subsources) . " new subsource(s) from config\n";

    foreach my $subsource (@$subsources) {
        my $code = $subsource->{code};
        my $abbrev = $subsource->{abbreviation};
        my $fullname = $subsource->{full_name};
        my $semantic_type = $subsource->{semantic_type} || "Intellectual Product";

        print "  Processing subsource: $code\n";

        # Create RPT atom (full name)
        $miscAtom1->dumpAtom({
            str => $fullname,
            code => "V-$code",
            tty => 'RPT',
            vsab => 'SRC'
        });
        my $misc_ID1 = $miscAtom1->getLastId();

        # Create RAB atom (abbreviation)
        $miscAtom2->dumpAtom({
            str => $abbrev,
            code => "V-$code",
            tty => 'RAB',
            vsab => 'SRC'
        });
        my $misc_ID2 = $miscAtom2->getLastId();

        # Create SSN atom (source short name)
        $miscAtom3->dumpAtom({
            str => $abbrev,
            code => "V-$code",
            tty => 'SSN',
            vsab => 'SRC'
        });
        my $misc_ID3 = $miscAtom3->getLastId();

        # Create relationship to MTH
        $tgRel->dumpRel({
            sgId1 => 'V-MTH',
            sgId2 => "V-$code",
            rel => 'RT',
            rela => '',
            sgQual1 => 'SRC',
            sgQual2 => 'SRC',
            vsab => 'SRC',
            sl => 'SRC'
        });

        # Merge atoms
        $misc_merge->dumpMerge({
            sgId1 => $misc_ID1,
            sgId2 => $misc_ID2,
            mergeSet => 'NCI-SRC',
            sgType1 => 'SRC_ATOM_ID',
            sgType2 => 'SRC_ATOM_ID',
            vsab => 'SRC'
        });

        $misc_merge->dumpMerge({
            sgId1 => $misc_ID1,
            sgId2 => $misc_ID3,
            mergeSet => 'NCI-SRC',
            sgType1 => 'SRC_ATOM_ID',
            sgType2 => 'SRC_ATOM_ID',
            vsab => 'SRC'
        });

        # Add semantic type attribute
        $Attribute->dumpAttr({
            sgId => $misc_ID1,
            lvl => 'C',
            atn => "SEMANTIC_TYPE",
            atv => $semantic_type,
            vsab => "SRC",
            sgType => 'SRC_ATOM_ID',
            sgQual => ""
        });

        print "  Completed subsource: $code\n";
    }

    print "Completed processing all subsources\n";
}

# Process source metadata and update sources.src
sub processSourceMetadataFromConfig {
    my ($config) = @_;

    # Check if processing is enabled
    if (!$config->{options}->{process_source_metadata}) {
        print "Source metadata processing disabled in config\n";
        return;
    }

    my $metadata_entries = $config->{new_source_metadata};
    if (!$metadata_entries || scalar(@$metadata_entries) == 0) {
        print "No new source metadata defined in config\n";
        return;
    }

    print "Processing " . scalar(@$metadata_entries) . " new source metadata entr(ies) from config\n";

    # Get version info
    my $current_version = $config->{version_info}->{current_version};
    my $previous_version = $config->{version_info}->{previous_version};

    # Extract VSABs (remove NCI_ prefix)
    my $current_vsab = $current_version;
    $current_vsab =~ s/^NCI_//;
    my $previous_vsab = $previous_version;
    $previous_vsab =~ s/^NCI_//;

    # Path to sources.src file
    my $sources_file = "../src/sources.src";

    if (! -f $sources_file) {
        print "WARNING: sources.src not found at $sources_file - cannot add metadata\n";
        return;
    }

    # Read existing sources.src
    open(my $fh, '<', $sources_file) or die "Cannot open $sources_file: $!";
    my @lines = <$fh>;
    close($fh);

    # Build new entries
    my @new_entries;
    foreach my $meta (@$metadata_entries) {
        my $code = $meta->{code};
        my $source_family = $meta->{source_family} || "NCI";
        my $full_name = $meta->{full_name};
        my $contact = $meta->{contact} || "";
        my $url = $meta->{url} || "";
        my $language = $meta->{language} || "ENG";
        my $acq_contact = $meta->{acquisition_contact} || "";
        my $content_contact = $meta->{content_contact} || "";
        my $license_contact = $meta->{license_contact} || "";
        my $context = $meta->{context} || "";
        my $charset = $meta->{character_set} || "UTF-8";

        # Get previous source - if specified, use that instead of previous version of same source
        my $prev_source = $meta->{previous_source};
        my $vsab_field;

        if ($prev_source) {
            # Use specified previous source with current VSAB
            $vsab_field = "${prev_source}_${current_vsab}";
            print "  Adding source metadata for: $code (previous source: $prev_source)\n";
        } else {
            # Use previous version of the same source
            $vsab_field = "${code}_${previous_vsab}";
            print "  Adding source metadata for: $code (previous version)\n";
        }

        # Build the pipe-delimited line
        # Format: RSAB|VSAB|SON|SF|SVER|VSTART|VEND|IMETA|RMETA|SLC|SCC|SRL|TFR|CFR|CXTY|TTYL|ATNL|LAT|CENC|CURVER|SABIN|SSN|SCIT|
        my $line = join('|',
            "${code}_${current_vsab}",       # RSAB: root source abbreviation
            $vsab_field,                      # VSAB: versioned source abbreviation (may reference different source)
            "0",                              # SON: source official name
            "${code}_${current_vsab}",       # SF: source family
            $code,                            # SVER: source version
            $current_vsab,                    # VSTART: version start
            $source_family,                   # VEND: version end
            $full_name,                       # IMETA: internal meta
            "",                               # RMETA: restriction meta
            $contact,                         # SLC: source language code
            $content_contact,                 # SCC: source citation code
            $license_contact,                 # SRL: source restriction level
            $acq_contact,                     # TFR: term frequency
            "",                               # CFR: CUI frequency
            $url,                             # CXTY: context type
            $language,                        # TTYL: term type list
            $context,                         # ATNL: attribute name list
            "",                               # LAT: language
            $charset,                         # CENC: character encoding
            "",                               # CURVER: current version
            "",                               # SABIN: (empty)
            "",                               # SSN: (empty)
            ""                                # SCIT: (empty)
        );

        push @new_entries, "$line|\n";  # Add trailing pipe
    }

    # Deduplicate: Remove existing entries for the codes we are adding
    foreach my $meta (@$metadata_entries) {
        my $code = $meta->{code};
        # Remove lines where the first field (RSAB) matches the code (ignoring version suffix)
        @lines = grep { 
            my ($rsab) = split(/\|/); 
            # Check if RSAB starts with Code_
            !($rsab && $rsab =~ /^$code\_/) 
        } @lines;
    }

    # Append new entries to list
    push @lines, @new_entries;

    # Sort lines alphabetically
    my @sorted_lines = sort @lines;

    # Write updated sources.src
    open($fh, '>', $sources_file) or die "Cannot write to $sources_file: $!";
    print $fh $_ for @sorted_lines;
    close($fh);

    print "Completed adding, deduplicating, and sorting " . scalar(@new_entries) . " source metadata entr(ies) in sources.src\n";
}

# Process termgroup metadata and update termgroups.src
sub processTermgroupMetadataFromConfig {
    my ($config) = @_;

    # Check if processing is enabled
    if (!$config->{options}->{process_termgroup_metadata}) {
        print "Termgroup metadata processing disabled in config\n";
        return;
    }

    my $metadata_entries = $config->{new_termgroup_metadata};
    if (!$metadata_entries || scalar(@$metadata_entries) == 0) {
        print "No new termgroup metadata defined in config\n";
        return;
    }

    print "Processing " . scalar(@$metadata_entries) . " new termgroup metadata entr(ies) from config\n";

    # Get version info
    my $current_version = $config->{version_info}->{current_version};
    my $previous_version = $config->{version_info}->{previous_version};

    # Extract VSABs (remove NCI_ prefix)
    my $current_vsab = $current_version;
    $current_vsab =~ s/^NCI_//;
    my $previous_vsab = $previous_version;
    $previous_vsab =~ s/^NCI_//;

    # Path to termgroups.src file
    my $termgroups_file = "../src/termgroups.src";

    if (! -f $termgroups_file) {
        print "WARNING: termgroups.src not found at $termgroups_file - cannot add metadata\n";
        return;
    }

    # Read existing termgroups.src
    open(my $fh, '<', $termgroups_file) or die "Cannot open $termgroups_file: $!";
    my @lines = <$fh>;
    close($fh);

    # Build new entries
    my @new_entries;
    foreach my $meta (@$metadata_entries) {
        my $code = $meta->{code};
        my $termgroups = $meta->{termgroups};

        # Get previous source - if specified, use that instead of previous version of same source
        my $prev_source = $meta->{previous_source};
        my $prev_vsab_entry;

        if ($prev_source) {
            # Use specified previous source with current VSAB
            $prev_vsab_entry = "${prev_source}_${current_vsab}";
            print "  Adding termgroup metadata for: $code (previous source: $prev_source)\n";
        } else {
            # Use previous version of the same source
            $prev_vsab_entry = "${code}_${previous_vsab}";
            print "  Adding termgroup metadata for: $code (previous version)\n";
        }

        if (!$termgroups || scalar(@$termgroups) == 0) {
            print "  WARNING: No termgroups defined for $code - skipping\n";
            next;
        }

        foreach my $tg (@$termgroups) {
            my $tty = $tg->{tty};
            my $suppress = $tg->{suppress} || "N";
            my $obsolete = $tg->{obsolete} || "N";
            my $normalized = $tg->{normalized} || "N";

            # Format: SOURCE_VSAB/TTY|PREV_SOURCE_VSAB/TTY|suppress|obsolete|normalized|TTY|
            my $line = join('|',
                "${code}_${current_vsab}/${tty}",
                "${prev_vsab_entry}/${tty}",
                $suppress,
                $obsolete,
                $normalized,
                $tty,
                ""  # trailing empty field
            );

            push @new_entries, "$line\n";
            print "    Added: ${code}_${current_vsab}/${tty} -> ${prev_vsab_entry}/${tty}\n";
        }
    }

    # Append new entries to termgroups.src
    open($fh, '>>', $termgroups_file) or die "Cannot append to $termgroups_file: $!";
    print $fh $_ for @new_entries;
    close($fh);

    print "Completed adding " . scalar(@new_entries) . " termgroup entr(ies) to termgroups.src\n";
}

# Update nci.cfg with new subsource configuration
sub updateNciCfgFromConfig {
    my ($config) = @_;

    # Check if processing is enabled
    if (!$config->{options}->{process_subsources}) {
        print "Subsource processing disabled in config - skipping nci.cfg update\n";
        return;
    }

    my $subsources = $config->{new_subsources};
    if (!$subsources || scalar(@$subsources) == 0) {
        print "No new subsources defined in config - skipping nci.cfg update\n";
        return;
    }

    # Get version info
    my $current_version = $config->{version_info}->{current_version};

    # Extract VSAB (remove NCI_ prefix)
    my $current_vsab = $current_version;
    $current_vsab =~ s/^NCI_//;

    # Path to nci.cfg file
    my $cfg_file = "../etc/nci.cfg";

    if (! -f $cfg_file) {
        print "WARNING: nci.cfg not found at $cfg_file - cannot update configuration\n";
        return;
    }

    print "Updating nci.cfg with " . scalar(@$subsources) . " new subsource(s)\n";

    # Read existing nci.cfg
    open(my $fh, '<', $cfg_file) or die "Cannot open $cfg_file: $!";
    my @lines = <$fh>;
    close($fh);

    # Track what we've added
    my %added_codes = ();

    foreach my $subsource (@$subsources) {
        my $code = $subsource->{code};
        my $abbrev = $subsource->{abbreviation};
        my $fullname = $subsource->{full_name};

        print "  Updating nci.cfg for: $code\n";

        # 1. Update CFG2RSAB list
        my $updated_cfg2rsab = 0;
        for (my $i = 0; $i < scalar(@lines); $i++) {
            if ($lines[$i] =~ /^CFG2RSAB\s*=/) {
                # Check if code already exists in the list
                if ($lines[$i] !~ /'$code'/) {
                    # Find appropriate position to insert (after 'FDA' or at end before last quote)
                    if ($lines[$i] =~ /('FDA')(,\s*'[^']+')/) {
                        # Insert after FDA
                        $lines[$i] =~ s/('FDA')(,)/$1, '$code'$2/;
                        print "    Updated CFG2RSAB list (added after FDA)\n";
                        $updated_cfg2rsab = 1;
                    } else {
                        # Fallback: add before the last entry
                        $lines[$i] =~ s/(\s*)$/,  '$code'$1/;
                        print "    Updated CFG2RSAB list (added at end)\n";
                        $updated_cfg2rsab = 1;
                    }
                } else {
                    print "    Code '$code' already in CFG2RSAB list\n";
                    $updated_cfg2rsab = 1;
                }
                last;
            }
        }

        if (!$updated_cfg2rsab) {
            print "    WARNING: Could not find CFG2RSAB line in nci.cfg\n";
        }

        # 2. Add vsab.{code} entry (after vsab.FDA or in vsab section)
        my $found_vsab = 0;
        for (my $i = 0; $i < scalar(@lines); $i++) {
            if ($lines[$i] =~ /^vsab\.$code\s*=/) {
                print "    vsab.$code entry already exists\n";
                $found_vsab = 1;
                last;
            }
        }

        if (!$found_vsab) {
            # Find position after vsab.FDA or vsab.EDQM-HC
            my $insert_pos = -1;
            for (my $i = 0; $i < scalar(@lines); $i++) {
                if ($lines[$i] =~ /^vsab\.(FDA|EDQM-HC)\s*=/) {
                    $insert_pos = $i + 1;
                    last;
                }
            }

            if ($insert_pos > 0) {
                splice(@lines, $insert_pos, 0, "vsab.$code = ${code}_${current_vsab}\n");
                print "    Added vsab.$code = ${code}_${current_vsab}\n";
            } else {
                print "    WARNING: Could not find position to insert vsab.$code\n";
            }
        }

        # 3. Add rsab.{code} entry (after rsab.FDA or in rsab section)
        my $found_rsab = 0;
        for (my $i = 0; $i < scalar(@lines); $i++) {
            if ($lines[$i] =~ /^rsab\.$code\s*=/) {
                print "    rsab.$code entry already exists\n";
                $found_rsab = 1;
                last;
            }
        }

        if (!$found_rsab) {
            # Find position after rsab.FDA or rsab.EDQM-HC
            my $insert_pos = -1;
            for (my $i = 0; $i < scalar(@lines); $i++) {
                if ($lines[$i] =~ /^rsab\.(FDA|EDQM-HC)\s*=/) {
                    $insert_pos = $i + 1;
                    last;
                }
            }

            if ($insert_pos > 0) {
                splice(@lines, $insert_pos, 0, "rsab.$code = $code\n");
                print "    Added rsab.$code = $code\n";
            } else {
                print "    WARNING: Could not find position to insert rsab.$code\n";
            }
        }

        # 4. Add {code}_{vsab}.RSSN entry (after FDA_{vsab}.RSSN or in RSSN section)
        my $rssn_key = "${code}_${current_vsab}";
        my $found_rssn = 0;
        for (my $i = 0; $i < scalar(@lines); $i++) {
            if ($lines[$i] =~ /^${rssn_key}\.RSSN\s*=/) {
                print "    ${rssn_key}.RSSN entry already exists\n";
                $found_rssn = 1;
                last;
            }
        }

        if (!$found_rssn) {
            # Find position after FDA_{vsab}.RSSN or EDQM-HC_{vsab}.RSSN
            my $insert_pos = -1;
            for (my $i = 0; $i < scalar(@lines); $i++) {
                if ($lines[$i] =~ /^(FDA|EDQM-HC)_${current_vsab}\.RSSN\s*=/) {
                    $insert_pos = $i + 1;
                    last;
                }
            }

            if ($insert_pos > 0) {
                splice(@lines, $insert_pos, 0, "${rssn_key}.RSSN = $fullname\n");
                print "    Added ${rssn_key}.RSSN = $fullname\n";
            } else {
                print "    WARNING: Could not find position to insert ${rssn_key}.RSSN\n";
            }
        }

        $added_codes{$code} = 1;
    }

    # Write updated nci.cfg
    open($fh, '>', $cfg_file) or die "Cannot write to $cfg_file: $!";
    print $fh $_ for @lines;
    close($fh);

    print "Completed updating nci.cfg with " . scalar(keys %added_codes) . " subsource(s)\n";
}

1; # Return true for module
