flownexus Documentation
=======================

This directory contains the source code for the flownexus documentation.

System Requirements
###################

To build the documentation, you need the following system packages installed:

- Python 3
- tox
- Graphviz (for ERD diagrams)
- Default JRE and PlantUML (for sequence diagrams)

On Debian/Ubuntu-based systems, you can install them with::

    sudo apt-get install python3 tox graphviz default-jre plantuml

Build the Documentation
#######################

The documentation is built using ``tox``.

Build HTML documentation::

    tox -e html

The generated documentation will be available in ``build/html/index.html``.

Build PDF documentation (requires LaTeX)::

    tox -e pdf
