Django E-commerce Audit, Fix & Improve

Act as a senior Django engineer. Inspect my existing repository, implement fixes directly in the codebase, run tests, resolve regressions, and continue until all feasible tasks are complete. Do not stop after analysis or provide only code snippets.

1. Inspect First
Identify Django/Python versions, dependencies, apps, models, URLs, views, templates, static files, migrations, tests, settings, and existing features.
Understand current conventions and behavior before editing.
Create a prioritized checklist and execute it incrementally.
Preserve existing routes, data, admin features, and working functionality.
2. Priority 1 — Critical Fixes
Fix guest checkout, missing product images, quantity limits, and cart mutations using POST with CSRF protection.
Correct login redirects, category 404 handling, and production settings.
Implement safe checkout with server-side price, ownership, discount, and stock validation.
Handle insufficient inventory, atomic rollback, row locking, concurrent checkout, and overselling prevention.
Restore inventory correctly when orders are cancelled.
Preserve existing admin stock management.
3. Priority 2 — Shopping Experience
Improve cart, checkout profile autofill, phone validation, product variants, and order items.
Add pagination, search, category filters, and related products.
Improve product cards, image loading, and performance.
Ensure forms validate inputs and handle errors correctly.
4. Priority 3 — Security & Core Features
Implement password reset and order tracking.
Enforce ownership and permissions for orders, wishlists, and reviews.
Validate payment webhook signatures and handle duplicate events idempotently.
Add reviews, wishlist, recently viewed products, and email/SMS notifications where feasible.
Add translations, unique page titles, SEO, theme switching, and grid/list views.
Improve business information and accessibility.
5. Priority 4 — Payments & Performance
Implement online payments only when the provider and credentials are available.
Optimize queries, caching, static assets, and database access without unnecessary dependencies or architectural rewrites.
Implementation Rules
Follow the project's existing Django version and coding conventions.
Inspect installed dependencies before adding packages.
Make small, maintainable changes and preserve backward compatibility.
Review and create migrations for necessary model changes; never delete production data or overwrite production configuration.
Enforce all sensitive validations server-side.
Use authentication, authorization, CSRF protection, database transactions, and appropriate locking.
Never trust client-supplied prices, stock, ownership, discounts, or payment status.
Do not silently suppress unexpected exceptions.
Use environment variables for secrets and document required configuration.
If credentials or business rules are missing, implement independent functionality and document blockers.
Do not claim a feature or test works without verifying it.
Testing & Verification

Use the existing test framework or establish a practical Django test suite. Cover:

Category 404s, pagination, search, filters, and templates.
Guest/authenticated checkout, profile autofill, phone validation, variants, and order items.
Quantity limits, insufficient stock, transaction rollback, concurrency, and cancellation/restocking.
Password reset, webhook signatures/idempotency, and authorization boundaries.
Translations, unique titles, admin stock management, and existing functionality.

Use PostgreSQL or another database with equivalent locking behavior for concurrency tests. SQLite results alone do not prove concurrency safety. Clearly document tests requiring external services or credentials.

Run these commands using the project's actual configuration:

python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test

Also verify:

Template rendering and URL resolution.
Static assets and image paths.
Migration consistency and application startup.
Relevant regression tests and production configuration.

Fix failures and rerun affected checks. Record actual results; never claim unexecuted tests passed. Distinguish environment/configuration failures from application defects.

Required Final Report

Provide:

Implemented fixes and features, grouped by priority.
Modified and created files.
Migrations created and whether they were applied.
Dependencies and environment variables added.
Tests and checks executed, with actual results and failures.
Commands for migrations, static collection, translation compilation, and startup.
Production deployment and security steps.
Missing credentials/business requirements.
Remaining bugs, blockers, and incomplete features.
Execution

Start by inspecting the repository and producing a concise checklist. Then implement and verify each priority in sequence. Continue through all feasible work without unnecessary pauses. Preserve the application and its data, and clearly report anything that cannot be safely completed.