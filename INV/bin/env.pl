#!/usr/bin/perl
#
# env.pl - Environment configuration for NCI Inversion Framework
# This file sets up the required environment variables for inversion scripts
#

use strict;
use warnings;
use FindBin qw($Bin);
use File::Basename;

# Set environment variables
$ENV{INV_HOME} = "/Users/deborahshapiro/Code/workspace-meme-inversion2/INV" unless $ENV{INV_HOME};
$ENV{INV_HOME_OLD} = $ENV{INV_HOME} unless $ENV{INV_HOME_OLD};
$ENV{ENV_HOME} = $ENV{INV_HOME} unless $ENV{ENV_HOME};
$ENV{SRC_ROOT} = "/Users/deborahshapiro/Code/workspace-meme-inversion2/sources" unless $ENV{SRC_ROOT};

# Set locale for consistent behavior
$ENV{LANG} = "en_US.UTF-8";
$ENV{LC_COLLATE} = "C";

# Return true to indicate successful loading
1;
