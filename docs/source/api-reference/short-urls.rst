ShortUrlsClient
===============

Client for the Kibana Short URLs API.

Kibana URLs may be long and cumbersome; short URLs are much easier to
remember and share. Short URLs are created by specifying a locator ID and
locator parameters. When a short URL is resolved, the locator ID and locator
parameters are used to redirect the user to the right Kibana page.

.. note::
   All Short URL APIs are marked as **technical preview** in Kibana 9.4 and
   may change in future releases.

Short URLs are space-scoped saved objects: a short URL created in one space
is not visible from another space. Every method accepts an optional
``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.short_urls

.. autoclass:: ShortUrlsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating Short URLs

   Create a short URL with the :meth:`~ShortUrlsClient.create` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a short URL using the legacy short URL locator
      created = client.short_urls.create(
          locator_id="LEGACY_SHORT_URL_LOCATOR",
          params={"url": "/app/dashboards"},
      )

      slug = created.body["slug"]
      short_url_id = created.body["id"]
      print(f"Short URL: http://localhost:5601/r/s/{slug}")

      # Ask Kibana for a human-readable slug instead of a random one
      readable = client.short_urls.create(
          locator_id="LEGACY_SHORT_URL_LOCATOR",
          params={"url": "/app/dashboards"},
          human_readable_slug=True,
      )

   .. rubric:: Resolving and Retrieving Short URLs

   .. code-block:: python

      # Resolve a short URL by its slug
      resolved = client.short_urls.resolve(slug=slug)
      print(resolved.body["locator"])

      # Get a short URL by its ID
      short_url = client.short_urls.get(id=short_url_id)

   .. rubric:: Deleting Short URLs

   .. code-block:: python

      client.short_urls.delete(id=short_url_id)

AsyncShortUrlsClient
--------------------

Asynchronous version of the ShortUrlsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.short_urls.AsyncShortUrlsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncShortUrlsClient provides the same methods as ShortUrlsClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a short URL (async)
              created = await client.short_urls.create(
                  locator_id="LEGACY_SHORT_URL_LOCATOR",
                  params={"url": "/app/dashboards"},
              )

              # Resolve it by slug, then delete it (async)
              resolved = await client.short_urls.resolve(
                  slug=created.body["slug"]
              )
              await client.short_urls.delete(id=resolved.body["id"])

      asyncio.run(main())
