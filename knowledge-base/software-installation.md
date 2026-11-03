# Visual Studio Code installation and approved software requests

Scope: an employee needs Visual Studio Code installed on a company laptop. Common requests include 'I need Visual Studio Code', 'Install VS Code on my laptop', and 'Request the vscode editor'. Owner: Desktop Support. Approved demo article, reviewed 2 November 2026.

The demonstration catalogue approves Visual Studio Code, identified by vscode. Requests such as 'I need Visual Studio Code' or 'Install VS Code' can follow the approved provisioning flow. The only approved automatic provisioning action is provision_vscode. The target is the fictional device DEMO-LAPTOP-01 belonging to demo-avinash. No executable is downloaded or installed on the laptop running this application.

Create a ServiceNow service request first, record its reference, then record a provisioning attempt in the audit trail. The mock provisioning API adds vscode to installed_software on the demo device. Read the device record again to confirm membership before reporting completion. A second request should detect that the software is already present. Update the request in mock ServiceNow and local storage only after validation. A failed API or validation leaves a failed or pending-review request rather than a completed one.

Software outside the approved catalogue requires human review for licensing, security and business approval. Do not substitute a similar product or execute model-generated installation commands. Application access is a separate entitlement request and may require an application owner's approval. In real mode a ServiceNow catalogue item must be configured; mock provisioning is never described as a real endpoint installation.
