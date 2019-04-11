===========================================================
``Distpickymodel`` shared Mongoengine-based model library
===========================================================

.. image:: https://travis-ci.com/d2gex/distpickymodel.svg?branch=master
    :target: https://travis-ci.com/d2gex/distpickymodel

.. image:: https://img.shields.io/badge/version-0.1.1-orange.svg
    :target: #


A library that is shared and used by different services of the distributed web scraper. The 'data relationship'
diagram is shown below:

.. image:: docs/images/distpickyscraper_collection_relationships.png
    :alt: Database Relationship Model
    :target: #

Installing Distpickymodel
==========================

Bleach is not available on PyPI_, so you need to install it with ``pip`` providing a GitHub path::

    $ pip install git+https://github.com/d2gex/distpickymodel.git@0.1.1#egg=distpickymodel


.. _PyPI: http://pypi.python.org/