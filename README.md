# NCI Thesaurus Inversion Automation Script

## Overview

This script automates the NCI Thesaurus inversion process based on the NCIt Inversion Documentation. It adapts the Linux-based workflow for Windows/Git Bash environment.

## Prerequisites

### 1. Software Requirements
- **Git Bash** (MINGW64) - for running the script
- **Perl 64-bit** with required modules (see INV/INSTALL.txt):
  - Carp, Config::Properties, DBD::Oracle, DBI, Digest::MD5
  - Encode, File::Basename, File::Copy, File::Find, FindBin
  - Getopt::Long, Getopt::Std, IO::Handle, Symbol
  - Text::Wrap, Time::Local, Tk modules

### 2. Directory Structure
```
C:/workspace-meme-inversion/
├── INV/                          # Inversion framework (already present)
│   ├── bin/                      # Framework scripts
│   ├── lib/                      # Perl modules
│   ├── etc/                      # Framework documentation and reference files
│   └── config/                   # User-provided configuration files
│       ├── inversion_config_template.json
│       └── api_metadata_export.txt
├── sources/                      # Source inversions directory (will be created)
│   ├── NCI_2025_06E/            # Previous version (must exist)
│   └── NCI_2025_07D/            # Current version (will be created)
├── run_nci_inversion.sh          # This automation script
└── NCIt Inversion Documentation.txt
```

### 3. Required Data Before Running

#### a) Inversion Configuration File

**REQUIRED**: User must provide `INV/config/inversion_config.json` before running the inversion.

**Location**: `INV/config/inversion_config.json`

**How to Prepare**:

**For each NEW version**, edit the existing `INV/config/inversion_config.json`:
- Update `current_version` to the new version (e.g., `NCI_2025_09E`)
- Update `previous_version` to the prior version (e.g., `NCI_2025_08D`)
- Update `prior_previous_version` to two versions back (e.g., `NCI_2025_07D`)
- Update `runtime_parameters`:
  - `previous_month` (e.g., `August`)
  - `current_month` (e.g., `September`)
  - `said_start` (from new SAID range request - see section 3d)
  - `meta_export_file` (filename in sources/ directory, e.g., `meta_export_25.09e.zip`)
- Add any new subsources for this release
- Add any new source metadata or termgroup metadata
- Add any new attributes or MRDOC entries
- Adjust option flags (`true`/`false`) based on what's being added

**First time only** (if file doesn't exist):
```bash
cp INV/config/inversion_config_template.json INV/config/inversion_config.json
# Then edit as described above
```

**See**: `INV/config/INVERSION_CONFIG_README.md` for detailed documentation

**Important Notes**:
- The script checks for this file in Step 2.6 and exits if not found
- The script does NOT overwrite this file - you can re-run for testing without losing changes
- Prepare this file once per version, then run the script as many times as needed for testing

#### b) Metadata Export File (For Offline Environments)

**Background:**
The MRDOC generation process (Step 15) requires metadata from the NCIMeta API to populate RELA inverse mappings, expanded forms, and TTY classifications. In an offline environment (like Windows/Git Bash), direct API access isn't available.

**Solution:**
Extract metadata on a server with API access and copy it to your offline environment.

**On the Server (with API access):**
1. Ensure environment variables are set:
   ```bash
   echo $MEME_HOME   # Should point to MEME installation
   echo $INV_HOME    # Should point to INV directory
   ```

2. Run the extraction script:
   ```bash
   cd $INV_HOME/bin
   ./extract_metadata.sh
   ```

3. This creates `$INV_HOME/config/api_metadata_export.txt` containing:
   - **[RELA_INVERSE]** - Relationship attribute inverse mappings
   - **[EXPANDED_FORM]** - Full names for TTY, ATN, and RELA codes
   - **[TTY_CLASS]** - Term type classifications (preferred, synonym, abbreviation, etc.)

4. Copy the file to your offline environment:
   ```bash
   # Example using scp
   scp $INV_HOME/config/api_metadata_export.txt user@offline-machine:/path/to/INV/config/
   ```

**In Your Offline Environment:**
- Place `api_metadata_export.txt` in `C:/workspace-meme-inversion/INV/config/`
- The `makeDoc.pl` script will automatically detect and use this file instead of making API calls

**File Format:**
```
[RELA_INVERSE]
3_UTR_of|Has_3_UTR
Allele_of|Has_Allele
...

[EXPANDED_FORM]
TTY|AB|expanded_form|Abbreviation
ATN|ALT_DEFINITION|expanded_form|Alternative Definition
RELA|isa|expanded_form|Has Parent
...

[TTY_CLASS]
TTY|AB|tty_class|abbreviation
TTY|PT|tty_class|preferred
...
```

**When to Re-extract:**
- Before each new inversion release (to capture any new metadata)
- If new RELAs, ATNs, or TTYs have been added to NCIMTH
- If RELA inverse mappings have changed

**Scripts Involved:**
- `INV/bin/extract_metadata.sh` - Orchestrates the extraction process
- `INV/bin/api_metadata.sh` - Low-level API wrapper (called by extract_metadata.sh)
- `INV/config/api_metadata_export.txt` - Output file used by makeDoc.pl

#### c) Previous Inversion Directory
The previous version directory must exist with the following structure:
```
sources/NCI_2025_06E/
├── bin/           # Inversion scripts to copy
├── etc/           # Config files, README, si_proposal, qa/
├── src/           # sources.src, termgroups.src
└── orig/          # MRDOC.TREF, MRSAB.TREF
```

#### d) Source Atom ID (SAID) Range
**Manual Step Required:**
1. Login to: `meme-edit.semantics.cancer.gov/ncim-server-rest/index.html#/login`
2. Go to **Inversion** tab
3. Click **"Request Range"**
4. Enter:
   - Versioned Terminology: `NCI_2025_07D`
   - Number of IDs: `900000`
5. Click **"Add"**
6. Note the **Min** number (e.g., `750646883`) - you'll need this for the script

#### e) Meta Export File (Source Data)
Download from NCI FTP (or obtain from source):
```bash
# Example filename: meta_export_25.07d.zip
# Place in: sources/NCI_2025_07D/orig/fromprovider/
```

**Manual download (if needed):**
```bash
wget --user=apelon --password=ncicbapelon \
  ftp://lpgftp.nci.nih.gov/evs/apelon/ForMEME/meta_export_25.07d.zip
```

## Usage

### Step 1: Prepare Your Configuration

1. **Update** `INV/config/inversion_config.json` (see section 3a)
2. **Ensure previous inversion exists**:
   ```bash
   ls C:/workspace-meme-inversion/sources/NCI_2025_07D
   ```
3. **Ensure** `INV/config/api_metadata_export.txt` exists (see section 3b)
4. **Place meta export file** in `sources/` directory

### Step 2: Run the Script

```bash
cd C:/workspace-meme-inversion
./run_nci_inversion.sh
```

The script will:
- Load configuration from `INV/config/inversion_config.json`
- Display configuration summary
- Ask for confirmation to proceed

**No repetitive prompting** - all parameters come from the config file!

### Step 3: Monitor Progress

The script will:
- Create directory structure
- Copy files from previous version
- Update all version numbers
- Extract meta export files
- Create TREF files
- Run the inversion (1-2 hours)
- Run QA (45 minutes)
- Generate reports

Monitor inversion progress:
```bash
tail -f C:/workspace-meme-inversion/sources/NCI_2025_07D/bin/invert.log
```

## Automated Steps

The script automates these steps from the documentation:

| Step | Description | Status |
|------|-------------|--------|
| 1 | Create source directory | ✅ Automated |
| 2 | Copy files from previous inversion | ✅ Automated |
| 3 | Setup meta export file | ✅ Semi-automated (requires manual file placement) |
| 4 | Update NCI_<ver>.txt | ✅ Automated |
| 5 | Update sources.src | ✅ Automated |
| 6 | Update termgroups.src | ✅ Automated |
| 7 | Update nci.cfg | ✅ Automated |
| 8 | Create role groups file | ✅ Automated |
| 9 | Create TREF files | ✅ Automated |
| 10 | Copy/update MRDOC/MRSAB | ✅ Automated |
| 11 | Update compare_exportrels2tref | ✅ Automated |
| 12 | Run tref_2_relational_files.pl | ✅ Automated |
| 13 | Run inversion | ✅ Automated |
| 14 | Create MRDOC.RRF | ✅ Automated (requires api_metadata_export.txt) |
| 15 | Run QA | ✅ Automated |
| 16 | Conservation of mass | ⚠️ Manual review required |
| 17 | Update si_proposal | ⚠️ Manual |

## Manual Steps Still Required

### Before Running Script:
1. **Prepare inversion_config.json** in `INV/config/` (see section 3a)
2. **Prepare api_metadata_export.txt** in `INV/config/` (see section 3b)
3. **Place meta export file** in `sources/` directory

### After Script Completion:

#### 1. Review QA Reports
```bash
cd C:/workspace-meme-inversion/sources/NCI_2025_07D/etc/qa

# Check for errors
cat QaReport.NCI_2025_07D.txt.err

# Review full report
less QaReport.NCI_2025_07D.txt

# Check forbidden characters
cat Forbidden_attr.txt
cat Forbidden_classes.txt
```

#### 2. Conservation of Mass
Update `etc/qa/conservation.txt`:
- Document all ERRs from QaReport
- Provide rationale for each error
- Confirm termgroup counts
- Verify SAID range not exceeded
- Validate relationship counts

#### 3. Update SI Proposal
Edit `etc/si_proposal_<ver>.txt`:
- Update Section I.B with new/changed items
- Add data issues to Section IV

#### 4. TDE QA Checks (if applicable)
The script doesn't handle `/local/content/MEME/MEME5/inv/archive/projects/TDE_QA/` checks.
You'll need to run these manually if needed.

## Troubleshooting

### Script Fails to Find Previous Version
- Ensure directory exists: `sources/NCI_2025_06E/`
- Check that all required subdirectories exist (bin/, etc/, src/, orig/)

### Perl Module Errors
Install missing modules:
```bash
cpan install <module_name>
```

### Path Issues
The script uses Windows paths (`C:/workspace-meme-inversion`).
If you need different paths, edit these variables at the top of the script:
```bash
BASE_DIR="C:/workspace-meme-inversion"
INV_HOME="${BASE_DIR}/INV"
SOURCES_DIR="${BASE_DIR}/sources"
```

### File Not Found Errors
Check that all Perl scripts exist in the copied bin/ directory:
- create_rolegroups.pl
- create_tref.pl
- delete_dup_tref_lines.pl
- tref_2_relational_files.pl
- invert_NCI.pl

### MRDOC.RRF Generation Fails or Has Missing Data
If `makeDoc.pl` fails or MRDOC.RRF is incomplete:

1. **Check for api_metadata_export.txt**:
   ```bash
   ls -lh C:/workspace-meme-inversion/INV/config/api_metadata_export.txt
   ```

2. **If missing**, you need to extract it from the server (see section 3a):
   - Run `extract_metadata.sh` on a server with API access
   - Copy the resulting file to `INV/config/`

3. **If file exists but makeDoc.pl still fails**:
   - Check file format (should have [RELA_INVERSE], [EXPANDED_FORM], [TTY_CLASS] sections)
   - Verify file isn't empty or corrupted
   - Re-extract from server if needed

4. **Alternative (if server access unavailable)**:
   - `makeDoc.pl` can attempt direct API calls if `api_metadata_export.txt` is missing
   - This requires network access to the NCIMeta API server
   - Not recommended for offline environments

## Output Files

After successful completion, you'll find:

```
sources/NCI_2025_07D/
├── bin/
│   ├── invert.log              # Main log file
│   └── qa.log                  # QA log
├── etc/
│   ├── NCI_2025_07D.txt        # Updated config
│   ├── nci.cfg                 # Updated with SAID
│   └── qa/
│       ├── QaReport.NCI_2025_07D.txt
│       ├── QaReport.NCI_2025_07D.txt.err
│       ├── Forbidden_attr.txt
│       ├── Forbidden_classes.txt
│       └── conservation.txt
├── src/
│   ├── *.src files             # Generated source files
│   └── MRDOC.RRF              # Generated MRDOC
└── orig/
    ├── *.TREF files           # Generated TREF files
    └── rels_needing_relgrp.txt
```

## Next Steps After Script Completes

1. **Review all QA reports**
2. **Complete conservation of mass**
3. **Update si_proposal_*.txt**
4. **Archive to S3** (if applicable):
   ```bash
   push_s3.csh inv NCI_2025_07D
   ```
5. **Announce completion** at: https://wiki.nci.nih.gov/display/EVSproj/NCI+Source+Tracking
6. **Archive config file** to ncicbftp2.nci.nih.gov:/evs/apelon/ForMEME/
7. **Send summary** to Lori W. and Lyubov R.

## Support

For issues or questions:
- Review original documentation: `NCIt Inversion Documentation.txt`
- Check INV framework docs: `INV/INSTALL.txt`, `INV/README.txt`
- Review Perl script comments in `bin/` directory
