# Security Policy

## Supported versions

Security fixes are provided for the latest released `1.x` version. Pre-release
branches and older releases may receive a fix only when the issue also affects
the latest supported release.

| Version | Supported |
| --- | --- |
| Latest `1.x` | Yes |
| Older versions | No |

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability or include
credentials, internal addresses, logs, or exploit details in public comments.

Use GitHub's **Report a vulnerability** form in the repository Security tab to
send a private report. Include the affected Flask-Nacos version, Python and
Flask versions, the impact, reproduction steps, and any suggested mitigation.

If private vulnerability reporting is temporarily unavailable, contact the
maintainer through the email listed in the package metadata and request a
private channel before sharing sensitive details.

The maintainer will acknowledge a complete report as soon as practical,
validate the impact, prepare a coordinated fix, and credit the reporter unless
anonymity is requested.

## Credential safety

Flask-Nacos accepts Nacos usernames, passwords, access keys, and secret keys
through Flask configuration. Applications should inject them through a secret
manager or environment variables, restrict log access, and rotate any value
that may have been exposed.
