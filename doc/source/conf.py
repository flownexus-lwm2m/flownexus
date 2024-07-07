# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys
import re

sys.path.insert(0, os.path.abspath('../../src/'))
master_doc = "index"

project = 'Flow Nexus'
copyright = '2024, Individual contributors to Flow Nexus'

version = re.sub('', '', os.popen('git describe --tags').read().strip())
release = version

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinxcontrib.plantuml',
    'sphinx.ext.imgconverter',
    'sphinx.ext.todo',
    'sphinxcontrib.redoc',
]

exclude_patterns = []

html_theme = 'sphinx_book_theme'
html_static_path = ['_static']
html_logo = '_static/LogoForReadme.png'

html_css_files = [
  'custom.css',
]

# Automatically generate ReST API documentation
redoc = [
    {
    'spec': '../build/generated/openapi-schema.yaml',
    'page': 'api_doc/api',
    'embed': True,
    },
]
# Specify a more recent version for API Doc v
redoc_uri = 'https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js'

html_theme_options = {
    'repository_url': 'https://github.com/jonas-rem/lwm2m_server',
    'repository_branch': 'main',
    'path_to_docs': 'doc/source/',
    'use_repository_button': True,
    'use_issues_button': True,
    'use_edit_page_button': True,
    'use_download_button': True,
    'collapse_navbar': False,
    'home_page_in_toc': False,
    'navigation_with_keys': False,
}

latex_elements = {
    'fontpkg': '\\usepackage{lmodern}',
    'papersize': 'a4paper',
    'extraclassoptions': 'oneside',
    'pointsize': '10pt',
    'preamble': r'''
        \usepackage{microtype}
        \setcounter{tocdepth}{2}
        \usepackage{tocbibind} % Adds LoT and LoF to the ToC
    ''',
}

latex_documents = [
    (master_doc, f'flow_nexus_{version}.tex', 'Flow Nexus Documentation',
     'Jonas Remmert, Akarshan Kapoor', 'manual'),
]
