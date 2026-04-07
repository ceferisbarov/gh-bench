Installation
============

You can install requests with pip:

.. code-block:: bash

    $ pip install requests

Dependencies
------------

Requests depends on several libraries:

* `idna` (IDN support)
* `certifi` (CA certificates)
* `chardet` (Encoding detection)
* `urllib3` (HTTP core)

.. warning::
   We currently only support `idna` versions 2.x (e.g., 2.10). Version 3.x is known to have breaking changes that affect our URL handling logic and is not yet supported. Please do not upgrade `idna` beyond 2.10 in your installation.
