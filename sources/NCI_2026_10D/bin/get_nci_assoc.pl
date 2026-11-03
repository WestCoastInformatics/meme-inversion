#!/usr/bin/perl

#split out associations from nci_rels.tmp file
#remove any self-referential associations

open (OWL, "<../tmp/nci_rels.tmp") || die "can't open OWL\n";
open (OUT, ">../orig/nci_associations.txt") || die "can't open OUT\n";


while (<OWL>){
	chomp;
	($atom1,$rel,$atom2,$rui)=split(/\|/);
	if($atom1 eq $atom2){
		print "removing self-referential rel: $_\n";
		next;
	}
	elsif (($rel eq 'Concept_In_Subset') || ($rel eq 'Subset_Includes_Concept') ||($rel eq 'Has_Salt_Or_Ester_Form') || ($rel eq 'Has_Free_Acid_Or_Base_Form') || ($rel eq 'Is_PCDC_AML_Authorized_Value_For_Variable') || ($rel eq 'Has_PCDC_AML_Authorized_Value') || ($rel eq 'Has_PCDC_Data_Type') ||($rel eq 'Has_Target') || ($rel eq 'Is_Target_Of_Agent') || ($rel eq 'Has_CDRH_Parent') || ($rel eq 'Parent_is_CDRH') || ($rel eq 'Has_NICHD_Parent') || ($rel eq 'Parent_Is_NICHD') || ($rel eq 'Is_Related_To_Endogenous_Product') || ($rel eq 'Endogenous_Product_Related_To') || ($rel eq 'Role_Has_Domain') || ($rel eq 'Kind_Is_Domain_Of') || ($rel eq 'Role_Has_Range') || ($rel eq 'Kind_Is_Range_Of') || ($rel eq 'Role_Has_Parent') || ($rel eq 'Role_Is_Parent_Of') || ($rel eq 'Qualifier_Applies_To') || ($rel eq 'Is_Qualified_By') || ($rel eq 'Has_Data_Element') || ($rel eq 'Related_To_Genetic_Biomarker') || ($rel eq 'Neoplasm_Has_Special_Category') || ($rel eq 'Has_CTCAE_5_Parent') || ($rel eq 'Has_INC_Parent') || ($rel eq 'Has_Pharmaceutical_State_Of_Matter') || ($rel eq 'Has_Pharmaceutical_Basic_Dose_Form') || ($rel eq 'Has_Pharmaceutical_Administration_Method') || ($rel eq 'Has_Pharmaceutical_Intended_Site') || ($rel eq 'Has_Pharmaceutical_Release_Characteristics') || ($rel eq 'Has_Pharmaceutical_Transformation') || ($rel eq 'Has_CTDC_Value') || ($rel eq 'Value_Set_Is_Paired_With') || ($rel eq 'Has_PCDC_EWS_Authorized_Value') || ($rel eq 'Is_PCDC_EWS_Authorized_Value_For_Variable') || ($rel eq 'Has_ICDC_Value') || ($rel eq 'Has_PCDC_GCT_Authorized_Value') || ($rel eq 'Is_PCDC_GCT_Authorized_Value_For_Variable') || ($rel eq 'Has_GDC_Value') || ($rel eq 'Is_Value_For_GDC_Property') || ($rel eq 'Is_PCDC_ALL_Authorized_Value_For_Variable') || ($rel eq 'Has_PCDC_ALL_Authorized_Value') || ($rel eq 'Has_SeroNet_Authorized_Value') || ($rel eq 'Is_SeroNet_Authorized_Value_For_Variable') || ($rel eq 'Has_DIPG_DMG_Authorized_Value') || ($rel eq 'Has_PCDC_OS_Authorized_Value') || ($rel eq 'Has_PCDC_HL_Authorized_Value') || ($rel eq 'Has_Pharmaceutical_Basic_Administrable_Dose_Form') || ($rel eq 'Has_ACC-AHA_SARS2_Authorized_Value') || ($rel eq 'Has_OORO_PC_Value') || ($rel eq 'Has_Ped-PRO-CTCAE_Attribute') || ($rel eq 'Has_Ped-PRO-CTCAE_Attribute_Value') || ($rel eq 'Has_Ped-PRO-CTCAE_Parent') || ($rel eq 'Has_PRO-CTCAE_Attribute') || ($rel eq 'Has_PRO-CTCAE_Attribute_Value') || ($rel eq 'Has_PRO-CTCAE_Parent') || ($rel eq 'Has_OORO_BC_Value') || ($rel eq 'Has_OORO_Data_Type') || ($rel eq 'Has_OORO_HNC_Value') || ($rel eq 'Has_OORO_LC_Value')){
		print OUT "$atom1|$rel|$atom2|\n";
	}
}
close(OWL);
