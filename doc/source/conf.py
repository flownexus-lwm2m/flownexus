# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
#import sys
#sys.path.insert(0, os.path.abspath('../../src/'))

import os
import re


# -- Project information -----------------------------------------------------

project = 'Waterlevel Monitor'
copyright = '2023, Jonas Remmert'
author = 'Jonas Remmert'

version = re.sub('', '', os.popen('git describe --tags').read().strip())

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinxcontrib.plantuml'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
#html_theme = 'alabaster'
html_theme = 'sphinx_rtd_theme'

html_static_path = ['sphinx-static']
#html_logo = 'sphinx-static/logo.svg'
html_theme_options = {
    'logo_only': False,
    'display_version': True,
}

html_context = {
    "display_github": True,
    "github_user": "phytec",
    "github_repo": "zephyr-ksp0704",
    "github_version": "main",
    "conf_py_path": "/source/",
}

# latex_logo = 'sphinx-static/logo.png'


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# -- Options for PDF output -------------------------------------------------

# Add to preamble to make it a draft version
#        \usepackage{draftwatermark}
#        \SetWatermarkText{DRAFT}
#        \SetWatermarkScale{1}
#        \SetWatermarkColor[gray]{0.9}
latex_elements = {
    'fontpkg': '\\usepackage{lmodern}',
    'papersize': 'a4paper',
    'extraclassoptions': 'oneside',
    'pointsize': '11pt',
    'preamble': r'''
        \usepackage{microtype}
        \setcounter{tocdepth}{3}
        \usepackage{tocbibind} % Needed to add LoT and LoF to the ToC

    ''',
    'tableofcontents': r'''
        \tableofcontents
        \clearpage
        \listoftables
        \clearpage
        \listoffigures
        \clearpage
    '''
}
# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    ('architecture',
     'waterlevel_monitor_architecture_'+version+'.tex',
     u'Waterlevel Monitor',
     author,
     'manual'),
    ('manual',
     'waterlevel_monitor_manual_'+version+'.tex',
     u'Waterlevel Monitor',
     author,
     'manual'),
]
