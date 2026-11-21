# KMyBanners Pages

A list of the Ingress agents' banner pages made with [KMyBanners](https://github.com/elkuku/KMyBanners),
updated every day: **https://elkuku.github.io/KMyBanners-directory/** (also as `pages.json`).

## How pages are found

Once a day (and on every push to `main`) the [Directory workflow](.github/workflows/directory.yml) runs
[`directory.py`](directory.py), which:

1. searches GitHub for repositories with the topic `kmybanners` (the app adds it to every page repo); run
   locally with a token, it also searches for workflows that call `KMyBanners-tool/.github/workflows/build-page.yml`
   (GitHub's code search refuses the token of GitHub Actions);
2. keeps the public ones that GitHub says were made from
   [KMyBanners-template](https://github.com/elkuku/KMyBanners-template), or whose `banner-page.yml` calls the tool;
3. leaves out pages whose agent turned the directory off in the app (`"directory": false` in the page repo's
   `config.json`);
4. reads each agent's page for its title, description, preview image and agent name;
5. writes `index.html` and `pages.json` and publishes them with GitHub Pages.

Private repositories can't be found, and neither can page repos whose topic `kmybanners` was removed (the daily
run only searches by topic).

## Run it locally

```bash
GH_TOKEN=$(gh auth token) python3 directory.py site/
```

Only the Python standard library is needed. Without a token the code search is skipped.

GitHub pauses scheduled workflows in a repository without activity for 60 days; a push or a manual run
(Actions → Directory → Run workflow) starts them again.
