Kibana Python Client Documentation
===================================

.. note::

   **Disclaimer:** This is an independent, community-driven project and is **not**
   officially affiliated with, endorsed by, or supported by Elastic N.V. or any of
   its subsidiaries. "Kibana" and "Elasticsearch" are trademarks of Elastic N.V.
   This software is provided "as is", without warranty of any kind. See the
   `LICENSE <https://github.com/pedro-angel/kibana-py/blob/main/LICENSE>`_ for full terms.

A Python client library for interacting with Kibana's REST API.

The kibana-py library provides both synchronous and asynchronous interfaces for
communicating with Kibana instances, built on top of the elastic-transport library
for reliable HTTP communication.

kibana-py targets Kibana 9.4 and covers the full platform API surface — 24
namespaces and roughly 270 endpoints — including the new (technical preview)
:doc:`Dashboards HTTP API <user-guide/dashboards>` for managing dashboards as
code. It requires Python 3.11 or newer.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user-guide/index
   user-guide/authentication
   user-guide/dashboards
   user-guide/alerting
   user-guide/data-views
   user-guide/cases
   user-guide/connectors
   user-guide/spaces
   user-guide/saved-objects
   user-guide/status-monitoring
   user-guide/platform-apis
   user-guide/error-handling
   user-guide/observability
   user-guide/advanced-usage

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api-reference/index

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/index

.. toctree::
   :maxdepth: 2
   :caption: Development

   development/index

.. toctree::
   :maxdepth: 1
   :caption: Additional Resources

   migration-guides/index
   troubleshooting/index
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
