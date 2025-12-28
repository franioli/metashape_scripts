import Metashape

from metashape_tools.utils import ask_bool, require_active_chunk


def duplicate_chunk(
    doc: Metashape.Document, chunk: Metashape.Chunk, new_label: str | None = None
) -> Metashape.Chunk:
    c2 = chunk.copy()
    doc.chunks.add(c2)
    if new_label:
        c2.label = new_label
    return c2


def expand_region(chunk: Metashape.Chunk, factor: float = 1.25) -> None:
    r = chunk.region
    r.size = Metashape.Vector([r.size.x * factor, r.size.y * factor, r.size.z * factor])
    chunk.region = r


def clear_all_sensors(chunk: Metashape.Chunk) -> int:
    n = len(chunk.sensors)
    for s in list(chunk.sensors):
        chunk.remove(s)
    return n


def expand_region_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return
    if not ask_bool("Expand region by 25%?"):
        return
    expand_region(chunk, 1.25)
    Metashape.app.messageBox("Region expanded.")
