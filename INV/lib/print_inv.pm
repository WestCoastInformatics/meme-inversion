# to use this library:
# use lib "$ENV{INV_HOME}/lib";
# use print_inv;

sub print_attr{
	# turn on last field printing
	if($Prt_Lst_Fld_Attr){ $last = $lst_fld_attr}
	else{ $last = ""}

	my $fh = shift;
	my $flg = shift;
	$str = "$attr_id|$at_id|$at_lev|$attr_name|$attr_val|$source|$at_stat|$at_tbr|$at_rel|$at_supp|$id_type|$id_qual|$src_atui|$hashcode|$last";
	print $fh "$str\n";
	if($flg){
		print STDOUT "$str\n";
	 }
}
	
sub print_class {
	my $fh = shift;
	my $flg = shift;
	$str = "$said|$sab|$sab/$tty|$code|$cl_stat|$cl_tbr|$cl_rel|$term|$cl_supp|$saui|$scui|$sdui|$lang|$oid|";
	print $fh "$str\n";
	if($flg){
		print STDOUT "$str\n";
	 }
}

sub print_merge{
	my $fh = shift;
	my $flg = shift;
	$str = "$id_1|$lev|$id_2|$sab||$make_demo|$chg_stat|$merge_set|$id_type1|$id_qual1|$id_type2|$id_qual2|";
	print $fh "$str\n";
	if($flg){
		print STDOUT "$str\n";
	 }

}

sub print_rel{
	my $fh = shift;
	my $flg = shift;
	$str="$rel_id|$rel_lev|$rel_id1|$rel|$rela|$rel_id2|$rel_src|$rel_lab_src|$rel_stat|$rel_tbr|$rel_rel|$rel_supp|$rel_id_type1|$rel_qual1|$rel_id_type2|$rel_qual2|$src_rui|$rel_grp|";
	print $fh "$str\n";
}

	
	
1;
