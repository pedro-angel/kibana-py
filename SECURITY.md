# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅ Current          |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please open a [private security advisory](https://github.com/pedro-angel/kibana-py/security/advisories/new) on GitHub, or contact the maintainer [@pedro-angel](https://github.com/pedro-angel) directly via GitHub.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within **48 hours** and provide a detailed response within **5 business days**, including next steps and an estimated timeline for a fix.

## Security Best Practices for Users

- **Never hardcode credentials.** Use environment variables or a secrets manager.
- **Use API keys** instead of basic auth when possible.
- **Enable TLS/SSL** for all connections to Kibana.
- **Keep dependencies updated**, especially `elastic-transport`.
- **Review DEBUG-level logs** before enabling them in production — they may contain request metadata.
