Exceptions
==========

Exception classes for error handling in the Kibana Python client.

The kibana-py library provides a comprehensive exception hierarchy for handling
various error conditions that may occur when interacting with the Kibana API.

.. currentmodule:: kibana

Exception Hierarchy
-------------------

All exceptions inherit from the base :class:`KibanaException` class:

.. code-block:: text

   KibanaException
   ├── ApiError
   │   ├── BadRequestError (400)
   │   ├── AuthenticationException (401)
   │   ├── AuthorizationException (403)
   │   ├── NotFoundError (404)
   │   └── ConflictError (409)
   ├── TransportError
   │   ├── ConnectionError
   │   │   ├── ConnectionTimeout
   │   │   └── SSLError
   │   └── SerializationError
   └── SpaceError
       ├── SpaceNotFoundError
       └── InvalidSpaceIdError

Base Exceptions
---------------

KibanaException
^^^^^^^^^^^^^^^

.. autoclass:: KibanaException
   :members:
   :show-inheritance:

   Base exception for all Kibana client errors. Catch this to handle any
   error from the Kibana client.

   .. code-block:: python

      from kibana import Kibana
      from kibana.exceptions import KibanaException

      client = Kibana("http://localhost:5601")

      try:
          # Perform operations
          connector = client.actions.create(
              name="Test",
              connector_type_id=".webhook",
              config={"url": "https://example.com"}
          )
      except KibanaException as e:
          print(f"Kibana error occurred: {e}")

API Exceptions
--------------

ApiError
^^^^^^^^

.. autoclass:: ApiError
   :members:
   :show-inheritance:

   Base class for API-level errors. Contains response metadata and body.

   **Attributes:**

   - ``message`` (str): Error message
   - ``meta`` (ApiResponseMeta): Response metadata including status code
   - ``body`` (Any): Response body containing error details
   - ``status_code`` (int): HTTP status code

   .. code-block:: python

      from kibana.exceptions import ApiError

      try:
          result = client.actions.get(id="nonexistent")
      except ApiError as e:
          print(f"API error: {e.message}")
          print(f"Status code: {e.status_code}")
          print(f"Response body: {e.body}")

BadRequestError
^^^^^^^^^^^^^^^

.. autoclass:: BadRequestError
   :members:
   :show-inheritance:

   Raised when the API returns a 400 Bad Request status code.

   This typically indicates invalid parameters or malformed requests.

   .. code-block:: python

      from kibana.exceptions import BadRequestError

      try:
          # Invalid connector configuration
          connector = client.actions.create(
              name="Test",
              connector_type_id=".webhook",
              config={}  # Missing required 'url' field
          )
      except BadRequestError as e:
          print(f"Invalid request: {e.message}")
          print(f"Details: {e.body}")

AuthenticationException
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: AuthenticationException
   :members:
   :show-inheritance:

   Raised when authentication fails (401 Unauthorized).

   This indicates invalid or missing authentication credentials.

   .. code-block:: python

      from kibana.exceptions import AuthenticationException

      try:
          client = Kibana(
              "http://localhost:5601",
              api_key="invalid_key"
          )
          status = client.status.get_status()
      except AuthenticationException as e:
          print(f"Authentication failed: {e.message}")
          print("Please check your API key or credentials")

AuthorizationException
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: AuthorizationException
   :members:
   :show-inheritance:

   Raised when authorization fails (403 Forbidden).

   This indicates the authenticated user lacks permissions for the requested operation.

   .. code-block:: python

      from kibana.exceptions import AuthorizationException

      try:
          # User doesn't have permission to create connectors
          connector = client.actions.create(
              name="Test",
              connector_type_id=".webhook",
              config={"url": "https://example.com"}
          )
      except AuthorizationException as e:
          print(f"Permission denied: {e.message}")
          print("User lacks required privileges")

NotFoundError
^^^^^^^^^^^^^

.. autoclass:: NotFoundError
   :members:
   :show-inheritance:

   Raised when a resource is not found (404 Not Found).

   .. code-block:: python

      from kibana.exceptions import NotFoundError

      try:
          connector = client.actions.get(id="nonexistent-id")
      except NotFoundError as e:
          print(f"Resource not found: {e.message}")

      try:
          space = client.spaces.get(id="nonexistent-space")
      except NotFoundError as e:
          print(f"Space not found: {e.message}")

ConflictError
^^^^^^^^^^^^^

.. autoclass:: ConflictError
   :members:
   :show-inheritance:

   Raised when a conflict occurs (409 Conflict).

   This typically indicates a resource already exists or a version conflict.

   .. code-block:: python

      from kibana.exceptions import ConflictError

      try:
          # Create space with existing ID
          space = client.spaces.create(
              id="default",  # 'default' space already exists
              name="Default Space"
          )
      except ConflictError as e:
          print(f"Conflict: {e.message}")
          print("Resource already exists")

Transport Exceptions
--------------------

TransportError
^^^^^^^^^^^^^^

.. autoclass:: TransportError
   :members:
   :show-inheritance:

   Base class for transport-level errors.

   .. code-block:: python

      from kibana.exceptions import TransportError

      try:
          status = client.status.get_status()
      except TransportError as e:
          print(f"Transport error: {e}")

ConnectionError
^^^^^^^^^^^^^^^

.. autoclass:: ConnectionError
   :members:
   :show-inheritance:

   Raised when connection to Kibana fails.

   .. code-block:: python

      from kibana.exceptions import ConnectionError

      try:
          client = Kibana("http://nonexistent:5601")
          status = client.status.get_status()
      except ConnectionError as e:
          print(f"Cannot connect to Kibana: {e}")
          print("Check that Kibana is running and accessible")

ConnectionTimeout
^^^^^^^^^^^^^^^^^

.. autoclass:: ConnectionTimeout
   :members:
   :show-inheritance:

   Raised when a connection times out.

   .. code-block:: python

      from kibana.exceptions import ConnectionTimeout

      try:
          client = Kibana(
              "http://localhost:5601",
              request_timeout=1  # Very short timeout
          )
          status = client.status.get_status()
      except ConnectionTimeout as e:
          print(f"Connection timed out: {e}")

SSLError
^^^^^^^^

.. autoclass:: SSLError
   :members:
   :show-inheritance:

   Raised when an SSL/TLS error occurs.

   .. code-block:: python

      from kibana.exceptions import SSLError

      try:
          client = Kibana(
              "https://localhost:5601",
              verify_certs=True
          )
          status = client.status.get_status()
      except SSLError as e:
          print(f"SSL error: {e}")
          print("Check SSL certificate configuration")

SerializationError
^^^^^^^^^^^^^^^^^^

.. autoclass:: SerializationError
   :members:
   :show-inheritance:

   Raised when serialization or deserialization fails.

   .. code-block:: python

      from kibana.exceptions import SerializationError

      try:
          # This would raise SerializationError if response is invalid JSON
          result = client.actions.get_all()
      except SerializationError as e:
          print(f"Serialization error: {e}")

Space Exceptions
----------------

SpaceError
^^^^^^^^^^

.. autoclass:: SpaceError
   :members:
   :show-inheritance:

   Base class for space-related errors.

   .. code-block:: python

      from kibana.exceptions import SpaceError

      try:
          connector = client.actions.create(
              name="Test",
              connector_type_id=".webhook",
              config={"url": "https://example.com"},
              space_id="invalid-space"
          )
      except SpaceError as e:
          print(f"Space error: {e}")

SpaceNotFoundError
^^^^^^^^^^^^^^^^^^

.. autoclass:: SpaceNotFoundError
   :members:
   :show-inheritance:

   Raised when a specified space does not exist.

   **Attributes:**

   - ``space_id`` (str): The ID of the space that was not found

   .. code-block:: python

      from kibana.exceptions import SpaceNotFoundError

      try:
          connector = client.actions.create(
              name="Test",
              connector_type_id=".webhook",
              config={"url": "https://example.com"},
              space_id="nonexistent"
          )
      except SpaceNotFoundError as e:
          print(f"Space not found: {e.space_id}")
          print("Create the space first or use an existing space")

InvalidSpaceIdError
^^^^^^^^^^^^^^^^^^^

.. autoclass:: InvalidSpaceIdError
   :members:
   :show-inheritance:

   Raised when a space ID format is invalid.

   **Attributes:**

   - ``space_id`` (str): The invalid space ID

   .. code-block:: python

      from kibana.exceptions import InvalidSpaceIdError

      try:
          space = client.spaces.create(
              id="Invalid Space!",  # Spaces cannot contain spaces or special chars
              name="Invalid Space"
          )
      except InvalidSpaceIdError as e:
          print(f"Invalid space ID: {e.space_id}")
          print("Space IDs must be lowercase alphanumeric with hyphens/underscores")

Error Handling Patterns
-----------------------

Specific Exception Handling
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Handle specific exceptions for fine-grained error handling:

.. code-block:: python

   from kibana import Kibana
   from kibana.exceptions import (
       NotFoundError,
       ConflictError,
       BadRequestError,
       AuthenticationException,
       SpaceNotFoundError
   )

   client = Kibana("http://localhost:5601")

   try:
       connector = client.actions.create(
           name="My Connector",
           connector_type_id=".webhook",
           config={"url": "https://example.com"},
           space_id="marketing"
       )
   except SpaceNotFoundError as e:
       print(f"Space '{e.space_id}' doesn't exist. Creating it...")
       client.spaces.create(id=e.space_id, name="Marketing")
       # Retry operation
   except BadRequestError as e:
       print(f"Invalid configuration: {e.message}")
       print(f"Details: {e.body}")
   except ConflictError as e:
       print(f"Connector already exists: {e.message}")
   except AuthenticationException as e:
       print(f"Authentication failed: {e.message}")
       # Re-authenticate or exit
   except NotFoundError as e:
       print(f"Resource not found: {e.message}")

Broad Exception Handling
^^^^^^^^^^^^^^^^^^^^^^^^^

Use base exceptions for broader error handling:

.. code-block:: python

   from kibana.exceptions import ApiError, TransportError, KibanaException

   try:
       # Perform operations
       result = client.actions.get_all()
   except ApiError as e:
       # Handle all API-level errors
       print(f"API error ({e.status_code}): {e.message}")
   except TransportError as e:
       # Handle all transport-level errors
       print(f"Transport error: {e}")
   except KibanaException as e:
       # Handle any other Kibana errors
       print(f"Kibana error: {e}")

Context Manager Error Handling
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Proper error handling with context managers:

.. code-block:: python

   from kibana import Kibana
   from kibana.exceptions import KibanaException

   try:
       with Kibana("http://localhost:5601") as client:
           # Perform operations
           status = client.status.get_status()
           print(f"Status: {status.body['status']['overall']['level']}")
   except KibanaException as e:
       print(f"Error: {e}")
   # Client is automatically closed even if an exception occurs

Async Error Handling
^^^^^^^^^^^^^^^^^^^^^

Error handling with async client:

.. code-block:: python

   from kibana import AsyncKibana
   from kibana.exceptions import KibanaException
   import asyncio

   async def main():
       try:
           async with AsyncKibana("http://localhost:5601") as client:
               # Perform async operations
               status = await client.status.get_status()
               print(f"Status: {status.body['status']['overall']['level']}")
       except KibanaException as e:
           print(f"Error: {e}")

   asyncio.run(main())
