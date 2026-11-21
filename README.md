# KMyBanners Pages

A list of the Ingress agents' banner pages made with [KMyBanners](https://github.com/elkuku/KMyBanners),
updated every day: **https://elkuku.github.io/KMyBanners-directory/** (also as `pages.json`).

## How pages are found

Once a day (and on every push to `main`) the [Directory workflow](.github/workflows/directory.yml) runs
[`directory.py`](directory.py), which:

1. searches GitHub for repositories with the topic `kmybanners` (the app adds it to every page repo) and for
   workflows that call `KMyBanners-tool/.github/workflows/build-page.yml`;
2. keeps the public ones that GitHub says were made from
   [KMyBanners-template](https://github.com/elkuku/KMyBanners-template), or whose `banner-page.yml` calls the tool;
3. reads each agent's page for its title, description, preview image and agent name;
4. writes `index.html` and `pages.json` and publishes them with GitHub Pages.

Private repositories can't be found. GitHub's code search may take a while to see a new repository; the topic
search usually finds it sooner.

## Run it locally

```bash
GH_TOKEN=$(gh auth token) python3 directory.py site/
```

Only the Python standard library is needed. Without a token the code search is skipped.

GitHub pauses scheduled workflows in a repository without activity for 60 days; a push or a manual run
(Actions → Directory → Run workflow) starts them again.
