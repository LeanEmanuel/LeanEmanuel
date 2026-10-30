# Profile statistics cards

This repository ships **two separate, responsive SVG cards** for the GitHub
profile:

| File | Content |
| --- | --- |
| `assets/stats/contributions.svg` | Contributions, commits, pull requests, issues, owned repositories and the activity heat map of the last 52 weeks. |
| `assets/stats/languages.svg` | Distribution of the languages by code volume across the owned repositories. |

Both cards follow the artboard `design/stats-variantes/01-sobria.html`: a dark
and sober palette, rounded panels, no pixel art effect, one card per topic so
that they stack on top of each other on a phone.

**Every visible text is written in English**: the titles, the metric labels,
the calendar legend and the dates.

The cards are **static files committed to this repository**. Nothing is
rendered by a third party service at read time, so the profile never depends
on an external deployment.

---

## 1. Mobile first layout

The cards are designed for a narrow viewport, not for a wide one:

* the `viewBox` is **480 units wide** and the root element carries
  `width="100%"` plus `preserveAspectRatio`, so the card scales to any
  container;
* the metrics of the contributions card are **stacked vertically** (label on
  the left, value on the right) instead of squeezed into a horizontal row;
* the contribution calendar is **split into blocks of 18 weeks**, each block
  drawn with its own date range, so no cell becomes an unreadable dot;
* the smallest font size is 16 units, which is **10.7 pixels** on a 320 pixel
  wide screen;
* long language names are truncated so they never collide with the bar.

In the README both cards are embedded with `width="100%"` and
`style="max-width:480px"`, so they fill a phone screen and stay readable on a
wide monitor, where they are now clearly bigger than the previous 360 pixel
version. If a renderer strips the inline style, the card still scales with
the container (`width="100%"`) and never overflows.

### What each card shows

| Card | Header | Body | Footer |
| --- | --- | --- | --- |
| Contributions | `Contributions` (no subtitle, no tag) | The five metrics, the `Daily activity` calendar and the `Less`/`More` legend | A single `Updated on <date>` line |
| Languages | `Languages` (no subtitle, no tag) | The language rows with their share | No footer |

---

## 2. Token requirements

The generator talks to the GitHub GraphQL API and needs a token that can read
**your own private repositories**. Public data alone is not enough: private
contributions and private repository languages are only visible to a token
that owns (or can read) them.

The token is read from the environment variable **`STATS_TOKEN`**.

### Recommended: fine-grained personal access token (`github_pat_…`)

Create it in *GitHub → Settings → Developer settings → Personal access
tokens → Fine-grained tokens* with exactly these permissions:

| Scope | Permission | Level | Why |
| --- | --- | --- | --- |
| Repository access | All repositories | – | The token must see every repository you own. |
| Repository permissions | **Contents** | **Read-only** | Reads the language breakdown of each repository. |
| Repository permissions | **Metadata** | **Read-only** | Required by GitHub for every repository (granted implicitly). |
| Account permissions | **Profile** | **Read-only** | Reads the profile and its contribution collection. |

Nothing else is needed: no write permissions, no `workflow` scope, no
organization access.

### Alternative: classic personal access token (`ghp_…`)

The classic token needs the **`repo`** scope, because it is the scope that
grants read access to private repositories. The **`read:user`** scope is
recommended but not mandatory.

`repo` is broader than needed (it also allows writing). Prefer the fine
grained token above.

### Rules the generator enforces

* The token must be present, non empty and shaped like a GitHub token
  (`ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` or `github_pat_`). Otherwise the run
  stops immediately.
* For classic tokens the `X-OAuth-Scopes` header is verified: a token without
  `repo` is rejected as *inadequate* instead of silently reporting zero
  private data.
* An expired or revoked token is reported as *inadequate* (`Bad credentials`).
* **The token is never logged.** It is only sent in the `Authorization`
  header, every error message is scrubbed of any token material, and it is
  never written to the repository.
* **No error message names a repository.** The errors of the generator reach
  the public log of the workflow, so they describe the failure without the
  name of the repository it happened on. The text of an upstream error is
  never relayed: the client reports the class of the failure (and the HTTP
  status of an answer) and nothing else, because an upstream message may
  name a repository in a way that no redaction could catch.

### Fail closed

The generator never publishes partial data. It exits with a non zero status
and writes **no file** when:

* the token is missing, malformed, expired or lacks the required scope;
* the API answers with an error, a malformed body or an HTTP failure;
* the pagination of repositories or languages is incomplete or loses its
  cursor;
* a **connection is missing or malformed**. A repository connection without
  `pageInfo` or without a node list, a repository without a `languages`
  connection, a language connection without `pageInfo` and a language edge
  list that is not a list are all rejected. They are never read as "this
  repository has no data".

---

## 3. Running it locally

```bash
# Live run: reads the token from the environment and rewrites assets/stats.
STATS_TOKEN=github_pat_xxx python scripts/generate_stats.py

# Placeholder run: no token and no network; writes the "pending" cards.
python scripts/generate_stats.py --pending

# Offline run: render from a snapshot file, no token and no network needed.
python scripts/generate_stats.py --snapshot snapshot.json --out-dir /tmp/cards

# Verify that the committed cards are up to date (exit code 1 when stale).
python scripts/generate_stats.py --check

# Test suite (standard library only, no network).
python -m unittest discover -s tests -t .
```

| Option | Meaning |
| --- | --- |
| `--login` | Login to render. Defaults to `STATS_LOGIN`, then to `LeanEmanuel`. |
| `--out-dir` | Destination directory. Defaults to `assets/stats`. |
| `--snapshot` | Render from a local snapshot JSON file instead of calling GitHub. |
| `--pending` | Write the placeholder cards that announce the missing data. No token, no network. Cards that already hold real data are never overwritten. |
| `--check` | Do not write; exit `1` when the rendered cards differ from the files on disk. |
| `--dry-run` | Render and print what would be written, without writing. |

Requirements: Python 3.9+ and the standard library only. No dependency has to
be installed.

---

## 4. The pending state

Every card carries a `data-state` attribute:

| `data-state` | Meaning |
| --- | --- |
| `pending` | Placeholder. The card states that it holds no data yet and shows **no number at all**. |
| `ready` | The card was produced by a successful live run. |

**The cards committed in `assets/stats` are in the `pending` state.** They do
not contain any statistic, because no live run with a valid token has been
performed from this repository yet. A placeholder never pretends to be data:
it shows the title, the pending notice and an empty frame. It carries no
footer at all: neither a number nor the path of the file it will be written
to.

The first successful run of the workflow replaces them with the real cards.
`--pending` refuses to overwrite a card whose state is `ready`, so real data
can never be replaced by a placeholder by accident.

---

## 5. The scheduled workflow

`.github/workflows/stats.yml` refreshes the cards every day at **04:23 UTC**,
on demand (`workflow_dispatch`) and whenever `scripts/**` changes.

* **Least privileges**: the job declares `permissions: contents: write` and
  nothing else; every other permission is `none`. `contents: write` is the
  minimum needed to push the generated SVG files.
* **Immutable pins**: every action is pinned to a commit SHA that was
  verified against the upstream tag (`actions/checkout` v4.4.0 and
  `actions/setup-python` v5.6.0). The version stays readable in the comment.
* **Two different tokens**: the *Generate the cards* step receives the
  repository secret `STATS_TOKEN` (`secrets.STATS_TOKEN`), a **read-only**
  token that is used only for the GraphQL queries. The workflow also uses
  the **built-in `GITHUB_TOKEN`** that GitHub creates automatically:
  `actions/checkout` authenticates the clone with it, and the `git push`
  that follows reuses the credentials that the checkout stored. The
  built-in token is never handed to the generator and never leaves the
  checkout step.
* The job runs the test suite before generating anything.
* Only `assets/stats` is staged and committed; the commit is skipped when
  nothing changed.

Store the token as the repository secret `STATS_TOKEN`
(*Settings → Secrets and variables → Actions → New repository secret*).

---

## 6. What exactly is counted

### Contributions card

* **Contributions**: `contributionsCollection.contributionCalendar.totalContributions`
  of the last 52 weeks, that is **public and private** activity.
* **Commits / Pull requests / Issues**: the contributions of the same window
  (`totalCommitContributions`, `totalPullRequestContributions`,
  `totalIssueContributions`), not only the open ones.
* **Repositorios**: the number of repositories the account owns.
* **Heat map**: one cell per day, coloured with five intensity levels
  relative to the busiest day of the window.

### Languages card

* Every repository **owned** by the account is requested with
  `ownerAffiliations: OWNER`.
* **Forks are included**: a fork the account created is a repository the
  account owns, so it counts like any other owned repository. No `isFork`
  filter is applied.
* The language breakdown of every repository is **fully paginated** and the
  sizes are summed per language.
* Percentages are shares of the total number of bytes reported by GitHub
  Linguist; the languages that do not fit in the first eight rows are grouped
  under *Other*.

---

## 7. Privacy

* Only **aggregated numbers** reach the cards: counters, percentages and a
  per day activity count.
* **No repository name, file name, commit message or branch ever appears** in
  a card or in the snapshot. The aggregation step drops the repository
  identity before anything is rendered.
* Private repositories contribute to the counters and to the language totals,
  exactly like the public ones, but they stay anonymous.
* **No repository name reaches the log.** The workflow log is public, so the
  error messages of the generator are free of repository names: the
  validation and pagination errors describe what failed without naming the
  repository, and the upstream error text is never relayed — only the class
  of the failure and the HTTP status are reported. The token is scrubbed at
  the same time.
* The snapshot format (`profile-stats-snapshot/1`) is the only artifact that
  can be stored or shared; it contains no repository identifiers.

---

## 8. Limitations

* **Window**: the calendar covers the last 52 weeks (364 days). Older
  activity is not shown.
* **Visibility depends on the token**: a token that cannot read a private
  repository reports that repository as empty, and its private contributions
  are not counted. The cards can therefore differ from what the owner sees
  in the GitHub UI.
* **Linguist semantics**: sizes are bytes of code as detected by GitHub
  Linguist, not lines of code. Vendored, generated or documentation files are
  excluded by Linguist, and the language set of a repository can change over
  time.
* **Language colours** are the ones published by Linguist; unknown languages
  fall back to a neutral grey.
* **Rate limits**: the GraphQL API bills each query by node count. Accounts
  with hundreds of repositories may hit the secondary rate limit; in that
  case the run fails closed and the previous cards stay in place.
* **Caching**: GitHub computes the contribution calendar lazily, so the
  numbers can lag behind the profile page by minutes or hours.
* **Pending cards**: as long as no live run succeeded, the committed cards
  are placeholders that show no statistics on purpose.
* The cards are plain SVG files served from this repository. GitHub renders
  them through `<img>`, so no script inside an SVG can ever run.
