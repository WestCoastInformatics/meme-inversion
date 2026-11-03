To run NLM-independent SNOMEDCT_US inversion:

1) Download SNOMED files from uts.nlm.nih.gov.

2) On ncias-q3793-c, as the tomcat user, create_vsab_dirs.s <VSAB>

2) FTP the zip file to ncias-q3793-c.nci.nih.gov;  You will probably log in as 
yourself and put the files in /tmp (this might be the only directory you can
write to).  Then move the zip file to:
/local/content/MEME/MEME5/inv/sources/<VSAB>/orig/fromprovider
and unzip

3) update sources.src and termgroups.src
You should not have issues if you copy the previous versions of these 
files, but note:
 * The old source is the last version inserted into NCI Meta.  This is
probably different from what is in the UMLS, which updates more frequently
 * The SFAM should be set to SNOMEDCT_US.  This is different from the UMLS.

4) Update invert.s:
conso to MRCONSO from latest NCI Meta, for checking which ICD code 
targets are in Meta

5) Update the .cfg file, including said, current and previous versions, 

***
For the record regarding the NLM-independent SNOMEDCT_US inversion at NCI

Some minor changes to the inversion, and a couple comments for the record about decisions I’ve confronted during this process.    


Questions/comments/changes for the NLM-independent SNOMEDCT_US inversion at NCI.  

Changes:

•	Remove MTH_ atoms for sub/superscript:  it is no longer best practice to make additional atoms in cases like these, and they are confusing; per Brian, this representation is under discussion at IHTSDO so we should wait to incorporate data from their original release files when they make changes.

•	Change rels with typeId = 411116001 from has_dose_form to has_manufactured_dose_form

o	This conceptId has both active and inactive descriptions.  The UMLS and subsequently NCI Meta have been using “has_dose_form” but we agreed it should be  “has_manufactured_dose_form.”  This will be changed at NLM and NCI.    (This is the kind of synergy between projects that makes me happy.)

2466567019|20170731|0|900000000000012004|411116001|en|900000000000003001|Has dose form (attribute)|900000000000020002
2472759013|20170731|0|900000000000012004|411116001|en|900000000000013009|Has dose form|900000000000020002
3495165015|20170731|1|900000000000012004|411116001|en|900000000000013009|Has manufactured dose form|900000000000448009
3495166019|20170731|1|900000000000012004|411116001|en|900000000000003001|Has manufactured dose form (attribute)|900000000000448009

* removed SUBSET_MEMBER TARGETCOMPONENT attributes for cases where targetComponentId is inactive:
1493816011|SUBSET_MEMBER|900000000000531004~TARGETCOMPONENT~6719004
2162346017|SUBSET_MEMBER|900000000000531004~TARGETCOMPONENT~386101005
2162347014|SUBSET_MEMBER|900000000000531004~TARGETCOMPONENT~386101005
2475624011|SUBSET_MEMBER|900000000000531004~TARGETCOMPONENT~282096008
27616012|SUBSET_MEMBER|900000000000531004~TARGETCOMPONENT~359659005
490341018|SUBSET_MEMBER|900000000000531004~TARGETCOMPONENT~300906006
500753011|SUBSET_MEMBER|900000000000531004~TARGETCOMPONENT~17775009

* UMLSRELA: removed attributes for UMLSRELA values that are not in 
relationships (i.e. all the relationships with that RELA were obsolete):
has_associated_etiologic_finding
has_associated_function
has_communication_with_wound
has_concentration_strength_denominator_value
has_concentration_strength_numerator_value
has_count_of_active_ingredient
has_count_of_base_of_active_ingredient
has_definitional_manifestation
has_episodicity
has_extent
has_ingredient_characteristic
has_instrumentation
has_location
has_measured_component
has_presentation_strength_denominator_value
has_presentation_strength_numerator_value
has_product_characteristic
has_stage
has_subject_of_information
may_be_a
measures
moved_from
temporally_follows


Comments:
•	Pairwise rels to ICD10 & ICD10CM are not included in NCI Meta, however they are included in mappings, which are included in EVS Explore.  I could add them to this inversion, but Brian agrees that they probably wouldn’t be used anyway, and I think there would potentially be an issue keeping them synced.  
•	We expect “refers_to” rels ("REFERS TO concept association reference set") to involve obsolete descriptions.  However, there are a handful of refers_to rels involving current descriptions.  These are being dropped
 (*** Note:  I was reviewing some old monthly reports from NLM and noticed
that we discovered this issue when I was writing the documentation in 2021
and decided that it was a violation of their model but it didn't affect us).

