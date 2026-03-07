# Rate Limiting Design

This service uses token bucket rate limiting per user.
The bucket is refilled periodically.
Redis can be used to store counters in a distributed deployment.

# Caching

The service may cache retrieved chunks and final answers.
