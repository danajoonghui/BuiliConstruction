# Security policy

## Reporting

Do not open a public issue containing customer drawings, field photos, access
tokens, API keys, personal data, or project identifiers. Report suspected
security issues privately to the repository owner.

## Credential handling

- Secrets are provided only through environment variables or a managed secret
  store.
- Credentials and signed object URLs must never be logged.
- Any credential posted in chat or committed to source control is considered
  compromised and must be revoked and replaced.
- Use separate provider projects/keys for development, staging, and production.

## Customer data

- Original files remain private and immutable.
- All access is tenant/project authorized and audit logged.
- Public share links are scoped, revocable, and expiring.
- AI-generated content is a candidate until an authorized reviewer approves it.
