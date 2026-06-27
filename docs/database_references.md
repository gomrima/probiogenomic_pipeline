# Database references

Full references for the reference databases the pipeline screens against. These
databases keep their own licenses and terms, which the MIT license of this
pipeline does not cover. Record the local version and download date of each
database in `database_provenance.tsv` per run. Entries marked `to verify` need a
final check against the publisher page at packaging. For where to obtain each
database and where to place it under `PIPE_ROOT`, see the Acquisition blocks in
`docs/database_provenance.md`.

- **CARD** (module 02, antimicrobial resistance). Alcock BP, et al. CARD 2023:
  expanded curation, support for machine learning, and resistome prediction at
  the Comprehensive Antibiotic Resistance Database. Nucleic Acids Res.
  2023;51(D1):D690-D699. doi:10.1093/nar/gkac920.
- **VFDB** (module 02, virulence factors). Liu B, Zheng D, Zhou S, Chen L, Yang J.
  VFDB 2022: a general classification scheme for bacterial virulence factors.
  Nucleic Acids Res. 2022;50(D1):D912-D917. doi:10.1093/nar/gkab1107.
- **TASmania** (module 03, toxin-antitoxin systems). Akarsu H, et al. TASmania: a
  bacterial toxin-antitoxin systems database. PLoS Comput Biol.
  2019;15(4):e1006946. doi:10.1371/journal.pcbi.1006946.
- **DBETH** (module 05, bacterial exotoxins). Chakraborty A, Ghosh S, Chowdhary G,
  Maulik U, Chakrabarti S. DBETH: a database of bacterial exotoxins for human.
  Nucleic Acids Res. 2012;40(D1):D615-D620. doi:10.1093/nar/gkr942.
- **PAT** (module 05, prokaryotic antimicrobial toxins). PAT: a comprehensive
  database of prokaryotic antimicrobial toxins. Nucleic Acids Res.
  2023;51(D1):D452-D459. doi:10.1093/nar/gkac879. Database download:
  http://bioinfo.qd.sdu.edu.cn/PAT/download.html.
- **ProbioDB / ProbioSML** (module 11, probiotic-associated genes). Neres
  Rodrigues DL, Sodrzeieski P, Benko Iseppon AM, Azevedo VAC, de Castro Soares S,
  Figueira Aburjaile F. Probiotic sequences dataset based on Machine Learning
  (1.0). Zenodo. 2025. doi:10.5281/zenodo.14181444. License: CC-BY-4.0.
- **dbCAN3** (module 12, carbohydrate-active enzymes). Zheng J, Ge Q, Yan Y,
  Zhang X, Huang L, Yin Y. dbCAN3: automated carbohydrate-active enzyme and
  substrate annotation. Nucleic Acids Res. 2023;51(W1):W115-W121.
  doi:10.1093/nar/gkad328.

Tools that bundle their own model or HMM set (geNomad, antiSMASH, BAGEL5,
ISEScan, MOB-suite, ProbML) should also have their bundled data versions recorded
in `database_provenance.tsv`.
