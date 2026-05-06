# GitHub Config Snapshot — fake-news-generator

Captured 2026-05-06 before repo deletion. Re-apply these settings after recreating the repo.

---

## 1. Repo Settings

| Setting | Value |
|---|---|
| Name | `fake-news-generator` |
| Description | `satiricalize scraped news` |
| Visibility | Public |
| Default branch | `main` |
| Delete branch on merge | ✅ enabled |
| Merge commits | ❌ disabled |
| Squash merging | ✅ enabled (only strategy) |
| Rebase merging | ❌ disabled |
| Issues | ✅ enabled |
| Projects | ✅ enabled |
| Wiki | ❌ disabled |
| Discussions | ❌ disabled |

**gh CLI to re-apply:**

```bash
gh repo edit \
  --description "satiricalize scraped news" \
  --enable-issues \
  --enable-projects \
  --delete-branch-on-merge \
  --allow-squash-merge \
  --no-allow-merge-commit \
  --no-allow-rebase-merge \
  --no-enable-wiki
```

---

## 2. Branch Ruleset — `main-protection`

Targets the default branch (`~DEFAULT_BRANCH`). Enforcement: **active**.

| Rule | Value |
|---|---|
| Block branch deletion | ✅ |
| Block force push | ✅ |
| Require PR before merge | ✅ |
| Required approving reviews | 1 |
| Dismiss stale reviews on push | ✅ |
| Require code owner review | ❌ |
| Require last-push approval | ❌ |
| Require all review threads resolved | ✅ |
| Allowed merge methods | squash only |
| Bypass | Repo admins (always) |

**gh CLI to re-apply:**

```bash
gh api repos/{owner}/fake-news-generator/rulesets \
  --method POST \
  --field name="main-protection" \
  --field target="branch" \
  --field enforcement="active" \
  --field 'conditions={"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}}' \
  --field 'rules=[
    {"type":"deletion"},
    {"type":"non_fast_forward"},
    {"type":"pull_request","parameters":{
      "required_approving_review_count":1,
      "dismiss_stale_reviews_on_push":true,
      "required_reviewers":[],
      "require_code_owner_review":false,
      "require_last_push_approval":false,
      "required_review_thread_resolution":true,
      "allowed_merge_methods":["squash"]
    }}
  ]' \
  --field 'bypass_actors=[{"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"always"}]'
```

---

## 3. Labels

Only the two non-default labels need to be re-created (GitHub adds the defaults automatically).

| Label | Color | Description |
|---|---|---|
| `dependencies` | `#0366d6` | Pull requests that update a dependency file |
| `javascript` | `#168700` | Pull requests that update javascript code |

**gh CLI to re-apply:**

```bash
gh label create dependencies --color "0366d6" --description "Pull requests that update a dependency file"
gh label create javascript   --color "168700" --description "Pull requests that update javascript code"
```

---

## 4. Nothing else to restore

- No GitHub Actions workflows (no `.github/` directory)
- No secrets or environment variables
- No webhooks
- No GitHub Apps / integrations
