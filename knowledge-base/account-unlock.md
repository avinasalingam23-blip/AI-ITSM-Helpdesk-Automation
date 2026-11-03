# Locked account recovery

Scope: an employee reports that their account is locked or they are locked out. Owner: Identity Support. Approved demo article, reviewed 2 November 2026.

Repeated incorrect sign-in attempts can lock an account. Stop repeated attempts, close clients that might be retrying stale credentials, and use the official recovery channel. Never bypass multi-factor authentication. Production unlock would require verified identity and access controls; this application demonstrates only a fictional account.

The approved prototype action is account_unlock, limited to demo-avinash. Read the stored account first. If locked is true, record the attempted action before changing state, set locked to false, then retrieve the account to validate locked=false. If the account is already unlocked, record an already-healthy result and avoid unnecessary mutation. The workflow must not clear password_expired; a password reset is a separate operation.

After validation, update the associated mock ServiceNow incident and local ticket. Report resolution only after that update succeeds. On missing identity, failed persistence, failed validation or integration outage, retain a failed or escalated state and a safe audit record. There is no API to select another target account or execute arbitrary operating-system commands. The demonstration reset procedure restores this fictional account to locked=true without affecting any real account.
