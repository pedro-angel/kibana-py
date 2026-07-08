"""Kibana Security Detections (detection engine) API client."""

import json
import uuid
from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


def _ndjson_bytes(file: bytes | str | list[dict[str, Any]]) -> bytes:
    """Normalize an import payload to NDJSON bytes.

    Accepts raw ``bytes``/``str`` (e.g. the body returned by the export API)
    or a list of rule dicts, which are encoded one-JSON-per-line.

    :param file: NDJSON content as bytes/str, or a list of objects to encode
    :return: NDJSON-encoded bytes
    """
    if isinstance(file, bytes):
        return file
    if isinstance(file, str):
        return file.encode("utf-8")
    return ("\n".join(json.dumps(obj) for obj in file) + "\n").encode("utf-8")


def _build_multipart_body(
    file: bytes,
    *,
    filename: str = "import.ndjson",
) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for the rules import API.

    :param file: NDJSON file content for the ``file`` form field
    :param filename: Filename advertised for the uploaded file part
    :return: Tuple of (body bytes, content-type header value with boundary)
    """
    boundary = f"kbnpy{uuid.uuid4().hex}"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/ndjson\r\n"
            "\r\n"
        ).encode()
        + file
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


def _build_rule_body(
    *,
    type: str | None = None,
    name: str | None = None,
    description: str | None = None,
    severity: str | None = None,
    risk_score: int | None = None,
    id: str | None = None,
    rule_id: str | None = None,
    actions: list[dict[str, Any]] | None = None,
    alert_suppression: dict[str, Any] | None = None,
    alias_purpose: str | None = None,
    alias_target_id: str | None = None,
    anomaly_threshold: int | None = None,
    author: list[str] | None = None,
    building_block_type: str | None = None,
    concurrent_searches: int | None = None,
    data_view_id: str | None = None,
    enabled: bool | None = None,
    event_category_override: str | None = None,
    exceptions_list: list[dict[str, Any]] | None = None,
    false_positives: list[str] | None = None,
    filters: list[Any] | None = None,
    from_: str | None = None,
    history_window_start: str | None = None,
    index: list[str] | None = None,
    interval: str | None = None,
    investigation_fields: dict[str, Any] | None = None,
    items_per_search: int | None = None,
    language: str | None = None,
    license: str | None = None,
    machine_learning_job_id: str | list[str] | None = None,
    max_signals: int | None = None,
    meta: dict[str, Any] | None = None,
    namespace: str | None = None,
    new_terms_fields: list[str] | None = None,
    note: str | None = None,
    outcome: str | None = None,
    output_index: str | None = None,
    query: str | None = None,
    references: list[str] | None = None,
    related_integrations: list[dict[str, Any]] | None = None,
    required_fields: list[dict[str, Any]] | None = None,
    response_actions: list[dict[str, Any]] | None = None,
    risk_score_mapping: list[dict[str, Any]] | None = None,
    rule_name_override: str | None = None,
    saved_id: str | None = None,
    setup: str | None = None,
    severity_mapping: list[dict[str, Any]] | None = None,
    tags: list[str] | None = None,
    threat: list[dict[str, Any]] | None = None,
    threat_filters: list[Any] | None = None,
    threat_index: list[str] | None = None,
    threat_indicator_path: str | None = None,
    threat_language: str | None = None,
    threat_mapping: list[dict[str, Any]] | None = None,
    threat_query: str | None = None,
    threshold: dict[str, Any] | None = None,
    throttle: str | None = None,
    tiebreaker_field: str | None = None,
    timeline_id: str | None = None,
    timeline_title: str | None = None,
    timestamp_field: str | None = None,
    timestamp_override: str | None = None,
    timestamp_override_fallback_disabled: bool | None = None,
    to: str | None = None,
    version: int | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a detection-rule request body from rule-definition kwargs.

    Only keys whose value is not ``None`` are included. ``from_`` is mapped
    to the ``from`` body key (reserved word in Python). ``fields`` is merged
    verbatim at the end so callers can pass spec fields that have no named
    parameter yet.

    :return: Request body dict for the rules create/update/patch/preview APIs
    """
    body: dict[str, Any] = {}
    values: dict[str, Any] = {
        "type": type,
        "name": name,
        "description": description,
        "severity": severity,
        "risk_score": risk_score,
        "id": id,
        "rule_id": rule_id,
        "actions": actions,
        "alert_suppression": alert_suppression,
        "alias_purpose": alias_purpose,
        "alias_target_id": alias_target_id,
        "anomaly_threshold": anomaly_threshold,
        "author": author,
        "building_block_type": building_block_type,
        "concurrent_searches": concurrent_searches,
        "data_view_id": data_view_id,
        "enabled": enabled,
        "event_category_override": event_category_override,
        "exceptions_list": exceptions_list,
        "false_positives": false_positives,
        "filters": filters,
        "from": from_,
        "history_window_start": history_window_start,
        "index": index,
        "interval": interval,
        "investigation_fields": investigation_fields,
        "items_per_search": items_per_search,
        "language": language,
        "license": license,
        "machine_learning_job_id": machine_learning_job_id,
        "max_signals": max_signals,
        "meta": meta,
        "namespace": namespace,
        "new_terms_fields": new_terms_fields,
        "note": note,
        "outcome": outcome,
        "output_index": output_index,
        "query": query,
        "references": references,
        "related_integrations": related_integrations,
        "required_fields": required_fields,
        "response_actions": response_actions,
        "risk_score_mapping": risk_score_mapping,
        "rule_name_override": rule_name_override,
        "saved_id": saved_id,
        "setup": setup,
        "severity_mapping": severity_mapping,
        "tags": tags,
        "threat": threat,
        "threat_filters": threat_filters,
        "threat_index": threat_index,
        "threat_indicator_path": threat_indicator_path,
        "threat_language": threat_language,
        "threat_mapping": threat_mapping,
        "threat_query": threat_query,
        "threshold": threshold,
        "throttle": throttle,
        "tiebreaker_field": tiebreaker_field,
        "timeline_id": timeline_id,
        "timeline_title": timeline_title,
        "timestamp_field": timestamp_field,
        "timestamp_override": timestamp_override,
        "timestamp_override_fallback_disabled": timestamp_override_fallback_disabled,
        "to": to,
        "version": version,
    }
    for key, value in values.items():
        if value is not None:
            body[key] = value
    if fields:
        body.update(fields)
    return body


class DetectionEngineClient(NamespaceClient):
    """Client for the Kibana Security Detections API.

    Manages Elastic Security detection rules (create, read, update, delete,
    find, bulk actions, preview, export/import, prebuilt rule installation),
    detection alerts -- also called *signals* -- (search, status, tags,
    assignees, legacy signals migrations) and the ``.alerts-security.alerts``
    index for a Kibana space.

    All Security Detections APIs are space-scoped: rules and alerts live in
    the space they were created in. Every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Note: the rule-exceptions endpoint
    ``POST /api/detection_engine/rules/{id}/exceptions`` is exposed on the
    ``exception_lists`` namespace, not here.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a custom query rule and find it
        >>> rule = client.detection_engine.create_rule(
        ...     type="query",
        ...     name="Suspicious login",
        ...     description="Detects suspicious logins",
        ...     severity="low",
        ...     risk_score=21,
        ...     query='user.name: "suspicious"',
        ...     index=["logs-*"],
        ... )
        >>> found = client.detection_engine.find_rules(
        ...     filter='alert.attributes.name: "Suspicious login"'
        ... )
        >>> client.detection_engine.delete_rule(id=rule.body["id"])
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the DetectionEngineClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> detection_engine_client = DetectionEngineClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Privileges and alerts index
    # ------------------------------------------------------------------

    def get_privileges(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get detection-engine privileges for the current user.

        ``GET /api/detection_engine/privileges``. Retrieves whether or not
        the user is authenticated, and the user's Kibana space and index
        privileges, which determine if the user can create an index for the
        Elastic Security alerts generated by detection rules.

        Args:
            space_id: Optional space ID to check privileges in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``username``, ``has_all_requested``,
            ``cluster`` and ``index`` privilege maps, ``is_authenticated``
            and ``has_encryption_key``.

        Raises:
            AuthenticationException: If authentication fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> privileges = client.detection_engine.get_privileges()
            >>> print(privileges.body["is_authenticated"])
            True
        """
        path = self._build_space_path(
            "/api/detection_engine/privileges", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def create_alerts_index(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an alerts index.

        ``POST /api/detection_engine/index``. Creates the
        ``.alerts-security.alerts-<space>`` index (alias) for detection
        alerts in the target space, if it does not already exist. The call
        is idempotent: it acknowledges even when the index already exists.

        Args:
            space_id: Optional space ID to create the alerts index for.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``{"acknowledged": true}`` on success.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient index privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.detection_engine.create_alerts_index()
            >>> print(result.body["acknowledged"])
            True
        """
        path = self._build_space_path(
            "/api/detection_engine/index", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    def get_alerts_index(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Read the alerts index name.

        ``GET /api/detection_engine/index``. Reads the name of the alerts
        index for the target space (e.g.
        ``.alerts-security.alerts-default``) if it exists.

        Args:
            space_id: Optional space ID to read the alerts index for.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the index ``name`` and
            ``index_mapping_outdated``.

        Raises:
            NotFoundError: If the alerts index does not exist.
            AuthenticationException: If authentication fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> index = client.detection_engine.get_alerts_index()
            >>> print(index.body["name"])
            .alerts-security.alerts-default
        """
        path = self._build_space_path(
            "/api/detection_engine/index", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def delete_alerts_index(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an alerts index.

        ``DELETE /api/detection_engine/index``. Deletes the alerts index for
        the target space.

        Note: on Kibana 9.4.3 this endpoint only removes legacy
        ``.siem-signals-<space>`` indices; when only the modern
        ``.alerts-security.alerts-<space>`` alias exists the server responds
        404 (``index: ".siem-signals-<space>" does not exist``).

        Args:
            space_id: Optional space ID to delete the alerts index for.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``{"acknowledged": true}`` on success.

        Raises:
            NotFoundError: If no deletable alerts index exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient index privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.detection_engine.delete_alerts_index(
            ...     space_id="my-space"
            ... )
        """
        path = self._build_space_path(
            "/api/detection_engine/index", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Rules CRUD
    # ------------------------------------------------------------------

    def create_rule(
        self,
        *,
        type: str,
        name: str,
        description: str,
        severity: str,
        risk_score: int,
        rule_id: str | None = None,
        actions: list[dict[str, Any]] | None = None,
        alert_suppression: dict[str, Any] | None = None,
        anomaly_threshold: int | None = None,
        author: list[str] | None = None,
        building_block_type: str | None = None,
        concurrent_searches: int | None = None,
        data_view_id: str | None = None,
        enabled: bool | None = None,
        event_category_override: str | None = None,
        exceptions_list: list[dict[str, Any]] | None = None,
        false_positives: list[str] | None = None,
        filters: list[Any] | None = None,
        from_: str | None = None,
        history_window_start: str | None = None,
        index: list[str] | None = None,
        interval: str | None = None,
        investigation_fields: dict[str, Any] | None = None,
        items_per_search: int | None = None,
        language: str | None = None,
        license: str | None = None,
        machine_learning_job_id: str | list[str] | None = None,
        max_signals: int | None = None,
        meta: dict[str, Any] | None = None,
        namespace: str | None = None,
        new_terms_fields: list[str] | None = None,
        note: str | None = None,
        output_index: str | None = None,
        query: str | None = None,
        references: list[str] | None = None,
        related_integrations: list[dict[str, Any]] | None = None,
        required_fields: list[dict[str, Any]] | None = None,
        response_actions: list[dict[str, Any]] | None = None,
        risk_score_mapping: list[dict[str, Any]] | None = None,
        rule_name_override: str | None = None,
        saved_id: str | None = None,
        setup: str | None = None,
        severity_mapping: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        threat: list[dict[str, Any]] | None = None,
        threat_filters: list[Any] | None = None,
        threat_index: list[str] | None = None,
        threat_indicator_path: str | None = None,
        threat_language: str | None = None,
        threat_mapping: list[dict[str, Any]] | None = None,
        threat_query: str | None = None,
        threshold: dict[str, Any] | None = None,
        throttle: str | None = None,
        tiebreaker_field: str | None = None,
        timeline_id: str | None = None,
        timeline_title: str | None = None,
        timestamp_field: str | None = None,
        timestamp_override: str | None = None,
        timestamp_override_fallback_disabled: bool | None = None,
        to: str | None = None,
        version: int | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a detection rule.

        ``POST /api/detection_engine/rules``. Creates a new detection rule
        of type ``query``, ``saved_query``, ``eql``, ``esql``, ``threshold``,
        ``threat_match``, ``machine_learning`` or ``new_terms``. Required
        type-specific fields differ per type: ``query``/``language`` for EQL
        and ES|QL rules, ``saved_id`` for saved-query rules, ``threshold``
        for threshold rules, ``threat_index``/``threat_query``/
        ``threat_mapping`` for indicator-match rules,
        ``machine_learning_job_id``/``anomaly_threshold`` for ML rules and
        ``new_terms_fields``/``history_window_start`` for new-terms rules.

        Args:
            type: Rule type: ``query``, ``saved_query``, ``eql``, ``esql``,
                ``threshold``, ``threat_match``, ``machine_learning`` or
                ``new_terms``.
            name: A human-readable name for the rule.
            description: The rule's description.
            severity: Severity level of alerts produced by the rule:
                ``low``, ``medium``, ``high`` or ``critical``.
            risk_score: A numerical representation of the alert's severity
                from 0 to 100.
            rule_id: A stable unique identifier for the rule object (used
                across Kibana instances; distinct from the object ``id``).
                Generated by Kibana when unspecified.
            actions: Actions to perform when the rule fires.
            alert_suppression: Alert suppression configuration (e.g.
                ``{"group_by": ["host.name"]}``).
            anomaly_threshold: Anomaly score threshold above which alerts
                are created (``machine_learning`` rules only).
            author: The rule's author(s).
            building_block_type: Set to ``default`` to mark alerts from this
                rule as building-block alerts.
            concurrent_searches: Number of concurrent threat-indicator
                searches (``threat_match`` rules only).
            data_view_id: Data view ID the rule runs against (cannot be
                combined with ``index``).
            enabled: Whether the rule is enabled on creation.
            event_category_override: EQL event category field override
                (``eql`` rules only).
            exceptions_list: Exception containers associated with the rule
                (``id``, ``list_id``, ``namespace_type``, ``type``).
            false_positives: Common reasons why the rule may issue
                false-positive alerts.
            filters: Query and filter context array (Query DSL filters) used
                to define rule conditions.
            from_: Time from which data is analyzed each rule execution
                (date math, e.g. ``"now-6m"``). Sent as the ``from`` body
                field.
            history_window_start: Start date for the new-terms history
                window (``new_terms`` rules only).
            index: Indices the rule runs against.
            interval: Frequency of rule execution (e.g. ``"5m"``).
            investigation_fields: Fields highlighted during investigation
                (e.g. ``{"field_names": ["host.name"]}``).
            items_per_search: Number of documents per threat-indicator
                search (``threat_match`` rules only).
            language: Query language: ``kuery``, ``lucene``, ``eql`` or
                ``esql`` depending on the rule type.
            license: The rule's license.
            machine_learning_job_id: Anomaly-detection job ID(s)
                (``machine_learning`` rules only).
            max_signals: Maximum number of alerts the rule can create per
                execution (default 100).
            meta: Placeholder for metadata about the rule; unvalidated and
                overwritten on each update.
            namespace: Alerts index namespace (has no effect on 9.x; alerts
                are written to the space-aware index).
            new_terms_fields: Fields containing the new terms
                (``new_terms`` rules only).
            note: Notes to help investigate alerts produced by the rule.
            output_index: (deprecated) Has no effect; alerts are written to
                the space-aware ``.alerts-security.alerts-<space>`` index.
            query: The query the rule runs (KQL/Lucene/EQL/ES|QL depending
                on ``type``/``language``).
            references: References to information relevant to the rule.
            related_integrations: Related integrations for the rule
                (``package``, ``version``, optional ``integration``).
            required_fields: ECS fields the rule needs to function.
            response_actions: Response actions to run when the rule fires
                (e.g. Osquery or Endpoint actions).
            risk_score_mapping: Overrides that map source-event field values
                to risk scores.
            rule_name_override: Source-event field used to override the
                rule's name in alerts.
            saved_id: Saved-query ID the rule runs (required for
                ``saved_query`` rules).
            setup: Setup guide with instructions on rule prerequisites.
            severity_mapping: Overrides that map source-event field values
                to severities.
            tags: String array used to organize rules.
            threat: MITRE ATT&CK framework threat information.
            threat_filters: Query DSL filters applied to the threat-indicator
                index (``threat_match`` rules only).
            threat_index: Threat-indicator indices (``threat_match`` rules
                only).
            threat_indicator_path: Path to the threat-indicator object
                (``threat_match`` rules only).
            threat_language: Query language for ``threat_query``
                (``threat_match`` rules only).
            threat_mapping: Field mappings between source events and threat
                indicators (``threat_match`` rules only).
            threat_query: Query run against the threat-indicator index
                (``threat_match`` rules only).
            threshold: Threshold configuration (``field``, ``value``,
                optional ``cardinality``; ``threshold`` rules only).
            throttle: (deprecated) Action frequency shorthand; use the
                per-action ``frequency`` object instead.
            tiebreaker_field: Tiebreaker field for EQL sequences (``eql``
                rules only).
            timeline_id: Timeline template ID used when investigating
                alerts.
            timeline_title: Timeline template title (required when
                ``timeline_id`` is set).
            timestamp_field: Timestamp field for event ordering (``eql``
                rules only).
            timestamp_override: Field used instead of ``@timestamp`` when
                executing the rule.
            timestamp_override_fallback_disabled: Disable fallback to
                ``@timestamp`` when the override field is missing.
            to: End of the time range analyzed each execution (date math,
                default ``"now"``).
            version: The rule's version number (defaults to 1).
            fields: Additional body fields merged into the request verbatim,
                for spec fields without a named parameter.
            space_id: Optional space ID to create the rule in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created rule, including its generated
            ``id`` and ``rule_id``.

        Raises:
            BadRequestError: If the rule definition is invalid.
            ConflictError: If a rule with the same ``rule_id`` exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> rule = client.detection_engine.create_rule(
            ...     type="query",
            ...     name="Suspicious login",
            ...     description="Detects suspicious logins",
            ...     severity="low",
            ...     risk_score=21,
            ...     query='user.name: "suspicious"',
            ...     index=["logs-*"],
            ...     interval="10m",
            ...     from_="now-20m",
            ... )
            >>> print(rule.body["rule_id"])
        """
        body = _build_rule_body(
            type=type,
            name=name,
            description=description,
            severity=severity,
            risk_score=risk_score,
            rule_id=rule_id,
            actions=actions,
            alert_suppression=alert_suppression,
            anomaly_threshold=anomaly_threshold,
            author=author,
            building_block_type=building_block_type,
            concurrent_searches=concurrent_searches,
            data_view_id=data_view_id,
            enabled=enabled,
            event_category_override=event_category_override,
            exceptions_list=exceptions_list,
            false_positives=false_positives,
            filters=filters,
            from_=from_,
            history_window_start=history_window_start,
            index=index,
            interval=interval,
            investigation_fields=investigation_fields,
            items_per_search=items_per_search,
            language=language,
            license=license,
            machine_learning_job_id=machine_learning_job_id,
            max_signals=max_signals,
            meta=meta,
            namespace=namespace,
            new_terms_fields=new_terms_fields,
            note=note,
            output_index=output_index,
            query=query,
            references=references,
            related_integrations=related_integrations,
            required_fields=required_fields,
            response_actions=response_actions,
            risk_score_mapping=risk_score_mapping,
            rule_name_override=rule_name_override,
            saved_id=saved_id,
            setup=setup,
            severity_mapping=severity_mapping,
            tags=tags,
            threat=threat,
            threat_filters=threat_filters,
            threat_index=threat_index,
            threat_indicator_path=threat_indicator_path,
            threat_language=threat_language,
            threat_mapping=threat_mapping,
            threat_query=threat_query,
            threshold=threshold,
            throttle=throttle,
            tiebreaker_field=tiebreaker_field,
            timeline_id=timeline_id,
            timeline_title=timeline_title,
            timestamp_field=timestamp_field,
            timestamp_override=timestamp_override,
            timestamp_override_fallback_disabled=timestamp_override_fallback_disabled,
            to=to,
            version=version,
            fields=fields,
        )
        path = self._build_space_path(
            "/api/detection_engine/rules", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_rule(
        self,
        *,
        id: str | None = None,
        rule_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Retrieve a detection rule.

        ``GET /api/detection_engine/rules``. Retrieves a detection rule by
        its object ``id`` or its stable ``rule_id``; exactly one of the two
        must be provided.

        Args:
            id: The rule's object identifier (UUID generated by Kibana).
            rule_id: The rule's stable signature identifier.
            space_id: Optional space ID to read the rule from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the rule.

        Raises:
            ValueError: If neither or both of ``id`` and ``rule_id`` are
                given.
            NotFoundError: If the rule does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> rule = client.detection_engine.get_rule(rule_id="my-rule")
            >>> print(rule.body["name"])
        """
        if (id is None) == (rule_id is None):
            raise ValueError("Exactly one of 'id' or 'rule_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if rule_id is not None:
            params["rule_id"] = rule_id

        path = self._build_space_path(
            "/api/detection_engine/rules", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def update_rule(
        self,
        *,
        type: str,
        name: str,
        description: str,
        severity: str,
        risk_score: int,
        id: str | None = None,
        rule_id: str | None = None,
        actions: list[dict[str, Any]] | None = None,
        alert_suppression: dict[str, Any] | None = None,
        anomaly_threshold: int | None = None,
        author: list[str] | None = None,
        building_block_type: str | None = None,
        concurrent_searches: int | None = None,
        data_view_id: str | None = None,
        enabled: bool | None = None,
        event_category_override: str | None = None,
        exceptions_list: list[dict[str, Any]] | None = None,
        false_positives: list[str] | None = None,
        filters: list[Any] | None = None,
        from_: str | None = None,
        history_window_start: str | None = None,
        index: list[str] | None = None,
        interval: str | None = None,
        investigation_fields: dict[str, Any] | None = None,
        items_per_search: int | None = None,
        language: str | None = None,
        license: str | None = None,
        machine_learning_job_id: str | list[str] | None = None,
        max_signals: int | None = None,
        meta: dict[str, Any] | None = None,
        namespace: str | None = None,
        new_terms_fields: list[str] | None = None,
        note: str | None = None,
        output_index: str | None = None,
        query: str | None = None,
        references: list[str] | None = None,
        related_integrations: list[dict[str, Any]] | None = None,
        required_fields: list[dict[str, Any]] | None = None,
        response_actions: list[dict[str, Any]] | None = None,
        risk_score_mapping: list[dict[str, Any]] | None = None,
        rule_name_override: str | None = None,
        saved_id: str | None = None,
        setup: str | None = None,
        severity_mapping: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        threat: list[dict[str, Any]] | None = None,
        threat_filters: list[Any] | None = None,
        threat_index: list[str] | None = None,
        threat_indicator_path: str | None = None,
        threat_language: str | None = None,
        threat_mapping: list[dict[str, Any]] | None = None,
        threat_query: str | None = None,
        threshold: dict[str, Any] | None = None,
        throttle: str | None = None,
        tiebreaker_field: str | None = None,
        timeline_id: str | None = None,
        timeline_title: str | None = None,
        timestamp_field: str | None = None,
        timestamp_override: str | None = None,
        timestamp_override_fallback_disabled: bool | None = None,
        to: str | None = None,
        version: int | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a detection rule (full replacement).

        ``PUT /api/detection_engine/rules``. Updates a detection rule using
        the ``id`` or ``rule_id`` field; one of the two must be provided.
        The whole rule definition is replaced: any field not supplied is
        reset to its default value (use :meth:`patch_rule` for partial
        updates).

        Args:
            type: Rule type (see :meth:`create_rule`).
            name: A human-readable name for the rule.
            description: The rule's description.
            severity: Severity level of alerts produced by the rule.
            risk_score: A numerical representation of the alert's severity
                from 0 to 100.
            id: The rule's object identifier. Either ``id`` or ``rule_id``
                must be provided.
            rule_id: The rule's stable signature identifier.
            fields: Additional body fields merged into the request verbatim.
            space_id: Optional space ID the rule lives in.
            validate_spaces: Override space validation setting for this
                operation.

        All remaining keyword arguments are the rule-definition fields
        documented on :meth:`create_rule` and map one-to-one to the 9.4.3
        ``RuleUpdateProps`` body fields (``from_`` is sent as ``from``).

        Returns:
            ObjectApiResponse with the updated rule.

        Raises:
            ValueError: If neither ``id`` nor ``rule_id`` is given.
            NotFoundError: If the rule does not exist.
            BadRequestError: If the rule definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.detection_engine.update_rule(
            ...     rule_id="my-rule",
            ...     type="query",
            ...     name="Suspicious login (updated)",
            ...     description="Now with a better query",
            ...     severity="medium",
            ...     risk_score=47,
            ...     query='user.name: "suspicious" and event.outcome: failure',
            ... )
        """
        if id is None and rule_id is None:
            raise ValueError("Either 'id' or 'rule_id' must be provided")

        body = _build_rule_body(
            type=type,
            name=name,
            description=description,
            severity=severity,
            risk_score=risk_score,
            id=id,
            rule_id=rule_id,
            actions=actions,
            alert_suppression=alert_suppression,
            anomaly_threshold=anomaly_threshold,
            author=author,
            building_block_type=building_block_type,
            concurrent_searches=concurrent_searches,
            data_view_id=data_view_id,
            enabled=enabled,
            event_category_override=event_category_override,
            exceptions_list=exceptions_list,
            false_positives=false_positives,
            filters=filters,
            from_=from_,
            history_window_start=history_window_start,
            index=index,
            interval=interval,
            investigation_fields=investigation_fields,
            items_per_search=items_per_search,
            language=language,
            license=license,
            machine_learning_job_id=machine_learning_job_id,
            max_signals=max_signals,
            meta=meta,
            namespace=namespace,
            new_terms_fields=new_terms_fields,
            note=note,
            output_index=output_index,
            query=query,
            references=references,
            related_integrations=related_integrations,
            required_fields=required_fields,
            response_actions=response_actions,
            risk_score_mapping=risk_score_mapping,
            rule_name_override=rule_name_override,
            saved_id=saved_id,
            setup=setup,
            severity_mapping=severity_mapping,
            tags=tags,
            threat=threat,
            threat_filters=threat_filters,
            threat_index=threat_index,
            threat_indicator_path=threat_indicator_path,
            threat_language=threat_language,
            threat_mapping=threat_mapping,
            threat_query=threat_query,
            threshold=threshold,
            throttle=throttle,
            tiebreaker_field=tiebreaker_field,
            timeline_id=timeline_id,
            timeline_title=timeline_title,
            timestamp_field=timestamp_field,
            timestamp_override=timestamp_override,
            timestamp_override_fallback_disabled=timestamp_override_fallback_disabled,
            to=to,
            version=version,
            fields=fields,
        )
        path = self._build_space_path(
            "/api/detection_engine/rules", space_id, validate_spaces
        )
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def patch_rule(
        self,
        *,
        id: str | None = None,
        rule_id: str | None = None,
        type: str | None = None,
        name: str | None = None,
        description: str | None = None,
        severity: str | None = None,
        risk_score: int | None = None,
        actions: list[dict[str, Any]] | None = None,
        alert_suppression: dict[str, Any] | None = None,
        anomaly_threshold: int | None = None,
        author: list[str] | None = None,
        building_block_type: str | None = None,
        concurrent_searches: int | None = None,
        data_view_id: str | None = None,
        enabled: bool | None = None,
        event_category_override: str | None = None,
        exceptions_list: list[dict[str, Any]] | None = None,
        false_positives: list[str] | None = None,
        filters: list[Any] | None = None,
        from_: str | None = None,
        history_window_start: str | None = None,
        index: list[str] | None = None,
        interval: str | None = None,
        investigation_fields: dict[str, Any] | None = None,
        items_per_search: int | None = None,
        language: str | None = None,
        license: str | None = None,
        machine_learning_job_id: str | list[str] | None = None,
        max_signals: int | None = None,
        meta: dict[str, Any] | None = None,
        namespace: str | None = None,
        new_terms_fields: list[str] | None = None,
        note: str | None = None,
        output_index: str | None = None,
        query: str | None = None,
        references: list[str] | None = None,
        related_integrations: list[dict[str, Any]] | None = None,
        required_fields: list[dict[str, Any]] | None = None,
        response_actions: list[dict[str, Any]] | None = None,
        risk_score_mapping: list[dict[str, Any]] | None = None,
        rule_name_override: str | None = None,
        saved_id: str | None = None,
        setup: str | None = None,
        severity_mapping: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        threat: list[dict[str, Any]] | None = None,
        threat_filters: list[Any] | None = None,
        threat_index: list[str] | None = None,
        threat_indicator_path: str | None = None,
        threat_language: str | None = None,
        threat_mapping: list[dict[str, Any]] | None = None,
        threat_query: str | None = None,
        threshold: dict[str, Any] | None = None,
        throttle: str | None = None,
        tiebreaker_field: str | None = None,
        timeline_id: str | None = None,
        timeline_title: str | None = None,
        timestamp_field: str | None = None,
        timestamp_override: str | None = None,
        timestamp_override_fallback_disabled: bool | None = None,
        to: str | None = None,
        version: int | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Patch a detection rule (partial update).

        ``PATCH /api/detection_engine/rules``. Updates specific fields of an
        existing detection rule using the ``id`` or ``rule_id`` field; one
        of the two must be provided. Only the supplied fields are changed.

        Note: on Kibana 9.4.3 patching the ``enabled`` field is rejected
        with 403 (``The current user does not have the permissions to edit
        the following fields: enabled``) even for superusers; toggle
        ``enabled`` through :meth:`update_rule` instead.

        Args:
            id: The rule's object identifier. Either ``id`` or ``rule_id``
                must be provided.
            rule_id: The rule's stable signature identifier.
            fields: Additional body fields merged into the request verbatim.
            space_id: Optional space ID the rule lives in.
            validate_spaces: Override space validation setting for this
                operation.

        All remaining keyword arguments are the rule-definition fields
        documented on :meth:`create_rule`; every one is optional here and
        maps one-to-one to the 9.4.3 ``RulePatchProps`` body fields
        (``from_`` is sent as ``from``).

        Returns:
            ObjectApiResponse with the patched rule.

        Raises:
            ValueError: If neither ``id`` nor ``rule_id`` is given.
            NotFoundError: If the rule does not exist.
            BadRequestError: If the patch payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> patched = client.detection_engine.patch_rule(
            ...     rule_id="my-rule",
            ...     tags=["triage", "linux"],
            ... )
        """
        if id is None and rule_id is None:
            raise ValueError("Either 'id' or 'rule_id' must be provided")

        body = _build_rule_body(
            type=type,
            name=name,
            description=description,
            severity=severity,
            risk_score=risk_score,
            id=id,
            rule_id=rule_id,
            actions=actions,
            alert_suppression=alert_suppression,
            anomaly_threshold=anomaly_threshold,
            author=author,
            building_block_type=building_block_type,
            concurrent_searches=concurrent_searches,
            data_view_id=data_view_id,
            enabled=enabled,
            event_category_override=event_category_override,
            exceptions_list=exceptions_list,
            false_positives=false_positives,
            filters=filters,
            from_=from_,
            history_window_start=history_window_start,
            index=index,
            interval=interval,
            investigation_fields=investigation_fields,
            items_per_search=items_per_search,
            language=language,
            license=license,
            machine_learning_job_id=machine_learning_job_id,
            max_signals=max_signals,
            meta=meta,
            namespace=namespace,
            new_terms_fields=new_terms_fields,
            note=note,
            output_index=output_index,
            query=query,
            references=references,
            related_integrations=related_integrations,
            required_fields=required_fields,
            response_actions=response_actions,
            risk_score_mapping=risk_score_mapping,
            rule_name_override=rule_name_override,
            saved_id=saved_id,
            setup=setup,
            severity_mapping=severity_mapping,
            tags=tags,
            threat=threat,
            threat_filters=threat_filters,
            threat_index=threat_index,
            threat_indicator_path=threat_indicator_path,
            threat_language=threat_language,
            threat_mapping=threat_mapping,
            threat_query=threat_query,
            threshold=threshold,
            throttle=throttle,
            tiebreaker_field=tiebreaker_field,
            timeline_id=timeline_id,
            timeline_title=timeline_title,
            timestamp_field=timestamp_field,
            timestamp_override=timestamp_override,
            timestamp_override_fallback_disabled=timestamp_override_fallback_disabled,
            to=to,
            version=version,
            fields=fields,
        )
        path = self._build_space_path(
            "/api/detection_engine/rules", space_id, validate_spaces
        )
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_rule(
        self,
        *,
        id: str | None = None,
        rule_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a detection rule.

        ``DELETE /api/detection_engine/rules``. Deletes a detection rule by
        its object ``id`` or its stable ``rule_id``; exactly one of the two
        must be provided.

        Args:
            id: The rule's object identifier (UUID generated by Kibana).
            rule_id: The rule's stable signature identifier.
            space_id: Optional space ID to delete the rule from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the deleted rule.

        Raises:
            ValueError: If neither or both of ``id`` and ``rule_id`` are
                given.
            NotFoundError: If the rule does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.detection_engine.delete_rule(rule_id="my-rule")
        """
        if (id is None) == (rule_id is None):
            raise ValueError("Exactly one of 'id' or 'rule_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if rule_id is not None:
            params["rule_id"] = rule_id

        path = self._build_space_path(
            "/api/detection_engine/rules", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def find_rules(
        self,
        *,
        fields: list[str] | None = None,
        filter: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        gaps_range_start: str | None = None,
        gaps_range_end: str | None = None,
        gap_fill_statuses: list[str] | None = None,
        gap_auto_fill_scheduler_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List and paginate detection rules.

        ``GET /api/detection_engine/rules/_find``. Retrieves a paginated
        subset of detection rules; by default the first page with 20 rules
        sorted by creation date.

        Args:
            fields: Rule fields to return in the response.
            filter: KQL search filter over rule saved-object attributes,
                e.g. ``'alert.attributes.name: "My rule"'``.
            sort_field: Field to sort by (e.g. ``name``, ``enabled``,
                ``severity``, ``risk_score``, ``created_at``,
                ``updated_at``).
            sort_order: Sort order: ``asc`` or ``desc``.
            page: Page number (default 1).
            per_page: Rules per page (default 20).
            gaps_range_start: Gaps range start (used with gap filtering).
            gaps_range_end: Gaps range end (used with gap filtering).
            gap_fill_statuses: Filter rules with gaps by gap-fill status:
                ``unfilled``, ``in_progress``, ``filled`` or ``error``.
            gap_auto_fill_scheduler_id: Gap auto-fill scheduler ID used to
                determine gap-fill status.
            space_id: Optional space ID to search rules in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``page``, ``perPage``, ``total`` and the
            ``data`` array of rules.

        Raises:
            BadRequestError: If the filter or sort options are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = client.detection_engine.find_rules(
            ...     filter='alert.attributes.tags: "linux"',
            ...     sort_field="name",
            ...     sort_order="asc",
            ...     per_page=50,
            ... )
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if fields is not None:
            params["fields"] = fields
        if filter is not None:
            params["filter"] = filter
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if gaps_range_start is not None:
            params["gaps_range_start"] = gaps_range_start
        if gaps_range_end is not None:
            params["gaps_range_end"] = gaps_range_end
        if gap_fill_statuses is not None:
            params["gap_fill_statuses"] = gap_fill_statuses
        if gap_auto_fill_scheduler_id is not None:
            params["gap_auto_fill_scheduler_id"] = gap_auto_fill_scheduler_id

        path = self._build_space_path(
            "/api/detection_engine/rules/_find", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Rules bulk action, export/import, prepackaged, preview, tags
    # ------------------------------------------------------------------

    def bulk_action_rules(
        self,
        *,
        action: str,
        ids: list[str] | None = None,
        query: str | None = None,
        dry_run: bool | None = None,
        edit: list[dict[str, Any]] | None = None,
        duplicate: dict[str, Any] | None = None,
        run: dict[str, Any] | None = None,
        fill_gaps: dict[str, Any] | None = None,
        gaps_range_start: str | None = None,
        gaps_range_end: str | None = None,
        gap_fill_statuses: list[str] | None = None,
        gap_auto_fill_scheduler_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Apply a bulk action to detection rules.

        ``POST /api/detection_engine/rules/_bulk_action``. Applies
        ``enable``, ``disable``, ``delete``, ``duplicate``, ``export``,
        ``run``, ``fill_gaps`` or ``edit`` to multiple rules selected by
        ``ids`` or by a KQL ``query``. The edit action supports operations
        like adding/deleting tags or index patterns and changing schedules.

        Note: on Kibana 9.4.3 the ``export`` action responds with NDJSON
        (parsed to a list) instead of a JSON summary. On the tested stack
        the ``enable``, ``disable``, ``run`` and ``fill_gaps`` actions were
        rejected with ``USER_INSUFFICIENT_RULE_PRIVILEGES`` even for
        superusers; toggle ``enabled`` through :meth:`update_rule` instead.

        Args:
            action: Bulk action to apply: ``enable``, ``disable``,
                ``delete``, ``duplicate``, ``export``, ``run``,
                ``fill_gaps`` or ``edit``.
            ids: Array of rule object ``id``s (not ``rule_id``s) to apply
                the action to. Cannot be combined with ``query``.
            query: KQL query to select the rules to apply the action to.
            dry_run: Validate the action and report per-rule outcomes
                without applying it (sent as the ``dry_run`` query
                parameter; not supported for ``export``).
            edit: Array of edit operations (required for the ``edit``
                action), e.g. ``[{"type": "add_tags", "value": ["prod"]}]``.
            duplicate: Duplicate options (for the ``duplicate`` action):
                ``{"include_exceptions": bool,
                "include_expired_exceptions": bool}``.
            run: Manual-run window (required for the ``run`` action):
                ``{"start_date": ..., "end_date": ...}``.
            fill_gaps: Gap-fill window (required for the ``fill_gaps``
                action): ``{"start_date": ..., "end_date": ...}``.
            gaps_range_start: Gaps range start (gap filtering, with
                ``query``).
            gaps_range_end: Gaps range end (gap filtering, with ``query``).
            gap_fill_statuses: Filter rules with gaps by gap-fill status.
            gap_auto_fill_scheduler_id: Gap auto-fill scheduler ID used to
                determine gap-fill status.
            space_id: Optional space ID to apply the bulk action in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success``, ``rules_count`` and an
            ``attributes.results`` breakdown (``updated``, ``created``,
            ``deleted``, ``skipped``) -- or the NDJSON export payload for
            the ``export`` action.

        Raises:
            BadRequestError: If the bulk action payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.detection_engine.bulk_action_rules(
            ...     action="edit",
            ...     ids=[rule.body["id"]],
            ...     edit=[{"type": "add_tags", "value": ["kbnpy"]}],
            ... )
            >>> print(result.body["attributes"]["summary"])
        """
        body: dict[str, Any] = {"action": action}
        if ids is not None:
            body["ids"] = ids
        if query is not None:
            body["query"] = query
        if edit is not None:
            body["edit"] = edit
        if duplicate is not None:
            body["duplicate"] = duplicate
        if run is not None:
            body["run"] = run
        if fill_gaps is not None:
            body["fill_gaps"] = fill_gaps
        if gaps_range_start is not None:
            body["gaps_range_start"] = gaps_range_start
        if gaps_range_end is not None:
            body["gaps_range_end"] = gaps_range_end
        if gap_fill_statuses is not None:
            body["gap_fill_statuses"] = gap_fill_statuses
        if gap_auto_fill_scheduler_id is not None:
            body["gap_auto_fill_scheduler_id"] = gap_auto_fill_scheduler_id

        params: dict[str, Any] = {}
        if dry_run is not None:
            params["dry_run"] = dry_run

        path = self._build_space_path(
            "/api/detection_engine/rules/_bulk_action", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=body,
        )

    def export_rules(
        self,
        *,
        objects: list[dict[str, Any]] | None = None,
        exclude_export_details: bool | None = None,
        file_name: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Export detection rules as NDJSON.

        ``POST /api/detection_engine/rules/_export``. Exports detection
        rules to an NDJSON stream (one rule per line, plus an
        export-details line unless excluded). The parsed response body is a
        list of dicts that can be fed back to :meth:`import_rules`. Only
        custom rules can be exported; prebuilt rules are skipped.

        Args:
            objects: Array of ``{"rule_id": ...}`` descriptors selecting
                the rules to export (use the stable ``rule_id``, not the
                object ``id``). Exports **all** rules when omitted.
            exclude_export_details: Exclude the export-details line at the
                end of the stream (default False).
            file_name: File name for the exported file (sent as the
                ``file_name`` query parameter; default ``export.ndjson``).
            space_id: Optional space ID to export rules from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the parsed NDJSON list of
            exported rules (and the trailing export-details object unless
            excluded).

        Raises:
            BadRequestError: If the export request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> exported = client.detection_engine.export_rules(
            ...     objects=[{"rule_id": "my-rule"}],
            ...     exclude_export_details=True,
            ... )
            >>> print(len(list(exported)))
            1
        """
        params: dict[str, Any] = {}
        if exclude_export_details is not None:
            params["exclude_export_details"] = exclude_export_details
        if file_name is not None:
            params["file_name"] = file_name

        body: dict[str, Any] | None = None
        if objects is not None:
            body = {"objects": objects}

        path = self._build_space_path(
            "/api/detection_engine/rules/_export", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/ndjson"},
            body=body,
        )

    def import_rules(
        self,
        *,
        file: bytes | str | list[dict[str, Any]],
        overwrite: bool | None = None,
        overwrite_exceptions: bool | None = None,
        overwrite_action_connectors: bool | None = None,
        as_new_list: bool | None = None,
        filename: str = "import.ndjson",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Import detection rules from an NDJSON export file.

        ``POST /api/detection_engine/rules/_import``. Imports detection
        rules (and their associated exception lists and action connectors)
        from an NDJSON file uploaded as ``multipart/form-data``. Rules are
        matched by ``rule_id``; existing rules are only replaced when
        ``overwrite`` is True.

        Args:
            file: NDJSON export content: raw ``bytes``/``str``, or a list of
                rule dicts (e.g. the parsed body returned by
                :meth:`export_rules`), which is NDJSON-encoded
                automatically.
            overwrite: Overwrite existing rules with the same ``rule_id``
                (default False).
            overwrite_exceptions: Overwrite existing exception lists with
                the same ``list_id`` (default False).
            overwrite_action_connectors: Overwrite existing action
                connectors with the same ``id`` (default False).
            as_new_list: Generate a new list ID for each imported exception
                list (default False).
            filename: Filename advertised in the multipart upload.
            space_id: Optional space ID to import the rules into.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the import summary: ``success``,
            ``success_count``, ``rules_count``, ``errors`` and the
            exceptions/action-connectors counterparts.

        Raises:
            ValueError: If ``file`` is empty.
            BadRequestError: If the NDJSON payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> exported = client.detection_engine.export_rules(
            ...     objects=[{"rule_id": "my-rule"}]
            ... )
            >>> result = client.detection_engine.import_rules(
            ...     file=list(exported),
            ...     overwrite=True,
            ... )
            >>> print(result.body["success"])
            True
        """
        if file is None or (isinstance(file, (str, bytes, list)) and not file):
            raise ValueError("Parameter 'file' is required")

        params: dict[str, Any] = {}
        if overwrite is not None:
            params["overwrite"] = overwrite
        if overwrite_exceptions is not None:
            params["overwrite_exceptions"] = overwrite_exceptions
        if overwrite_action_connectors is not None:
            params["overwrite_action_connectors"] = overwrite_action_connectors
        if as_new_list is not None:
            params["as_new_list"] = as_new_list

        body, content_type = _build_multipart_body(
            _ndjson_bytes(file), filename=filename
        )

        path = self._build_space_path(
            "/api/detection_engine/rules/_import", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json", "content-type": content_type},
            body=body,  # type: ignore[arg-type]
        )

    def get_prepackaged_rules_status(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the status of Elastic prebuilt rules and Timelines.

        ``GET /api/detection_engine/rules/prepackaged/_status``. Retrieves
        how many Elastic prebuilt detection rules and Timeline templates
        are installed, not installed, or outdated in the target space.

        Args:
            space_id: Optional space ID to read the status for.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``rules_custom_installed``,
            ``rules_installed``, ``rules_not_installed``,
            ``rules_not_updated`` and the ``timelines_*`` counterparts.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = client.detection_engine.get_prepackaged_rules_status()
            >>> print(status.body["rules_installed"])
        """
        path = self._build_space_path(
            "/api/detection_engine/rules/prepackaged/_status",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def install_prepackaged_rules(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install or update Elastic prebuilt rules and Timelines.

        ``PUT /api/detection_engine/rules/prepackaged``. Installs and
        updates the Elastic prebuilt detection rules and Timeline templates
        (downloading the ``security_detection_engine`` Fleet package on
        first use). The call is idempotent: already-installed and
        up-to-date assets are skipped.

        Args:
            space_id: Optional space ID to install the prebuilt content in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``rules_installed``, ``rules_updated``,
            ``timelines_installed`` and ``timelines_updated`` counts.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.detection_engine.install_prepackaged_rules()
            >>> print(result.body["rules_installed"])
        """
        path = self._build_space_path(
            "/api/detection_engine/rules/prepackaged", space_id, validate_spaces
        )
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
        )

    def preview_rule(
        self,
        *,
        type: str,
        name: str,
        description: str,
        severity: str,
        risk_score: int,
        invocation_count: int,
        timeframe_end: str,
        enable_logged_requests: bool | None = None,
        rule_id: str | None = None,
        actions: list[dict[str, Any]] | None = None,
        alert_suppression: dict[str, Any] | None = None,
        anomaly_threshold: int | None = None,
        author: list[str] | None = None,
        building_block_type: str | None = None,
        concurrent_searches: int | None = None,
        data_view_id: str | None = None,
        enabled: bool | None = None,
        event_category_override: str | None = None,
        exceptions_list: list[dict[str, Any]] | None = None,
        false_positives: list[str] | None = None,
        filters: list[Any] | None = None,
        from_: str | None = None,
        history_window_start: str | None = None,
        index: list[str] | None = None,
        interval: str | None = None,
        investigation_fields: dict[str, Any] | None = None,
        items_per_search: int | None = None,
        language: str | None = None,
        license: str | None = None,
        machine_learning_job_id: str | list[str] | None = None,
        max_signals: int | None = None,
        meta: dict[str, Any] | None = None,
        namespace: str | None = None,
        new_terms_fields: list[str] | None = None,
        note: str | None = None,
        output_index: str | None = None,
        query: str | None = None,
        references: list[str] | None = None,
        related_integrations: list[dict[str, Any]] | None = None,
        required_fields: list[dict[str, Any]] | None = None,
        response_actions: list[dict[str, Any]] | None = None,
        risk_score_mapping: list[dict[str, Any]] | None = None,
        rule_name_override: str | None = None,
        saved_id: str | None = None,
        setup: str | None = None,
        severity_mapping: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        threat: list[dict[str, Any]] | None = None,
        threat_filters: list[Any] | None = None,
        threat_index: list[str] | None = None,
        threat_indicator_path: str | None = None,
        threat_language: str | None = None,
        threat_mapping: list[dict[str, Any]] | None = None,
        threat_query: str | None = None,
        threshold: dict[str, Any] | None = None,
        throttle: str | None = None,
        tiebreaker_field: str | None = None,
        timeline_id: str | None = None,
        timeline_title: str | None = None,
        timestamp_field: str | None = None,
        timestamp_override: str | None = None,
        timestamp_override_fallback_disabled: bool | None = None,
        to: str | None = None,
        version: int | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Preview the alerts a rule would generate.

        ``POST /api/detection_engine/rules/preview``. Runs a rule
        definition over a specified time range without creating the rule,
        and reports the execution logs (and, via the returned
        ``previewId``, the preview alerts written to the preview index).

        Args:
            type: Rule type (see :meth:`create_rule`).
            name: A human-readable name for the rule.
            description: The rule's description.
            severity: Severity level of alerts produced by the rule.
            risk_score: A numerical representation of the alert's severity
                from 0 to 100.
            invocation_count: Number of rule executions to simulate (sent
                as ``invocationCount``).
            timeframe_end: End of the simulated execution timeframe, as an
                ISO date-time (sent as ``timeframeEnd``).
            enable_logged_requests: Log the Elasticsearch requests issued
                during the preview (query parameter).
            fields: Additional body fields merged into the request verbatim.
            space_id: Optional space ID to run the preview in.
            validate_spaces: Override space validation setting for this
                operation.

        All remaining keyword arguments are the rule-definition fields
        documented on :meth:`create_rule` (``from_`` is sent as ``from``).

        Returns:
            ObjectApiResponse with the ``previewId``, per-invocation
            ``logs`` (errors, warnings, duration) and ``isAborted``.

        Raises:
            BadRequestError: If the rule definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> preview = client.detection_engine.preview_rule(
            ...     type="query",
            ...     name="Preview rule",
            ...     description="Preview",
            ...     severity="low",
            ...     risk_score=21,
            ...     query='user.name: "suspicious"',
            ...     index=["logs-*"],
            ...     invocation_count=1,
            ...     timeframe_end="2026-07-06T12:00:00.000Z",
            ...     from_="now-6h",
            ...     interval="1h",
            ... )
            >>> print(preview.body["previewId"])
        """
        body = _build_rule_body(
            type=type,
            name=name,
            description=description,
            severity=severity,
            risk_score=risk_score,
            rule_id=rule_id,
            actions=actions,
            alert_suppression=alert_suppression,
            anomaly_threshold=anomaly_threshold,
            author=author,
            building_block_type=building_block_type,
            concurrent_searches=concurrent_searches,
            data_view_id=data_view_id,
            enabled=enabled,
            event_category_override=event_category_override,
            exceptions_list=exceptions_list,
            false_positives=false_positives,
            filters=filters,
            from_=from_,
            history_window_start=history_window_start,
            index=index,
            interval=interval,
            investigation_fields=investigation_fields,
            items_per_search=items_per_search,
            language=language,
            license=license,
            machine_learning_job_id=machine_learning_job_id,
            max_signals=max_signals,
            meta=meta,
            namespace=namespace,
            new_terms_fields=new_terms_fields,
            note=note,
            output_index=output_index,
            query=query,
            references=references,
            related_integrations=related_integrations,
            required_fields=required_fields,
            response_actions=response_actions,
            risk_score_mapping=risk_score_mapping,
            rule_name_override=rule_name_override,
            saved_id=saved_id,
            setup=setup,
            severity_mapping=severity_mapping,
            tags=tags,
            threat=threat,
            threat_filters=threat_filters,
            threat_index=threat_index,
            threat_indicator_path=threat_indicator_path,
            threat_language=threat_language,
            threat_mapping=threat_mapping,
            threat_query=threat_query,
            threshold=threshold,
            throttle=throttle,
            tiebreaker_field=tiebreaker_field,
            timeline_id=timeline_id,
            timeline_title=timeline_title,
            timestamp_field=timestamp_field,
            timestamp_override=timestamp_override,
            timestamp_override_fallback_disabled=timestamp_override_fallback_disabled,
            to=to,
            version=version,
            fields=fields,
        )
        body["invocationCount"] = invocation_count
        body["timeframeEnd"] = timeframe_end

        params: dict[str, Any] = {}
        if enable_logged_requests is not None:
            params["enable_logged_requests"] = enable_logged_requests

        path = self._build_space_path(
            "/api/detection_engine/rules/preview", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_tags(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List all unique detection-rule tags.

        ``GET /api/detection_engine/tags``. Aggregates and returns all
        unique tags used by detection rules in the target space.

        Args:
            space_id: Optional space ID to list tags from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the array of unique tag strings.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> tags = client.detection_engine.get_tags()
            >>> print(list(tags))
        """
        path = self._build_space_path(
            "/api/detection_engine/tags", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Detection alerts (signals)
    # ------------------------------------------------------------------

    def search_alerts(
        self,
        *,
        query: dict[str, Any] | None = None,
        aggs: dict[str, Any] | None = None,
        size: int | None = None,
        sort: dict[str, Any] | list[Any] | str | None = None,
        fields: list[str] | None = None,
        source: bool | str | list[str] | None = None,
        runtime_mappings: dict[str, Any] | None = None,
        track_total_hits: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Find and/or aggregate detection alerts.

        ``POST /api/detection_engine/signals/search``. Searches the
        detection alerts (signals) index of the target space with an
        Elasticsearch query DSL body.

        Args:
            query: Elasticsearch query DSL to select alerts, e.g.
                ``{"match_all": {}}``.
            aggs: Elasticsearch aggregations to compute over the alerts.
            size: Maximum number of alerts to return.
            sort: Elasticsearch sort specification (field name, dict, or a
                list of either).
            fields: Fields to return via the search ``fields`` option.
            source: The ``_source`` option: True/False, a field pattern, or
                a list of field patterns.
            runtime_mappings: Runtime field mappings for the search.
            track_total_hits: Whether the exact total hit count is tracked.
            space_id: Optional space ID to search alerts in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the Elasticsearch search response
            (``hits``, ``took``, ``aggregations``, ...).

        Raises:
            BadRequestError: If the search body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> results = client.detection_engine.search_alerts(
            ...     query={
            ...         "bool": {
            ...             "filter": [
            ...                 {"match": {"kibana.alert.workflow_status": "open"}}
            ...             ]
            ...         }
            ...     },
            ...     size=10,
            ... )
            >>> print(results.body["hits"]["total"]["value"])
        """
        body: dict[str, Any] = {}
        if query is not None:
            body["query"] = query
        if aggs is not None:
            body["aggs"] = aggs
        if size is not None:
            body["size"] = size
        if sort is not None:
            body["sort"] = sort
        if fields is not None:
            body["fields"] = fields
        if source is not None:
            body["_source"] = source
        if runtime_mappings is not None:
            body["runtime_mappings"] = runtime_mappings
        if track_total_hits is not None:
            body["track_total_hits"] = track_total_hits

        path = self._build_space_path(
            "/api/detection_engine/signals/search", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def set_alert_status(
        self,
        *,
        status: str,
        signal_ids: list[str] | None = None,
        query: dict[str, Any] | None = None,
        conflicts: str | None = None,
        reason: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Set the workflow status of detection alerts.

        ``POST /api/detection_engine/signals/status``. Sets the workflow
        status (``open``, ``acknowledged`` or ``closed``) of detection
        alerts selected either by alert IDs or by an Elasticsearch query;
        exactly one of ``signal_ids`` and ``query`` must be provided.

        Args:
            status: The new workflow status: ``open``, ``acknowledged`` or
                ``closed`` (``in-progress`` is a deprecated alias of
                ``acknowledged``).
            signal_ids: List of alert ids (the alert document ``_id`` /
                ``kibana.alert.uuid``).
            query: Elasticsearch query DSL selecting the alerts to update.
            conflicts: Behavior on version conflicts when updating by
                query: ``abort`` (default) or ``proceed``.
            reason: Reason for closing the alerts (only valid with
                ``status="closed"``).
            space_id: Optional space ID the alerts live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the Elasticsearch update-by-query
            summary (``updated``, ``total``, ``failures``, ...).

        Raises:
            ValueError: If neither or both of ``signal_ids`` and ``query``
                are given.
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.detection_engine.set_alert_status(
            ...     status="closed",
            ...     signal_ids=["6f37fdd4..."],
            ... )
            >>> print(result.body["updated"])
        """
        if (signal_ids is None) == (query is None):
            raise ValueError("Exactly one of 'signal_ids' or 'query' must be provided")

        body: dict[str, Any] = {"status": status}
        if signal_ids is not None:
            body["signal_ids"] = signal_ids
        if query is not None:
            body["query"] = query
        if conflicts is not None:
            body["conflicts"] = conflicts
        if reason is not None:
            body["reason"] = reason

        path = self._build_space_path(
            "/api/detection_engine/signals/status", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def set_alert_tags(
        self,
        *,
        ids: list[str],
        tags_to_add: list[str],
        tags_to_remove: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Add and remove detection alert tags.

        ``POST /api/detection_engine/signals/tags``. Adds and/or removes
        tags on the given detection alerts in a single request.

        Args:
            ids: List of alert ids to update.
            tags_to_add: Tags to add to the alerts. A tag that is in both
                lists results in a no-op.
            tags_to_remove: Tags to remove from the alerts.
            space_id: Optional space ID the alerts live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the Elasticsearch update-by-query
            summary (``updated``, ``total``, ``failures``, ...).

        Raises:
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.detection_engine.set_alert_tags(
            ...     ids=["6f37fdd4..."],
            ...     tags_to_add=["triage"],
            ...     tags_to_remove=[],
            ... )
        """
        body: dict[str, Any] = {
            "ids": ids,
            "tags": {
                "tags_to_add": tags_to_add,
                "tags_to_remove": tags_to_remove,
            },
        }

        path = self._build_space_path(
            "/api/detection_engine/signals/tags", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def set_alert_assignees(
        self,
        *,
        ids: list[str],
        add: list[str],
        remove: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Assign and unassign users from detection alerts.

        ``POST /api/detection_engine/signals/assignees``. Assigns and/or
        unassigns users (by user-profile ``uid``) on the given detection
        alerts. Users need to activate their user profile by logging into
        Kibana at least once.

        Args:
            ids: List of alert ids to update.
            add: User profile ``uid`` values to assign. A uid that is in
                both lists results in a no-op.
            remove: User profile ``uid`` values to unassign.
            space_id: Optional space ID the alerts live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the Elasticsearch update-by-query
            summary (``updated``, ``total``, ``failures``, ...).

        Raises:
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.detection_engine.set_alert_assignees(
            ...     ids=["6f37fdd4..."],
            ...     add=["u_myuserprofileuid"],
            ...     remove=[],
            ... )
        """
        body: dict[str, Any] = {
            "ids": ids,
            "assignees": {
                "add": add,
                "remove": remove,
            },
        }

        path = self._build_space_path(
            "/api/detection_engine/signals/assignees", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Legacy signals migrations (deprecated)
    # ------------------------------------------------------------------

    def create_alerts_migration(
        self,
        *,
        index: list[str],
        requests_per_second: int | None = None,
        size: int | None = None,
        slices: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Initiate a detection alert migration.

        .. deprecated:: 9.4
           The legacy signals migration APIs are deprecated; modern
           ``.alerts-security.alerts`` indices do not need migration.

        ``POST /api/detection_engine/signals/migration``. Initiates the
        migration of legacy detection alerts (``.siem-signals-*`` indices)
        to the current schema, one migration task per index.

        Args:
            index: Array of legacy signals index names to migrate.
            requests_per_second: Throttle for the migration task in
                sub-requests per second (Reindex ``requests_per_second``).
            size: Number of alerts to migrate per batch (Reindex
                ``source.size``).
            slices: Number of subtasks for the migration task (Reindex
                ``slices``).
            space_id: Optional space ID the indices belong to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with per-index ``indices`` results
            (``migration_id``, ``migration_index``).

        Raises:
            BadRequestError: If a migration prerequisite is unmet (e.g.
                ``Cannot migrate due to the signals template being out of
                date`` when no legacy signals template exists).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> migration = client.detection_engine.create_alerts_migration(
            ...     index=[".siem-signals-default-000001"],
            ... )
        """
        body: dict[str, Any] = {"index": index}
        if requests_per_second is not None:
            body["requests_per_second"] = requests_per_second
        if size is not None:
            body["size"] = size
        if slices is not None:
            body["slices"] = slices

        path = self._build_space_path(
            "/api/detection_engine/signals/migration", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_alerts_migration_status(
        self,
        *,
        from_: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Retrieve the status of detection alert migrations.

        .. deprecated:: 9.4
           The legacy signals migration APIs are deprecated; modern
           ``.alerts-security.alerts`` indices do not need migration.

        ``GET /api/detection_engine/signals/migration_status``. Retrieves
        the migration status of detection alerts in indices containing
        alerts from the given time range.

        Note: on Kibana 9.4.3 this endpoint responds 404 (``undefined:
        undefined``) when no legacy signals indices exist for the range.

        Args:
            from_: Maximum age of qualifying detection alerts, as date
                math (e.g. ``"now-30d"``); sent as the ``from`` query
                parameter.
            space_id: Optional space ID the indices belong to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with per-index migration statuses.

        Raises:
            NotFoundError: If no qualifying signals indices exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = client.detection_engine.get_alerts_migration_status(
            ...     from_="now-30d",
            ... )
        """
        params: dict[str, Any] = {"from": from_}

        path = self._build_space_path(
            "/api/detection_engine/signals/migration_status",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def finalize_alerts_migration(
        self,
        *,
        migration_ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Finalize detection alert migrations.

        .. deprecated:: 9.4
           The legacy signals migration APIs are deprecated; modern
           ``.alerts-security.alerts`` indices do not need migration.

        ``POST /api/detection_engine/signals/finalize_migration``.
        Finalizes completed migrations of legacy detection alerts: swaps
        the alias to the migrated index and marks the migration as
        complete.

        Args:
            migration_ids: Array of migration IDs to finalize (as returned
                by :meth:`create_alerts_migration`).
            space_id: Optional space ID the migrations belong to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the finalized ``migrations`` statuses.

        Raises:
            NotFoundError: If a migration ID does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.detection_engine.finalize_alerts_migration(
            ...     migration_ids=["924f7c50-505f-11eb-ae0a-3fa2e626a51d"],
            ... )
        """
        body: dict[str, Any] = {"migration_ids": migration_ids}

        path = self._build_space_path(
            "/api/detection_engine/signals/finalize_migration",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_alerts_migration(
        self,
        *,
        migration_ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Clean up detection alert migrations.

        .. deprecated:: 9.4
           The legacy signals migration APIs are deprecated; modern
           ``.alerts-security.alerts`` indices do not need migration.

        ``DELETE /api/detection_engine/signals/migration``. Migrations are
        initiated per index; when a migration is stale or its results are
        no longer needed, this soft-deletes the migration saved object.

        Args:
            migration_ids: Array of migration IDs to clean up (as returned
                by :meth:`create_alerts_migration`).
            space_id: Optional space ID the migrations belong to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the cleaned-up ``migrations`` statuses.

        Raises:
            NotFoundError: If a migration ID does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.detection_engine.delete_alerts_migration(
            ...     migration_ids=["924f7c50-505f-11eb-ae0a-3fa2e626a51d"],
            ... )
        """
        body: dict[str, Any] = {"migration_ids": migration_ids}

        path = self._build_space_path(
            "/api/detection_engine/signals/migration", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            body=body,
        )
