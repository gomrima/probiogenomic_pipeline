# Tool references

Full references for the external tools the pipeline calls. Pair this with
`docs/database_references.md` for the reference databases, and with
`metadata/tool_and_database_citations.tsv` for the machine-readable table copied
into each run. Tool versions and DOIs below were checked against the installed
build on 2026-05-12 and 2026-06-13, and updated on 2026-06-15.

- **Prodigal** (module 00, gene calling). Hyatt D, Chen GL, LoCascio PF, Land ML,
  Larimer FW, Hauser LJ. Prodigal: prokaryotic gene recognition and translation
  initiation site identification. BMC Bioinformatics. 2010;11:119.
  doi:10.1186/1471-2105-11-119.
- **Biopython** (module 00, FASTA handling). Cock PJA, et al. Biopython: freely
  available Python tools for computational molecular biology and bioinformatics.
  Bioinformatics. 2009;25(11):1422-1423. doi:10.1093/bioinformatics/btp163.
- **ABRicate** (module 02, AMR and virulence screening). Seemann T. ABRicate.
  https://github.com/tseemann/abricate. Cite the databases it screens (CARD,
  VFDB) separately.
- **HMMER** (modules 03 and 12, profile HMM search). Eddy SR. Accelerated profile
  HMM searches. PLoS Comput Biol. 2011;7(10):e1002195.
  doi:10.1371/journal.pcbi.1002195.
- **MinCED** (module 04, CRISPR arrays). Skennerton CT, et al. MinCED: Mining
  CRISPRs in Environmental Datasets. https://github.com/ctSkennerton/minced
  (GPL-3.0). Derived from the CRISPR Recognition Tool (Bland C, et al. BMC
  Bioinformatics. 2007;8:209. doi:10.1186/1471-2105-8-209).
- **ISEScan** (module 06, insertion sequences). Xie Z, Tang H. ISEScan: automated
  identification of insertion sequence elements in prokaryotic genomes.
  Bioinformatics. 2017;33(21):3340-3347. doi:10.1093/bioinformatics/btx433.
- **MOB-suite** (module 07, plasmid reconstruction). Robertson J, Nash JHE.
  MOB-suite: software tools for clustering, reconstruction and typing of plasmids
  from draft assemblies. Microb Genom. 2018;4(8):e000206.
  doi:10.1099/mgen.0.000206.
- **geNomad** (module 08, prophages and mobile elements). Camargo AP, et al.
  Identification of mobile genetic elements with geNomad. Nat Biotechnol.
  2024;42:1303-1312. doi:10.1038/s41587-023-01953-y. License: LBNL Academic /
  Non-Commercial Use License (academic, non-commercial only; commercial use via
  IPO@lbl.gov).
- **DIAMOND** (modules 10 and 11, protein alignment). Buchfink B, Reuter K, Drost
  HG. Sensitive protein alignments at tree-of-life scale using DIAMOND. Nat
  Methods. 2021;18:366-368. doi:10.1038/s41592-021-01101-x.
- **antiSMASH 8.0.4** (module 13, biosynthetic gene clusters). Blin K, Shaw S,
  Vader L, et al. antiSMASH 8.0: extended gene cluster detection capabilities and
  analyses of chemistry, enzymology, and regulation. Nucleic Acids Res.
  2025;53(W1):W32-W38. doi:10.1093/nar/gkaf334. License: AGPL-3.0.
- **BAGEL5** (module 14, bacteriocins and RiPPs). The BAGEL5 paper is not yet
  published; the BAGEL authors recommend the BAGEL4 citation: van Heel AJ, de Jong
  A, Song C, Viel JH, Kok J, Kuipers OP. BAGEL4: a user-friendly web server to
  thoroughly mine RiPPs and bacteriocins. Nucleic Acids Res. 2018;46(W1):W278-W281.
  doi:10.1093/nar/gky383. http://bagel.molgenrug.nl.
- **epsSMASH 1.2.1** (module 15, EPS-related clusters). An antiSMASH-derived tool
  by AOHD; https://github.com/AOHD/epsSMASH. License: AGPL-3.0. Cite the antiSMASH
  dependency (Blin et al. 2025, above).
- **ProbML / XGBoost** (module 16, external comparator). ProbML models: Arjun OK,
  Mudgal LN, Soni V, Prakash T. ProbML: a machine learning-based genome classifier
  for identifying probiotic organisms. Mol Nutr Food Res. 2025;69(17):e70025.
  doi:10.1002/mnfr.70025. Distributed as MLG_Dashboard
  (https://github.com/sysbio-iitmandi/MLG_Dashboard, MIT). Underlying library:
  Chen T, Guestrin C. XGBoost. KDD. 2016. doi:10.1145/2939672.2939785 (Apache-2.0).
