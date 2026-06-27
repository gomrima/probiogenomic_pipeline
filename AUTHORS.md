# Authors and rights

## Pipeline owner and author

The Probiogenomic Pipeline V4 is owned and authored by:

**Dr. Mohamed Amine Gomri**
Associate Professor, Department of Biotechnology
Institute of Nutrition, Food and Agri-Food Technologies (INATAA)
University of Constantine 1 Frères Mentouri (UC1FM), 25000 Constantine, Algeria
Email: gomrima@umc.edu.dz
GitHub: https://github.com/gomrima
ORCID: 0000-0003-0347-3412

Dr. Gomri is the sole owner and designer of the pipeline. The MIT license in
`LICENSE` holds the copyright in his name and covers the original pipeline code.

## Core marker database (module 10)

The internal marker database used by module 10 was designed in this study and is
published as a separate scientific work:

Gomri MA, El Hadef El Okki M, Ounissi NE, Bachtarzi N, Meradji M. Bridging the
gap between probiotic genomic potential and research priorities beyond the
survival core. World Journal of Microbiology and Biotechnology. 2026;42:229.
DOI 10.1007/s11274-026-04967-1 (DOI, volume, and article number confirmed via
Crossref on 2026-06-15). The database itself is deposited on Zenodo under DOI
10.5281/zenodo.20699785, released under CC-BY-4.0.

That paper has its own co-authors, listed above, who are credited for the
database publication. This is distinct from the ownership of the pipeline code,
which is held solely by Dr. Gomri. See `docs/marker_database_attribution.md` and
`metadata/marker_database_provenance.tsv`.

## Third-party components

The MIT license does not cover the third-party tools, the reference databases, or
the external ProbML models the pipeline calls. Those are listed with their
citations and licenses in `THIRD_PARTY_NOTICES.md`, `docs/tool_references.md`, and
`docs/database_references.md`, and each keeps its own terms.

## Release readiness

1. Marker database DOI confirmed via Crossref on 2026-06-15 (volume 42, article
   229); marker counts and SHA256 hashes recorded in
   `metadata/marker_database_provenance.tsv`.
2. Marker database reuse terms set to CC-BY-4.0 (field `license_or_terms`).
3. Third-party tool, database, and model licenses named in
   `THIRD_PARTY_NOTICES.md` and `metadata/tool_and_database_citations.tsv`.
4. Repository URL set in `CITATION.cff`
   (https://github.com/gomrima/probiogenomic_pipeline).
