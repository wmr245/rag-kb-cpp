# Aurora Failure Playbook

## Validation Failure

Return `422` when required fields are missing, types are wrong, or the payload format is invalid.
The caller should fix the request content before trying again. This is not a backoff retry case.

## Downstream Timeout

Return `504` when a dependency does not finish in time.
The request itself can still be valid, so this case usually fits backoff retry.

## Signature Failure

Return `401` when signature verification fails.
This means the request source is not trusted, so the next step is to inspect credentials or the signing process instead of changing business fields.
