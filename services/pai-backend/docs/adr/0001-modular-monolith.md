# ADR-0001: Modular Monolith cho MVP

## Status

Accepted.

## Context

Domain và quy trình còn thay đổi, dữ liệu chưa có, đội ngũ/chỉ tiêu tải chưa chốt.

## Decision

Dùng modular monolith cho FastAPI, worker tách process và Model Gateway có boundary rõ.

## Consequences

- Dễ phát triển và refactor.
- Giảm overhead vận hành.
- Có thể tách service sau khi boundary và tải đã ổn định.
