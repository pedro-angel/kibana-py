#!/usr/bin/env python3
"""Example: Kibana Machine Learning saved objects APIs.

Demonstrates the three ML saved objects endpoints:

- ml.sync(): synchronize Kibana saved objects with ML jobs / trained models
- ml.update_jobs_spaces(): assign ML jobs to Kibana spaces
- ml.update_trained_models_spaces(): assign trained models to Kibana spaces

The spaces-update calls below use a nonexistent example ID, so they change
nothing and simply show the per-item result shape the API returns.
"""

from utils import get_kibana_config

from kibana import Kibana


def main() -> None:
    """Run the ML saved objects examples."""
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        # 1. Simulate a sync: report what would change without doing it
        result = client.ml.sync(simulate=True).body
        print("Simulated sync:")
        print(f"  saved objects to create: {result['savedObjectsCreated']}")
        print(f"  saved objects to delete: {result['savedObjectsDeleted']}")
        print(f"  datafeeds to add:        {result['datafeedsAdded']}")
        print(f"  datafeeds to remove:     {result['datafeedsRemoved']}")

        # To actually perform the synchronization:
        # client.ml.sync()

        # 2. Update the spaces of anomaly detection jobs.
        # Each job gets its own success/error entry in the 200 response.
        jobs_result = client.ml.update_jobs_spaces(
            job_ids=["kbnpy-example-nonexistent-job"],
            job_type="anomaly-detector",
            spaces_to_add=["default"],
            spaces_to_remove=[],
        ).body
        print("\nupdate_jobs_spaces result:")
        for job_id, outcome in jobs_result.items():
            status = "ok" if outcome["success"] else outcome.get("error", "failed")
            print(f"  {job_id}: {status}")

        # 3. Update the spaces of trained models (same per-item shape)
        models_result = client.ml.update_trained_models_spaces(
            model_ids=["kbnpy-example-nonexistent-model"],
            spaces_to_add=["default"],
            spaces_to_remove=[],
        ).body
        print("\nupdate_trained_models_spaces result:")
        for model_id, outcome in models_result.items():
            status = "ok" if outcome["success"] else outcome.get("error", "failed")
            print(f"  {model_id}: {status}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
