#!/usr/bin/env python3
"""
Short URLs Management Example

This example shows the minimal code needed to:
1. Create a short URL for a Kibana page (custom slug)
2. Get the short URL by ID
3. Resolve the short URL by its slug
4. Clean up (delete the short URL)

The Short URL APIs are a technical preview in Kibana 9.4.

Run this example:
    python examples/short_urls_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-short-urls"
    slug = f"{prefix}-dashboards"
    short_url_id = None
    created: list[tuple[str, str]] = []
    try:
        # Idempotent start: clear only THIS example's own prior short URL
        try:
            resolved_prior = client.short_urls.resolve(slug=slug)
            client.short_urls.delete(id=resolved_prior.body["id"])
        except NotFoundError:
            pass

        # 1. Create a short URL that redirects to the dashboards app
        created_url = client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
            slug=slug,
        )
        short_url_id = created_url.body["id"]
        created.append(("short url", short_url_id))
        print(f"Created short URL {short_url_id}")
        print(f"  Share it as: {kibana_url}/goto/{created_url.body['slug']}")

        # 2. Get it by ID
        fetched = client.short_urls.get(id=short_url_id)
        print(f"Fetched by ID: slug={fetched.body['slug']}")

        # 3. Resolve it by slug (what Kibana does when a /goto link is opened)
        resolved = client.short_urls.resolve(slug=slug)
        locator = resolved.body["locator"]
        print(f"Resolved slug '{slug}' -> locator {locator['id']} {locator['state']}")
    finally:
        # 4. Clean up
        if short_url_id is not None:
            if should_cleanup():
                client.short_urls.delete(id=short_url_id)
                print(f"Deleted short URL {short_url_id}")
            else:
                print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
