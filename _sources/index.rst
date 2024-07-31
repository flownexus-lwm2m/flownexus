.. only:: html

   📥 Documentation as `PDF <./_static/flownexus.pdf>`_.

.. Do not add a heading in this file. A heading would be placed at the upper
   hierarchical level for the pdf document.

**Introduction**

Welcome to flownexus, your comprehensive solution for small to medium scale
IoT deployments. This platform is designed to streamline the setup,
configuration, and use of IoT devices, making it easy to manage your IoT
ecosystem.

This project aims to provide a minimal and standalone Open Source IoT platform.
The focus is on systems with a deployment of up to a few thousand devices; it
does not aim to be scalable to millions of devices. The goal is to build a
system that receives, for example, regular temperature samples from remote IoT
devices. These temperature samples will be sent to a backend and stored in a
database. The data is then visualized in a web application.

Our vision for flownexus is to create a user-friendly, efficient, and robust
Open Source platform for IoT management. We aim to simplify the complexities of
IoT deployments, making them accessible and manageable for businesses of all
sizes.


.. toctree::
   :maxdepth: 1
   :caption: Documentation

   overview
   architecture/index
   application_guide/index
   deploy
   simulation
   documentation
   glossary


.. toctree::
   :maxdepth: 1
   :caption: APIs

   api_doc/api


.. toctree::
   :maxdepth: 1
   :caption: News and Updates

   news/weblog
