"""Embed referenced raster images as ``data:`` URIs inside the SVG.

Replaces an ``<image xlink:href="logo.png">`` reference with the
fully inlined base64 form (``xlink:href="data:image/png;base64,…"``).
Only ``png`` / ``jpg`` / ``gif`` references are touched — other
extensions are left alone since their MIME mapping isn't
unambiguous.

The pass is opt-in (``--embed-rasters`` / ``OptimizeOptions.embed_rasters``)
and is the only place ``svg_polish`` reads from the filesystem or
network. The ``urllib`` and ``base64`` imports are deferred to the
function body so they're paid only when this pass actually runs —
the cold-import path of the rest of the library stays clean.

Path handling:

* ``\\`` is normalised to ``/`` (Windows-flavoured paths in SVG attrs
  are common in editors).
* ``file:`` URIs with mis-counted slashes are normalised to the
  three-slash ``file:///`` form.
* Schemeless paths default to ``file:`` and are resolved relative to
  ``options.infilename``'s directory when the path is itself relative.
  The working directory is restored in a ``finally`` block so a
  network/file failure mid-loop doesn't leak it.
"""

from __future__ import annotations

import optparse
import os
import re
import sys
from xml.dom.minidom import Element

from svg_polish.constants import NS

__all__ = ["embed_rasters"]


def embed_rasters(element: Element, options: optparse.Values) -> int:
    """Inline a raster image reference on *element* as a base64 data URI.

    Inspects the ``xlink:href`` attribute; if the target is a
    ``png`` / ``jpg`` / ``gif`` file the file is downloaded (or
    read from disk for ``file:`` URIs), base64-encoded, and the
    attribute is rewritten to a self-contained ``data:image/{ext};base64,…``
    URI.

    On read failure prints a warning to ``options.stdout`` (or
    ``sys.stdout`` if the option isn't set) and leaves the element
    unchanged — the original reference may still resolve in a
    rendering context that has different network/filesystem access.

    Args:
        element: The ``<image>`` (or anything carrying an
            ``xlink:href`` to a raster) to inline.
        options: Optimizer options. ``options.infilename`` is the
            anchor used to resolve relative ``file:`` URIs.

    Returns:
        1 if a raster was successfully embedded, 0 otherwise. The
        caller accumulates these into a per-document count.
    """
    # Lazy: ``embed_rasters`` is opt-in, so don't pay urllib's import
    # cost on the cold path of every other call to the optimizer.
    import base64
    import urllib.parse
    import urllib.request

    num_rasters_embedded = 0

    href = element.getAttributeNS(NS["XLINK"], "href")

    if href and len(href) > 1:
        ext = os.path.splitext(os.path.basename(href))[1].lower()[1:]

        if ext in ["png", "jpg", "gif"]:
            # Common path-shape fix-ups: backslashes from Windows
            # editors; ``file:/x`` (one or two slashes) → ``file:///x``.
            # TODO: warn on these instead of silently fixing?
            href_fixed = href.replace("\\", "/")
            href_fixed = re.sub("file:/+", "file:///", href_fixed)

            # urlparse + urlunparse round-trips lose information for
            # ``file:`` URIs — ``urlunparse(urlparse("file:raster.png"))``
            # yields ``"file:///raster.png"`` which is just wrong.
            # So we work with the parsed scheme but rebuild the URI
            # by hand below.
            parsed_href = urllib.parse.urlparse(href_fixed)

            # Schemeless paths → assume local file.
            if parsed_href.scheme == "":
                parsed_href = parsed_href._replace(scheme="file")
                href_fixed = "file://" + href_fixed if href_fixed[0] == "/" else "file:" + href_fixed

            # Relative ``file:`` paths resolve against the input file's
            # directory, not the current process cwd. Saved to restore
            # in the finally block.
            working_dir_old = None
            if parsed_href.scheme == "file" and parsed_href.path[0] != "/" and options.infilename:
                working_dir_old = os.getcwd()
                working_dir_new = os.path.abspath(os.path.dirname(options.infilename))
                os.chdir(working_dir_new)

            try:
                file = urllib.request.urlopen(href_fixed)  # noqa: S310 — opt-in pass; user supplies the URL
                rasterdata = file.read()
                file.close()
            except Exception as e:
                print(
                    "WARNING: Could not open file '" + href + "' for embedding. "
                    "The raster image will be kept as a reference but might be invalid. "
                    "(Exception details: " + str(e) + ")",
                    file=options.ensure_value("stdout", sys.stdout),
                )
                rasterdata = ""
            finally:
                if working_dir_old is not None:
                    os.chdir(working_dir_old)

            # TODO: also remove unresolvable images? Need to handle
            # the offline-but-hosted-elsewhere case carefully.
            if rasterdata:
                b64eRaster = base64.b64encode(rasterdata)

                if b64eRaster:
                    # MIME type matches the extension except for
                    # JPEG, which uses ``image/jpeg`` not ``image/jpg``.
                    if ext == "jpg":
                        ext = "jpeg"

                    element.setAttributeNS(NS["XLINK"], "href", "data:image/" + ext + ";base64," + b64eRaster.decode())
                    num_rasters_embedded += 1
                    del b64eRaster
    return num_rasters_embedded
