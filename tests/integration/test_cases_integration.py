"""Integration tests for the Cases API against a live Kibana stack.

Every resource created here is prefixed ``kbnpy-cases-`` and cleaned up via
fixtures/finalizers. Case-configuration tests run in a dedicated throwaway
space so the shared default-space settings are never modified.
"""

import uuid

import pytest

from kibana.exceptions import ApiError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-cases"


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def unique_suffix():
    """Unique suffix so parallel runs never collide."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def created_cases(kibana_client):
    """Track (case_id, space_id) pairs created during tests for cleanup."""
    entries: list[tuple[str, str | None]] = []
    yield entries

    for case_id, space_id in entries:
        try:
            kibana_client.cases.delete(
                ids=[case_id], space_id=space_id, validate_spaces=False
            )
        except NotFoundError:
            pass  # Already deleted by the test itself
        except Exception as e:  # pragma: no cover - cleanup best effort
            print(f"Warning: failed to clean up case {case_id}: {e}")


def _create_case(client, created_cases, suffix, *, space_id=None, **overrides):
    """Create a small test case and register it for cleanup."""
    payload = {
        "title": f"{PREFIX}-case-{suffix}",
        "description": f"kibana-py integration test case ({suffix})",
        "tags": [f"{PREFIX}-tag-{suffix}"],
        "owner": "cases",
    }
    payload.update(overrides)
    response = client.cases.create(space_id=space_id, **payload)
    assert response.meta.status == 200
    created_cases.append((response.body["id"], space_id))
    return response.body


class TestCasesCrudLifecycle:
    """Full case CRUD round-trip against the live server."""

    def test_create_get_update_delete_roundtrip(
        self, kibana_client, created_cases, unique_suffix
    ):
        case = _create_case(
            kibana_client, created_cases, unique_suffix, severity="high"
        )
        case_id = case["id"]
        assert case["title"] == f"{PREFIX}-case-{unique_suffix}"
        assert case["status"] == "open"
        assert case["severity"] == "high"
        assert case["owner"] == "cases"
        assert f"{PREFIX}-tag-{unique_suffix}" in case["tags"]
        assert case["totalComment"] == 0

        # --- get ---
        fetched = kibana_client.cases.get(case_id=case_id)
        assert fetched.body["id"] == case_id
        assert fetched.body["description"].startswith("kibana-py integration")

        # --- update (single-case-friendly form of the bulk PATCH) ---
        updated = kibana_client.cases.update(
            id=case_id,
            version=fetched.body["version"],
            status="in-progress",
            title=f"{PREFIX}-case-{unique_suffix}-renamed",
        )
        assert updated.meta.status == 200
        assert isinstance(updated.body, list)
        assert updated.body[0]["status"] == "in-progress"
        assert updated.body[0]["title"].endswith("-renamed")

        # --- delete ---
        deleted = kibana_client.cases.delete(ids=[case_id])
        assert deleted.meta.status == 204
        with pytest.raises(NotFoundError):
            kibana_client.cases.get(case_id=case_id)

    def test_find_filters_by_unique_tag(
        self, kibana_client, created_cases, unique_suffix
    ):
        tag = f"{PREFIX}-tag-{unique_suffix}"
        case_a = _create_case(kibana_client, created_cases, f"{unique_suffix}-a")
        case_b = _create_case(kibana_client, created_cases, f"{unique_suffix}-b")
        # Both share the per-test unique tag via overrides
        for case in (case_a, case_b):
            got = kibana_client.cases.get(case_id=case["id"])
            kibana_client.cases.update(
                id=case["id"], version=got.body["version"], tags=[tag]
            )

        found = kibana_client.cases.find(tags=tag, per_page=10, sort_field="createdAt")
        assert found.body["total"] == 2
        found_ids = {c["id"] for c in found.body["cases"]}
        assert found_ids == {case_a["id"], case_b["id"]}

        # Search text + status filters narrow the result set
        none_found = kibana_client.cases.find(tags=tag, status="closed")
        assert none_found.body["total"] == 0

    def test_delete_multiple_ids_in_one_call(
        self, kibana_client, created_cases, unique_suffix
    ):
        case_a = _create_case(kibana_client, created_cases, f"{unique_suffix}-x")
        case_b = _create_case(kibana_client, created_cases, f"{unique_suffix}-y")

        deleted = kibana_client.cases.delete(ids=[case_a["id"], case_b["id"]])
        assert deleted.meta.status == 204
        for case in (case_a, case_b):
            with pytest.raises(NotFoundError):
                kibana_client.cases.get(case_id=case["id"])

    def test_get_tags_and_reporters(self, kibana_client, created_cases, unique_suffix):
        tag = f"{PREFIX}-tag-{unique_suffix}"
        _create_case(kibana_client, created_cases, unique_suffix)

        tags = kibana_client.cases.get_tags(owner="cases")
        assert tags.meta.status == 200
        assert isinstance(tags.body, list)
        assert tag in tags.body

        reporters = kibana_client.cases.get_reporters(owner="cases")
        assert reporters.meta.status == 200
        assert isinstance(reporters.body, list)
        assert len(reporters.body) >= 1
        assert all("username" in reporter for reporter in reporters.body)


class TestCaseCommentsLifecycle:
    """Comment add/find/get/update/delete round-trip."""

    def test_comment_full_lifecycle(self, kibana_client, created_cases, unique_suffix):
        case = _create_case(kibana_client, created_cases, unique_suffix)
        case_id = case["id"]

        # --- add ---
        commented = kibana_client.cases.add_comment(
            case_id=case_id, comment=f"{PREFIX} first note {unique_suffix}"
        )
        assert commented.body["totalComment"] == 1
        comment = commented.body["comments"][-1]
        assert comment["type"] == "user"

        # --- find (paginated) ---
        page = kibana_client.cases.get_comments(case_id=case_id, per_page=10)
        assert page.body["total"] == 1
        assert page.body["comments"][0]["id"] == comment["id"]

        # --- get one ---
        fetched = kibana_client.cases.get_comment(
            case_id=case_id, comment_id=comment["id"]
        )
        assert fetched.body["comment"] == f"{PREFIX} first note {unique_suffix}"

        # --- update ---
        kibana_client.cases.update_comment(
            case_id=case_id,
            id=comment["id"],
            version=fetched.body["version"],
            comment=f"{PREFIX} edited note {unique_suffix}",
        )
        refetched = kibana_client.cases.get_comment(
            case_id=case_id, comment_id=comment["id"]
        )
        assert refetched.body["comment"] == f"{PREFIX} edited note {unique_suffix}"

        # --- delete ---
        deleted = kibana_client.cases.delete_comment(
            case_id=case_id, comment_id=comment["id"]
        )
        assert deleted.meta.status == 204
        assert kibana_client.cases.get_comments(case_id=case_id).body["total"] == 0

    def test_delete_all_comments(self, kibana_client, created_cases, unique_suffix):
        case = _create_case(kibana_client, created_cases, unique_suffix)
        case_id = case["id"]

        for i in range(2):
            kibana_client.cases.add_comment(
                case_id=case_id, comment=f"{PREFIX} note {i} {unique_suffix}"
            )
        assert kibana_client.cases.get_comments(case_id=case_id).body["total"] == 2

        deleted = kibana_client.cases.delete_all_comments(case_id=case_id)
        assert deleted.meta.status == 204
        assert kibana_client.cases.get_comments(case_id=case_id).body["total"] == 0


class TestCaseAlertsAndActivity:
    """Alert-related reads and the user-actions activity log."""

    def test_get_alerts_empty_for_new_case(
        self, kibana_client, created_cases, unique_suffix
    ):
        case = _create_case(kibana_client, created_cases, unique_suffix)
        alerts = kibana_client.cases.get_alerts(case_id=case["id"])
        assert alerts.meta.status == 200
        assert alerts.body == []

    def test_get_cases_by_alert_returns_empty_for_unknown_alert(self, kibana_client):
        result = kibana_client.cases.get_cases_by_alert(
            alert_id=f"{PREFIX}-no-such-alert", owner="cases"
        )
        assert result.meta.status == 200
        assert result.body == []

    def test_find_user_actions_records_status_change(
        self, kibana_client, created_cases, unique_suffix
    ):
        case = _create_case(kibana_client, created_cases, unique_suffix)
        kibana_client.cases.update(
            id=case["id"], version=case["version"], status="closed"
        )

        activity = kibana_client.cases.find_user_actions(
            case_id=case["id"], types=["status"], sort_order="asc"
        )
        assert activity.body["total"] >= 1
        statuses = [
            action["payload"]["status"] for action in activity.body["userActions"]
        ]
        assert "closed" in statuses


class TestCaseFiles:
    """File attachment upload (multipart/form-data)."""

    def test_attach_text_file(self, kibana_client, created_cases, unique_suffix):
        case = _create_case(kibana_client, created_cases, unique_suffix)
        response = kibana_client.cases.add_file(
            case_id=case["id"],
            file=b"kibana-py integration test attachment",
            filename=f"{PREFIX}-notes-{unique_suffix}.txt",
            mime_type="text/plain",
        )
        assert response.meta.status == 200
        attachments = response.body["comments"]
        assert len(attachments) == 1
        # Files are persisted as externalReference attachments backed by a
        # "file" saved object
        assert attachments[0]["type"] == "externalReference"
        assert attachments[0]["externalReferenceAttachmentTypeId"] == ".files"
        file_meta = attachments[0]["externalReferenceMetadata"]["files"][0]
        assert file_meta["name"] == f"{PREFIX}-notes-{unique_suffix}.txt"
        assert file_meta["mimeType"] == "text/plain"


class TestCasePushErrorPath:
    """Pushing to an unknown connector surfaces the server's 404."""

    def test_push_with_unknown_connector_raises_not_found(
        self, kibana_client, created_cases, unique_suffix
    ):
        case = _create_case(kibana_client, created_cases, unique_suffix)
        with pytest.raises((NotFoundError, ApiError)):
            kibana_client.cases.push(
                case_id=case["id"],
                connector_id="00000000-0000-0000-0000-000000000000",
            )


class TestCaseConfigurationInIsolatedSpace:
    """Configuration CRUD, run inside a dedicated throwaway space.

    Case configurations are singletons per owner within a space, so testing
    them in the (shared) default space would clobber other users' settings.
    """

    @pytest.fixture
    def cases_space(self, kibana_client, unique_suffix):
        space_id = f"{PREFIX}-space-{unique_suffix}"
        kibana_client.spaces.create(
            id=space_id, name=f"kibana-py cases test space {unique_suffix}"
        )
        yield space_id
        try:
            kibana_client.spaces.delete(id=space_id)
        except Exception as e:  # pragma: no cover - cleanup best effort
            print(f"Warning: failed to clean up space {space_id}: {e}")

    def test_configuration_lifecycle(self, kibana_client, cases_space):
        # --- create ---
        created = kibana_client.cases.create_configuration(
            closure_type="close-by-user",
            owner="cases",
            custom_fields=[
                {
                    "key": "kbnpy_env",
                    "label": "Environment",
                    "type": "text",
                    "required": False,
                }
            ],
            space_id=cases_space,
        )
        assert created.meta.status == 200
        config_id = created.body["id"]
        assert created.body["closure_type"] == "close-by-user"
        assert created.body["owner"] == "cases"

        # --- get ---
        configs = kibana_client.cases.get_configuration(
            owner="cases", space_id=cases_space
        )
        ours = [config for config in configs.body if config["id"] == config_id]
        assert len(ours) == 1
        assert ours[0]["customFields"][0]["key"] == "kbnpy_env"

        # --- update ---
        updated = kibana_client.cases.update_configuration(
            configuration_id=config_id,
            version=ours[0]["version"],
            closure_type="close-by-pushing",
            space_id=cases_space,
        )
        assert updated.body["closure_type"] == "close-by-pushing"

        # --- connectors usable in cases (none configured in a fresh space) ---
        connectors = kibana_client.cases.find_connectors(space_id=cases_space)
        assert connectors.meta.status == 200
        assert isinstance(connectors.body, list)

    def test_space_scoped_case_crud(
        self, kibana_client, created_cases, unique_suffix, cases_space
    ):
        case = _create_case(
            kibana_client, created_cases, unique_suffix, space_id=cases_space
        )

        # Visible in its own space...
        fetched = kibana_client.cases.get(case_id=case["id"], space_id=cases_space)
        assert fetched.body["id"] == case["id"]

        # ...but not in the default space
        with pytest.raises(NotFoundError):
            kibana_client.cases.get(case_id=case["id"])

        found = kibana_client.cases.find(
            tags=f"{PREFIX}-tag-{unique_suffix}", space_id=cases_space
        )
        assert found.body["total"] == 1

        deleted = kibana_client.cases.delete(ids=case["id"], space_id=cases_space)
        assert deleted.meta.status == 204


class TestAsyncCasesRoundTrip:
    """Async client end-to-end lifecycle against the live server."""

    @pytest.fixture
    async def async_kibana_client(self):
        client = create_test_async_kibana_client(auth_method="auto")
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_async_case_lifecycle(self, async_kibana_client, unique_suffix):
        tag = f"{PREFIX}-async-tag-{unique_suffix}"
        case_id = None
        try:
            created = await async_kibana_client.cases.create(
                title=f"{PREFIX}-async-{unique_suffix}",
                description="kibana-py async integration test case",
                tags=[tag],
                severity="low",
            )
            assert created.meta.status == 200
            case_id = created.body["id"]

            commented = await async_kibana_client.cases.add_comment(
                case_id=case_id, comment=f"{PREFIX} async note {unique_suffix}"
            )
            assert commented.body["totalComment"] == 1

            found = await async_kibana_client.cases.find(tags=tag)
            assert found.body["total"] == 1
            assert found.body["cases"][0]["id"] == case_id

            fetched = await async_kibana_client.cases.get(case_id=case_id)
            updated = await async_kibana_client.cases.update(
                id=case_id, version=fetched.body["version"], status="closed"
            )
            assert updated.body[0]["status"] == "closed"
        finally:
            if case_id is not None:
                deleted = await async_kibana_client.cases.delete(ids=[case_id])
                assert deleted.meta.status == 204
