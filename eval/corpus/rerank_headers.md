# Aurora Header Notes

## Cache Hit Header

`x-cache` only tells whether the response was served from cache.
It does not prove the data is the newest version, and it should not be used for version comparison.

## Data Version Field

Use `data-version` when you need to decide whether the response is the newest snapshot.
This field is the right signal for freshness and version comparison.

## Trace Header

`x-trace-id` is only for request tracing.
It says nothing about cache hit status or response freshness.
