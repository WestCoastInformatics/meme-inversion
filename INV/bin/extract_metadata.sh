#!/bin/bash
#
# Script to extract metadata from NCIMeta API on server for offline use
#
# REQUIREMENTS:
# - Must be run on a server with API access to NCIMeta
# - $MEME_HOME must be set and contain config/config.properties
# - config.properties must have admin.user and admin.password configured
# - $INV_HOME must be set
#
# USAGE:
# 1. Run this script on the server: ./extract_metadata.sh
# 2. Copy the output file to your offline environment:
#    cp $INV_HOME/etc/api_metadata_export.txt /path/to/offline/INV/etc/
# 3. Run makeDoc.pl offline - it will automatically use the exported file
#

# Validate environment
if [ -z "$INV_HOME" ]; then
    echo "ERROR: INV_HOME environment variable is not set"
    exit 1
fi

if [ -z "$MEME_HOME" ]; then
    echo "ERROR: MEME_HOME environment variable is not set"
    exit 1
fi

if [ ! -f "$MEME_HOME/config/config.properties" ]; then
    echo "ERROR: $MEME_HOME/config/config.properties not found"
    exit 1
fi

# Check for required credentials
adminUser=`grep 'admin.user' $MEME_HOME/config/config.properties | perl -ne '@_ = split/=/; print $_[1];'`
adminPwd=`grep 'admin.password' $MEME_HOME/config/config.properties | perl -ne '@_ = split/=/; print $_[1];'`

if [ -z "$adminUser" ]; then
    echo "ERROR: admin.user not found in config.properties"
    exit 1
fi

if [ -z "$adminPwd" ]; then
    echo "ERROR: admin.password not found in config.properties"
    exit 1
fi

# Set output file location
OUTPUT_FILE="${INV_HOME}/etc/api_metadata_export.txt"

echo "-----------------------------------------------------"
echo "Extracting metadata from NCIMeta API"
echo "Started at: $(date)"
echo "MEME_HOME: $MEME_HOME"
echo "INV_HOME: $INV_HOME"
echo "Admin User: $adminUser"
echo "Output file: $OUTPUT_FILE"
echo "-----------------------------------------------------"

# Create etc directory if it doesn't exist
#mkdir -p "${INV_HOME}/etc"

# Clear output file
> "$OUTPUT_FILE"

# Extract RELA inverse mappings
echo "Extracting RELA inverse mappings..."
echo "[RELA_INVERSE]" >> "$OUTPUT_FILE"
"${INV_HOME}/bin/api_metadata.sh" rela_inverse --quiet >> "$OUTPUT_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to extract RELA inverse mappings"
    exit 1
fi
echo "" >> "$OUTPUT_FILE"

# Extract expanded forms
echo "Extracting expanded forms..."
echo "[EXPANDED_FORM]" >> "$OUTPUT_FILE"
"${INV_HOME}/bin/api_metadata.sh" expanded_form --quiet >> "$OUTPUT_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to extract expanded forms"
    exit 1
fi
echo "" >> "$OUTPUT_FILE"

# Extract TTY classifications
echo "Extracting TTY classifications..."
echo "[TTY_CLASS]" >> "$OUTPUT_FILE"
"${INV_HOME}/bin/api_metadata.sh" tty_class --quiet >> "$OUTPUT_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to extract TTY classifications"
    exit 1
fi

echo "-----------------------------------------------------"
echo "Extraction complete!"
echo "Finished at: $(date)"
echo "-----------------------------------------------------"
echo ""
echo "Next steps:"
echo "1. Copy $OUTPUT_FILE to your offline environment"
echo "2. Place it in the INV/etc/ directory"
echo "3. Run makeDoc.pl - it will automatically use this file"
echo ""
