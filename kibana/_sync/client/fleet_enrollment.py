"""Kibana Fleet enrollment keys and tokens API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class FleetEnrollmentClient(NamespaceClient):
    """Client for the Kibana Fleet enrollment keys and tokens API.

    Covers the Fleet APIs used to enroll Elastic Agents and Fleet Servers:

    - **Enrollment API keys**: tokens that Elastic Agents present to Fleet
      Server to enroll into an agent policy (list, create, get, revoke).
    - **Service tokens**: Elasticsearch service tokens used to enroll Fleet
      Server instances with Kibana.
    - **Logstash API keys**: API keys for Logstash to receive data from
      Elastic Agents via a Fleet Logstash output.
    - **Uninstall tokens**: per-policy tokens required to uninstall
      tamper-protected Elastic Agents.
    - **Message signing service**: rotate the key pair Fleet uses to sign
      messages sent to Elastic Agents.
    - **Kubernetes manifests**: fetch or download the manifest for deploying
      Elastic Agent on Kubernetes.

    All operations are space-aware: every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create an enrollment API key for an agent policy
        >>> created = client.fleet_enrollment.create_key(
        ...     policy_id="agent-policy-id", name="my-enrollment-key"
        ... )
        >>> key_id = created.body["item"]["id"]
        >>>
        >>> # List keys, then revoke the one we created
        >>> keys = client.fleet_enrollment.get_keys(per_page=50)
        >>> client.fleet_enrollment.delete_key(key_id=key_id)
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the FleetEnrollmentClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> fleet_enrollment_client = FleetEnrollmentClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    def get_keys(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        kuery: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get enrollment API keys.

        Lists all enrollment API keys. Requires the ``fleet-agents-all`` or
        ``fleet-setup`` privilege.

        Args:
            page: Page number (default: 1).
            per_page: Number of results per page (default: 20).
            kuery: A KQL query string to filter results (for example,
                ``'policy_id:"my-policy-id"'``).
            space_id: Optional space ID to list enrollment API keys from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: List of enrollment API keys (``id``, ``api_key_id``,
                  ``api_key``, ``name``, ``policy_id``, ``active``,
                  ``created_at``, ``hidden``)
                - list: Deprecated duplicate of ``items``
                - total / page / perPage: pagination metadata

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> keys = client.fleet_enrollment.get_keys(
            ...     per_page=50, kuery='policy_id:"my-policy-id"'
            ... )
            >>> for key in keys.body["items"]:
            ...     print(key["id"], key["name"], key["active"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if kuery is not None:
            params["kuery"] = kuery

        path = self._build_space_path(
            "/api/fleet/enrollment_api_keys", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def create_key(
        self,
        *,
        policy_id: str,
        name: str | None = None,
        expiration: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an enrollment API key.

        Creates an enrollment API key for a given agent policy. Elastic
        Agents use the returned ``api_key`` to enroll into the policy.
        Requires the ``fleet-agents-all`` privilege.

        Note: Kibana appends the generated key ID to the provided ``name``
        (the stored name looks like ``"my-name (<key-id>)"``).

        Args:
            policy_id: The ID of the agent policy the Elastic Agent will be
                enrolled in.
            name: The name of the enrollment API key.
            expiration: Expiration timestamp for the key (for example,
                ``"2025-01-01T00:00:00.000Z"``).
            space_id: Optional space ID to create the enrollment API key in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - item: The created enrollment API key (``id``,
                  ``api_key_id``, ``api_key``, ``name``, ``policy_id``,
                  ``active``, ``created_at``)
                - action: ``"created"``

        Raises:
            BadRequestError: If the agent policy does not exist or the body
                is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.fleet_enrollment.create_key(
            ...     policy_id="agent-policy-id", name="my-enrollment-key"
            ... )
            >>> print(created.body["item"]["api_key"])
        """
        body: dict[str, Any] = {"policy_id": policy_id}
        if name is not None:
            body["name"] = name
        if expiration is not None:
            body["expiration"] = expiration

        path = self._build_space_path(
            "/api/fleet/enrollment_api_keys", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_key(
        self,
        *,
        key_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an enrollment API key.

        Gets an enrollment API key by ID. Requires the ``fleet-agents-all``
        or ``fleet-setup`` privilege.

        Args:
            key_id: The ID of the enrollment API key.
            space_id: Optional space ID to get the enrollment API key from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the enrollment API key under
            ``item`` (``id``, ``api_key_id``, ``api_key``, ``name``,
            ``policy_id``, ``active``, ``created_at``, ``hidden``).

        Raises:
            NotFoundError: If no enrollment API key exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> key = client.fleet_enrollment.get_key(key_id="key-id-1")
            >>> print(key.body["item"]["policy_id"])
        """
        path = self._build_space_path(
            f"/api/fleet/enrollment_api_keys/{_quote(key_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def delete_key(
        self,
        *,
        key_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Revoke an enrollment API key.

        Revokes an enrollment API key by ID by marking it as inactive. The
        key is not removed, but it can no longer be used to enroll Elastic
        Agents. Requires the ``fleet-agents-all`` privilege.

        Args:
            key_id: The ID of the enrollment API key.
            space_id: Optional space ID to revoke the enrollment API key in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``{"action": "deleted"}`` on
            success.

        Raises:
            NotFoundError: If no enrollment API key exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.fleet_enrollment.delete_key(key_id="key-id-1")
            >>> print(result.body["action"])
            deleted
        """
        path = self._build_space_path(
            f"/api/fleet/enrollment_api_keys/{_quote(key_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    def create_service_token(
        self,
        *,
        remote: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a service token.

        Creates a Fleet Server service token. The token is used to enroll
        Fleet Server instances with Kibana. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            remote: When True, generates a token for a remote Fleet Server
                (service account ``elastic/fleet-server-remote``) instead of
                the default ``elastic/fleet-server`` account.
            space_id: Optional space ID to create the service token in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - name: The name of the generated service token
                - value: The service token secret value

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> token = client.fleet_enrollment.create_service_token()
            >>> print(token.body["name"], token.body["value"])
        """
        body: dict[str, Any] | None = None
        if remote is not None:
            body = {"remote": remote}

        path = self._build_space_path(
            "/api/fleet/service_tokens", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def create_logstash_api_key(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Generate a Logstash API key.

        Generates an Elasticsearch API key for Logstash to use with a Fleet
        Logstash output (the ``logstash-output`` permission set). Requires
        the ``fleet-settings-all`` privilege.

        Args:
            space_id: Optional space ID to generate the API key in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the generated key under ``api_key``
            in the ``id:secret`` format expected by the Logstash
            ``elastic_agent`` input.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> key = client.fleet_enrollment.create_logstash_api_key()
            >>> print(key.body["api_key"])
        """
        path = self._build_space_path(
            "/api/fleet/logstash_api_keys", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    def get_uninstall_tokens(
        self,
        *,
        policy_id: str | None = None,
        search: str | None = None,
        per_page: int | None = None,
        page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get metadata for the latest uninstall tokens.

        Lists the metadata for the latest uninstall tokens per agent policy.
        Uninstall tokens are required to uninstall tamper-protected Elastic
        Agents. Token values are not included; use
        :meth:`get_uninstall_token` to get a decrypted token. Requires the
        ``fleet-agents-all`` privilege.

        Note: ``policy_id`` and ``search`` cannot be used at the same time.

        Args:
            policy_id: Partial match filtering for policy IDs (max length
                50).
            search: Partial match filtering for uninstall token values (max
                length 50).
            per_page: The number of items to return (minimum 5).
            page: Page number (minimum 1).
            space_id: Optional space ID to list uninstall tokens from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: List of token metadata (``id``, ``policy_id``,
                  ``policy_name``, ``created_at``, ``namespaces``)
                - total / page / perPage: pagination metadata

        Raises:
            BadRequestError: If both ``policy_id`` and ``search`` are
                provided, or the parameters are otherwise invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> tokens = client.fleet_enrollment.get_uninstall_tokens()
            >>> for token in tokens.body["items"]:
            ...     print(token["id"], token["policy_id"])
        """
        params: dict[str, Any] = {}
        if policy_id is not None:
            params["policyId"] = policy_id
        if search is not None:
            params["search"] = search
        if per_page is not None:
            params["perPage"] = per_page
        if page is not None:
            params["page"] = page

        path = self._build_space_path(
            "/api/fleet/uninstall_tokens", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def get_uninstall_token(
        self,
        *,
        uninstall_token_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a decrypted uninstall token.

        Gets one decrypted uninstall token by its ID. The returned ``token``
        value can be used to uninstall a tamper-protected Elastic Agent
        enrolled in the token's agent policy. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            uninstall_token_id: The ID of the uninstall token.
            space_id: Optional space ID to get the uninstall token from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the decrypted token under ``item``
            (``id``, ``policy_id``, ``policy_name``, ``token``,
            ``created_at``, ``namespaces``).

        Raises:
            NotFoundError: If no uninstall token exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> token = client.fleet_enrollment.get_uninstall_token(
            ...     uninstall_token_id="token-id-1"
            ... )
            >>> print(token.body["item"]["token"])
        """
        path = self._build_space_path(
            f"/api/fleet/uninstall_tokens/{_quote(uninstall_token_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def rotate_message_signing_key_pair(
        self,
        *,
        acknowledge: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Rotate the Fleet message signing key pair.

        Rotates the key pair used by Fleet to sign messages sent to Elastic
        Agents. This operation is irreversible and requires all agents in
        the Fleet to be re-enrolled after rotation. You must explicitly
        acknowledge the risk by passing ``acknowledge=True``; the server
        rejects the request with a 400 warning otherwise. Requires the
        ``fleet-agents-all``, ``fleet-agent-policies-all`` and
        ``fleet-settings-all`` privileges.

        Args:
            acknowledge: Set to True to confirm you understand the risks of
                rotating the key pair (default: False, which is rejected).
            space_id: Optional space ID to perform the rotation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing a confirmation ``message``
            (``"Key pair rotated successfully."``).

        Raises:
            BadRequestError: If ``acknowledge`` is not set to True.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            ApiError: If the message signing service is unavailable (500).
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.fleet_enrollment.rotate_message_signing_key_pair(
            ...     acknowledge=True
            ... )
            >>> print(result.body["message"])
            Key pair rotated successfully.
        """
        params: dict[str, Any] = {}
        if acknowledge is not None:
            params["acknowledge"] = acknowledge

        path = self._build_space_path(
            "/api/fleet/message_signing_service/rotate_key_pair",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def get_kubernetes_manifest(
        self,
        *,
        download: bool | None = None,
        fleet_server: str | None = None,
        enrol_token: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a full Kubernetes agent manifest.

        Gets the Kubernetes manifest for deploying Elastic Agent as a
        DaemonSet, as a JSON object with the YAML document under ``item``.
        Requires the ``fleet-agent-policies-read`` or ``fleet-setup``
        privilege.

        Args:
            download: If True, returns the manifest as a downloadable file.
            fleet_server: Fleet Server host URL to include in the manifest
                (substituted for the ``FLEET_URL`` placeholder).
            enrol_token: Enrollment token to include in the manifest
                (substituted for the ``FLEET_ENROLLMENT_TOKEN`` placeholder).
            space_id: Optional space ID to get the manifest from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the manifest YAML string under
            ``item``.

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> manifest = client.fleet_enrollment.get_kubernetes_manifest(
            ...     fleet_server="https://fleet.example.com:8220",
            ...     enrol_token="my-enrollment-token",
            ... )
            >>> print(manifest.body["item"][:22])
        """
        params: dict[str, Any] = {}
        if download is not None:
            params["download"] = download
        if fleet_server is not None:
            params["fleetServer"] = fleet_server
        if enrol_token is not None:
            params["enrolToken"] = enrol_token

        path = self._build_space_path(
            "/api/fleet/kubernetes", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def download_kubernetes_manifest(
        self,
        *,
        download: bool | None = None,
        fleet_server: str | None = None,
        enrol_token: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Download a Kubernetes agent manifest.

        Downloads the Kubernetes manifest for deploying Elastic Agent as a
        raw YAML document (content type ``text/x-yaml``); the response body
        is the YAML string itself. Requires the ``fleet-agent-policies-read``
        or ``fleet-setup`` privilege.

        Args:
            download: If True, returns the manifest as a downloadable file.
            fleet_server: Fleet Server host URL to include in the manifest
                (substituted for the ``FLEET_URL`` placeholder).
            enrol_token: Enrollment token to include in the manifest
                (substituted for the ``FLEET_ENROLLMENT_TOKEN`` placeholder).
            space_id: Optional space ID to download the manifest from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            Response whose ``body`` is the manifest YAML document as a
            string.

        Raises:
            BadRequestError: If the query parameters are invalid.
            NotFoundError: If no manifest is found.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> manifest = client.fleet_enrollment.download_kubernetes_manifest()
            >>> yaml_text = manifest.body
            >>> print(yaml_text.splitlines()[0])
            ---
        """
        params: dict[str, Any] = {}
        if download is not None:
            params["download"] = download
        if fleet_server is not None:
            params["fleetServer"] = fleet_server
        if enrol_token is not None:
            params["enrolToken"] = enrol_token

        path = self._build_space_path(
            "/api/fleet/kubernetes/download", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "text/x-yaml"},
        )
