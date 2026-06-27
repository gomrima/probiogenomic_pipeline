# Database provenance and acquisition

This document records two things for every database the pipeline uses: the frozen
provenance (version, date, size, SHA256, local location) verified on the V4 Linux
reference host, and the acquisition (where to obtain the database and where to
place it under `PIPE_ROOT`). It combines the former provenance-only record with
acquisition instructions so the `db/` and `external_tools/` trees can be
reconstructed without redistributing third party files.

Provenance was verified on the target Linux host (gma-Inspiron-15-3567,
Linux 6.17.0-14-generic x86_64) from `pipeline_V4.txt` generated 2026-05-12 and
live terminal verification 2026-06-13. All SHA256 hashes below are from
`pipeline_V4.txt`.

## How to read the acquisition entries

Each database has an Acquisition block giving the download source or command, the
target version, and the final placement under `PIPE_ROOT`. All sources were
confirmed against the publisher or tool documentation, or provided by the research
team, as of 2026-06-15.

Paths use `PIPE_ROOT` as the package root. The reference databases keep their own
licenses and terms, which the MIT license of the pipeline code does not cover.
Record the local version and download date of each database in
`database_provenance.tsv` per run, and see `docs/database_references.md` for the
scientific citations.

## ABRicate databases (CARD, VFDB)

Managed by the ABRicate conda environment (`probio_core`). All ABRicate databases
dated 2025-Dec-5.

| Database | Sequences | Type | Date |
|---|---|---|---|
| card | 6052 | nucl | 2025-Dec-5 |
| vfdb | 4592 | nucl | 2025-Dec-5 |
| argannot | 2224 | nucl | 2025-Dec-5 |
| resfinder | 3206 | nucl | 2025-Dec-5 |
| ncbi | 8035 | nucl | 2025-Dec-5 |
| ecoli_vf | 2701 | nucl | 2025-Dec-5 |
| plasmidfinder | 488 | nucl | 2025-Dec-5 |
| victors | 4545 | nucl | 2025-Dec-5 |
| ecoh | 597 | nucl | 2025-Dec-5 |
| bacmet2 | 746 | prot | 2025-Dec-5 |
| megares | 6635 | nucl | 2025-Dec-5 |

Pipeline module 02 (safety_abricate) uses CARD and VFDB.

Acquisition. ABRicate bundles its database setup tool. With the
`probio_core` environment active:

```bash
abricate-get_db --db card --force
abricate-get_db --db vfdb --force
abricate --list   # record the installed DATE and NSEQ per database
```

ABRicate is from https://github.com/tseemann/abricate. The databases install into
the ABRicate share directory inside the active conda environment, not under `db/`.
Note for reproducibility: `abricate-get_db` always fetches the current upstream
build of CARD and VFDB, so it will not reproduce the exact 2025-Dec-5 snapshot.
Record the `abricate --list` date with each run. CARD and VFDB carry their own
licenses; cite them separately.

## TASmania toxin-antitoxin HMM database

Location: `db/tasmania/compiled/tasmania_all.hmm`
Raw HMM file count: 682 individual HMM profiles.
Compiled HMM size: 57,935,618 bytes.

| File | SHA256 |
|---|---|
| tasmania_all.hmm | 332e6697a839f781f4358dd856497ffbc8014a5a6e5a629a84cc632f74ef19b7 |
| TASmania_HMMs.tar (raw) | bae65b81d104ffdcab5ebba94642733bb7fef9c43bb892967ea681f054bd3f3f |

Acquisition. TASmania (Akarsu et al. 2019) is available from the SIB
resource at https://shiny.bioinformatics.unibe.ch/apps/tasmania/ (download path
provided by the research team, 2026-06-15). Obtain the HMM profile set,
concatenate the profiles into `tasmania_all.hmm`, place it at
`$PIPE_ROOT/db/tasmania/compiled/tasmania_all.hmm`, and run `hmmpress` on it. Match
the SHA256 above to validate the frozen artifact.

## DBETH and PAT bacterial toxin databases

Location: `db/safety/`

| File | Sequences | SHA256 |
|---|---|---|
| DBETH/Human_pathogenic_bacterial_exotoxin.fasta | 229 | e9f7c94c38599ab65a93d466fedf566c06ec1aa256afb0ebc061eb6f8bcb457d |
| DBETH/Human_pathogenic_bacterial_exotoxin_homologs.fasta | 31,769 | aa027386b3027f8c9656c2e658a25c555a176a2af91413d257487da1b683d30e |
| PAT/PAT-prot.fasta | 441 | 20645cf50175362f8b1b3ffe8721c37379effb69185a278f40ad6c21f709e271 |
| PAT/IMM-prot.fasta | 288 | 7931a1eace7e881cb2eb3220441ccbc0adfec194f9e00ae288555e2ba312fb08 |
| PAT/Expanded-PAT-prot.fasta | 6,026 | a32289bb7ddeeca1f74459314f6994ffb40f1c3823fdf6ecd23cadb94cf8e64c |

Pre-compiled DIAMOND databases:

| File | SHA256 |
|---|---|
| compiled_diamond/dbeth_exotoxins.dmnd | 34ff8e139d628c3f4ead2c04cdc6dbc6693806b6f158d82d89385c1d65c055e1 |
| compiled_diamond/pat_toxins.dmnd | c496ab9e6589fe29b86801e2846a6ae6677c3c917ec22003c3e6bd6e82405fc4 |
| compiled_diamond/pat_immunity.dmnd | d49de9e493a1694bf6433d9d6fc0233353f9fbf74159fcae309ad6dac8d84e64 |

Module 05 (bacterial_toxins_screen) uses these resources.

Acquisition DBETH. DBETH (Chakraborty et al. 2012) sequences are
downloaded from
http://www.hpppi.iicb.res.in/btox/cgi-bin2/download-list.cgi?name=download
(provided by the research team, 2026-06-15). Download the human pathogenic
bacterial exotoxin sequences and their homologs, place them under
`$PIPE_ROOT/db/safety/DBETH/`, and rebuild the DIAMOND database with
`diamond makedb`. Match the SHA256 hashes above.

Acquisition PAT. PAT (NAR 2023;51(D1):D452-D459,
doi:10.1093/nar/gkac879) provides its sequences at
http://bioinfo.qd.sdu.edu.cn/PAT/download.html (provided by the research team,
2026-06-15). Download the PAT and IMM protein FASTA files and the expanded set,
place them under `$PIPE_ROOT/db/safety/PAT/`, and rebuild the DIAMOND databases.
Match the SHA256 hashes above.

## Curated probiotic marker database

Location: `db/compiled/`

| File | Sequences | SHA256 |
|---|---|---|
| diamond/all_markers_for_diamond.dmnd | 1,351 | 6f058510d9f5fc0d6a2935ea07cb3bc94434231611f39298cfd76825ea9dc60e |
| diamond/all_markers_for_diamond.faa | 151,537 | 90c54b0eab4d72f464f2ef10a3ea200e1fa24886cc8b779c2fc7e3a60ea93712 |
| hmm/all_markers.hmm | n/a | ca9e0bc8913c4b201f01afe7dce786f194b2c88f3ad7f65fc62c00fc5b652791 |
| metadata/marker_metadata.tsv | 204 lines | 9f1f9a913b77d3b222b69baab88218c8ea825da80a75ccde5bc00e5e8860e973 |
| metadata/markers_diamond_only.txt | 7 lines | bbc6fe8e2ebdfb97d007badea554911a3b91c904da2af0445ba2c1de41d855cb |
| metadata/markers_with_hmm.txt | 190 lines | f84ab40d2cd42ac05d14c2024dba13b703ef854ade9807fcb2b990db9099a6ce |
| metadata/markers_missing_both.txt | 6 lines | 41889f906970a1a9e2cedb571a984e3b41239eafc9f367fc8598aa7a2781b644 |

Module 10 (marker_screening) uses this database. It is a scientific resource
designed in this study, not taken from an external resource; see
`docs/marker_database_attribution.md`.

Acquisition. The database is distributed on Zenodo under DOI
10.5281/zenodo.20699785 (https://doi.org/10.5281/zenodo.20699785), released under
the Creative Commons Attribution 4.0 International license (CC-BY-4.0). It is not
bundled in this code repository.

```bash
# Download the marker database archive from the Zenodo record above, then:
unzip <downloaded_archive>.zip -d "$PIPE_ROOT/db/"
ls "$PIPE_ROOT/db/"   # expect markers_DB.xlsx, marker_fastas/, hmm_profiles/
bash scripts/01_run_prepare_marker_resources.sh
```

The preparation step builds the compiled `db/compiled/` resources listed above from
`db/markers_DB.xlsx`, `db/marker_fastas/`, and `db/hmm_profiles/` using DIAMOND and
HMMER. The scientific citation is Gomri et al. 2026, World J Microbiol Biotechnol
42:229 (DOI 10.1007/s11274-026-04967-1).

## dbCAN (CAZyme HMM database)

Location: `db/dbcan/compiled/dbCAN.txt`
Version: HMMdb-V12 (source file: `dbCAN-HMMdb-V12.txt`, dated 2023-08-03).

| File | SHA256 |
|---|---|
| dbCAN.txt | c30a7be44952e8d13825043686ca79ee81ed78da473ebb0cbbe4bdb46c3f5093 |
| dbCAN-HMMdb-V12.txt (download) | c30a7be44952e8d13825043686ca79ee81ed78da473ebb0cbbe4bdb46c3f5093 |

Matching SHA256 confirms that the compiled HMM is identical to the downloaded source.
Module 12 (cazymes_dbcan) uses this database.

Acquisition. dbCAN HMMdb V12 is hosted by the dbCAN group at the
University of Nebraska-Lincoln.

```bash
mkdir -p "$PIPE_ROOT/db/dbcan/compiled"
cd "$PIPE_ROOT/db/dbcan/compiled"
wget https://bcb.unl.edu/dbCAN2/download/Databases/V12/dbCAN-HMMdb-V12.txt
mv dbCAN-HMMdb-V12.txt dbCAN.txt
hmmpress dbCAN.txt
```

The fixed V12 URL pins the exact version used here, so this is reproducible. Match
the SHA256 above.

## MOB-suite database

Location: `db/mob_suite/`
Downloaded: 2026-03-08 (confirmed via terminal history).

Module 07 (mobsuite_plasmids) uses this database.

Acquisition. MOB-suite (phac-nml/mob-suite,
https://github.com/phac-nml/mob-suite) downloads its plasmid database from figshare
on first use, or manually with `mob_init`. With the `mob_suite_env` environment
active:

```bash
mob_init -d "$PIPE_ROOT/db/mob_suite"
```

Note for reproducibility: `mob_init` fetches the current upstream database, so it
may not reproduce the 2026-03-08 snapshot. Record the download date and the
MOB-suite version with each run. To override the location at runtime, set
`MOBSUITE_DB`.

## geNomad database

Location: `db/genomad/genomad_db`
Database version: 1.9 (confirmed via `genomad_db/version.txt` on the Linux host,
terminal verification 2026-06-13).
Size: 1.4 GB, 27 files.
Tool version: geNomad 1.12.0.

Module 08 (genomad_prophages) uses this database.

Acquisition. geNomad (apcamargo/genomad,
https://github.com/apcamargo/genomad) provides a database downloader. With the
`genomad_env` environment active:

```bash
genomad download-database "$PIPE_ROOT/db/genomad"
cat "$PIPE_ROOT/db/genomad/genomad_db/version.txt"   # confirm the version
```

Note for reproducibility: `download-database` fetches the latest database, which
may now be newer than 1.9. Record `version.txt` with each run. The frozen runs used
database version 1.9. To override the location at runtime, set `GENOMAD_DB`.
License: geNomad uses the LBNL Academic and Non-Commercial Use License; commercial
use requires a separate agreement (see `docs/tool_references.md`).

## ProbioSML database (ProbioDB 1.0)

Location: `db/ProbioSML_DB/`
Detection: DIAMOND-only against ProbioDB_1.0.faa.
Sequences: 1,072 in ProbioDB_1.0.faa (local count from `pipeline_V4.txt`). The
Zenodo record describes ProbioSML as 1,071 genes; reconcile this difference of one
sequence against the deposited FASTA before final submission.

| File | SHA256 (local) | MD5 (Zenodo record) |
|---|---|---|
| ProbioDB_1.0.faa | dfee99f627a6e7940c8e98e46d907a5feafdff18a8581a5c5ddcb9efdfc2c755 | 09c7ba01026bc62ba8eb502416d1147e |
| ProbioDB_1.0.dmnd | a221f3879d548d7935e11d7b8f7fd47a0f649e7215fc5a3aabd6904ec9053c4d | built locally, not on Zenodo |

Module 11 (probiosml_screen) uses this database.

Acquisition. ProbioDB 1.0 is deposited on Zenodo under DOI 10.5281/zenodo.14181444
(https://zenodo.org/records/14181444), version 1.0 published 2025-06-18, released
under the Creative Commons Attribution 4.0 International license (CC-BY-4.0). The
concept DOI 10.5281/zenodo.14181443 always resolves to the latest version. The
record contains `ProbioDB_1.0.faa`, `ProbioDB_1.0.ffn`, `db_overall.tsv`, and
`db_overall.xlsx`.

```bash
mkdir -p "$PIPE_ROOT/db/ProbioSML_DB"
# Download ProbioDB_1.0.faa from the Zenodo record above into that directory, then:
diamond makedb --in "$PIPE_ROOT/db/ProbioSML_DB/ProbioDB_1.0.faa" \
  --db "$PIPE_ROOT/db/ProbioSML_DB/ProbioDB_1.0"
```

The pinned version DOI makes this reproducible. Verify the downloaded
`ProbioDB_1.0.faa` against the Zenodo MD5 (09c7ba01026bc62ba8eb502416d1147e), then
confirm the local SHA256 above. Do not assume it is the same resource as the ProbML
comparator (module 16). Citation: Neres Rodrigues DL, Sodrzeieski P, Benko Iseppon
AM, Azevedo VAC, de Castro Soares S, Figueira Aburjaile F. Probiotic sequences
dataset based on Machine Learning (1.0). Zenodo. 2025.
doi:10.5281/zenodo.14181444.

## antiSMASH database

Location: `db/antismash/` (bundled with antiSMASH 8.0.4 conda environment).
Key resources: `clusterblast/`, `knownclusterblast/4.0/`, `clustercompare/mibig/4.0/`,
`pfam/35.0/Pfam-A.hmm`.

Module 13 (antismash_minimal) uses this database.

Acquisition. antiSMASH ships a database downloader. With the antiSMASH
8.0.4 environment active:

```bash
download-antismash-databases
```

By default the databases install into the antiSMASH installation share directory.
To place them elsewhere, configure the antiSMASH database directory or set
`ANTISMASH_DB` for the wrappers. antiSMASH 8.0.4 (Blin et al. 2025, NAR
53(W1):W32-W38, doi:10.1093/nar/gkaf334) is AGPL-3.0. Official documentation:
https://docs.antismash.secondarymetabolites.org/install/.

## BAGEL5 resources

Location: `external_tools/BAGEL5/`
No standalone semantic version. Local integration.

| File | SHA256 |
|---|---|
| bagel5.py | 0b83baa9a1b28a5d593de14a7908b840552e4519bef516a681f4b92fd1fba9f0 |
| sORF_prediction.py | a6109f88a10d399fba2a52ef4e9fa5c2e5012bf5411bf492fd42d57fefbb9b8c |
| bagel5_AOI_Rules_table.txt | df76a3834b72a516591317cf02b22281d44b7677b12795f87c4fffa52beb0ec3 |
| bagel5_CorePeptidesTypes.table | a807b6c0296ca64a1591682272e61d85f70d5f8b1c217ead4245a5a818b9a0b3 |
| bagel5_ContextProteinTypes.table | 04917da1b306d96b4f54b120fa4781c204d4865e3d38b1ba3e788c794994a217 |
| bagel5_bacteriocins_annotation.table | dd5e958956d00e9d92d727a20d1eb99fbba9b06efaad3be56a7cd06d7093c864 |

Module 14 (bagel5_full) uses these resources.

Acquisition. BAGEL5 is downloaded from http://ngs.molgenrug.nl/bagel5/
(provided by the research team, 2026-06-15). Install BAGEL5 so that the script
resolves at
`$PIPE_ROOT/external_tools/BAGEL5/src/data/bagel5/scripts/bagel5.py`, as expected by
the installation guide. The BAGEL5 paper is not yet published; the authors
recommend the BAGEL4 citation (van Heel et al. 2018, doi:10.1093/nar/gky383). Match
the SHA256 hashes above.

## epsSMASH database

Location: `db/epssmash/`
Key resources: `clusterblast/clusters.txt`, `clusterblast/proteins.dmnd`,
`pfam/35.0/Pfam-A.hmm`.
epsSMASH version: 1.2.1 (based on antiSMASH 7.dev).
Executable: `conda/envs/antismash_dependencies/bin/epsSMASH`.

Module 15 (epssmash_full) uses this database.

Acquisition. epsSMASH version 1.2.1 is an antiSMASH-derived tool by
AOHD at https://github.com/AOHD/epsSMASH (AGPL-3.0). Clone the repository and
install version 1.2.1, exposing the executable at
`$PIPE_ROOT/conda/envs/antismash_dependencies/bin/epsSMASH`. The bundled resources
(`clusterblast/`, `pfam/35.0/`) derive from the antiSMASH 7.dev dependency. To
override the database location at runtime, set `EPSSMASH_DB`.

## ProbML models

Location: `db/ProbML/MLG_Dashboard-main/models/`
Git revision: db346196f02c15ad09755f74307773c395b7303d.
Model count: 12 Model*.json + 12 TF_Model*.txt.
XGBoost JSON version: 2.0.3 for all models.
Models 1 to 6: RS4658 feature set (942 features).
Models 7 to 12: RS6331 feature set (892 features).

| Model file | SHA256 |
|---|---|
| Model1.json to Model6.json | 9668d72221c2e10791d8450ffe200c4a89abc0d77006371467515dd2331bcc03 |
| Model7.json to Model12.json | 5f93c1f71781142078322d642cc196a9347e627c98112a1a70a942b0fe22fea8 |
| TF_Model1.txt to TF_Model6.txt | d0105400accfa6c20641d58b428753d817075a29473efebcc4bc49125b447368 |
| TF_Model7.txt to TF_Model12.txt | 12c6752f6dd820815e177d4b5bb8d5a83956b75163a705de6cebd2813915b7b3 |

Module 16 (probml_screen) uses these models. ProbML is an external comparator only.

Acquisition. ProbML is distributed as MLG_Dashboard
(https://github.com/sysbio-iitmandi/MLG_Dashboard, MIT). Clone the repository and
check out the exact revision used here:

```bash
git clone https://github.com/sysbio-iitmandi/MLG_Dashboard "$PIPE_ROOT/db/ProbML/MLG_Dashboard-main"
cd "$PIPE_ROOT/db/ProbML/MLG_Dashboard-main"
git checkout db346196f02c15ad09755f74307773c395b7303d
```

The pinned revision makes this reproducible. The 12 models and 12 threshold files
live under `models/`. ProbML citation: Arjun OK et al. 2025, Mol Nutr Food Res
69(17):e70025, doi:10.1002/mnfr.70025.

## Source

Primary evidence: `pipeline_V4.txt` (generated 2026-05-12, host
gma-Inspiron-15-3567). geNomad DB version confirmed live on 2026-06-13.
MOB-suite download date confirmed via terminal history (2026-03-08). Acquisition
URLs for TASmania, DBETH, PAT, ProbioDB 1.0, BAGEL5, and epsSMASH were provided by
the research team on 2026-06-15; the remaining acquisition commands were checked
against tool and publisher documentation on 2026-06-15.
