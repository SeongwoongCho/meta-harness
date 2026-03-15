# Data Engineering Scenario: Spark ETL Pipeline for Order Aggregation

Build a Spark ETL pipeline that reads raw order events from S3, aggregates daily revenue by product category, and writes the results to a Parquet data warehouse partition.

## Requirements

- Read raw events from `s3://data-lake/orders/raw/date={YYYY-MM-DD}/` (JSON, ~50M rows/day)
- Deduplicate events by `event_id` (late arrivals may cause duplicates)
- Aggregate: sum `order_total` grouped by `product_category` and `order_date`
- Write output to `s3://data-warehouse/orders/daily_revenue/date={YYYY-MM-DD}/` as Parquet
- Idempotent: re-running for the same date must overwrite, not append

## Acceptance Criteria

- [ ] Unit tests cover deduplication logic with sample DataFrames
- [ ] Integration test validates output schema matches expected Parquet structure
- [ ] Pipeline handles empty input partitions without failing
