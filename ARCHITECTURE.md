# Workstation Manager Architecture

## Frontend

The application is organized around a typed domain layer (`src/types`), data access modules (`src/api`), and presentational screens in the console shell. Views request data from named API modules such as `devicesApi`, `sessionsApi`, `alertsApi`, `schedulesApi`, `usersApi`, and `auditApi`; they do not import mock collections directly. The mock implementations can later be replaced by HTTP clients for preliminary `/api/v1/*` FastAPI routes without changing the screens.

## Backend boundary

The intended production boundary is a FastAPI service over HTTPS. Preliminary resource areas are auth, devices, groups, users, roles, schedules, sessions, operations, alerts, and audit. These are frontend integration seams, not a final API or database specification.

## Realtime

The UI treats live state as API-owned data and exposes refresh/live-status affordances. A future realtime adapter can map backend events such as `device.updated`, `session.updated`, `operation.progress`, and `alert.updated` into the same domain models. No Windows Agent protocol is assumed.

## Operations and audit

Power commands, session cleanup, and bulk commands should be represented by backend-owned operation records. The UI already models confirmation dialogs, progress/result surfaces, retry affordances, and audit entries as separate concerns.

## RBAC

The navigation and permission screens model Super Admin, Administrator, Operator, and Viewer roles, with scopes for all devices, selected groups, and selected devices. The backend must enforce authorization; frontend permission checks are for visibility and user experience only.

## Future services

PostgreSQL will persist users, devices, groups, schedules, operations, alerts, and audit records. Redis will support queues, scheduler jobs, and realtime fan-out. A separate Windows Service Agent will later report system information, heartbeats, metrics, RDP sessions, and execute approved commands. Its protocol and final database schema are intentionally deferred.
