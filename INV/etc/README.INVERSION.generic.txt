README.INVERSION

DISCLAIMER:

Data submitted by source providers may vary from version to version, including
changes in file names and file formats.  The source inversion spec is also 
subject to change.  It is the responsibility of the inverter to evaluate
source data and determine how/whether to accomodate changse/additions and
deletions, and to update the source inversion accordingly.

RSAB:  <RSAB>

Last update of this file:  <MM/DD/YYYY>
Last VSAB inverted using this README:  <VSAB>

Overview:  

<Provide an overview of the source here.  This should include a simple
description of what the source is used for, its general structure, etc., 
and any other general information which would be useful to an inverter.>

A.  Files from source provider

1)  Required files 
<Provide a very brief description of the file here.  Additional details can 
be found in the source inversion proposal and in the source's documentation.>

2)  Other files provided by source provider
<Provide a list of other files we usually get from the source provider,
indicating why they are not used or not required.>

B.  Scripts and other files required for source inversion 
<All scripts should be in the bin directory;  additional files should
be in etc).

1) scripts

2)  required files:


3) other useful scripts and files:


C.  Process
(step-by-step instructions on how to run the inversion)

1.  copy previous version of sources.src and update it.  Compare what is
in this file to the data in the MRSAB editors (see 
http://unimed.nlm.nih.gov/apelon.html) to make sure none of the information
was changed manually after the insertion.

2.  update termgroups.src

3.  etc.

D.  Standard steps

Run QA4.pl;  review the ERROR_LOG and QA_FILE; rerun inversion as necessary
to fix problems.

Do some conservation of mass.  Start by running $INV_HOME/bin/conservation.s

Complete the si_proposal_<VSAB>.txt and review with NLM.  Convert to
html using $INV_HOME/bin/txt2meow.pl

Create the SIMS record, including uploading the si_proposal_<VSAB>.html file

Announce that the source is ready for test insertion.

After test insertion:
use sty_term_ids to make semantic types, if applicable
<Indicate if this step is applicable or not, and if it does need to run,
give precise instructions>

After real insertion:
resolve SRC-SRC QA counts

D.  Considerations for next inversion:
<Use this area to keep notes about things that we may want to revisit for the
next update>

E.  Inversion changes

<This is a place to keep a running log of relatively high-level inversion 
changes over time> 
