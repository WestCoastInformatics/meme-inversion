# NCIt core code package

This is the release-independent Git home for the executed NCIt core/preparation closure. `provenance.json` records the production-derived stable engine (`bfda2ce`) and each captured/package file hash. Historical source-folder snapshots remain unchanged in Git.

`invert_NCI.pl` and `delete_dup_tref_lines.pl` retain their exact verified bytes. The only preparation changes make `create_rolegroups.pl` accept the declared relations filename and `create_tref.pl` accept the five declared native filenames. They have no dated fallback. Representation and serialization rules are unchanged.

`nci.cfg.in` preserves every effective property from the verified configuration, including existing spelling/casing. Only the release suffix, complete-range start and explicitly saved root ID are substituted. Source/subsource mapping rules remain versioned policy; new publisher/subsource decisions require review. Generated settings are read-only at the unchanged server location `etc/nci.cfg`.

Use the common request/lock runner with the reviewed `generated-configuration` case. The generator binds common configuration fields to hash-identified native exports, source metadata, saved identity and range evidence. It checks the metadata replacement baseline before native preparation. No executable is obtained from a prior server release folder. Full new-release acquisition, production allocation/eligibility and other sources' configuration generation remain later work.
