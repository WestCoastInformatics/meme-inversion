/bin/bash
#
# NCI Thesaurus Inversion Automation Script
# Adapted for Windows/Git Bash environment
#
# This script automates the NCI inversion process based on the NCIt Inversion Documentation
# It prompts for all required information and executes the inversion steps
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color


# Base configuration
BASE_DIR="/Users/deborahshapiro/Code/workspace-meme-inversion2"

INV_HOME="${BASE_DIR}/INV"
SOURCES_DIR="${BASE_DIR}/sources"

# Function to print colored messages
print_msg() {

    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "\n${BLUE}==== STEP $1 ====${NC}"
}

# Function to prompt for input with validation
prompt_input() {
    local prompt="$1"
    local var_name="$2"
    local default="${3:-}"
    local value=""

    while [ -z "$value" ]; do
        if [ -n "$default" ]; then
            read -p "$prompt [$default]: " value
            value="${value:-$default}"
        else
            read -p "$prompt: " value
        fi

        if [ -z "$value" ]; then
            print_error "This field is required. Please provide a value."
        fi
    done

    eval "$var_name='$value'"
}

# Function to confirm action
confirm() {
    local prompt="$1"
    local response
    read -p "$prompt (y/n): " response
    case "$response" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

# Function to check if directory exists
check_dir_exists() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        print_error "Directory not found: $dir"
        return 1
    fi
    return 0
}

# Function to check if file exists
check_file_exists() {
    local file="$1"
    if [ ! -f "$file" ]; then
        print_error "File not found: $file"
        return 1
    fi
    return 0
}

# Banner
echo "=========================================="
echo "  NCI Thesaurus Inversion Automation"
echo "=========================================="
echo ""


# OS Detection and sed configuration
OS="$(uname -s)"
case "${OS}" in
    Linux*)     machine=Linux; SED_INPLACE=("-i") ;;
    Darwin*)    machine=Mac;   SED_INPLACE=("-i" "") ;;
    CYGWIN*)    machine=Cygwin; SED_INPLACE=("-i") ;;
    MINGW*)     machine=MinGw;  SED_INPLACE=("-i") ;;
    *)          machine="UNKNOWN:${OS}"; SED_INPLACE=("-i") ;;
esac

print_msg "Dedicated detection: Operating System listed as ${machine}"

# ============================================
# LOAD CONFIGURATION FROM FILE
# ============================================

print_msg "Loading configuration from INV/config/inversion_config.json..."
echo ""

CONFIG_FILE="${INV_HOME}/config/inversion_config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    print_error "Configuration file not found: $CONFIG_FILE"
    print_warn "Please provide INV/config/inversion_config.json before running inversion"
    print_warn "See INV/config/INVERSION_CONFIG_README.md for documentation"
    exit 1
fi

# Read version information using simpler Python approach
read_config_simple() {
    python3 << 'PYTHON_SCRIPT'
import json
import sys

try:
    with open('INV/config/inversion_config.json') as f:
        config = json.load(f)

    print("CURRENT_VERSION=" + config['version_info']['current_version'])
    print("PREVIOUS_VERSION=" + config['version_info']['previous_version'])
    print("PRIOR_PREVIOUS_VERSION=" + config['version_info']['prior_previous_version'])
    print("PREVIOUS_MONTH=" + config['runtime_parameters']['previous_month'])
    print("CURRENT_MONTH=" + config['runtime_parameters']['current_month'])
    print("SAID_START=" + config['runtime_parameters']['said_start'])
    print("META_EXPORT_FILE=" + config['runtime_parameters']['meta_export_file'])
except Exception as e:
    print("ERROR: " + str(e), file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT
}

# Read all config values at once and strip carriage returns (Windows line endings)
eval $(read_config_simple | tr -d '\r')

# Debug output
print_msg "DEBUG: CURRENT_VERSION='$CURRENT_VERSION'"
print_msg "DEBUG: PREVIOUS_VERSION='$PREVIOUS_VERSION'"
print_msg "DEBUG: PRIOR_PREVIOUS_VERSION='$PRIOR_PREVIOUS_VERSION'"

# Validate required fields
if [ -z "$CURRENT_VERSION" ]; then
    print_error "current_version not set in config file"
    exit 1
fi

if [ -z "$PREVIOUS_VERSION" ]; then
    print_error "previous_version not set in config file"
    exit 1
fi

if [ -z "$PRIOR_PREVIOUS_VERSION" ]; then
    print_error "prior_previous_version not set in config file"
    exit 1
fi

if [ -z "$PREVIOUS_MONTH" ]; then
    print_error "previous_month not set in config file"
    exit 1
fi

if [ -z "$CURRENT_MONTH" ]; then
    print_error "current_month not set in config file"
    exit 1
fi

if [ -z "$SAID_START" ]; then
    print_error "said_start not set in config file"
    exit 1
fi

# Set directory paths
PREVIOUS_DIR="${SOURCES_DIR}/${PREVIOUS_VERSION}"
CURRENT_DIR="${SOURCES_DIR}/${CURRENT_VERSION}"

# Check if previous version directory exists
if ! check_dir_exists "$PREVIOUS_DIR"; then
    print_error "Previous version directory not found: $PREVIOUS_DIR"
    if confirm "Do you want to continue anyway?"; then
        print_warn "Continuing without previous version - some steps will be skipped"
        SKIP_COPY_PREVIOUS=true
    else
        exit 1
    fi
else
    print_msg "Found previous version at: $PREVIOUS_DIR"
    SKIP_COPY_PREVIOUS=false
fi

# Extract version components for various uses
# e.g., NCI_2025_07D -> 2025_07D, 07D, 2507D
CURRENT_VSAB=$(echo "$CURRENT_VERSION" | sed 's/NCI_//')
CURRENT_SHORT=$(echo "$CURRENT_VSAB" | sed 's/2025_//')
CURRENT_COMPACT=$(echo "$CURRENT_VSAB" | sed 's/2025_/25/' | tr '[:upper:]' '[:lower:]')

if [ "$SKIP_COPY_PREVIOUS" = false ]; then
    PREVIOUS_VSAB=$(echo "$PREVIOUS_VERSION" | sed 's/NCI_//')
    PREVIOUS_SHORT=$(echo "$PREVIOUS_VSAB" | sed 's/2025_//')
    PREVIOUS_COMPACT=$(echo "$PREVIOUS_VSAB" | sed 's/2025_/25/' | tr '[:upper:]' '[:lower:]')
fi

# Extract VSAB from prior previous version
PRIOR_PREVIOUS_VSAB=$(echo "$PRIOR_PREVIOUS_VERSION" | sed 's/NCI_//')

# Find meta export file
if [ -n "$META_EXPORT_FILE" ]; then
    # Use filename from config if specified
    EXPORT_FILE="${SOURCES_DIR}/${META_EXPORT_FILE}"
    if [ ! -f "$EXPORT_FILE" ]; then
        print_error "Meta export file specified in config not found: $EXPORT_FILE"
        exit 1
    fi
else
    # Auto-detect meta_export*.zip in sources directory
    EXPORT_FILE=$(find "$SOURCES_DIR" -maxdepth 1 -name "meta_export*.zip" -type f 2>/dev/null | head -1)
    if [ -z "$EXPORT_FILE" ]; then
        print_error "No meta_export*.zip file found in $SOURCES_DIR"
        print_warn "Please place the meta export zip file in: $SOURCES_DIR"
        print_warn "Or specify the filename in config: runtime_parameters.meta_export_file"
        exit 1
    fi
fi

EXPORT_BASENAME=$(basename "$EXPORT_FILE")
EXPORT_DEST="${SOURCES_DIR}/${CURRENT_VERSION}/orig/fromprovider"

# Configuration summary
echo ""
echo "=========================================="
echo "  Configuration Summary"
echo "=========================================="
echo "Loaded from: $CONFIG_FILE"
echo ""
echo "Prior Previous:   $PRIOR_PREVIOUS_VERSION ($PRIOR_PREVIOUS_VSAB)"
echo "Previous Version: $PREVIOUS_VERSION ($PREVIOUS_VSAB)"
echo "Current Version:  $CURRENT_VERSION ($CURRENT_VSAB)"
echo "Previous Month:   $PREVIOUS_MONTH"
echo "Current Month:    $CURRENT_MONTH"
echo "SAID Start:       $SAID_START"
echo "Export File:      $EXPORT_BASENAME"
echo "=========================================="
echo ""

if ! confirm "Proceed with inversion using this configuration?"; then
    print_msg "Inversion cancelled by user"
    exit 0
fi

# ============================================
# BEGIN INVERSION PROCESS
# ============================================

print_step "1" "Creating source directory structure"
if [ -d "$CURRENT_DIR" ]; then
    print_warn "Directory already exists: $CURRENT_DIR"
    if ! confirm "Remove and recreate?"; then
        print_error "Cannot proceed with existing directory"
        exit 1
    fi
    rm -rf "$CURRENT_DIR"
fi

# Create directory structure using create_vsab_dirs.pl if it exists
if [ -f "${INV_HOME}/bin/create_vsab_dirs.pl" ]; then
    print_msg "Using create_vsab_dirs.pl to create directory structure"

    # Set required environment variables for Perl scripts
    export ENV_HOME="$INV_HOME"
    export INV_HOME_OLD="$INV_HOME"
    export SRC_ROOT="$SOURCES_DIR"

    cd "$INV_HOME/bin"
    perl create_vsab_dirs.pl "$CURRENT_VERSION"

    # Move created directory to sources if needed
    if [ -d "${INV_HOME}/${CURRENT_VERSION}" ]; then
        mkdir -p "$SOURCES_DIR"
        mv "${INV_HOME}/${CURRENT_VERSION}" "$SOURCES_DIR/"
    fi
else
    # Manual directory creation
    print_msg "Manually creating directory structure"
    mkdir -p "${CURRENT_DIR}"/{bin,etc,src,orig,tmp,lib}
    mkdir -p "${CURRENT_DIR}/orig/fromprovider"
    mkdir -p "${CURRENT_DIR}/etc/qa"
fi

print_msg "Created directory: $CURRENT_DIR"

# ============================================
print_step "2" "Copying files from previous inversion"
if [ "$SKIP_COPY_PREVIOUS" = true ]; then
    print_warn "Skipping copy from previous version"
else
    # Copy bin scripts
    print_msg "Copying inversion scripts from bin/..."
    cp -r "${PREVIOUS_DIR}/bin/." "${CURRENT_DIR}/bin/"

    # Copy etc files
    print_msg "Copying configuration files from etc/..."
    [ -f "${PREVIOUS_DIR}/etc/README.INVERSION" ] && cp "${PREVIOUS_DIR}/etc/README.INVERSION" "${CURRENT_DIR}/etc/"
    [ -f "${PREVIOUS_DIR}/etc/nci.cfg" ] && cp "${PREVIOUS_DIR}/etc/nci.cfg" "${CURRENT_DIR}/etc/"
    # Copy NCI*.txt files (format: NCI2025_07D.txt, not NCI_2025_07D.txt)
    find "${PREVIOUS_DIR}/etc" -maxdepth 1 -name "NCI*.txt" ! -name "NCI_*.txt" -exec cp {} "${CURRENT_DIR}/etc/" \; 2>/dev/null
    [ -f "${PREVIOUS_DIR}/etc/si_proposal"* ] && cp "${PREVIOUS_DIR}/etc/si_proposal"* "${CURRENT_DIR}/etc/"
    [ -d "${PREVIOUS_DIR}/etc/qa" ] && cp -r "${PREVIOUS_DIR}/etc/qa" "${CURRENT_DIR}/etc/"

    # Copy src files
    print_msg "Copying source files from src/..."
    [ -f "${PREVIOUS_DIR}/src/sources.src" ] && cp "${PREVIOUS_DIR}/src/sources.src" "${CURRENT_DIR}/src/"
    [ -f "${PREVIOUS_DIR}/src/termgroups.src" ] && cp "${PREVIOUS_DIR}/src/termgroups.src" "${CURRENT_DIR}/src/"

    print_msg "Files copied successfully"
fi

# ============================================
print_step "2.5" "Copying updated inversion scripts from INV"
# Overwrite with latest versions from INV/bin to ensure fixes are applied
if [ -f "${INV_HOME}/bin/invert_NCI.pl" ]; then
    print_msg "Copying latest invert_NCI.pl from INV/bin..."
    cp "${INV_HOME}/bin/invert_NCI.pl" "${CURRENT_DIR}/bin/"
    print_msg "Updated invert_NCI.pl with latest version"
fi

if [ -f "${INV_HOME}/bin/invert_NCI_config_reader.pl" ]; then
    print_msg "Copying latest invert_NCI_config_reader.pl from INV/bin..."
    cp "${INV_HOME}/bin/invert_NCI_config_reader.pl" "${CURRENT_DIR}/bin/"
    print_msg "Updated invert_NCI_config_reader.pl with latest version"
fi

# ============================================
print_step "2.6" "Setting up inversion configuration"
# Copy the inversion config from INV/config to the current version's etc directory
CONFIG_SOURCE="${INV_HOME}/config/inversion_config.json"
CONFIG_DEST="${CURRENT_DIR}/etc/inversion_config.json"

print_msg "Checking for inversion configuration..."
if [ ! -f "$CONFIG_SOURCE" ]; then
    print_error "Configuration file not found: $CONFIG_SOURCE"
    print_warn "Please provide INV/config/inversion_config.json before running inversion"
    print_warn "See INV/config/INVERSION_CONFIG_README.md for documentation"
    exit 1
fi

print_msg "Copying inversion configuration from INV/config/..."
cp "$CONFIG_SOURCE" "$CONFIG_DEST"
print_msg "Configuration file copied to: $CONFIG_DEST"

# ============================================
print_step "3" "Setting up meta export file"
if [ ! -d "$EXPORT_DEST" ]; then
    mkdir -p "$EXPORT_DEST"
fi

print_msg "Copying meta export file to destination..."
print_msg "  Source: $EXPORT_FILE"
print_msg "  Destination: $EXPORT_DEST"

cp "$EXPORT_FILE" "$EXPORT_DEST/"

print_msg "Unzipping meta export file..."
cd "$EXPORT_DEST"
unzip -o "$EXPORT_BASENAME"

print_msg "Meta export files extracted successfully"

# ============================================
print_step "4" "Updating NCI<ver>.txt file"
if [ "$SKIP_COPY_PREVIOUS" = false ]; then
    cd "${CURRENT_DIR}/etc"

    # Find and rename the NCI*.txt file (format: NCI2025_07D.txt)
    OLD_NCI_FILE=$(ls NCI*.txt 2>/dev/null | grep -v "^NCI_" | head -1)
    if [ -n "$OLD_NCI_FILE" ]; then
        print_msg "Found: $OLD_NCI_FILE"
        # New filename: NCI<VSAB>.txt (e.g., NCI2025_08D.txt)
        NEW_NCI_FILE="NCI${CURRENT_VSAB}.txt"
        print_msg "Renaming to: ${NEW_NCI_FILE}"
        mv "$OLD_NCI_FILE" "${NEW_NCI_FILE}"

        # Update VSABs in the file
        print_msg "Updating VSABs in ${NEW_NCI_FILE}..."
        sed "${SED_INPLACE[@]}" "s/${PREVIOUS_VSAB}/${CURRENT_VSAB}/g" "${NEW_NCI_FILE}"

        # Copy to orig/fromprovider
        print_msg "Copying to orig/fromprovider..."
        cp "${NEW_NCI_FILE}" "${CURRENT_DIR}/orig/fromprovider/"
    else
        print_warn "No NCI*.txt file found to update"
    fi
else
    print_warn "Skipping NCI<ver>.txt update - no previous version"
fi

# ============================================
print_step "5" "Updating sources.src"
if [ -f "${CURRENT_DIR}/src/sources.src" ]; then
    print_msg "Updating sources.src with version information..."
    cd "${CURRENT_DIR}/src"

    print_msg "Step 1: Replacing all ${PREVIOUS_VSAB} with ${CURRENT_VSAB}..."
    sed "${SED_INPLACE[@]}"  "s/${PREVIOUS_VSAB}/${CURRENT_VSAB}/g" sources.src

    print_msg "Step 2: Replacing all ${PRIOR_PREVIOUS_VSAB} with ${PREVIOUS_VSAB}..."
    sed "${SED_INPLACE[@]}" "s/${PRIOR_PREVIOUS_VSAB}/${PREVIOUS_VSAB}/g" sources.src

    # Update month names
    print_msg "Step 3: Replacing month name ${PREVIOUS_MONTH} with ${CURRENT_MONTH}..."
    sed "${SED_INPLACE[@]}" "s/${PREVIOUS_MONTH}/${CURRENT_MONTH}/g" sources.src

    print_msg "Step 4: Fixing mismatched sources in source entries..."
    # For entries where field 1 (RSAB) and field 2 (VSAB) have different source codes,
    # update field 2 to use the same source as field 1 with the previous VSAB
    # Example: FDA-NIH-MoRE_2025_09E|EDQM-HC_2025_09E|... -> FDA-NIH-MoRE_2025_09E|FDA-NIH-MoRE_2025_08D|...

    awk -F'|' -v current_vsab="${CURRENT_VSAB}" -v previous_vsab="${PREVIOUS_VSAB}" '
    {
        # Extract source codes from field 1 (RSAB) and field 2 (VSAB)
        # Format: SOURCE_VSAB (e.g., "FDA-NIH-MoRE_2025_09E")

        rsab = $1
        vsab = $2

        # Extract source code from RSAB (everything before _VSAB)
        rsab_source = rsab
        sub(/_[0-9]+_[0-9A-Z]+$/, "", rsab_source)

        # Extract source code from VSAB (everything before _VSAB)
        vsab_source = vsab
        sub(/_[0-9]+_[0-9A-Z]+$/, "", vsab_source)

        # If sources dont match, update field 2 to use RSAB source with previous VSAB
        if (rsab_source != vsab_source) {
            $2 = rsab_source "_" previous_vsab
        }

        # Print the line with all fields
        print $0
    }' OFS='|' sources.src > sources.src.tmp && mv sources.src.tmp sources.src

    print_msg "sources.src updated"
else
    print_warn "sources.src not found - skipping update"
fi

# ============================================
print_step "6" "Updating termgroups.src"
if [ -f "${CURRENT_DIR}/src/termgroups.src" ]; then
    print_msg "Updating termgroups.src with version information..."
    cd "${CURRENT_DIR}/src"

    print_msg "Step 1: Replacing all ${PREVIOUS_VSAB} with ${CURRENT_VSAB}..."
    sed "${SED_INPLACE[@]}" "s/${PREVIOUS_VSAB}/${CURRENT_VSAB}/g" termgroups.src

    print_msg "Step 2: Replacing all ${PRIOR_PREVIOUS_VSAB} with ${PREVIOUS_VSAB}..."
    sed "${SED_INPLACE[@]}" "s/${PRIOR_PREVIOUS_VSAB}/${PREVIOUS_VSAB}/g" termgroups.src

    print_msg "Step 3: Fixing mismatched sources in termgroup entries..."
    # For entries where field 1 and field 2 have different source codes,
    # update field 2 to use the same source as field 1 with the previous VSAB
    # The TTY in field 2 should match the TTY in field 1
    # Examples:
    #   FDA-NIH-MoRE_2025_09E/PT|EDQM-HC_2025_09E/PT -> FDA-NIH-MoRE_2025_09E/PT|FDA-NIH-MoRE_2025_08D/PT
    #   FDA-NIH-MoRE_2025_09E/SY|EDQM-HC_2025_09E/SY -> FDA-NIH-MoRE_2025_09E/SY|FDA-NIH-MoRE_2025_08D/SY

    awk -F'|' -v current_vsab="${CURRENT_VSAB}" -v previous_vsab="${PREVIOUS_VSAB}" '
    {
        # Extract source and TTY from field 1 (e.g., "FDA-NIH-MoRE_2025_09E/PT")
        split($1, field1_parts, "/")
        tty1 = field1_parts[2]

        # Extract source and TTY from field 2 (e.g., "EDQM-HC_2025_09E/PT")
        split($2, field2_parts, "/")

        # Get source codes (everything before the last underscore and VSAB)
        # For "FDA-NIH-MoRE_2025_09E", we want "FDA-NIH-MoRE"
        source1_code = field1_parts[1]
        sub(/_[0-9]+_[0-9A-Z]+$/, "", source1_code)

        source2_code = field2_parts[1]
        sub(/_[0-9]+_[0-9A-Z]+$/, "", source2_code)

        # If sources dont match, update field 2 to use source1 with previous VSAB and same TTY
        if (source1_code != source2_code) {
            $2 = source1_code "_" previous_vsab "/" tty1
        }

        # Print the line with all fields
        print $0
    }' OFS='|' termgroups.src > termgroups.src.tmp && mv termgroups.src.tmp termgroups.src

    print_msg "termgroups.src updated"
else
    print_warn "termgroups.src not found - skipping update"
fi

# ============================================
print_step "7" "Updating nci.cfg"
if [ -f "${CURRENT_DIR}/etc/nci.cfg" ]; then
    print_msg "Updating nci.cfg with version and SAID information..."
    cd "${CURRENT_DIR}/etc"

    # Update VSAB
    if [ "$SKIP_COPY_PREVIOUS" = false ]; then
        sed "${SED_INPLACE[@]}" "s/${PREVIOUS_VSAB}/${CURRENT_VSAB}/g" nci.cfg
    fi

    # Update SAID start
    print_msg "Setting SaidStart to: $SAID_START"
    sed "${SED_INPLACE[@]}" "s/SaidStart\s*=\s*[0-9]*/SaidStart = ${SAID_START}/" nci.cfg

    print_msg "nci.cfg updated"
else
    print_warn "nci.cfg not found - skipping update"
fi

# ============================================
print_step "8" "Creating role groups file"
if [ -f "${CURRENT_DIR}/bin/create_rolegroups.pl" ]; then
    print_msg "Updating create_rolegroups.pl with export date..."

    # Find relations file
    RELATIONS_FILE=$(find "${CURRENT_DIR}/orig/fromprovider" -name "relations-*.txt" 2>/dev/null | head -1)

    if [ -n "$RELATIONS_FILE" ]; then
        RELATIONS_BASENAME=$(basename "$RELATIONS_FILE")
        print_msg "Found relations file: $RELATIONS_BASENAME"

        # Update the script with the correct filename
        cd "${CURRENT_DIR}/bin"
        sed "${SED_INPLACE[@]}" "s/relations-[0-9-]*.txt/${RELATIONS_BASENAME}/g" create_rolegroups.pl

        print_msg "Running create_rolegroups.pl..."
        perl create_rolegroups.pl

        if [ -f "${CURRENT_DIR}/tmp/rolegroups.tmp" ]; then
            print_msg "Creating rels_needing_relgrp.txt..."
            sort "${CURRENT_DIR}/tmp/rolegroups.tmp" | uniq -d > "${CURRENT_DIR}/orig/rels_needing_relgrp.txt"
            print_msg "Role groups file created"
        fi
    else
        print_warn "Relations file not found in orig/fromprovider"
    fi
else
    print_warn "create_rolegroups.pl not found - skipping role groups"
fi

# ============================================
print_step "9" "Creating TREF files"
if [ -f "${CURRENT_DIR}/bin/create_tref.pl" ]; then
    print_msg "Updating create_tref.pl with export file dates..."
    cd "${CURRENT_DIR}/bin"

    # Extract date from annotation file
    ANNOT_FILE=$(find "${CURRENT_DIR}/orig/fromprovider" -name "annotationDeclaration-*.txt" 2>/dev/null | head -1)
    if [ -n "$ANNOT_FILE" ]; then
        # Extract the date (YYYYMMDD) from the filename
        CURRENT_EXPORT_DATE=$(basename "$ANNOT_FILE" | grep -oE '[0-9]{8}')
        print_msg "Found export date in files: $CURRENT_EXPORT_DATE"

        # Find the old date in create_tref.pl
        OLD_EXPORT_DATE=$(perl -nle 'print $1 if /annotationDeclaration-(\d{8})/' create_tref.pl | head -1)
        if [ -n "$OLD_EXPORT_DATE" ] && [ "$OLD_EXPORT_DATE" != "$CURRENT_EXPORT_DATE" ]; then
            print_msg "Updating dates in create_tref.pl from $OLD_EXPORT_DATE to $CURRENT_EXPORT_DATE"
            sed "${SED_INPLACE[@]}" "s/${OLD_EXPORT_DATE}/${CURRENT_EXPORT_DATE}/g" create_tref.pl
        fi
    else
        print_warn "Could not find annotationDeclaration file to extract date"
    fi

    print_msg "Running create_tref.pl..."
    perl create_tref.pl

    print_msg "De-duplicating TREF files..."
    if [ -f "${CURRENT_DIR}/bin/delete_dup_tref_lines.pl" ]; then
        perl delete_dup_tref_lines.pl
    fi

    print_msg "TREF files created"
else
    print_warn "create_tref.pl not found - skipping TREF creation"
fi

# ============================================
print_step "10" "Copying and updating MRDOC/MRSAB TREF files"
if [ "$SKIP_COPY_PREVIOUS" = false ]; then
    print_msg "Copying MRDOC.TREF and MRSAB.TREF from previous version..."
    cd "${CURRENT_DIR}/orig"

    [ -f "${PREVIOUS_DIR}/orig/MRDOC.TREF" ] && cp "${PREVIOUS_DIR}/orig/MRDOC.TREF" .
    [ -f "${PREVIOUS_DIR}/orig/MRSAB.TREF" ] && cp "${PREVIOUS_DIR}/orig/MRSAB.TREF" .

    # Update MRSAB.TREF
    if [ -f "MRSAB.TREF" ]; then
        print_msg "Updating MRSAB.TREF with version and date..."
        sed "${SED_INPLACE[@]}" "s/${PREVIOUS_VSAB}/${CURRENT_VSAB}/g" MRSAB.TREF
        sed "${SED_INPLACE[@]}" "s/${PREVIOUS_MONTH}/${CURRENT_MONTH}/g" MRSAB.TREF
    fi

    print_warn "REMINDER: If you configured new ATNs/RELAs in inversion_config.json,"
    print_warn "          manually verify they appear correctly in MRDOC.TREF"
else
    print_warn "Skipping MRDOC/MRSAB copy - no previous version"
fi

# ============================================
print_step "11" "Updating compare_exportrels2tref script"
if [ -f "${CURRENT_DIR}/bin/compare_exportrels2tref.s" ]; then
    print_msg "Updating compare_exportrels2tref.s..."
    cd "${CURRENT_DIR}/bin"

    if [ "$SKIP_COPY_PREVIOUS" = false ]; then
        sed "${SED_INPLACE[@]}" "s/${PREVIOUS_VSAB}/${CURRENT_VSAB}/g" compare_exportrels2tref.s
    fi

    # Update hardcoded absolute paths to relative paths
    print_msg "Converting absolute paths to relative paths..."
    sed "${SED_INPLACE[@]}" 's|/local/content/MEME/MEME5/inv/sources/[^/]*/orig/|../orig/|g' compare_exportrels2tref.s

    print_msg "compare_exportrels2tref.s updated"
fi

# ============================================
print_step "12" "Running tref_2_relational_files.pl"
if [ -f "${CURRENT_DIR}/bin/tref_2_relational_files.pl" ]; then
    print_msg "Running tref_2_relational_files.pl..."
    cd "${CURRENT_DIR}/bin"

    # Execute each step from tref_2_relational_files.pl manually
    # This avoids tcsh path issues by running with bash and perl

    print_msg "Building relational files"
    bash ./compare_exportrels2tref.s
    sort ../tmp/nci_concepts.tmp -o ../orig/nci_concepts.txt

    print_msg "Building associations file"
    perl ./get_nci_assoc.pl
    sort -u ../orig/nci_associations.txt -o ../orig/nci_associations.txt

    print_msg "Building property files"
    cut -f2,4,5 -d\| ../orig/MRSAT.TREF | sort -u > ../tmp/nci_properties.tmp
    perl ./get_prop_name.pl
    sort -u ../tmp/nci_properties2.tmp -o ../tmp/nci_properties2.tmp

    cut -f2,3,5,6 -d\| ../orig/MRCONSO.TREF > ../tmp/nci_sy_pt_properties.tmp
    perl ./get_sy_pt_name.pl

    cat ../tmp/nci_properties2.tmp ../tmp/nci_sy_pt_properties2.tmp | sort -t\| -k1,1 -k2,2 > ../orig/nci_properties.txt

    print_msg "Building roles file"
    perl ./get_owl_roles.pl
    sort -u ../tmp/nci_roles.tmp -o ../tmp/nci_roles.tmp
    perl ./assign_rolegroups.pl
    perl ./delete_dup_roles.pl


    print_msg "Relational files created"
    print_warn "NOTE: C15256 and C164057 may be reported as self-referential - this is expected"
else
    print_warn "tref_2_relational_files.pl not found - skipping"
fi

# ============================================
print_step "13" "Setting up Perl module library"
# Create symlink to INV/lib so invert_NCI.pl can find required Perl modules
if [ ! -e "${CURRENT_DIR}/lib" ]; then
    print_msg "Creating symlink to INV/lib..."
    cd "${CURRENT_DIR}"
    ln -sf "../../INV/lib" lib
    print_msg "Library symlink created"
elif [ -L "${CURRENT_DIR}/lib" ]; then
    print_msg "Library symlink already exists"
else
    print_warn "lib directory exists but is not a symlink - using existing directory"
fi

# Add INV/bin to PERL5LIB for Config::Properties module
print_msg "Setting up Perl module paths..."
# Export INV_HOME for Perl scripts
export INV_HOME

# Use cygpath to convert Windows paths to proper Cygwin paths
# Use cygpath to convert Windows paths to proper Cygwin paths if available
if command -v cygpath &> /dev/null; then
    INV_BIN_UNIX=$(cygpath -u "${INV_HOME}/bin")
    INV_LIB_UNIX=$(cygpath -u "${INV_HOME}/lib")
    INV_HOME_UNIX=$(cygpath -u "${INV_HOME}")
    CURRENT_DIR_UNIX=$(cygpath -u "${CURRENT_DIR}")
else
    # On non-Cygwin systems (macOS, Linux), use paths as-is
    INV_BIN_UNIX="${INV_HOME}/bin"
    INV_LIB_UNIX="${INV_HOME}/lib"
    INV_HOME_UNIX="${INV_HOME}"
    CURRENT_DIR_UNIX="${CURRENT_DIR}"
fi

export INV_HOME_UNIX
export PERL5LIB="${INV_BIN_UNIX}:${INV_LIB_UNIX}:${CURRENT_DIR_UNIX}/lib:${PERL5LIB:-}"
print_msg "PERL5LIB configured to include INV/bin and INV/lib"
print_msg "INV_HOME set to: $INV_HOME_UNIX"

# ============================================
print_step "14" "Running inversion script"
print_msg "Preparing to run invert_NCI.pl..."
print_msg "Configuration will be loaded from: ${CONFIG_DEST}"

if confirm "Ready to run inversion? (This takes 1-2 hours)"; then
    cd "${CURRENT_DIR}/bin"

    print_msg "Starting inversion in background..."
    # Run with explicit environment to ensure PERL5LIB and INV_HOME are preserved
    env PERL5LIB="${PERL5LIB}" INV_HOME="${INV_HOME_UNIX}" nohup perl invert_NCI.pl > invert.log 2>&1 &
    INVERT_PID=$!

    print_msg "Inversion started with PID: $INVERT_PID"
    print_msg "Monitor progress: tail -f ${CURRENT_DIR}/bin/invert.log"
    print_warn "Waiting for inversion to complete..."

    wait $INVERT_PID
    print_msg "Inversion completed!"
else
    print_warn "Skipping inversion - run manually when ready:"
    print_warn "  cd ${CURRENT_DIR}/bin"
    print_warn "  env PERL5LIB=\"${PERL5LIB}\" INV_HOME=\"${INV_HOME_UNIX}\" perl invert_NCI.pl"
    exit 0
fi

# ============================================
print_step "15" "Creating MRDOC.RRF"
if [ -f "${INV_HOME}/bin/makeDoc.pl" ]; then
    print_msg "Running makeDoc.pl..."
    cd "${CURRENT_DIR}/bin"

    perl "${INV_HOME}/bin/makeDoc.pl"

    # Check for '#' characters
    if [ -f "${CURRENT_DIR}/src/MRDOC.RRF" ]; then
        print_msg "Checking MRDOC.RRF for '#' characters..."
        if grep -q '#' "${CURRENT_DIR}/src/MRDOC.RRF"; then
            print_warn "Found '#' characters in MRDOC.RRF - review required"
            grep '#' "${CURRENT_DIR}/src/MRDOC.RRF"
        else
            print_msg "No '#' characters found - MRDOC.RRF looks good"
        fi
    fi
else
    print_warn "makeDoc.pl not found - skipping MRDOC.RRF creation"
fi

# ============================================
print_step "16" "Running QA"
print_msg "Running QA (this takes about 45 minutes)..."
cd "${CURRENT_DIR}/src"

if [ -f "${INV_HOME}/bin/srcQa.pl" ]; then
    print_msg "Running srcQa.pl..."
    nohup perl "${INV_HOME}/bin/srcQa.pl" -c "${CURRENT_DIR}/etc/"*cfg > "${CURRENT_DIR}/bin/qa.log" 2>&1 &
    QA_PID=$!

    wait $QA_PID
    print_msg "QA completed"
fi

if [ -f "${INV_HOME}/bin/findQaStats.pl" ]; then
    print_msg "Running findQaStats.pl..."
    perl "${INV_HOME}/bin/findQaStats.pl" >> "${CURRENT_DIR}/bin/invert.log"
fi

print_msg "Review QA results:"
print_msg "  - ${CURRENT_DIR}/bin/invert.log"
print_msg "  - ${CURRENT_DIR}/etc/qa/QaReport.${CURRENT_VERSION}.txt"
print_msg "  - ${CURRENT_DIR}/etc/qa/QaReport.${CURRENT_VERSION}.txt.err"

# ============================================
print_step "17" "Conservation of Mass"
print_warn "Manual steps required for conservation of mass:"
print_warn "  1. Review ${CURRENT_DIR}/etc/qa/QaReport.${CURRENT_VERSION}.txt for ERRs"
print_warn "  2. Review ${CURRENT_DIR}/etc/qa/Forbidden_attr.txt"
print_warn "  3. Review ${CURRENT_DIR}/etc/qa/Forbidden_classes.txt"
print_warn "  4. Update ${CURRENT_DIR}/etc/qa/conservation.txt"
print_warn "  5. Confirm SAID range not exceeded"

# ============================================
print_step "18" "Finalizing"
print_msg "Update si_proposal file:"
print_msg "  - Edit ${CURRENT_DIR}/etc/si_proposal_*.txt"
print_msg "  - Update Section I.B with new/changed items"
print_msg "  - List data issues in Section IV"

echo ""
echo "=========================================="
echo "  Inversion Process Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "  1. Review QA reports and conservation of mass"
echo "  2. Update si_proposal_*.txt"
echo "  3. Archive to S3 (if applicable)"
echo "  4. Announce inversion ready for test insertion"
echo "  5. Archive NCI_${CURRENT_VSAB}.txt to ncicbftp2.nci.nih.gov"
echo "  6. Send summary to Lori W. and Lyubov R."
echo ""
echo "Inversion Location: $CURRENT_DIR"
echo "=========================================="
