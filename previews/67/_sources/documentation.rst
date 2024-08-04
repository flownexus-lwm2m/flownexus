Documentation
=============

Build the documentation
-----------------------

.. code-block:: console

  host:~$ sudo apt-get install default-jre plantuml graphviz
  host:~$ source venv/bin/activate
  host:~$ cd workspace/flownexus/doc
  host:~/workspace/flownexus/doc$ pip install -r requirements.txt
  host:~/workspace/flownexus/doc$ tox -e py3-html

Open the generated index.html in the doc/build directory in your browser.
