# Security policy

Please do not publish credentials, private document links, tenant identifiers, customer data, or unredacted screenshots in an issue.

For a vulnerability, use the repository's private security advisory channel once the public repository is created. Include the affected Skill, a minimal reproduction, impact, and whether exploitation changes external state. Until that channel exists, do not open a public vulnerability report containing exploit details.

SYBuilder scripts inspect repositories, browsers, local applications, and delivery documents. Review commands before granting filesystem, browser, keychain, or network access. A missing tool or denied permission is `UNABLE`; it must not be converted into a successful result.

