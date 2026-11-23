# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import json
import os
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.abspath("../../src/"))
master_doc = "index"

project = "flownexus"
copyright = "2024, Individual contributors to flownexus"
author = ""

try:
    version = (
        subprocess.check_output(["git", "describe", "--tags", "--dirty"]).decode("utf-8").strip()
    )
except subprocess.CalledProcessError as e:
    raise RuntimeError("No git tags found. Documentation build requires at least one tag.") from e

release = version

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinxcontrib.plantuml",
    "sphinx.ext.imgconverter",
    "sphinx.ext.todo",
]

exclude_patterns = []

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]
templates_path = ["_templates"]
html_favicon = "_static/flownexus_favicon.svg"
html_baseurl = "https://flownexus-lwm2m.github.io/flownexus/"


# Single gray logo for both dark and light themes (not used)
# html_logo = '_static/flownexus_logo_gray.svg'

html_css_files = [
    "custom.css",
]

# The HTML build replaces api_doc/api with a standalone ReDoc page that embeds
# the generated OpenAPI schema. Other builders keep the placeholder text.
openapi_spec = "../build/generated/openapi-schema.yaml"
redoc_uri = "https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"


def redoc_page(app):
    with open(os.path.join(app.confdir, openapi_spec), encoding="utf-8") as f:
        spec = json.dumps(yaml.safe_load(f)).replace("</", "<\\/")
    yield "api_doc/api", {"spec": spec, "redoc_uri": redoc_uri}, "redoc.html"


def setup(app):
    app.connect("html-collect-pages", redoc_page)


html_theme_options = {
    "repository_url": "https://github.com/flownexus-lwm2m/flownexus",
    "repository_branch": "main",
    "path_to_docs": "doc/source/",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_edit_page_button": True,
    "use_download_button": False,
    "collapse_navbar": False,
    "home_page_in_toc": False,
    "navigation_with_keys": False,
    "logo": {
        "image_light": "_static/flownexus_logo_dark.svg",
        "image_dark": "_static/flownexus_logo_light.svg",
    },
}

latex_elements = {
    "fontpkg": "\\usepackage{lmodern}",
    "papersize": "a4paper",
    "extraclassoptions": "oneside",
    "pointsize": "10pt",
    "preamble": r"""
        \usepackage{microtype}
        \setcounter{tocdepth}{2}
        \usepackage{tocbibind} % Adds LoT and LoF to the ToC
    """,
}

latex_documents = [
    (
        master_doc,
        f"flownexus_{version}.tex",
        "flownexus Documentation",
        "Jonas Remmert, Akarshan Kapoor",
        "manual",
    ),
]
