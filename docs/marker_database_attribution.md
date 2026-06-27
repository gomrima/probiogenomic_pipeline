# Internal marker database attribution (module 10)

Module 10 (`10_marker_screening`) screens genomes against a curated core
probiotic marker database. That database was designed in this study, not taken
from an external resource, so it needs its own attribution in the package and in
any publication that uses the pipeline.

## Citation

Gomri MA, El Hadef El Okki M, Ounissi NE, Bachtarzi N, Meradji M. Bridging the
gap between probiotic genomic potential and research priorities beyond the
survival core. World Journal of Microbiology and Biotechnology. 2026;42:229.
DOI 10.1007/s11274-026-04967-1.

A web check on 2026-05-31 found an index page indicating publication on
2026-04-22 in *World Journal of Microbiology and Biotechnology*, with authors
Mohamed Amine Gomri, Mohamed El Hadef El Okki, Nour ElHouda Ounissi, Nadia
Bachtarzi, and Meriem Meradji. The DOI, volume 42, and article number 229 were
confirmed against Crossref on 2026-06-15 (published online 2026-04-22, issue 5).

## Database files (V4 layout)

The compiled resources reported in the V4 documentation are:

- `marker_metadata.tsv`
- `all_markers_for_diamond.faa`
- `all_markers_for_diamond.dmnd`
- `all_markers.hmm`

Record the exact counts and SHA256 hashes of the distributed version in
`metadata/marker_database_provenance.tsv`. The distributed version contains 203 markers; the `marker_metadata.tsv` file
has 204 lines including its header row. This matches the 203 markers reported in
Gomri et al. (2026) and the breakdown of 190 markers carrying an HMM profile,
7 DIAMOND-only, and 6 missing both (190 + 7 + 6 = 203).

## Deposit status

The database files are deposited on Zenodo under DOI 10.5281/zenodo.20699785
(https://doi.org/10.5281/zenodo.20699785), released under the Creative Commons
Attribution 4.0 International license (CC-BY-4.0). The same location is recorded
in `metadata/marker_database_provenance.tsv` (fields data_doi and data_url). The
publication above remains the primary scientific citation.

Zenodo assigns two DOIs to this resource: the concept DOI
10.5281/zenodo.20699784 (all versions; the form cited in Gomri et al. 2026) and
the version DOI 10.5281/zenodo.20699785 (this specific deposit, version 1.1).
Both resolve to the same Probiotic_Marker_Database record; this package pins the
version DOI.

## Distribution and attribution

- The database is distributed via Zenodo (DOI 10.5281/zenodo.20699785, CC-BY-4.0),
  not inside this code repository. See `docs/installation_guide.md` for the
  retrieval step.
- Marker counts and SHA256 hashes are recorded in
  `metadata/marker_database_provenance.tsv`.
- The database citation is in `CITATION.cff`, `AUTHORS.md`, and
  `THIRD_PARTY_NOTICES.md`.
- Module 10 should carry the citation and version with its outputs (for example a
  `marker_database_metadata.tsv`) so the attribution travels with the results.

## Scope

The marker database is a scientific resource with its own authorship. The MIT
license of the pipeline code does not cover it. Its reuse terms are Creative
Commons Attribution 4.0 International (CC-BY-4.0), recorded in the
`license_or_terms` field of `metadata/marker_database_provenance.tsv`.
