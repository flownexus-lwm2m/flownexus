Documentation
=============

Build the documentation
-----------------------

.. code-block:: console

  host:~$ sudo apt-get install default-jre plantuml graphviz
  host:~$ curl -LsSf https://astral.sh/uv/install.sh | sh
  host:~$ cd workspace/flownexus
  host:~/workspace/flownexus$ make doc-html

View at ``doc/build/html/index.html``.

Live reload::

  host:~/workspace/flownexus$ make doc
