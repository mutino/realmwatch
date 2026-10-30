# Security

Keep Realmwatch behind an authenticated HTTPS gateway. Restrict backend access
to that gateway and keep the upstream header secret server-side. The collector
requires Docker administration access; the dashboard container does not.

Never include world saves, player history, raw logs, credentials or generated
gateway configuration in public issues or pull requests. Use synthetic examples
when reporting parser problems. Keep backups outside the public source tree.
