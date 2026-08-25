# Deployment and infrastructure

The server, the services on it, how a change reaches production, and the
hazards found the hard way.

---

## The machine

`marvin`. 62 GB RAM, ~2.7 TB disk. Runs the public site, the search indexes, and
two model services. Only two of eight memory channels are populated, so memory
bandwidth is well below the board's capability; that matters for model
throughput more than capacity does.

## What runs

| Service | What | Notes |
|---|---|---|
| Apache + mod_wsgi | the site | `WSGIScriptAlias /api` only; 3 processes x 5 threads, recycling every 1000 requests |
| `tesserae-assistant` | Tessa's model (Qwen3-30B-A3B, llama.cpp) | port 8081, ~20 GB |
| `tesserae-embed` | passage-index query encoder (multilingual-e5-large) | port 8090, MemoryMax 6G, ~0.8 GB |

Both model services are systemd **user** units with lingering enabled, so they
survive a reboot. `systemctl --user status tesserae-embed`.

### Why the encoder is a separate service

Apache runs three worker processes that recycle every 1000 requests. A model
loaded inside the web app would be held three times over, and thrown away and
reloaded at about 22 seconds a time, forever. It would also put PyTorch
permanently inside the web server, where an upgrade could break the whole site
rather than one feature.

As a service: one copy, a hard memory bound, and it can be stopped without
touching the site. **The web application has no machine-learning dependency at
all** — it makes an HTTP call. If the encoder is down, Theme Search reports
itself unavailable and nothing else is affected.

Only Theme Search needs it. Similar Passages and the Reader gutter compare
vectors computed at index time.

---

## Deploying

Frontend and backend are one repo; `dist/` is committed.

```
# on the dev worktree
npm run build            # FROM THE REPO ROOT, not client/
git push origin <branch>:main

# on the production host
cd /var/www/tesseraev6_flask
scripts/keep_old_bundles.sh save      # see the hazard below
git pull --ff-only
scripts/keep_old_bundles.sh restore
touch tesseraev6_flask.wsgi           # NOT tesseraev6.wsgi
```

Data files (`data/passage_index/`, indexes, caches) are **not** in git and move
by rsync. Stage under an `.incoming` name and switch by rename, so the site keeps
serving during the copy and the switch is atomic.

**Verify the invariant after moving an index:** ids, embedding rows and
description records must agree in count. A slice whose ids and rows disagree does
not fail loudly, it returns the wrong passage for every query.

---

## Hazards, each found by a user rather than a test

### Stale pages fail silently, and this is not fully fixed

`index.html` is served with **no `Cache-Control`**, only an ETag, so browsers
cache it heuristically for hours. Every frontend deploy renames the bundle. A
cached page then requests a file that no longer exists, and Apache's
single-page-app fallback returns **200 OK with `Content-Type: text/html`** — the
page, pretending to be JavaScript. The browser fails to parse it and *nothing*
runs: no app, no error handler, no message. It looks like the site is broken
rather than out of date.

Mitigated without root by `scripts/keep_old_bundles.sh`, which keeps the last
eight bundles as untracked files so a stale page loads its old JavaScript and
works one version behind, plus an update banner offering a reload.

**The real fix needs root**, three lines in the vhost:

```apache
<Directory /var/www/tess-new>
  <FilesMatch "\.html$">
    Header set Cache-Control "no-cache, must-revalidate"
  </FilesMatch>
  <FilesMatch "\.(js|css|woff2?)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
</Directory>
```

Asset names carry a content hash, so a year is safe; only the 1 KB page needs
revalidating. An `.htaccess` does **not** work: the Directory block sets no
`AllowOverride`.

### Flask only serves `/api`

`WSGIScriptAlias /api` — the page and `/assets/` are served by Apache from
DocumentRoot. A Flask `after_request` hook cannot set headers on them. Worth
knowing before writing a fix that silently does nothing.

### A local checkout may be a stale branch

The main dev checkout has sat on `feature/hebrew-ship` with a local `main` that
is not `origin/main`. Confirm what a branch actually contains before concluding
a feature shipped.

### Heavy jobs degrade the live site

A benchmark at full tilt made the box slow enough that a phone timed out waiting
for Tessa. Run long jobs through `evaluation/scripts/run_bounded.sh`, which
applies `MemoryMax`, `RuntimeMax` and `CPUQuota`, and `nice` them.

### Ports are taken

8080 is a node process, 8081 is Tessa's llama-server. Check with `ss -ltnp`
before assigning one.

---

## Rollback

- **A feature that reads a data directory**: move the directory aside and reload.
  Availability is a file check, so the feature reports itself unavailable and the
  rest of the site is untouched.
- **A model service**: `systemctl --user stop tesserae-embed`.
- **Code**: `git reset --hard <sha>` in the production checkout, then touch the
  wsgi file. Pre-deploy backups go in `/home/ncoffee/tesserae-backups/` with a
  `ROLLBACK.md`.

---

## Logs

The Apache error log is not readable by the deploying user, so an unhandled
exception is invisible from the shell. **Routes should return their error in the
response body** rather than raising: an error the operator cannot read is an
error they cannot fix. The passages blueprint does this; it is why the missing
`sentence_transformers` was diagnosable in one request.
