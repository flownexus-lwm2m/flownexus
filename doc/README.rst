Waterlevel Monitor
==================

.. inclusion-marker-do-not-remove

Standalone Installation
#######################

- The packets virtualenv and tox must be installed on your distribution::

        apt install virtualenv tox

- Clone the repository locally::

        cd doc

- Create a virtualenv::

        virtualenv -p python3 venv
        . venv/bin/activate

- Install all dependencies::

        pip install -r requirements.txt

You can leave the virtualenv by running ``deactivate`` in the bash. Do not
forget to source the virtualenv again next time you want to use it.

Build with tox
**************

Build the documentation as html and pdf::

    tox -e py3-doc
