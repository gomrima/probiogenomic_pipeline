# Third-party notices

This pipeline runs external bioinformatics tools, databases, and models. The MIT
license in `LICENSE` covers only the original pipeline code. It does not cover
the third-party components below, the reference databases they use, or the
external ProbML models. Each component keeps its own authors, license, and terms.

The machine-readable version of this list is
`metadata/tool_and_database_citations.tsv`, which the launcher can copy into each
run under `runs/<run_name>/meta`. Detailed references are in
`docs/tool_references.md` and `docs/database_references.md`.

Tool versions and database provenance were verified on the target Linux host
(2026-05-12 and 2026-06-13). See `docs/tool_versions.md` and
`docs/database_provenance.md`. This repository does not redistribute any of these
third-party tools, databases, or models; each is obtained from its own source
under its own terms.

## Tools

| Module | Tool | Citation | License |
|---|---|---|---|
| 00 | Prodigal | Hyatt et al. 2010, BMC Bioinformatics, 10.1186/1471-2105-11-119 | GPL-3.0 |
| 00 | Biopython | Cock et al. 2009, Bioinformatics, 10.1093/bioinformatics/btp163 | Biopython License |
| 02 | ABRicate | Seemann T., github.com/tseemann/abricate | GPL-2.0 |
| 03, 12 | HMMER | Eddy 2011, PLoS Comput Biol, 10.1371/journal.pcbi.1002195 | BSD-3 |
| 04 | MinCED | github.com/ctSkennerton/minced (from CRISPR Recognition Tool) | GPL-3.0 |
| 06 | ISEScan | Xie & Tang 2017, Bioinformatics, 10.1093/bioinformatics/btx433 | GPL-3.0 |
| 07 | MOB-suite | Robertson & Nash 2018, Microb Genom, 10.1099/mgen.0.000206 | Apache-2.0 |
| 08 | geNomad | Camargo et al. 2024, Nat Biotechnol, 10.1038/s41587-023-01953-y | LBNL Academic/Non-Commercial Use License (academic, non-commercial only; commercial via IPO@lbl.gov) |
| 10, 11 | DIAMOND | Buchfink et al. 2021, Nat Methods, 10.1038/s41592-021-01101-x | GPL-3.0 |
| 13 | antiSMASH 8.0.4 | Blin et al. 2025, Nucleic Acids Res 53(W1):W32-W38, 10.1093/nar/gkaf334 | AGPL-3.0 |
| 14 | BAGEL5 | van Heel et al. 2018 (BAGEL4), Nucleic Acids Res 46(W1):W278-W281, 10.1093/nar/gky383; BAGEL5 paper not yet published; bagel.molgenrug.nl | BAGEL terms |
| 15 | epsSMASH 1.2.1 | AOHD, github.com/AOHD/epsSMASH; antiSMASH-derived; executable at `conda/envs/antismash_dependencies/bin/epsSMASH` | AGPL-3.0 |
| 16 | XGBoost (ProbML models) | Chen & Guestrin 2016, 10.1145/2939672.2939785 | Apache-2.0 |

## Databases

| Module | Database | Citation |
|---|---|---|
| 02 | CARD | Alcock et al. 2023 (CARD 2023), Nucleic Acids Res 51(D1):D690-D699, 10.1093/nar/gkac920 |
| 02 | VFDB | Liu et al. 2022, Nucleic Acids Res, 10.1093/nar/gkab1107 |
| 03 | TASmania | Akarsu et al. 2019, PLoS Comput Biol, 10.1371/journal.pcbi.1006946 |
| 05 | DBETH | Chakraborty et al. 2012, Nucleic Acids Res, 10.1093/nar/gkr942 |
| 05 | PAT | PAT database, Nucleic Acids Res 2023, 10.1093/nar/gkac829 |
| 12 | dbCAN3 | Zheng et al. 2023, Nucleic Acids Res 51(W1):W115-W121, 10.1093/nar/gkad328 |

## Internal database (module 10)

The core probiotic marker database used by module 10 was designed in this study.
Cite Gomri et al. 2026, *World Journal of Microbiology and Biotechnology* 42:229,
DOI 10.1007/s11274-026-04967-1 (confirmed via Crossref on 2026-06-15). The database
is deposited on Zenodo under DOI 10.5281/zenodo.20699785 and released under the
Creative Commons Attribution 4.0 International license (CC-BY-4.0). See
`metadata/marker_database_provenance.tsv` and `docs/marker_database_attribution.md`.

## ProbML

ProbML is an external comparator. Cite Arjun OK, Mudgal LN, Soni V, Prakash T.
ProbML: a machine learning-based genome classifier for identifying probiotic
organisms. Mol Nutr Food Res. 2025;69(17):e70025 (DOI 10.1002/mnfr.70025). The
models and GUI are distributed as MLG_Dashboard
(https://github.com/sysbio-iitmandi/MLG_Dashboard, MIT license) and bundle
XGBoost (Chen and Guestrin 2016, Apache-2.0). A ProbML prediction is a comparison
signal, not evidence of a probiotic phenotype.
