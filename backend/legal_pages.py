"""Public legal and support documents served outside the marketing SPA."""

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(include_in_schema=False)
SUPPORT_EMAIL = "platform-support@practenture.com"
EFFECTIVE_DATE = "August 2, 2026"


def _page(*, title: str, description: str, body: str) -> HTMLResponse:
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(description, quote=True)}">
  <title>{escape(title)} | Practenture</title>
  <style>
    :root {{ color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f7f8fa; color: #172033; line-height: 1.6; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 48px 24px 72px; }}
    article {{ background: #fff; border: 1px solid #dfe3ea; border-radius: 16px; padding: 32px; box-shadow: 0 8px 24px rgba(17, 24, 39, .06); }}
    h1 {{ margin-top: 0; line-height: 1.2; }}
    h2 {{ margin-top: 2rem; line-height: 1.3; }}
    a {{ color: #0759c7; }}
    .meta {{ color: #566176; }}
    nav {{ margin-bottom: 24px; display: flex; gap: 18px; flex-wrap: wrap; }}
    footer {{ margin-top: 32px; color: #566176; font-size: .95rem; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #111827; color: #e5e7eb; }}
      article {{ background: #182235; border-color: #344158; box-shadow: none; }}
      a {{ color: #8fc1ff; }}
      .meta, footer {{ color: #b8c2d4; }}
    }}
  </style>
</head>
<body>
  <main>
    <nav aria-label="Legal and support">
      <a href="/privacy">Privacy</a>
      <a href="/terms">Terms</a>
      <a href="/support">Support</a>
    </nav>
    <article>
      <h1>{escape(title)}</h1>
      <p class="meta">Effective {EFFECTIVE_DATE}</p>
      {body}
    </article>
    <footer>Practenture — business strategy, learned by doing.</footer>
  </main>
</body>
</html>"""
    return HTMLResponse(
        document,
        headers={
            "Cache-Control": "public, max-age=300",
            "X-Robots-Tag": "index, follow",
        },
    )


@router.get("/privacy", response_class=HTMLResponse)
def privacy_policy() -> HTMLResponse:
    return _page(
        title="Privacy Policy",
        description="How Practenture collects, uses, retains, and protects information.",
        body=f"""
      <h2>Information we collect</h2>
      <p>Practenture processes account and profile information; institutional, class, and enrollment information; simulation decisions and results; authentication-provider identifiers when you choose provider sign-in; and technical, security, and audit records needed to operate and protect the service.</p>
      <h2>How we use information</h2>
      <p>We use information to authenticate users, provide classroom simulations, show progress and results to authorized participants and instructors, maintain service security, prevent abuse, provide support, and improve reliability. Practenture does not sell personal information or use classroom activity for third-party advertising.</p>
      <h2>Sharing and educational access</h2>
      <p>Authorized instructors and institutions can access information associated with their classes and sessions. We use infrastructure and identity-service providers only as needed to operate the service, subject to their contractual and security obligations. We may disclose information when legally required or necessary to protect users and the service.</p>
      <h2>Retention and account deletion</h2>
      <p>Account information is retained while an account is active and as required for security, legal, and operational purposes. Users can request account deletion from Settings. Completed deletion removes authentication credentials and directly identifying profile data; simulation records that an institution must retain may be pseudonymized so results remain usable without identifying the deleted account.</p>
      <h2>Security</h2>
      <p>We use access controls, encryption in transit, protected credential storage, tenant isolation, and audit records. No method of storage or transmission is completely secure, so suspected security issues should be reported promptly.</p>
      <h2>Your choices</h2>
      <p>You may review account information in the service, choose among available sign-in methods, and use the account-deletion control in Settings. Students should also contact their instructor or institution for questions about institution-controlled educational records.</p>
      <h2>Children and students</h2>
      <p>Practenture is intended for educational use under the direction of an institution or instructor. Institutions are responsible for obtaining any authorization or consent required for their students and for configuring access appropriately.</p>
      <h2>Changes and contact</h2>
      <p>We may update this policy as the service changes. Material updates will be posted here with a revised effective date. Questions or privacy requests may be sent to <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>
        """,
    )


@router.get("/terms", response_class=HTMLResponse)
def terms_of_service() -> HTMLResponse:
    return _page(
        title="Terms of Service",
        description="Terms governing access to and use of Practenture.",
        body=f"""
      <h2>Using Practenture</h2>
      <p>Practenture provides educational business simulations. You may use the service only if you are authorized by your institution or otherwise permitted to create an account, and only in compliance with applicable law and institutional rules.</p>
      <h2>Accounts and access</h2>
      <p>You are responsible for safeguarding your credentials and for activity performed through your account. Do not share authentication codes, impersonate another person, attempt to obtain another class's information, or bypass access controls. Notify support if you believe an account has been compromised.</p>
      <h2>Acceptable use</h2>
      <p>You may not disrupt the service, probe or exploit vulnerabilities, automate abusive traffic, upload unlawful or harmful content, interfere with another participant's simulation, or use Practenture to violate another person's rights. We may restrict access needed to protect users, institutions, or the service.</p>
      <h2>Educational results</h2>
      <p>Simulation results are instructional and depend on modeled assumptions. They are not financial, investment, legal, or professional advice and should not be treated as predictions of real-world business outcomes.</p>
      <h2>Institution and instructor responsibilities</h2>
      <p>Institutions and instructors control class membership, simulation configuration, assignments, and their use of results. They are responsible for obtaining required student permissions and for using exported educational records appropriately.</p>
      <h2>Service availability</h2>
      <p>We work to keep Practenture reliable and secure, but the service may occasionally be unavailable for maintenance, security response, or circumstances outside our control. Features may evolve as long as changes do not override applicable contractual commitments.</p>
      <h2>Termination and deletion</h2>
      <p>You may stop using Practenture and may use the account-deletion control in Settings. Access may be suspended or terminated for material misuse, security risk, legal requirements, or loss of institutional authorization. Educational records may be retained or pseudonymized as described in the Privacy Policy.</p>
      <h2>Disclaimers and responsibility</h2>
      <p>To the extent permitted by law, Practenture is provided without warranties not expressly agreed in writing. Nothing in these terms excludes rights or responsibilities that cannot legally be excluded. Any institution-specific agreement controls if it conflicts with these public terms.</p>
      <h2>Changes and contact</h2>
      <p>We may update these terms and will post the effective date here. Questions may be sent to <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>. See also our <a href="/privacy">Privacy Policy</a>.</p>
        """,
    )


@router.get("/support", response_class=HTMLResponse)
def support_page() -> HTMLResponse:
    return _page(
        title="Support",
        description="Get help with Practenture accounts, classes, simulations, and privacy requests.",
        body=f"""
      <h2>Contact support</h2>
      <p>Email <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>. Do not include passwords, authentication codes, recovery codes, private keys, or payment information.</p>
      <h2>What to include</h2>
      <ul>
        <li>Your role: Student, Professor, or Administrator.</li>
        <li>The affected screen or workflow and the approximate time of the issue.</li>
        <li>A session code when relevant, but no account password or sign-in token.</li>
        <li>The app platform and version, plus a screenshot with private information removed.</li>
      </ul>
      <h2>Account and privacy help</h2>
      <p>Password, MFA, and provider-sign-in issues should be reported from the affected account when possible. Account deletion is available under Settings → Delete Account. If you cannot access the account, email support and describe the problem without sending credentials.</p>
      <h2>Classroom issues</h2>
      <p>Students should contact their Professor first for class codes, enrollment, session timing, grading, and simulation configuration. Professors and Administrators can contact platform support for service or account-administration issues.</p>
      <h2>Policies</h2>
      <p>Read the <a href="/privacy">Privacy Policy</a> and <a href="/terms">Terms of Service</a>.</p>
        """,
    )
