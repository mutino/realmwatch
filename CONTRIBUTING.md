# Contributing to Realmwatch

Thanks for helping improve Realmwatch. Its initial code, documentation and
placeholder artwork were AI-generated using OpenAI Codex under human direction.
Contributions should be your own work. Any AI-generated content must be
clearly identified in the pull request, including which files or parts were
generated. AI-assisted work is welcome too; describe how AI was used. Using
AI is not a requirement.

## Graphics and design

We would especially love original icons, illustrations, biome
artwork, map styling, typography and other UI improvements. Credit the artist
in your pull request and include any preferred attribution text.

- Prefer editable SVG sources for icons and simple map artwork. For raster
  artwork, include an appropriately sized export and the editable source when
  practical. Keep files small enough for a self-hosted dashboard.
- Keep portal markers, labels, links and the world edge easy to distinguish.
  Consider contrast, colour-vision differences and small screens.
- Preserve the map's privacy: biome guides and polar caps are illustrations.
  Do not add seed-derived coastlines, landmasses or details of unexplored areas.
- Submit original work you have the right to contribute under MIT. Do not
  include copyrighted game assets or third-party artwork without compatible
  permission and attribution. Discuss separately licensed assets in an issue
  before proposing their inclusion.

## Proposing changes

Open an issue for substantial ideas, or send a focused pull request describing
what changes and why. For visual changes, include a screenshot with synthetic
portal data rather than private world data. Clearly identify any AI-generated content, describe any AI assistance,
and acknowledge third-party sources.

Code, bug reports, accessibility fixes, tests, documentation and translations
are just as valuable as artwork. Explain how a code change was checked. Run:

```sh
python3 -m unittest -v
python3 -m compileall -q collector.py portals.py server.py
docker build -t realmwatch:test .
```

Never commit credentials, generated gateway configuration, player identifiers,
world saves or raw server logs. Use synthetic examples for bug reports.

Unless explicitly agreed otherwise before inclusion, contributions are
provided under the project's MIT licence. Contributors retain copyright in
their own work; attribution can be recorded in the relevant file or an artwork
credits file added with the contribution.
