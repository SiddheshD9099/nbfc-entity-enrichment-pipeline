# LeadLens — NBFC Entity Enrichment Benchmark

## 1. Overview

LeadLens is a Python-based entity enrichment pipeline that processes company
records, discovers company information using web search, extracts available
details, validates results, and stores records in SQLite.

## 2. Technology Stack

- Python
- Web search aggregation
- Company-domain matching
- Data validation
- SQLite persistence and caching
- Excel input/output
- Automated tests

## 3. Benchmark Configuration

| Parameter | Value |
|---|---|
| Input file | sample_nbfc_50_entities.xlsx |
| Number of entities | 50 |
| Output file | output_nbfc_50.xlsx |
| Database | leadlens_nbfc_50.db |
| Log file | nbfc_50_benchmark.log |
| Execution time | 725.61 seconds |
| Average processing time | 14.51 seconds per entity |

## 4. Results

| Metric | Result |
|---|---:|
| Entities processed | 50/50 |
| Websites populated | 15/50 (30%) |
| Addresses populated | 8/50 (16%) |
| Websites not populated | 35/50 (70%) |
| Addresses not populated | 42/50 (84%) |

These are field-population rates, not independently measured accuracy rates.

## 5. Data Quality Considerations

- Company-domain matching uses configured domain mappings and should be
  independently verified before treating every match as an official website.
- Parent-company websites and employee counts can be misleading when the
  target is a subsidiary or a specific financial-services entity.
- Missing information must remain explicitly missing rather than being
  replaced with fabricated values.
- Validation flags should be retained for records requiring manual review.
- The 50 input entities have not all been independently verified against
  an authoritative NBFC registry.

## 6. Limitations

The benchmark represents one execution, not a controlled performance study.
Search results, website availability, network conditions, and extraction
quality can affect runtime and field-population rates.

No independently labelled ground-truth dataset was used to establish
precision, recall, or overall enrichment accuracy.

## 7. Conclusion

The pipeline successfully processed 50 input entities and generated an
Excel output and SQLite records. The measured website population rate was
30%, and the address population rate was 16%.

The principal improvement priorities are better company-specific search
resolution, more reliable address extraction, stronger validation of
official domains, and reduced repeated searches for incomplete records.

The current results establish a baseline for future quality and performance
improvements; they do not establish production-grade enrichment accuracy.
