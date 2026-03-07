# RAG Platform Design

This document describes the design of a retrieval augmented generation platform built with a C plus plus gateway and a Python AI service. The gateway is responsible for external REST APIs, request validation, task orchestration, and unified response formatting. The Python service is responsible for document ingestion, text chunking, embedding generation, vector retrieval, and answer generation.

## Upload Flow

When a user uploads a document, the gateway stores the file in a shared upload directory and writes document metadata into the docs table. At the same time, the gateway creates a task record in the tasks table. The task starts in a queued state. The gateway then calls the internal ingestion endpoint exposed by the Python AI service. The Python service updates the task state to running and changes the document status from uploaded to processing.

## Chunking Strategy

The first implementation uses fixed size chunking with overlap. This approach is chosen because it is simple, predictable, and easy to debug. The chunk size is set to seven hundred characters and the overlap is set to one hundred characters. This means each new chunk starts six hundred characters after the previous chunk starts. The purpose of overlap is to reduce the risk that important information is split across chunk boundaries and becomes hard to retrieve later.

## Embedding and Storage

After chunking, each chunk will be sent to an online embedding model. The returned vector is validated against the configured embedding dimension. If the dimension does not match the database schema, the ingestion request fails and the error is written into the task record. Once validated, the text and embedding are written into the chunks table in PostgreSQL with pgvector enabled. This allows later similarity search using cosine distance.

## Query Flow

When a user submits a question, the gateway validates the request and checks whether the requested documents are ready. It then forwards the request to the Python AI service. The Python service embeds the question, performs vector retrieval on the chunks table, selects the top K chunks, and assembles a prompt. The prompt tells the language model to answer only based on the provided context. If the retrieved evidence is insufficient, the model should clearly say that the answer cannot be confirmed from the available documents.

## Citations

Each answer should include citations that point back to the supporting chunks. At minimum, each citation contains the document identifier, the chunk index, and a snippet of the chunk text. If page numbers are available, they should also be included. This makes the system more trustworthy because users can inspect the evidence used by the model.

## Reliability

The system is designed in stages. In the first stage, the team focuses on getting the full ingestion and query path working end to end. In the second stage, caching, rate limiting, structured logging, and evaluation are added. This staged design helps reduce risk because correctness is established before optimization. Failures in parsing, chunking, embedding, or database writes must all be surfaced clearly through task states and error messages.

## Operational Notes

The gateway and the AI service communicate over an internal network in Docker Compose. The services share an upload directory so that files written by the gateway can be read by the AI service. PostgreSQL stores metadata and vectors, while Redis is reserved for later use in caching and rate limiting. This architecture keeps the responsibilities of each component clear and makes it easier to replace the internal protocol in the future, for example by moving from internal HTTP calls to gRPC.
