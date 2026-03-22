flownexus Documentation
=======================

Build Documentation
###################

Requirements::

    sudo apt-get install python3 graphviz default-jre plantuml
    curl -LsSf https://astral.sh/uv/install.sh | sh

Build HTML::

    make doc-html

View at ``doc/build/html/index.html``.

Live reload server::

    make doc

Serves at http://localhost:8001.
