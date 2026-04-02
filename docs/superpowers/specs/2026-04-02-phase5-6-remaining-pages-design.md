# Phase 5 + 6: Remaining Pages Migration & Cleanup - Design Spec

Date: 2026-04-02

## Goal

Complete the frontend migration by converting the six remaining Django-template pages to Vue 3
(sign-in, sign-up, password-change, about-site, about-data, what's-new, user-profile), then
remove all old-frontend infrastructure (Webpack, Bootstrap, `assets/ts/`, Selenium tests).

Password-reset pages (request, sent confirmation, token confirm, complete) stay as Django
templates - they are rarely visited, token-bound, and already battle-tested.

## Architecture

Same pattern as Phases 2-4: Django URL patterns remain and serve `spa_shell(request)`, Vue
Router handles the UI, Ninja endpoints serve data. After sign-in or sign-up, a full page
reload (`window.location.href = '/'`) refreshes the server-rendered `nav_config_json` -
no Pinia auth store needed.

## Backend

### New Ninja endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/v2/auth/signin/` | No | Authenticate + create session |
| `POST` | `/api/v2/auth/signup/` | No | Create account + log in |
| `POST` | `/api/v2/auth/password-change/` | Yes | Change password |
| `POST` | `/api/v2/news/mark-visited/` | Yes (optional) | Mark news as seen |
| `GET` | `/api/v2/profile/` | Yes | Return editable profile fields |
| `PUT` | `/api/v2/profile/` | Yes | Save profile changes |
| `DELETE` | `/api/v2/account/` | Yes | Delete account + log out |

The existing `GET /api/v2/page-fragments/{identifier}/` and `GET /api/v2/data-imports/`
endpoints are reused unchanged.

### Endpoint details

**POST /api/v2/auth/signin/**
- Body: `{ username: str, password: str }`
- Calls `authenticate(request, username=username, password=password)` then `login()`
- Returns `200` with `{ username: str }` on success
- Returns `401` with `{ detail: str }` on failure
- No authentication required

**POST /api/v2/auth/signup/**
- Body: fields from `SignUpForm` (wraps existing validation logic)
- Creates user, calls `login()`, returns `201` with `{ username: str }`
- Returns `422` with `{ errors: dict[str, list[str]] }` on validation failure
- No authentication required

**POST /api/v2/auth/password-change/**
- Body: `{ old_password: str, new_password1: str, new_password2: str }`
- Validates old password, checks new passwords match, calls `set_password()` + `update_session_auth_hash()`
- Returns `204` on success
- Returns `422` with field-level errors on failure
- Requires authentication

**POST /api/v2/news/mark-visited/**
- Calls `request.user.mark_news_as_visited_now()` if authenticated
- Returns `204` always (no-op for anonymous users)
- No authentication required (anonymous users ignored silently)

**GET /api/v2/profile/**
- Returns `ProfileOut`: `{ username, firstName, lastName, email, language, delayValue, delayUnit }`
- Requires authentication

**PUT /api/v2/profile/**
- Accepts `ProfileIn`: `{ firstName, lastName, email, language, delayValue, delayUnit }`
- Validates (e.g. unique email) and saves; returns updated `ProfileOut`
- Returns `422` with field errors on failure
- Requires authentication

**DELETE /api/v2/account/**
- Calls `request.user.delete()` then `logout(request)`
- Returns `204`
- Requires authentication

### New schemas

```python
class SignInIn(Schema):
    username: str
    password: str

class SignInOut(Schema):
    username: str

class SignUpIn(Schema):
    # mirrors SignUpForm fields
    username: str
    email: str
    password1: str
    password2: str

class PasswordChangeIn(Schema):
    old_password: str
    new_password1: str
    new_password2: str

class AuthErrorOut(Schema):
    detail: str

class AuthValidationErrorOut(Schema):
    errors: dict[str, list[str]]

class ProfileOut(Schema):
    username: str
    firstName: str
    lastName: str
    email: str
    language: str
    delayValue: int
    delayUnit: str

class ProfileIn(Schema):
    firstName: str
    lastName: str
    email: str
    language: str
    delayValue: int
    delayUnit: str
```

## Frontend

### New routes

Added to `assets/new-frontend/router/index.ts`:

```
/accounts/signin/        -> SignInPage.vue
/signup                  -> SignUpPage.vue
/accounts/password-change/ -> PasswordChangePage.vue
/about-site              -> AboutSitePage.vue
/about-data              -> AboutDataPage.vue
/whats-new               -> NewsPage.vue
/profile                 -> UserProfilePage.vue
```

### New pages

**`SignInPage.vue`**
- Username + password inputs
- Submit calls `POST /api/v2/auth/signin/`
- On success: `window.location.href = '/'` (full reload to refresh nav_config_json)
- On 401: inline error message below form
- Link to sign-up page and password-reset page

**`SignUpPage.vue`**
- Fields from `SignUpForm`: username, email, password1, password2
- Submit calls `POST /api/v2/auth/signup/`
- On success: `window.location.href = '/'`
- On 422: field-level errors below each input
- Link to sign-in page

**`PasswordChangePage.vue`**
- Fields: old password, new password, confirm new password
- Requires authentication (redirect to sign-in if not logged in)
- Submit calls `POST /api/v2/auth/password-change/`
- On 204: success toast, navigate to `/profile`
- On 422: field-level errors

**`AboutSitePage.vue`**
- On mount: fetch `GET /api/v2/page-fragments/about_this_site_page_content/`
- Renders `html` field with `v-html`
- ProgressSpinner while loading

**`AboutDataPage.vue`**
- On mount: fetch `GET /api/v2/data-imports/` (already exists)
- Renders list of data imports (name, date) using PrimeVue DataTable or simple list
- No page fragment needed: the about-data page is entirely dynamic data

**`NewsPage.vue`**
- On mount: fetch `GET /api/v2/page-fragments/news_page_content/` and render with `v-html`
- On mount: call `POST /api/v2/news/mark-visited/` (fire and forget - no loading state)
- ProgressSpinner while fragment loads

**`UserProfilePage.vue`**
- Requires authentication
- On mount: fetch `GET /api/v2/profile/`
- Form fields: first name, last name, email, language (dropdown), delay value + delay unit
- Save button calls `PUT /api/v2/profile/`, shows success toast or field errors
- Delete account button triggers PrimeVue ConfirmDialog
- On confirm: calls `DELETE /api/v2/account/`, then `window.location.href = '/accounts/signin/'`

### Django view changes

The catch-all URL pattern in `djangoproject/urls.py` excludes `accounts/` paths
(`^(?!admin|api/|accounts/|...).*$`). This means `/accounts/signin/` and
`/accounts/password-change/` are NOT served by the catch-all - their Django views must be
explicitly replaced with `spa_shell` wrappers.

**In `dashboard/views/pages.py`** - convert to `spa_shell(request)` and remove dead logic:
- `about_site_page`
- `about_data_page` (remove `DataImport.objects.all()` query)
- `news_page` (remove `mark_news_as_visited_now()` call - now done via API)
- `user_profile_page` (remove form handling)
- `user_signup_page` (remove form handling)

**In `djangoproject/urls.py`** - replace built-in auth views with `spa_shell` wrappers:
- Replace `LoginView` at `accounts/signin/` with `spa_shell`
- Replace `PasswordChangeView` at `accounts/password-change/` with `spa_shell`
- Also remove `PasswordChangeDoneView` at `accounts/password-change-done/` since
  success is now handled client-side via toast (no redirect to a "done" page)

**Password-reset URLs keep their Django built-in views unchanged:**
- `accounts/password-reset/` - `PasswordResetView` (stays)
- `accounts/password-reset-done/` - `PasswordResetDoneView` (stays)
- `accounts/password-reset/confirm/<uidb64>/<token>/` - `PasswordResetConfirmView` (stays)
- `accounts/password-reset/complete/` - `PasswordResetCompleteView` (stays)

Their templates are updated to remove Bootstrap classes (see Phase 6).

### i18n

New translation keys needed in all three language blocks (`en`, `fr`, `nl`) in
`assets/ts/translations.ts`:

```
username, password, signIn, signUp, forgotPassword, changePassword, oldPassword,
newPassword, confirmNewPassword, saveProfile, deleteAccount, confirmDeleteAccount,
confirmDeleteAccountHeader, accountDeleted, passwordChanged, profileSaved,
firstName, lastName, email, language, notificationDelay, aboutSite, aboutData,
whatsNew, dataImportsTitle, noDataImports
```

## Testing

### Django unit tests (`dashboard/tests/views/test_api_v2.py`)

New test class `ApiV2AuthTests` covering:
- Sign-in success (200 + username returned)
- Sign-in wrong password (401)
- Sign-in nonexistent user (401)
- Sign-up success (201, user created in DB)
- Sign-up duplicate username (422 with field error)
- Sign-up password mismatch (422)
- Password change success (204)
- Password change wrong old password (422)
- Password change unauthenticated (401)
- Profile GET (200 with correct fields)
- Profile PUT success (200 with updated values)
- Profile PUT unauthenticated (401)
- Delete account success (204, user gone from DB)
- News mark-visited (204 for authenticated, 204 silently for anonymous)

### Playwright tests (`dashboard/tests/playwright/test_auth.py`)

| Test | Scenario |
|------|---------|
| `test_signin_succeeds` | Valid credentials -> navbar shows username |
| `test_signin_wrong_password` | Bad credentials -> inline error, stays on page |
| `test_signup_succeeds` | Valid form -> lands on index as new user |
| `test_signup_validation_errors` | Duplicate username -> field error shown |
| `test_password_change_succeeds` | Valid change -> success toast |
| `test_password_change_wrong_old_password` | Wrong old password -> error shown |
| `test_about_site_page_renders` | Page fragment content visible |
| `test_about_data_page_renders` | Data import list visible |
| `test_news_page_renders` | News fragment content visible |
| `test_profile_page_loads` | User values shown in form |
| `test_profile_save_succeeds` | Change first name -> success toast |
| `test_delete_account_confirmed` | Confirm -> account gone, redirected |
| `test_delete_account_cancelled` | Cancel -> account still exists |

## Phase 6: Cleanup

Executed after Phase 5 is complete and all tests pass.

### Steps

1. **Remove Webpack config**: delete `webpack.common.js`, `webpack.dev.js`, `webpack.prod.js`
2. **Remove `assets/ts/`**: delete entire directory (only dead code remains after Phase 5)
3. **Remove Bootstrap**: remove `bootstrap` and `bootstrap-icons` from `package.json`;
   remove any remaining Bootstrap CSS class usage from password-reset templates
4. **Update `base.html`**: remove `<script src="{% static 'js/early_alert-bundle.js' %}">` tag
5. **Remove Selenium tests**: delete `dashboard/tests/selenium/`
6. **Update deployment/CI**: replace `npm run webpack-prod` with `npm run vite-build` in
   any scripts or CI config files
7. **Clean `package.json`**: remove webpack-related devDependencies
   (`webpack`, `webpack-cli`, `webpack-merge`, `ts-loader`, `vue-loader`, etc.)
8. **Final review**: run full test suite, mypy, check for any remaining Bootstrap class
   references in templates that would be unstyled

### Password-reset template updates

The four password-reset templates (`password_reset.html`, `password_reset_done.html`,
`password_reset_confirm.html`, `password_reset_complete.html`) extend `base.html` and use
Bootstrap classes. When Bootstrap is removed, replace Bootstrap form/button classes with
plain HTML or PrimeVue-compatible classes so the pages remain usable.

## Key Decisions

- **Full reload after auth**: `window.location.href = '/'` after sign-in/sign-up avoids
  needing a Pinia auth store; nav state stays server-rendered.
- **Password-reset stays Django**: token-bound, rarely visited, already correct.
- **`POST /api/v2/news/mark-visited/` is fire-and-forget**: NewsPage doesn't wait for it;
  a failure doesn't affect the user experience.
- **About-data is pure data, no fragment**: `GET /api/v2/data-imports/` already exists.
- **Phase 6 cleanup is gated on Phase 5**: Webpack/Bootstrap removal only happens once all
  pages are migrated and tests pass.
