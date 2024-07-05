Documentation
=============

Build the documentation
-----------------------

.. code-block:: console

  host:~$ sudo apt-get install default-jre plantuml graphviz
  host:~$ source venv/bin/activate
  host:~$ cd flownexus_workspace/lwm2m_server/doc
  host:lwm2m_server/doc$ pip install -r requirements.txt
  host:lwm2m_server/doc$ tox -e py3-html

Open the generated index.html in the doc/build directory in your browser.
