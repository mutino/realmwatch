# Portal format and map privacy

The reader selects the highest complete `_main.N.ok` generation with companion
`.db2`, `.fwl2` and `.chunks` files. It parses only that committed index and its
referenced portal chunk (index 1, size 0). It never writes world files, forces
a game save, reads archived backups, or installs a game mod.

The parser supports versions 40–42. It bounds files to 16 MiB and rejects
unknown versions, malformed lengths, short records, nonfinite coordinates,
trailing bytes and mismatched index/chunk counts. A save rotation can trigger
one retry. Read failures retain the previous successful in-process scan for
that exact world and mark it stale; a first read after process restart may be
unavailable. The cache is isolated by container and world path.

Links require a unique pair of saved Portal (1) / Portal|Target (17) connection
records sharing a nonzero hash. Duplicate/missing records remain unresolved.
Tag matches are metadata, never inferred links. Exact case and blank tags
are retained. Modded routing and runtime teleport restrictions are not modelled.

The map displays portal coordinates, a generic 10.5 km world-edge circle,
distance rings and illustrative biome guides. Northern ice/southern volcanic
caps are generic illustrations, not measured biome boundaries. Nothing reads
world seeds, generates terrain, or reconstructs coastlines or exploration masks.
It is not a chart of discovered land. Existing portal locations are visible
to authorised dashboard viewers, including portals built by other players.

Binary-format research used these source-available format references; no
third-party parser implementation or runtime is bundled:
https://github.com/RyanDMcAfee/ValheimBakaLoader/tree/e59ee5e105593845a064b01e489b8ac77f671844/ValheimBakaLoader/Tools/Atlas

Biome-guide reference:
https://thunderstore.io/c/valheim/p/Tchernobill/Valheim_Map_Rings/v/1.0.0/
World-edge reference: https://valheim.weirdgloop.org/w/Biomes

Valheim is a trademark of its respective owners. No game assets or saved worlds
are distributed in this repository.
