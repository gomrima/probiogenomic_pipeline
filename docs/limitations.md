# Limitations

This final repository is a portable source package, not a standalone offline installer.

External tools and databases are not bundled unless already present in the local project. Their licenses and release conditions remain separate.

The final package was statically validated locally. End-to-end biological regression requires a Linux host with the complete environments, databases, and a legacy output set for comparison.

ProbML is an external comparator layer. It does not replace the biological interpretation of the safety, mobility, and probiotic function modules.

BAGEL5 and epsSMASH parser paths have been restored to the portable V4 Linux
layout, but their biological equivalence to the historical parser outputs has
not been tested with real Linux runs.

The module 10 marker resource setup now has a wrapper and preflight checks, but
the produced DIAMOND and HMMER compiled files still need to be hashed on the
target Linux host after preparation.

The epsSMASH executable path follows the V4 Linux source tree through
`conda/envs/antismash_dependencies/bin/epsSMASH`. epsSMASH provenance, citation,
license, and redistribution status still require confirmation before public
release.

## Scientific interpretation limits

Every output of this pipeline is predicted genomic potential inferred from
sequence. It is not evidence of a biological outcome. Read the matrices with the
following limits in mind.

- Genomic potential only. A detected feature shows that a gene or a signal is
  present in the assembly. It does not show that the gene is expressed, that the
  protein is active, that a metabolite is produced, that the strain colonises a
  host, or that any probiotic benefit, safety, or clinical effect occurs. None of
  these can be concluded from genome screening alone.
- A zero is not a biological absence. A binary 0 means the feature was not
  detected under the current input assembly, reference database, search
  threshold, and tool success state. A different assembly, a different database
  version, a different threshold, or a tool failure can change a 0. Read a 0 as
  not detected here, not as absent.
- Database and threshold dependence. Results depend on the reference databases
  and on fixed search thresholds, for example the DIAMOND and HMMER e-values. A
  marker missing from a database cannot be found, and a borderline hit can fall
  on either side of a threshold. Detection rates are not directly comparable
  across database versions.
- Taxonomy and assembly confounding. Feature counts track genus, genome size,
  and assembly quality. A fragmented or incomplete assembly can lower a feature
  count for technical reasons. Separate the functional signal from genus, genome
  size, and assembly quality before comparing genomes or groups.
- Safety first. Unresolved antimicrobial resistance, virulence, toxin, or
  mobile-element-localised risk signals override positive probiotic-associated
  markers. A high count of beneficial markers does not offset an unaddressed
  safety signal. The safety, mobility, and plasticity modules are screening
  evidence that must be reviewed case by case, not averaged against positive
  markers.
- ProbML is a comparator. The module 16 ProbML prediction is an external
  machine-learning comparison signal. It is not ground truth, not a curated
  marker, and not a substitute for the curated evidence or the scoring logic.
- No clinical or regulatory meaning. The pipeline does not provide a clinical,
  regulatory, or safety-certification interpretation. It does not qualify a
  strain as a probiotic, as safe for use, or as fit for any product. Such a
  decision requires wet-lab and in vivo validation and the appropriate
  regulatory process.

These limits are properties of genome screening in general. They hold whatever
the execution mode is, and whatever score a downstream system may compute from
these features.
