# Expired password and safe reset

Scope: an employee reports an expired or forgotten password. Owner: Identity Support. Approved demo article, reviewed 2 November 2026.

An expired password can prevent VPN, email and application sign-in. In a real organisation the employee would use the official identity portal and complete identity verification. Never ask the employee to paste an old password, a new password, a one-time code or a recovery token into chat. Escalate if identity verification is unavailable or repeated recovery attempts fail.

The approved prototype action is password_reset. It applies only to the fixed fictional user demo-avinash. The workflow must first read the demo account and diagnose whether password_expired is true. It then records an automation attempt in the audit collection, changes password_expired to false, increments reset_count, and reads the account again to validate the change. No actual password is created, returned, emailed or changed. A previously healthy account should return already healthy without incrementing the counter.

The incident may be marked resolved only when the post-action account read validates password_expired=false and the mock ServiceNow update succeeds. A validation or integration failure leaves the incident requiring human attention, with the failed step in its audit trail. A reset does not automatically unlock a locked account; account unlock is a separate approved workflow.
