# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add the project root to the path so we can import the package
sys.path.insert(0, os.path.abspath("../.."))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "kibana-py"
copyright = "2025, Kibana Python Client Contributors"
author = "Kibana Python Client Contributors"

# The version info for the project
try:
    from kibana._version import __versionstr__

    release = __versionstr__
    version = ".".join(release.split(".")[:2])  # Short X.Y version
except ImportError:
    release = "0.1.0"
    version = "0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
}

# -- Extension configuration -------------------------------------------------

# Autodoc configuration
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

# Napoleon configuration (Google-style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "elastic-transport": (
        "https://elastic-transport-python.readthedocs.io/en/latest/",
        None,
    ),
}

# MyST parser configuration
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_admonition",
]

# Auto-generate slug anchors for headings so cross-document links such as
# ``platform-apis.md#maintenance-windows`` resolve.
myst_heading_anchors = 3

# Source file suffixes
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Linkcheck configuration
# Local development endpoints are intentionally documented as examples and are
# not expected to be reachable in CI.
linkcheck_ignore = [
    r"http://localhost(:\d+)?(/.*)?$",
    r"https://localhost(:\d+)?(/.*)?$",
    r"http://127\.0\.0\.1(:\d+)?(/.*)?$",
    r"https://127\.0\.0\.1(:\d+)?(/.*)?$",
    # This repo's own release-tag and compare links resolve only *after* a
    # release is published (the tag is created at publish time). Don't gate a
    # pre-release branch's docs build on them.
    r"https://github\.com/pedro-angel/kibana-py/releases/tag/v.*$",
    r"https://github\.com/pedro-angel/kibana-py/compare/.*$",
]

# Two GitHub paths are unreachable from inside a Claude Code cloud session, and only
# from there. The session's GitHub credential proxy -- the control that keeps the real
# token outside the VM -- answers /discussions and /wiki with 403 ("sessions are bound
# to their configured repositories"), while /, /tree, /blob, /issues, /pulls,
# /releases and /issues/new/choose all resolve. Measured 2026-08-22; the map is in
# docs/source/development/cloud-environment.md. The links are valid -- this repository
# has Discussions enabled -- so the failure is the sandbox, not the documentation.
#
# Scoped to that environment ONLY, deliberately. CI and a maintainer's machine check
# these links exactly as before, so the gate is not weakened where it can run; it is
# relaxed only where it provably cannot. Widening `linkcheck_ignore` unconditionally
# would buy a green `docs_strict` in the sandbox by giving up the one place the link
# is actually verified.
#
# Announced rather than applied silently: an exemption nobody can see in the build
# log is how a gate stops gating without anyone deciding that it should.
_SANDBOX_UNREACHABLE_LINKS = [
    r"https://github\.com/.+/discussions/?$",
    r"https://github\.com/.+/wiki/?$",
]

if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
    linkcheck_ignore += _SANDBOX_UNREACHABLE_LINKS
    print(
        "conf.py: CLAUDE_CODE_REMOTE=true -- linkcheck is skipping "
        f"{len(_SANDBOX_UNREACHABLE_LINKS)} pattern(s) this environment's GitHub "
        "credential proxy refuses (see development/cloud-environment.md): "
        + ", ".join(_SANDBOX_UNREACHABLE_LINKS)
    )
