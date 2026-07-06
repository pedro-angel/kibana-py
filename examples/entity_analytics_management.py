#!/usr/bin/env python3
"""
Entity Analytics Management Example

This example shows the minimal code needed to:
1. Classify asset criticality for a host and a user (upsert / get / list)
2. Create a watchlist with a risk modifier (technical preview in 9.4)
3. Run privileged user monitoring (engine init, monitored users, CSV upload)
4. Check the Entity Store status
5. Clean up everything that was created

Run this example:
    python examples/entity_analytics_management.py
"""

from utils import get_kibana_config

from kibana import Kibana


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    ea = client.entity_analytics
    host_name = "kbnpy-example-host"
    user_name = "kbnpy-example-user"
    watchlist_id = None
    monitoring_started = False
    try:
        # 1. Asset criticality: classify how critical entities are
        ea.create_asset_criticality(
            id_field="host.name",
            id_value=host_name,
            criticality_level="high_impact",
            refresh="wait_for",
        )
        ea.bulk_upsert_asset_criticality(
            records=[
                {
                    "id_field": "user.name",
                    "id_value": user_name,
                    "criticality_level": "medium_impact",
                }
            ]
        )
        record = ea.get_asset_criticality(id_field="host.name", id_value=host_name)
        print(f"Asset criticality for {host_name}: {record.body['criticality_level']}")

        found = ea.find_asset_criticality(kuery="id_value: kbnpy-example*")
        print(f"Found {found.body['total']} kbnpy-example criticality records")

        # 2. Watchlists (technical preview): group entities, apply a modifier
        watchlist = ea.create_watchlist(
            name="kbnpy-example-watchlist",
            risk_modifier=1.5,
            description="Example watchlist created by kibana-py",
        )
        watchlist_id = watchlist.body["id"]
        print(f"Created watchlist {watchlist_id} (riskModifier=1.5)")

        # 3. Privileged user monitoring
        ea.init_monitoring_engine()
        monitoring_started = True
        monitored = ea.create_monitored_user(name=user_name)
        print(f"Monitoring privileged user {monitored.body['user']['name']}")

        csv_result = ea.upload_monitored_users_csv(
            file="kbnpy-example-admin-1\nkbnpy-example-admin-2\n"
        )
        print(f"CSV upload added {csv_result.body['stats']['uploaded']} users")

        users = ea.list_monitored_users(kql="user.name: kbnpy-example*")
        print(f"Monitored users: {[u['user']['name'] for u in users.body]}")

        # 4. Entity Store status (install/uninstall are heavier operations;
        # see the integration tests for the full lifecycle)
        status = ea.get_entity_store_status()
        print(f"Entity Store status: {status.body['status']}")
    finally:
        # 5. Clean up
        ea.delete_asset_criticality(
            id_field="host.name", id_value=host_name, refresh="wait_for"
        )
        ea.delete_asset_criticality(
            id_field="user.name", id_value=user_name, refresh="wait_for"
        )
        if watchlist_id is not None:
            ea.delete_watchlist(id=watchlist_id)
            print(f"Deleted watchlist {watchlist_id}")
        if monitoring_started:
            # Remove the monitoring engine and its data (monitored users)
            ea.delete_monitoring_engine(data=True)
            print("Deleted the privilege monitoring engine and its data")
        client.close()


if __name__ == "__main__":
    main()
